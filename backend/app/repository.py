from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.schemas import ManualRefundRequestSchema
import logging

logger = logging.getLogger(__name__)

def get_ingestion_logs_from_db(db: Session) -> List[Dict[str, Any]]:
    """
    Fetches all upload audit logs from the database, ordered by ID descending.
    """
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


def revert_ingestion_in_db(db: Session, log_id: int) -> Optional[Tuple[str, int, str]]:
    """
    Deletes staged rows for a specific ingestion, marks the log as REVERTED,
    and clears the reconciliation results to prevent stale data.
    Returns (filename, deleted_count, table_name) if found, otherwise None.
    """
    # 1. Fetch the log record
    log_query = text("SELECT id, filename, table_name, status FROM ingestion_logs WHERE id = :log_id")
    log_row = db.execute(log_query, {"log_id": log_id}).first()
    
    if not log_row:
        return None
        
    _, filename, table_name, status = log_row
    
    if status == 'REVERTED':
        raise ValueError("This file upload has already been reverted.")
        
    # SQL Injection prevention: Whitelist dynamic table names
    VALID_STAGING_TABLES = {
        'stg_mobile_mumbaione', 'stg_mobile_metroconnect3', 'stg_mobile_ondc',
        'stg_pg_transactions', 'stg_afc_transactions', 'reconciliation_results'
    }
    if table_name not in VALID_STAGING_TABLES:
        logger.error(f"SQL Injection attempt or invalid table name detected during reversion: {table_name}")
        raise ValueError(f"Invalid table name detected: {table_name}")
        
    # 2. Delete the transactions from the staging table
    logger.info(f"Reverting file ingestion: filename={filename}, table={table_name}")
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
    logger.info("Truncating reconciliation results to clear state after revert.")
    db.execute(text("TRUNCATE TABLE reconciliation_results CASCADE"))
    
    return filename, deleted_count, table_name


def create_manual_refund_in_db(db: Session, payload: ManualRefundRequestSchema) -> Tuple[str, int]:
    """
    Registers a manual refund in the manual_refunds table and updates the matching
    record in reconciliation_results.
    Returns (original_status, updated_rowcount).
    """
    # 1. Find the active record to identify the original status
    lookup_query = text("""
        SELECT recon_status, amount FROM reconciliation_results
        WHERE (NULLIF(order_id, '') = NULLIF(:order_id, '') OR (NULLIF(order_id, '') IS NULL AND NULLIF(:order_id, '') IS NULL))
          AND (NULLIF(ticket_no, '') = NULLIF(:ticket_no, '') OR (NULLIF(ticket_no, '') IS NULL AND NULLIF(:ticket_no, '') IS NULL))
          AND recon_status IN ('Liable for Refund', 'Discrepancy')
        LIMIT 1
    """)
    record = db.execute(lookup_query, {
        "order_id": payload.order_id or '',
        "ticket_no": payload.ticket_no or ''
    }).first()

    if not record:
        raise KeyError("No matching transaction in 'Liable for Refund' or 'Discrepancy' status found in active results.")

    orig_status, db_amount = record
    actual_amount = payload.amount if payload.amount is not None else (float(db_amount) if db_amount is not None else 0.0)

    # 2. Insert into manual_refunds table
    insert_query = text("""
        INSERT INTO manual_refunds (order_id, ticket_no, amount, original_status, updated_status, note)
        VALUES (:order_id, :ticket_no, :amount, :original_status, 'Manually Refunded', :note)
    """)
    db.execute(insert_query, {
        "order_id": payload.order_id or '',
        "ticket_no": payload.ticket_no or '',
        "amount": actual_amount,
        "original_status": orig_status,
        "note": payload.note
    })

    # 3. Update active reconciliation results
    update_query = text("""
        UPDATE reconciliation_results
        SET recon_status = 'Manually Refunded',
            notes = COALESCE(notes || ' | ', '') || 'Manual Refund: ' || :note
        WHERE (NULLIF(order_id, '') = NULLIF(:order_id, '') OR (NULLIF(order_id, '') IS NULL AND NULLIF(:order_id, '') IS NULL))
          AND (NULLIF(ticket_no, '') = NULLIF(:ticket_no, '') OR (NULLIF(ticket_no, '') IS NULL AND NULLIF(:ticket_no, '') IS NULL))
          AND recon_status = :original_status
    """)
    update_res = db.execute(update_query, {
        "order_id": payload.order_id or '',
        "ticket_no": payload.ticket_no or '',
        "original_status": orig_status,
        "note": payload.note
    })

    return orig_status, update_res.rowcount


def get_manual_refunds_from_db(db: Session) -> List[Dict[str, Any]]:
    """
    Fetches the historical log of all manual refund tag updates.
    """
    logs_query = text("""
        SELECT id, order_id, ticket_no, amount, original_status, updated_status, note, updated_at
        FROM manual_refunds
        ORDER BY updated_at DESC
    """)
    return db.execute(logs_query).mappings().all()


def get_paginated_results_from_db(
    db: Session,
    app: Optional[str],
    status: Optional[str],
    search: Optional[str],
    sources: Optional[str],
    from_date: Optional[str],
    to_date: Optional[str],
    page: int,
    limit: int
) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Builds the dynamic query string, performs count evaluation,
    and returns a tuple containing (total_count, records_list).
    """
    base_query_str = "FROM reconciliation_results WHERE 1=1"
    params: Dict[str, Any] = {}
    
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

    # Date Range filters (native timestamps)
    if from_date:
        base_query_str += " AND transaction_time >= CAST(:from_date AS TIMESTAMP)"
        params["from_date"] = from_date

    if to_date:
        base_query_str += " AND transaction_time < CAST(:to_date AS TIMESTAMP) + INTERVAL '1 day'"
        params["to_date"] = to_date

    # 1. Count Total Matches
    count_query = text(f"SELECT COUNT(*) {base_query_str}")
    total = db.execute(count_query, params).scalar()

    # 2. Paginate Results
    offset = (page - 1) * limit
    select_query_str = (
        f"SELECT id, app_source, order_id, ticket_no, pg_ref_no, amount, "
        f"transaction_time, recon_status, notes, data_sources, reconciled_at "
        f"{base_query_str} ORDER BY id ASC LIMIT :limit OFFSET :offset"
    )
    
    params["limit"] = limit
    params["offset"] = offset
    
    result_set = db.execute(text(select_query_str), params)
    records = []
    
    for row in result_set:
        records.append({
            "id": row[0],
            "app_source": row[1],
            "order_id": row[2],
            "ticket_no": row[3],
            "pg_ref_no": row[4],
            "amount": float(row[5]) if row[5] is not None else None,
            "transaction_time": row[6].strftime('%Y-%m-%d %H:%M:%S') if isinstance(row[6], datetime) else str(row[6]) if row[6] is not None else None,
            "recon_status": row[7],
            "notes": row[8],
            "data_sources": row[9],
            "reconciled_at": row[10]
        })

    return total, records
