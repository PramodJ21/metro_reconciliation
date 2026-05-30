import io
import json
import pandas as pd
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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
    RevertRequestSchema,
    ManualRefundRequestSchema,
    ManualRefundLogSchema
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
    Streams real-time progress back to the client using Server-Sent Events (SSE).

    Performance optimisations applied:
    - Files are read into BytesIO in memory — zero disk I/O during parsing.
    - Deduplication uses vectorised pandas string ops instead of row-level .apply().
    - A single bulk execute_values insert covers all files in one DB round-trip.
    """

    def _sse(event_type: str, payload: dict) -> str:
        payload["event"] = event_type
        return f"data: {json.dumps(payload)}\n\n"

    # Read all file bytes into memory before the generator runs.
    # UploadFile.file is a one-shot stream; buffering here means the
    # generator can seek/re-read freely without touching disk.
    file_payloads = []  # list of (filename, BytesIO)
    for uf in files:
        file_payloads.append((uf.filename, io.BytesIO(uf.file.read())))

    def event_generator():
        # --- 1. Input Validation ---
        _app = app_name.strip().lower()
        _ch  = channel.strip().lower()

        valid_apps     = {'mumbaione', 'metroconnect3', 'ondc'}
        valid_channels = {'mobile', 'payment_gateway', 'afc'}

        if _app not in valid_apps:
            yield _sse("error", {"message": f"Invalid app_name. Must be one of {valid_apps}"})
            return
        if _ch not in valid_channels:
            yield _sse("error", {"message": f"Invalid channel. Must be one of {valid_channels}"})
            return
        if _app == 'ondc' and _ch == 'payment_gateway':
            yield _sse("error", {"message": "ONDC App does not have a payment gateway."})
            return

        # --- 2. Determine Staging Table ---
        table_name = None
        if _ch == 'mobile':
            if _app == 'mumbaione':
                table_name = 'stg_mobile_mumbaione'
            elif _app == 'metroconnect3':
                table_name = 'stg_mobile_metroconnect3'
            elif _app == 'ondc':
                table_name = 'stg_mobile_ondc'
        elif _ch == 'payment_gateway':
            table_name = 'stg_pg_transactions'
        elif _ch == 'afc':
            table_name = 'stg_afc_transactions'

        if not table_name:
            yield _sse("error", {"message": "Could not resolve target database staging table."})
            return

        total_files     = len(file_payloads)
        parsed_dfs      = []
        processed_files = []

        yield _sse("progress", {
            "progress": 5,
            "message": f"Files buffered in memory. Parsing {total_files} file(s)..."
        })

        # --- 3. Parse files in parallel using ThreadPoolExecutor ---
        import concurrent.futures

        def _parse_single_file(filename, buf):
            buf.seek(0)
            df = None
            if _ch == 'mobile':
                if _app == 'mumbaione':
                    df = parse_mobile_mumbaione(buf)
                elif _app == 'metroconnect3':
                    df = parse_mobile_metroconnect3(buf)
                elif _app == 'ondc':
                    df = parse_mobile_ondc(buf)
            elif _ch == 'payment_gateway':
                pg_src = 'MumbaiOne' if _app == 'mumbaione' else 'MetroConnect3'
                df = parse_payment_gateway(buf, pg_src)
            elif _ch == 'afc':
                afc_src = 'MumbaiOne' if _app == 'mumbaione' else ('ONDC' if _app == 'ondc' else 'MetroConnect3')
                df = parse_afc(buf, afc_src)

            if df is not None and not df.empty:
                df['file_source'] = filename
            return filename, df

        # Use ThreadPoolExecutor to parse concurrently
        max_workers = min(8, len(file_payloads))
        yield _sse("progress", {
            "progress": 5,
            "message": f"Starting parallel parsing of {total_files} file(s) using {max_workers} threads..."
        })

        futures = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            for filename, buf in file_payloads:
                futures.append(executor.submit(_parse_single_file, filename, buf))

            completed_count = 0
            for future in concurrent.futures.as_completed(futures):
                completed_count += 1
                base_progress = 5 + int((completed_count / total_files) * 55)

                try:
                    filename, df = future.result()
                    if df is not None and not df.empty:
                        parsed_dfs.append(df)
                        row_hint = f"{len(df):,} rows parsed"
                    else:
                        row_hint = "0 rows (empty)"

                    processed_files.append({"filename": filename, "status": "Success", "rows_loaded": 0})
                    yield _sse("file_parsed", {
                        "progress": base_progress,
                        "message": f"✓ Parsed {filename} — {row_hint} ({completed_count}/{total_files})",
                        "filename": filename,
                        "rows_parsed": len(df) if df is not None else 0
                    })

                except ValueError as ve:
                    yield _sse("error", {"message": f"Wrong file structure: {str(ve)}", "filename": filename})
                    return
                except Exception as e:
                    yield _sse("error", {"message": f"Parsing error in file: {str(e)}"})
                    return

        # --- 4. Validate at least one non-empty result ---
        if not parsed_dfs:
            yield _sse("error", {"message": "All uploaded files parsed into empty DataFrames. No records to ingest."})
            return

        yield _sse("progress", {
            "progress": 65,
            "message": f"Merging {total_files} file(s) into a single batch..."
        })

        try:
            combined_df = pd.concat(parsed_dfs, ignore_index=True)

            # --- 6. Vectorised Deduplication ---
            if not clear_existing:
                original_len = len(combined_df)

                def _vec_clean(series: pd.Series) -> pd.Series:
                    """
                    Vectorised equivalent of normalize_key:
                    strip → lowercase check → replace sentinel strings with NaN.
                    Returns a str-typed Series with NaN where key is invalid.
                    """
                    s = series.astype(str).str.strip()
                    return s.where(~s.str.lower().isin({'nan', 'none', ''}), other=pd.NA)

                yield _sse("progress", {
                    "progress": 70,
                    "message": f"Checking {original_len:,} records for duplicates against staging table..."
                })

                if table_name == 'stg_mobile_mumbaione' and 'pg_reference_no' in combined_df.columns:
                    clean_col  = _vec_clean(combined_df['pg_reference_no'])
                    clean_keys = clean_col.dropna().unique().tolist()
                    existing   = {
                        str(r[0]).strip()
                        for r in db.execute(
                            text("SELECT pg_reference_no FROM stg_mobile_mumbaione WHERE pg_reference_no IN :k"),
                            {"k": tuple(clean_keys)}
                        )
                    } if clean_keys else set()
                    if existing:
                        sample = sorted(existing)[:20]
                        print(f"[DUPLICATE] stg_mobile_mumbaione: {len(existing)} duplicate pg_reference_no value(s) found in DB.")
                        print(f"[DUPLICATE] Sample keys (up to 20): {sample}")
                    combined_df = combined_df[clean_col.notna() & ~clean_col.isin(existing)]

                elif table_name == 'stg_mobile_metroconnect3' and 'ticket_no' in combined_df.columns:
                    clean_col  = _vec_clean(combined_df['ticket_no'])
                    clean_keys = clean_col.dropna().unique().tolist()
                    existing   = {
                        str(r[0]).strip()
                        for r in db.execute(
                            text("SELECT ticket_no FROM stg_mobile_metroconnect3 WHERE ticket_no IN :k"),
                            {"k": tuple(clean_keys)}
                        )
                    } if clean_keys else set()
                    if existing:
                        sample = sorted(existing)[:20]
                        print(f"[DUPLICATE] stg_mobile_metroconnect3: {len(existing)} duplicate ticket_no value(s) found in DB.")
                        print(f"[DUPLICATE] Sample keys (up to 20): {sample}")
                    combined_df = combined_df[clean_col.notna() & ~clean_col.isin(existing)]

                elif table_name == 'stg_mobile_ondc' and 'order_id' in combined_df.columns:
                    clean_col  = _vec_clean(combined_df['order_id'])
                    clean_keys = clean_col.dropna().unique().tolist()
                    existing   = {
                        str(r[0]).strip()
                        for r in db.execute(
                            text("SELECT order_id FROM stg_mobile_ondc WHERE order_id IN :k"),
                            {"k": tuple(clean_keys)}
                        )
                    } if clean_keys else set()
                    if existing:
                        sample = sorted(existing)[:20]
                        print(f"[DUPLICATE] stg_mobile_ondc: {len(existing)} duplicate order_id value(s) found in DB.")
                        print(f"[DUPLICATE] Sample keys (up to 20): {sample}")
                    combined_df = combined_df[clean_col.notna() & ~clean_col.isin(existing)]

                elif table_name == 'stg_pg_transactions' and 'pgi_ref_no' in combined_df.columns:
                    clean_pgi  = _vec_clean(combined_df['pgi_ref_no'])
                    clean_type = _vec_clean(combined_df['transaction_type'])
                    clean_keys = clean_pgi.dropna().unique().tolist()
                    existing   = {
                        (str(r[0]).strip(), str(r[1]).strip())
                        for r in db.execute(
                            text("SELECT pgi_ref_no, transaction_type FROM stg_pg_transactions WHERE pgi_ref_no IN :k"),
                            {"k": tuple(clean_keys)}
                        )
                    } if clean_keys else set()
                    if existing:
                        sample = sorted(existing)[:20]
                        print(f"[DUPLICATE] stg_pg_transactions: {len(existing)} duplicate (pgi_ref_no, transaction_type) pair(s) found in DB.")
                        print(f"[DUPLICATE] Sample pairs (up to 20): {sample}")
                    combo = list(zip(clean_pgi.fillna(''), clean_type.fillna('')))
                    mask  = pd.Series(
                        [pair in existing for pair in combo],
                        index=combined_df.index
                    )
                    combined_df = combined_df[clean_pgi.notna() & clean_type.notna() & ~mask]

                elif table_name == 'stg_afc_transactions' and 'slave_qr_no' in combined_df.columns:
                    clean_col  = _vec_clean(combined_df['slave_qr_no'])
                    clean_keys = clean_col.dropna().unique().tolist()
                    existing   = {
                        str(r[0]).strip()
                        for r in db.execute(
                            text("SELECT slave_qr_no FROM stg_afc_transactions WHERE slave_qr_no IN :k"),
                            {"k": tuple(clean_keys)}
                        )
                    } if clean_keys else set()
                    if existing:
                        sample = sorted(existing)[:20]
                        print(f"[DUPLICATE] stg_afc_transactions: {len(existing)} duplicate slave_qr_no value(s) found in DB.")
                        print(f"[DUPLICATE] Sample keys (up to 20): {sample}")
                    combined_df = combined_df[clean_col.notna() & ~clean_col.isin(existing)]

                dups    = original_len - len(combined_df)
                if dups > 0:
                    print(f"[DEDUP SUMMARY] {dups:,} row(s) removed total ({original_len:,} in \u2192 {len(combined_df):,} net new).")
                else:
                    print(f"[DEDUP SUMMARY] No duplicates found. All {original_len:,} row(s) are new.")
                dup_msg = f" ({dups:,} duplicates removed)" if dups > 0 else ""
                if combined_df.empty:
                    yield _sse("error", {"message": "All records already present in staging. Ingestion skipped to prevent duplicates."})
                    return

                yield _sse("progress", {
                    "progress": 78,
                    "message": f"Deduplication complete{dup_msg}. {len(combined_df):,} net new records ready."
                })


            # --- 7. Revert previous log entries if clearing ---
            if clear_existing:
                try:
                    db.execute(
                        text("UPDATE ingestion_logs SET status = 'REVERTED', reverted_at = CURRENT_TIMESTAMP WHERE table_name = :tname AND status = 'STAGED'"),
                        {"tname": table_name}
                    )
                    db.commit()
                except Exception as le:
                    db.rollback()
                    print(f"Warning: Failed to update previous logs on truncate: {le}")

            yield _sse("progress", {
                "progress": 82,
                "message": f"Bulk inserting {len(combined_df):,} rows into {table_name}..."
            })

            # --- 8. Bulk Insert ---
            total_rows_loaded = bulk_insert_df(table_name, combined_df, truncate=clear_existing)

            yield _sse("progress", {
                "progress": 92,
                "message": f"✓ Inserted {total_rows_loaded:,} rows. Writing audit log..."
            })

            # --- 9. Per-file row counts ---
            file_counts = {}
            if not combined_df.empty and 'file_source' in combined_df.columns:
                file_counts = combined_df['file_source'].value_counts().to_dict()
            for item in processed_files:
                item["rows_loaded"] = file_counts.get(item["filename"], 0)

            # --- 10. Audit Log ---
            try:
                pretty_app     = 'ONDC' if _app == 'ondc' else ('MumbaiOne' if _app == 'mumbaione' else 'MetroConnect3')
                pretty_channel = _ch.replace('_', ' ').title()
                log_query = text("""
                    INSERT INTO ingestion_logs (filename, app_name, channel, table_name, row_count, status)
                    VALUES (:filename, :app_name, :channel, :table_name, :row_count, 'STAGED')
                """)
                for item in processed_files:
                    db.execute(log_query, {
                        "filename":   item["filename"],
                        "app_name":   pretty_app,
                        "channel":    pretty_channel,
                        "table_name": table_name,
                        "row_count":  item["rows_loaded"]
                    })
                db.commit()
            except Exception as le:
                db.rollback()
                print(f"Warning: Failed to write to ingestion_logs: {le}")

            # --- 11. Completion event ---
            yield _sse("completed", {
                "progress": 100,
                "message": f"✓ Success! Staged {total_files} file(s). Bulk inserted {total_rows_loaded:,} rows.",
                "success": True,
                "app_name": _app,
                "channel": _ch,
                "staging_table": table_name,
                "total_rows_loaded": total_rows_loaded,
                "processed_files": processed_files
            })

        except ValueError as ve:
            yield _sse("error", {"message": str(ve)})
        except Exception as e:
            yield _sse("error", {"message": f"Database ingestion error: {str(e)}"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )

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


@app.post("/api/reconcile/manual-refund")
def create_manual_refund(payload: ManualRefundRequestSchema, db: Session = Depends(get_db)):
    """
    Registers a manual refund in the manual_refunds table
    and updates the active status of the matched record in reconciliation_results.
    """
    try:
        # 1. Insert into manual_refunds table
        insert_query = text("""
            INSERT INTO manual_refunds (order_id, ticket_no, amount, original_status, updated_status, note)
            VALUES (:order_id, :ticket_no, :amount, 'Liable for Refund', 'Manually Refunded', :note)
        """)
        db.execute(insert_query, {
            "order_id": payload.order_id or '',
            "ticket_no": payload.ticket_no or '',
            "amount": payload.amount or 0.0,
            "note": payload.note
        })

        # 2. Update active reconciliation results
        update_query = text("""
            UPDATE reconciliation_results r
            SET recon_status = 'Manually Refunded',
                notes = COALESCE(notes || ' | ', '') || 'Manual Refund: ' || :note
            WHERE (NULLIF(order_id, '') = NULLIF(:order_id, '') OR (NULLIF(order_id, '') IS NULL AND NULLIF(:order_id, '') IS NULL))
              AND (NULLIF(ticket_no, '') = NULLIF(:ticket_no, '') OR (NULLIF(ticket_no, '') IS NULL AND NULLIF(:ticket_no, '') IS NULL))
              AND recon_status = 'Liable for Refund'
        """)
        update_res = db.execute(update_query, {
            "order_id": payload.order_id or '',
            "ticket_no": payload.ticket_no or '',
            "note": payload.note
        })
        
        db.commit()
        return {
            "success": True,
            "message": "Manual refund registered and applied successfully.",
            "updated_count": update_res.rowcount
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to record manual refund: {e}")


@app.get("/api/reconcile/manual-refunds/logs", response_model=List[ManualRefundLogSchema])
def get_manual_refund_logs(db: Session = Depends(get_db)):
    """
    Fetches the full historical audit log of all manual tag updates.
    """
    try:
        logs_query = text("""
            SELECT id, order_id, ticket_no, amount, original_status, updated_status, note, updated_at
            FROM manual_refunds
            ORDER BY updated_at DESC
        """)
        results = db.execute(logs_query).mappings().all()
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch manual refund audit logs: {e}")


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
    from_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
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

    # Date Range filters
    if from_date:
        base_query_str += """ AND (
            CASE
                WHEN transaction_time ~ '^\\d{4}-\\d{2}-\\d{2}' THEN CAST(SUBSTRING(transaction_time FROM 1 FOR 10) AS DATE)
                WHEN transaction_time ~ '^\\d{2}-\\d{2}-\\d{4}' THEN TO_DATE(SUBSTRING(transaction_time FROM 1 FOR 10), 'DD-MM-YYYY')
                ELSE NULL
            END
        ) >= CAST(:from_date AS DATE)"""
        params["from_date"] = from_date

    if to_date:
        base_query_str += """ AND (
            CASE
                WHEN transaction_time ~ '^\\d{4}-\\d{2}-\\d{2}' THEN CAST(SUBSTRING(transaction_time FROM 1 FOR 10) AS DATE)
                WHEN transaction_time ~ '^\\d{2}-\\d{2}-\\d{4}' THEN TO_DATE(SUBSTRING(transaction_time FROM 1 FOR 10), 'DD-MM-YYYY')
                ELSE NULL
            END
        ) <= CAST(:to_date AS DATE)"""
        params["to_date"] = to_date


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
