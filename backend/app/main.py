import os
import shutil
import pandas as pd
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, execute_ddl, bulk_insert_df
from app.schemas import (
    ReconciliationRunResponse, 
    ReconciliationSummary,
    PaginatedReconciliationResults, 
    ReconciliationRecordSchema,
    DatabaseStatusSchema,
    DatabaseTableMetrics,
    RevertRequestSchema
)
from app.parser import (
    parse_mobile_mumbaione,
    parse_mobile_metroconnect3,
    parse_mobile_ondc,
    parse_afc,
    parse_payment_gateway
)
from app.reconciler import run_reconciliation_process, get_reconciliation_summaries

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for high-performance metro booking transaction reconciliation."
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    """Run database DDL statements on startup to guarantee tables exist"""
    try:
        execute_ddl()
    except Exception as e:
        print(f"Error executing database DDL on startup: {e}")

@app.get("/")
def read_root():
    return {
        "project": settings.PROJECT_NAME,
        "status": "Running",
        "docs_url": "/docs"
    }

@app.post("/api/reconcile/upload")
async def upload_files(
    app_name: str = Form(..., description="App: 'mumbaione', 'metroconnect3', 'ondc'"),
    channel: str = Form(..., description="Channel: 'mobile', 'payment_gateway', 'afc'"),
    clear_existing: bool = Form(False, description="Clear existing data in the target staging table first"),
    files: List[UploadFile] = File(..., description="Excel/CSV files to upload"),
    db: Session = Depends(get_db)
):
    """
    Accepts multiple file uploads for a specific App and Channel,
    parses them, and bulk inserts them into PostgreSQL.
    """
    # 1. Input Validation
    app_name = app_name.strip().lower()
    channel = channel.strip().lower()
    
    valid_apps = {'mumbaione', 'metroconnect3', 'ondc'}
    valid_channels = {'mobile', 'payment_gateway', 'afc'}
    
    if app_name not in valid_apps:
        raise HTTPException(status_code=400, detail=f"Invalid app_name. Must be one of {valid_apps}")
    if channel not in valid_channels:
        raise HTTPException(status_code=400, detail=f"Invalid channel. Must be one of {valid_channels}")
        
    # ONDC doesn't have a payment gateway
    if app_name == 'ondc' and channel == 'payment_gateway':
        raise HTTPException(status_code=400, detail="ONDC App does not have a payment gateway.")

    # 2. Determine Staging Table
    table_name = None
    if channel == 'mobile':
        if app_name == 'mumbaione':
            table_name = 'stg_mobile_mumbaione'
        elif app_name == 'metroconnect3':
            table_name = 'stg_mobile_metroconnect3'
        elif app_name == 'ondc':
            table_name = 'stg_mobile_ondc'
    elif channel == 'payment_gateway':
        table_name = 'stg_pg_transactions'
    elif channel == 'afc':
        table_name = 'stg_afc_transactions'

    if not table_name:
        raise HTTPException(status_code=500, detail="Could not resolve target database staging table.")

    processed_files = []
    parsed_dfs = []
    
    # 3. Parse Files Sequentially (CPU-bound / Disk space friendly)
    for upload_file in files:
        temp_file_path = os.path.join(settings.UPLOAD_TEMP_DIR, upload_file.filename)
        print(f"Receiving file: {upload_file.filename} -> Saving to {temp_file_path}")
        
        # Save upload stream to a temporary local file
        try:
            with open(temp_file_path, "wb") as buffer:
                shutil.copyfileobj(upload_file.file, buffer)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save uploaded file locally: {e}")

        # Parse local file to DataFrame
        try:
            df = None
            if channel == 'mobile':
                if app_name == 'mumbaione':
                    df = parse_mobile_mumbaione(temp_file_path)
                elif app_name == 'metroconnect3':
                    df = parse_mobile_metroconnect3(temp_file_path)
                elif app_name == 'ondc':
                    df = parse_mobile_ondc(temp_file_path)
            elif channel == 'payment_gateway':
                pg_app_src = 'MumbaiOne' if app_name == 'mumbaione' else 'MetroConnect3'
                df = parse_payment_gateway(temp_file_path, pg_app_src)
            elif channel == 'afc':
                afc_app_name = 'MumbaiOne' if app_name == 'mumbaione' else ('ONDC' if app_name == 'ondc' else 'MetroConnect3')
                df = parse_afc(temp_file_path, afc_app_name)

            if df is not None and not df.empty:
                # Add file_source column to DataFrame!
                df['file_source'] = upload_file.filename
                parsed_dfs.append(df)
                
            processed_files.append({
                "filename": upload_file.filename,
                "status": "Success",
                "rows_loaded": 0  # Will update after deduplication
            })
            
        except ValueError as ve:
            print(f"Validation error processing file {upload_file.filename}: {ve}")
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            raise HTTPException(status_code=400, detail=f"Wrong file structure: {str(ve)}")
        except Exception as e:
            print(f"System error processing file {upload_file.filename}: {e}")
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            raise HTTPException(status_code=500, detail=f"Parsing error: {str(e)}")
        finally:
            # Clean up temp file immediately to save disk space
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    # 4. Concatenate and Batch Insert (Single Database Transaction!)
    if not parsed_dfs:
        raise HTTPException(status_code=400, detail="All uploaded files parsed into empty DataFrames. No records to ingest.")

    try:
        combined_df = pd.concat(parsed_dfs, ignore_index=True)
        
        # Row-level duplicate prevention: filter out duplicate records already present in the database staging table
        if not clear_existing:
            original_len = len(combined_df)

            def normalize_key(val):
                """Normalize a key value to a clean string for set comparison.
                Converts NaN, None, 'nan', '', 'None' → None so they are excluded."""
                if val is None:
                    return None
                s = str(val).strip()
                if s.lower() in ('nan', 'none', ''):
                    return None
                return s

            if table_name == 'stg_mobile_mumbaione':
                if 'pg_reference_no' in combined_df.columns:
                    raw_keys = combined_df['pg_reference_no'].dropna().unique()
                    clean_keys = [str(k).strip() for k in raw_keys if normalize_key(k) is not None]
                    if clean_keys:
                        existing_keys = {
                            str(row[0]).strip() 
                            for row in db.execute(
                                text("SELECT pg_reference_no FROM stg_mobile_mumbaione WHERE pg_reference_no IN :keys"),
                                {"keys": tuple(clean_keys)}
                            )
                        }
                    else:
                        existing_keys = set()
                    combined_df = combined_df[combined_df['pg_reference_no'].apply(normalize_key).isin(existing_keys) == False]
                    combined_df = combined_df[combined_df['pg_reference_no'].apply(normalize_key).notna()]

            elif table_name == 'stg_mobile_metroconnect3':
                if 'ticket_no' in combined_df.columns:
                    raw_keys = combined_df['ticket_no'].dropna().unique()
                    clean_keys = [str(k).strip() for k in raw_keys if normalize_key(k) is not None]
                    if clean_keys:
                        existing_keys = {
                            str(row[0]).strip()
                            for row in db.execute(
                                text("SELECT ticket_no FROM stg_mobile_metroconnect3 WHERE ticket_no IN :keys"),
                                {"keys": tuple(clean_keys)}
                            )
                        }
                    else:
                        existing_keys = set()
                    combined_df = combined_df[combined_df['ticket_no'].apply(normalize_key).isin(existing_keys) == False]
                    combined_df = combined_df[combined_df['ticket_no'].apply(normalize_key).notna()]

            elif table_name == 'stg_mobile_ondc':
                if 'order_id' in combined_df.columns:
                    raw_keys = combined_df['order_id'].dropna().unique()
                    clean_keys = [str(k).strip() for k in raw_keys if normalize_key(k) is not None]
                    if clean_keys:
                        existing_keys = {
                            str(row[0]).strip()
                            for row in db.execute(
                                text("SELECT order_id FROM stg_mobile_ondc WHERE order_id IN :keys"),
                                {"keys": tuple(clean_keys)}
                            )
                        }
                    else:
                        existing_keys = set()
                    combined_df = combined_df[combined_df['order_id'].apply(normalize_key).isin(existing_keys) == False]
                    combined_df = combined_df[combined_df['order_id'].apply(normalize_key).notna()]

            elif table_name == 'stg_pg_transactions':
                if 'pgi_ref_no' in combined_df.columns and 'transaction_type' in combined_df.columns:
                    raw_keys = combined_df['pgi_ref_no'].dropna().unique()
                    clean_keys = [str(k).strip() for k in raw_keys if normalize_key(k) is not None]
                    if clean_keys:
                        existing_keys = {
                            (str(row[0]).strip(), str(row[1]).strip())
                            for row in db.execute(
                                text("SELECT pgi_ref_no, transaction_type FROM stg_pg_transactions WHERE pgi_ref_no IN :pgi_keys"),
                                {"pgi_keys": tuple(clean_keys)}
                            )
                        }
                    else:
                        existing_keys = set()
                    
                    def pg_key(row_pair):
                        pgi, ttype = row_pair
                        k1 = normalize_key(pgi)
                        k2 = normalize_key(ttype)
                        if k1 is None or k2 is None:
                            return None
                        return (k1, k2)
                    keys_series = list(zip(combined_df['pgi_ref_no'], combined_df['transaction_type']))
                    mask = pd.Series([pg_key(pair) in existing_keys for pair in keys_series], index=combined_df.index)
                    combined_df = combined_df[~mask]
                    combined_df = combined_df[combined_df['pgi_ref_no'].apply(normalize_key).notna()]

            elif table_name == 'stg_afc_transactions':
                if 'slave_qr_no' in combined_df.columns:
                    raw_keys = combined_df['slave_qr_no'].dropna().unique()
                    clean_keys = [str(k).strip() for k in raw_keys if normalize_key(k) is not None]
                    if clean_keys:
                        existing_keys = {
                            str(row[0]).strip()
                            for row in db.execute(
                                text("SELECT slave_qr_no FROM stg_afc_transactions WHERE slave_qr_no IN :keys"),
                                {"keys": tuple(clean_keys)}
                            )
                        }
                    else:
                        existing_keys = set()
                    combined_df = combined_df[combined_df['slave_qr_no'].apply(normalize_key).isin(existing_keys) == False]
                    combined_df = combined_df[combined_df['slave_qr_no'].apply(normalize_key).notna()]

            duplicates_removed = original_len - len(combined_df)
            if duplicates_removed > 0:
                print(f"Deduplication: Filtered out {duplicates_removed} duplicate/junk records from the batch.")
            if combined_df.empty:
                raise ValueError("All records in the uploaded file(s) are already present in staging (or contained no valid key values). Ingestion skipped to prevent duplicates.")

        # If clear_existing is selected, we perform update in ingestion_logs inside transaction
        if clear_existing:
            try:
                db.execute(text("UPDATE ingestion_logs SET status = 'REVERTED', reverted_at = CURRENT_TIMESTAMP WHERE table_name = :tname AND status = 'STAGED'"), {"tname": table_name})
                db.commit()
            except Exception as le:
                db.rollback()
                print(f"Warning: Failed to update previous logs on truncate: {le}")

        # Bulk insert into database
        total_rows_loaded = bulk_insert_df(table_name, combined_df, truncate=clear_existing)
        
        # Calculate rows loaded per file from the deduplicated combined_df
        file_counts = {}
        if not combined_df.empty and 'file_source' in combined_df.columns:
            file_counts = combined_df['file_source'].value_counts().to_dict()

        for item in processed_files:
            item["rows_loaded"] = file_counts.get(item["filename"], 0)

        # Log this upload in ingestion_logs inside transaction
        try:
            pretty_app = 'ONDC' if app_name == 'ondc' else ('MumbaiOne' if app_name == 'mumbaione' else 'MetroConnect3')
            pretty_channel = channel.replace('_', ' ').title()
            
            log_query = text("""
                INSERT INTO ingestion_logs (filename, app_name, channel, table_name, row_count, status)
                VALUES (:filename, :app_name, :channel, :table_name, :row_count, 'STAGED')
            """)
            for item in processed_files:
                db.execute(log_query, {
                    "filename": item["filename"],
                    "app_name": pretty_app,
                    "channel": pretty_channel,
                    "table_name": table_name,
                    "row_count": item["rows_loaded"]
                })
            db.commit()
        except Exception as le:
            db.rollback()
            print(f"Warning: Failed to write to ingestion_logs: {le}")

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database ingestion error: {str(e)}")

    return {
        "success": True,
        "app_name": app_name,
        "channel": channel,
        "staging_table": table_name,
        "total_rows_loaded": total_rows_loaded,
        "processed_files": processed_files
    }

