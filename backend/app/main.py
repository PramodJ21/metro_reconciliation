import io
import json
import pandas as pd
import logging
import os
from datetime import datetime
from typing import List, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form, Query, HTTPException, Depends, Request
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
from app.reconciler import run_reconciliation_process, get_reconciliation_summaries
from app.utils import deduplicate_dataframe
from app.tasks import parse_ingested_file
from app import repository

logger = logging.getLogger(__name__)

# Dead-Letter Queue helper to store invalid uploaded files
def save_to_dlq(filename: str, payloads: List[tuple]):
    try:
        dlq_dir = "backend/temp_uploads/dlq"
        os.makedirs(dlq_dir, exist_ok=True)
        
        # Find file bytes in payloads
        file_bytes = None
        for fname, fbytes in payloads:
            if fname == filename:
                file_bytes = fbytes
                break
        
        if file_bytes:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dlq_path = os.path.join(dlq_dir, f"{timestamp}_{filename}")
            with open(dlq_path, "wb") as f:
                f.write(file_bytes)
            logger.warning(f"Invalid spreadsheet parsing triggered. File saved to DLQ: {dlq_path}")
    except Exception as dlq_err:
        logger.error(f"Failed to write file {filename} to DLQ: {dlq_err}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run database DDL statements on startup to guarantee tables exist"""
    try:
        execute_ddl()
    except Exception as e:
        logger.error(f"Error executing database DDL on startup: {e}")
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for high-performance metro booking transaction reconciliation.",
    lifespan=lifespan
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root() -> dict:
    return {
        "project": settings.PROJECT_NAME,
        "status": "Running",
        "docs_url": "/docs"
    }

MAX_FILE_SIZE = 50 * 1024 * 1024 # 50 MB
ALLOWED_EXTENSIONS = {'.xlsx', '.xls', '.csv'}

@app.post("/api/reconcile/upload")
async def upload_files(
    request: Request,
    app_name: str = Form(..., description="App: 'mumbaione', 'metroconnect3', 'ondc'"),
    channel: str = Form(..., description="Channel: 'mobile', 'payment_gateway', 'afc'"),
    clear_existing: bool = Form(False, description="Clear existing data in the target staging table first"),
    files: List[UploadFile] = File(..., description="Excel/CSV files to upload"),
    db: Session = Depends(get_db)
) -> StreamingResponse:
    """
    Accepts multiple file uploads for a specific App and Channel,
    parses them concurrently in secondary processes, and bulk inserts them into PostgreSQL.
    Streams real-time progress back to the client using Server-Sent Events (SSE).
    """
    # 1. Enforce size and type limits before reading files into memory
    for uf in files:
        filename = uf.filename or ""
        ext = os.path.splitext(filename.lower())[1]
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file extension for {filename}. Only .xlsx, .xls, and .csv files are allowed."
            )
        
        # Determine file size
        uf.file.seek(0, 2)
        size = uf.file.tell()
        uf.file.seek(0)
        if size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File {filename} exceeds the maximum allowed size of 50MB."
            )

    def _sse(event_type: str, payload: dict) -> str:
        payload["event"] = event_type
        return f"data: {json.dumps(payload)}\n\n"

    # Read raw file bytes into memory to be pickle-safe for ProcessPoolExecutor
    file_payloads = []
    for uf in files:
        file_payloads.append((uf.filename, uf.file.read()))

    async def event_generator():
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

        import concurrent.futures

        # Cap ProcessPoolExecutor to leave at least 1 CPU core free
        cpu_count = os.cpu_count() or 1
        max_workers = max(1, min(cpu_count - 1, 4, len(file_payloads)))
        yield _sse("progress", {
            "progress": 5,
            "message": f"Starting parallel parsing of {total_files} file(s) using {max_workers} processes..."
        })

        futures = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            for filename, file_bytes in file_payloads:
                futures.append(executor.submit(parse_ingested_file, filename, file_bytes, app_name, channel))

            completed_count = 0
            for future in concurrent.futures.as_completed(futures):
                if await request.is_disconnected():
                    logger.warning("Client disconnected during parallel parsing, aborting upload.")
                    for fut in futures:
                        fut.cancel()
                    return

                completed_count += 1
                base_progress = 5 + int((completed_count / total_files) * 55)

                try:
                    filename, df, telemetry = future.result()
                    if not telemetry["success"]:
                        raise ValueError(telemetry["error"])

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
                    save_to_dlq(filename, file_payloads)
                    yield _sse("error", {"message": f"Wrong file structure: {str(ve)}", "filename": filename})
                    return
                except Exception as e:
                    save_to_dlq(filename, file_payloads)
                    yield _sse("error", {"message": f"Parsing error in file: {str(e)}"})
                    return

        if await request.is_disconnected():
            logger.warning("Client disconnected post-parsing, aborting upload.")
            return

        if not parsed_dfs:
            yield _sse("error", {"message": "All uploaded files parsed into empty DataFrames. No records to ingest."})
            return

        yield _sse("progress", {
            "progress": 65,
            "message": f"Merging {total_files} file(s) into a single batch..."
        })

        try:
            combined_df = pd.concat(parsed_dfs, ignore_index=True)

            # In-memory batch self-deduplication (always run to prevent overlaps within the same batch upload)
            _before_self = len(combined_df)
            if table_name == 'stg_mobile_mumbaione' and 'pg_reference_no' in combined_df.columns:
                combined_df = combined_df.drop_duplicates(subset=['pg_reference_no'], keep='first')
            elif table_name == 'stg_mobile_metroconnect3' and 'ticket_no' in combined_df.columns:
                combined_df = combined_df.drop_duplicates(subset=['ticket_no'], keep='first')
            elif table_name == 'stg_mobile_ondc' and 'order_id' in combined_df.columns:
                combined_df = combined_df.drop_duplicates(subset=['order_id'], keep='first')
            elif table_name == 'stg_pg_transactions' and 'pgi_ref_no' in combined_df.columns and 'transaction_type' in combined_df.columns:
                combined_df = combined_df.drop_duplicates(subset=['pgi_ref_no', 'transaction_type'], keep='first')
            elif table_name == 'stg_afc_transactions' and 'slave_qr_no' in combined_df.columns:
                combined_df = combined_df.drop_duplicates(subset=['slave_qr_no'], keep='first')

            self_dups = _before_self - len(combined_df)
            if self_dups > 0:
                logger.info(f"[BATCH SELF-DEDUP] Removed {self_dups:,} duplicate rows within the uploaded batch data.")

            if await request.is_disconnected():
                logger.warning("Client disconnected before deduplication database checks, aborting.")
                return

            if not clear_existing:
                yield _sse("progress", {
                    "progress": 70,
                    "message": f"Checking {len(combined_df):,} records for duplicates against staging table..."
                })

                original_len = len(combined_df)
                combined_df = deduplicate_dataframe(combined_df, table_name, db)
                dups = original_len - len(combined_df)
                dup_msg = f" ({dups:,} duplicates removed)" if dups > 0 else ""

                if combined_df.empty:
                    yield _sse("error", {"message": "All records already present in staging. Ingestion skipped to prevent duplicates."})
                    return

                yield _sse("progress", {
                    "progress": 78,
                    "message": f"Deduplication complete{dup_msg}. {len(combined_df):,} net new records ready."
                })

            if await request.is_disconnected():
                logger.warning("Client disconnected before bulk insert execution, aborting.")
                return

            if clear_existing:
                try:
                    db.execute(
                        text("UPDATE ingestion_logs SET status = 'REVERTED', reverted_at = CURRENT_TIMESTAMP WHERE table_name = :tname AND status = 'STAGED'"),
                        {"tname": table_name}
                    )
                    db.commit()
                except Exception as le:
                    db.rollback()
                    logger.warning(f"Failed to update previous logs on truncate: {le}")

            yield _sse("progress", {
                "progress": 82,
                "message": f"Bulk inserting {len(combined_df):,} rows into {table_name}..."
            })

            total_rows_loaded = bulk_insert_df(table_name, combined_df, truncate=clear_existing)

            yield _sse("progress", {
                "progress": 92,
                "message": f"✓ Inserted {total_rows_loaded:,} rows. Writing audit log..."
            })

            file_counts = {}
            if not combined_df.empty and 'file_source' in combined_df.columns:
                file_counts = combined_df['file_source'].value_counts().to_dict()
            for item in processed_files:
                item["rows_loaded"] = file_counts.get(item["filename"], 0)

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
                logger.warning(f"Failed to write to ingestion_logs: {le}")

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
            logger.exception("Database ingestion error occurred")
            yield _sse("error", {"message": "Internal server error. Check database logs."})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/reconcile/logs")
def get_ingestion_logs(db: Session = Depends(get_db)) -> List[dict]:
    """
    Fetches the upload audit logs from ingestion_logs.
    """
    try:
        return repository.get_ingestion_logs_from_db(db)
    except Exception as e:
        logger.exception("Failed to fetch ingestion logs")
        raise HTTPException(status_code=500, detail="Internal server error. Check database logs.")

@app.post("/api/reconcile/revert")
def revert_upload(payload: RevertRequestSchema, db: Session = Depends(get_db)) -> dict:
    """
    Reverts a specific file ingestion transaction.
    Deletes the staged rows, updates the log status to 'REVERTED',
    and truncates the reconciliation results table.
    """
    try:
        res = repository.revert_ingestion_in_db(db, payload.log_id)
        if not res:
            raise HTTPException(status_code=404, detail="Ingestion log record not found.")
            
        filename, deleted_count, table_name = res
        db.commit()
        return {
            "success": True,
            "message": f"Successfully reverted file '{filename}'. Deleted {deleted_count} records from '{table_name}'. Ledger cleared.",
            "deleted_count": deleted_count,
            "table_name": table_name
        }
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        db.rollback()
        logger.exception("Revert upload failed due to database error")
        raise HTTPException(status_code=500, detail="Internal server error. Check database logs.")