@app.get("/api/reconcile/logs")
def get_ingestion_logs(db: Session = Depends(get_db)):
    """
    Fetches the upload audit logs from ingestion_logs.
    """
    try:
        query = text("""
            SELECT id, filename, app_name, channel, table_name, row_count, status, uploaded_at, reverted_at 
            FROM ingestion_logs 
            ORDER BY id DESC
        """)
        result = db.execute(query)
        logs = []
        for row in result:
            logs.append({
                "id": row[0],
                "filename": row[1],
                "app_name": row[2],
                "channel": row[3],
                "table_name": row[4],
                "row_count": row[5],
                "status": row[6],
                "uploaded_at": row[7].isoformat() if row[7] else None,
                "reverted_at": row[8].isoformat() if row[8] else None
            })
        return logs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch ingestion logs: {e}")

@app.post("/api/reconcile/revert")
def revert_upload(payload: RevertRequestSchema, db: Session = Depends(get_db)):
    """
    Reverts a specific file ingestion transaction.
    Deletes the staged rows, updates the log status to 'REVERTED',
    and truncates the reconciliation results table.
    """
    # 1. Fetch the log record
    log_query = text("SELECT id, filename, table_name, status, row_count FROM ingestion_logs WHERE id = :log_id")
    log_row = db.execute(log_query, {"log_id": payload.log_id}).first()
    
    if not log_row:
        raise HTTPException(status_code=404, detail="Ingestion log record not found.")
        
    log_id, filename, table_name, status, row_count = log_row
    
    if status == 'REVERTED':
        raise HTTPException(status_code=400, detail="This file upload has already been reverted.")
        
    try:
        # 2. Delete the transactions from the staging table
        delete_query = text(f"DELETE FROM {table_name} WHERE file_source = :filename")
        delete_res = db.execute(delete_query, {"filename": filename})
        deleted_count = delete_res.rowcount
        
        # 3. Update the log status
        update_query = text("""
            UPDATE ingestion_logs 
            SET status = 'REVERTED', reverted_at = CURRENT_TIMESTAMP 
            WHERE id = :log_id
        """)
        db.execute(update_query, {"log_id": log_id})
        
        # 4. Truncate reconciliation_results to prevent stale ledger entries
        db.execute(text("TRUNCATE TABLE reconciliation_results CASCADE"))
        
        # Commit the transaction
        db.commit()
        
        return {
            "success": True,
            "message": f"Successfully reverted file '{filename}'. Deleted {deleted_count} records from '{table_name}'. Ledger cleared.",
            "deleted_count": deleted_count,
            "table_name": table_name
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Rollback transaction failed: {e}")

@app.post("/api/reconcile/run", response_model=ReconciliationRunResponse)
def run_reconciliation():
    """
    Triggers the SQL-based classification engine.
    Wipes previous results and builds fresh classified mappings.
    """
    try:
        summaries = run_reconciliation_process()
        return ReconciliationRunResponse(
            success=True,
            message="Reconciliation run completed successfully.",
            summaries=summaries
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute reconciliation queries: {e}")

@app.get("/api/reconcile/summary", response_model=List[ReconciliationSummary])
def get_summaries():
    """
    Fetches the current reconciliation summaries from the database
    WITHOUT running the classification engine again.
    """
    try:
        return get_reconciliation_summaries()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch summaries: {e}")

@app.get("/api/reconcile/results", response_model=PaginatedReconciliationResults)
def get_results(
    app: Optional[str] = Query(None, description="Filter by app: 'MumbaiOne', 'MetroConnect3', 'ONDC'"),
    status: Optional[str] = Query(None, description="Filter by status: 'Settled', 'Liable for Refund', 'Failed Transaction', 'Refunded'"),
    search: Optional[str] = Query(None, description="Search by Order ID, Ticket No, or PG Ref No"),
    sources: Optional[str] = Query(None, description="Comma-separated required sources presence, e.g., 'App,AFC'"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=500, description="Records per page"),
    db: Session = Depends(get_db)
):
    """
    Fetches the paginated reconciliation list with filters.
    """
    # 1. Base Query
    base_query_str = "FROM reconciliation_results WHERE 1=1"
    params = {}
    
    if app:
        base_query_str += " AND app_source = :app"
        params["app"] = app
    if status:
        base_query_str += " AND recon_status = :status"
        params["status"] = status
    if search:
        search_clean = f"%{search.strip()}%"
        base_query_str += " AND (order_id ILIKE :search OR ticket_no ILIKE :search OR pg_ref_no ILIKE :search)"
        params["search"] = search_clean
    if sources:
        required = [s.strip() for s in sources.split(',') if s.strip()]
        std_order = ['App', 'PG', 'AFC']
        sorted_req = [s for s in std_order if s in required]
        exact_sources = ",".join(sorted_req)
        base_query_str += " AND data_sources = :exact_sources"
        params["exact_sources"] = exact_sources

    # 2. Count Total Matches
    count_query = text(f"SELECT COUNT(*) {base_query_str}")
    total = db.execute(count_query, params).scalar()

    # 3. Paginate Results
    offset = (page - 1) * limit
    select_query_str = f"SELECT id, app_source, order_id, ticket_no, pg_ref_no, amount, transaction_time, recon_status, notes, data_sources, reconciled_at {base_query_str} ORDER BY id ASC LIMIT :limit OFFSET :offset"
    
    params["limit"] = limit
    params["offset"] = offset
    
    result_set = db.execute(text(select_query_str), params)
    records = []
    
    for row in result_set:
        records.append(
            ReconciliationRecordSchema(
                id=row[0],
                app_source=row[1],
                order_id=row[2],
                ticket_no=row[3],
                pg_ref_no=row[4],
                amount=float(row[5]) if row[5] is not None else None,
                transaction_time=row[6],
                recon_status=row[7],
                notes=row[8],
                data_sources=row[9],
                reconciled_at=row[10]
            )
        )

    return PaginatedReconciliationResults(
        total=total,
        page=page,
        limit=limit,
        results=records
    )

@app.get("/api/db/status", response_model=DatabaseStatusSchema)
def db_status(db: Session = Depends(get_db)):
    """
    Checks the status of the database connection and returns row counts for all tables.
    """
    tables = [
        'stg_mobile_mumbaione',
        'stg_mobile_metroconnect3',
        'stg_mobile_ondc',
        'stg_pg_transactions',
        'stg_afc_transactions',
        'reconciliation_results',
        'ingestion_logs'
    ]
    
    metrics = []
    try:
        # Check active connection
        db.execute(text("SELECT 1"))
        
        # Query counts
        for table in tables:
            query = text(f"SELECT COUNT(*) FROM {table}")
            try:
                count = db.execute(query).scalar()
                metrics.append(DatabaseTableMetrics(table_name=table, row_count=count))
            except Exception:
                # Table might not exist yet
                metrics.append(DatabaseTableMetrics(table_name=table, row_count=-1))
                
        return DatabaseStatusSchema(
            connected=True,
            message="Successfully connected to database.",
            metrics=metrics
        )
    except Exception as e:
        return DatabaseStatusSchema(
            connected=False,
            message=f"Database connection failed: {e}",
            metrics=[]
        )