@app.post("/api/reconcile/manual-refund")
def create_manual_refund(payload: ManualRefundRequestSchema, db: Session = Depends(get_db)) -> dict:
    """
    Registers a manual refund in the manual_refunds table
    and updates the active status of the matched record in reconciliation_results.
    Supports records with original status of 'Liable for Refund' or 'Discrepancy'.
    """
    try:
        orig_status, updated_count = repository.create_manual_refund_in_db(db, payload)
        db.commit()
        return {
            "success": True,
            "message": f"Manual refund registered and applied successfully from original status '{orig_status}'.",
            "updated_count": updated_count
        }
    except HTTPException:
        raise
    except KeyError as ke:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(ke))
    except Exception as e:
        db.rollback()
        logger.exception("Manual refund creation failed due to database error")
        raise HTTPException(status_code=500, detail="Internal server error. Check database logs.")

@app.get("/api/reconcile/manual-refunds/logs", response_model=List[ManualRefundLogSchema])
def get_manual_refund_logs(db: Session = Depends(get_db)) -> List[dict]:
    """
    Fetches the full historical audit log of all manual tag updates.
    """
    try:
        return repository.get_manual_refunds_from_db(db)
    except Exception as e:
        logger.exception("Failed to fetch manual refund logs")
        raise HTTPException(status_code=500, detail="Internal server error. Check database logs.")

@app.post("/api/reconcile/run", response_model=ReconciliationRunResponse)
def run_reconciliation() -> ReconciliationRunResponse:
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
        logger.exception("Reconciliation process execution failed")
        raise HTTPException(status_code=500, detail="Internal server error. Check database logs.")

@app.get("/api/reconcile/summary", response_model=List[ReconciliationSummary])
def get_summaries() -> List[ReconciliationSummary]:
    """
    Fetches the current reconciliation summaries from the database
    WITHOUT running the classification engine again.
    Queries the materialized view directly.
    """
    try:
        summaries = get_reconciliation_summaries()
        from app.schemas import ReconciliationSummary as SummarySchema
        return [SummarySchema(**s) for s in summaries]
    except Exception as e:
        logger.exception("Failed to fetch reconciliation summaries")
        raise HTTPException(status_code=500, detail="Internal server error. Check database logs.")

@app.get("/api/reconcile/results", response_model=PaginatedReconciliationResults)
def get_results(
    app: Optional[str] = Query(None, description="Filter by app: 'MumbaiOne', 'MetroConnect3', 'ONDC'"),
    status: Optional[str] = Query(None, description="Filter by status: 'Settled', 'Liable for Refund', 'Failed Transaction', 'Refunded'"),
    search: Optional[str] = Query(None, description="Search by Order ID, Ticket No, or PG Ref No"),
    sources: Optional[str] = Query(None, description="Comma-separated required sources presence, e.g., 'App,AFC'"),
    from_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=1000000, description="Records per page"),
    db: Session = Depends(get_db)
) -> PaginatedReconciliationResults:
    """
    Fetches the paginated reconciliation list with filters.
    """
    try:
        total, records = repository.get_paginated_results_from_db(
            db, app, status, search, sources, from_date, to_date, page, limit
        )
        records_schemas = [ReconciliationRecordSchema(**r) for r in records]
        return PaginatedReconciliationResults(
            total=total,
            page=page,
            limit=limit,
            results=records_schemas
        )
    except Exception as e:
        logger.exception("Failed to fetch reconciliation results")
        raise HTTPException(status_code=500, detail="Internal server error. Check database logs.")

@app.get("/api/db/status", response_model=DatabaseStatusSchema)
def db_status(db: Session = Depends(get_db)) -> DatabaseStatusSchema:
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
        logger.exception("Database status check failed")
        return DatabaseStatusSchema(
            connected=False,
            message="Database connection failed. Check database logs.",
            metrics=[]
        )
