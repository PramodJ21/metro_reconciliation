from sqlalchemy import text
from app.database import engine
from typing import List, Dict, Any

def run_reconciliation_process() -> List[Dict[str, Any]]:
    """
    Executes the SQL-based reconciliation classification process.
    Clears previous results and runs set-based classifying queries.
    Returns summaries of the results for each app.
    
    Status Rules (priority order):
      1. Refunded       – A REFUND exists in PG, or the App record is marked REFUNDED/refunded
      2. Settled         – App + PG (SETTLED) + AFC all have the record
      3. Liable for Refund – App + PG (SETTLED) but NOT in AFC; also any PG-only record with no App/AFC
      4. Failed Transaction – App only (no PG, no AFC); OR PG has record with no App AND no AFC match
      5. Discrepancy    – Any remaining unclassifiable state
    
    data_sources column contains a comma-separated list of which systems saw the record,
    e.g. "App", "App,PG", "App,PG,AFC", "PG" etc.
    """
    with engine.begin() as conn:
        # 1. Clear previous results
        print("Clearing previous reconciliation results...")
        conn.execute(text("TRUNCATE TABLE reconciliation_results;"))

        # -------------------------------------------------------------------------
        # 2. Reconcile MumbaiOne
        #    App Key:  pg_reference_no  <-> PG: pgi_ref_no
        #    App Key:  ticket_number    <-> AFC: slave_qr_no
        # -------------------------------------------------------------------------
        print("Reconciling MumbaiOne...")
        m1_query = """
        INSERT INTO reconciliation_results
            (app_source, order_id, ticket_no, pg_ref_no, amount, transaction_time,
             recon_status, notes, data_sources)

        -- Part A: App-led records (all records in the MumbaiOne mobile table)
        SELECT 
            'MumbaiOne' AS app_source,
            m.mumbai_one_id AS order_id,
            m.ticket_number AS ticket_no,
            m.pg_reference_no AS pg_ref_no,
            m.payment_amount AS amount,
            m.transaction_date_time AS transaction_time,
            CASE 
                -- Rule 1: Refunded
                WHEN EXISTS (
                    SELECT 1 FROM stg_pg_transactions p_ref 
                    WHERE p_ref.pgi_ref_no = m.pg_reference_no 
                    AND p_ref.transaction_type = 'REFUND'
                    AND p_ref.app_source = 'MumbaiOne'
                ) OR m.ticket_status = 'REFUNDED' THEN 'Refunded'

                -- Rule 2: Settled (App + PG settled + AFC)
                WHEN p_set.pgi_ref_no IS NOT NULL AND a.slave_qr_no IS NOT NULL THEN 'Settled'

                -- Rule 3: Liable for Refund (App + PG settled, but not in AFC)
                WHEN p_set.pgi_ref_no IS NOT NULL AND a.slave_qr_no IS NULL THEN 'Liable for Refund'

                -- Rule 4: Failed Transaction (App only – not in PG, not in AFC)
                WHEN p_set.pgi_ref_no IS NULL AND a.slave_qr_no IS NULL THEN 'Failed Transaction'

                ELSE 'Discrepancy'
            END AS recon_status,
            CASE
                WHEN EXISTS (
                    SELECT 1 FROM stg_pg_transactions p_ref 
                    WHERE p_ref.pgi_ref_no = m.pg_reference_no 
                    AND p_ref.transaction_type = 'REFUND'
                    AND p_ref.app_source = 'MumbaiOne'
                ) OR m.ticket_status = 'REFUNDED'
                    THEN 'Refund confirmed. Present in App' || CASE WHEN p_set.pgi_ref_no IS NOT NULL THEN ', PG' ELSE '' END || CASE WHEN a.slave_qr_no IS NOT NULL THEN ', AFC' ELSE '' END || '.'
                WHEN p_set.pgi_ref_no IS NOT NULL AND a.slave_qr_no IS NOT NULL
                    THEN 'Matched across all 3 systems: App, PG, and AFC gates.'
                WHEN p_set.pgi_ref_no IS NOT NULL AND a.slave_qr_no IS NULL
                    THEN 'Present in App and PG but missing in AFC gates. Passenger may have travelled without gate scan.'
                WHEN p_set.pgi_ref_no IS NULL AND a.slave_qr_no IS NULL
                    THEN 'Failed or aborted payment. Record only in App – no PG settlement, no AFC gate scan.'
                ELSE 'Unclassified state. Manual review required.'
            END AS notes,
            CASE
                WHEN p_set.pgi_ref_no IS NOT NULL AND a.slave_qr_no IS NOT NULL THEN 'App,PG,AFC'
                WHEN p_set.pgi_ref_no IS NOT NULL AND a.slave_qr_no IS NULL THEN 'App,PG'
                WHEN p_set.pgi_ref_no IS NULL AND a.slave_qr_no IS NOT NULL THEN 'App,AFC'
                ELSE 'App'
            END AS data_sources
        FROM stg_mobile_mumbaione m
        LEFT JOIN stg_pg_transactions p_set 
            ON m.pg_reference_no = p_set.pgi_ref_no 
            AND p_set.transaction_type = 'SETTLED'
            AND p_set.app_source = 'MumbaiOne'
        LEFT JOIN stg_afc_transactions a 
            ON m.ticket_number = a.slave_qr_no
            AND a.operator_name = 'MQR MUMBAI ONE APP'

        UNION ALL

        -- Part B: PG-only records (settled in PG but not matched to any App record)
        SELECT
            'MumbaiOne' AS app_source,
            NULL AS order_id,
            NULL AS ticket_no,
            p.pgi_ref_no AS pg_ref_no,
            p.gross_amount AS amount,
            p.date_of_txn AS transaction_time,
            'Failed Transaction' AS recon_status,
            'Payment settled in PG but no matching App record found. No AFC gate scan detected either.' AS notes,
            CASE
                WHEN EXISTS (
                    SELECT 1 FROM stg_afc_transactions afc
                    WHERE afc.operator_name = 'MQR MUMBAI ONE APP'
                    -- AFC doesn't join directly to PG; we flag as PG-only if no App record exists
                ) THEN 'PG'
                ELSE 'PG'
            END AS data_sources
        FROM stg_pg_transactions p
        WHERE p.transaction_type = 'SETTLED'
          AND p.app_source = 'MumbaiOne'
          AND NOT EXISTS (
              SELECT 1 FROM stg_mobile_mumbaione m2
              WHERE m2.pg_reference_no = p.pgi_ref_no
          );
        """
        conn.execute(text(m1_query))

        # -------------------------------------------------------------------------
        # 3. Reconcile MetroConnect3
        #    App Key: ticket_no <-> PG: ref_1
        #    App Key: ticket_no <-> AFC: slave_qr_no
        # -------------------------------------------------------------------------
        print("Reconciling MetroConnect3...")
        mc3_query = """
        INSERT INTO reconciliation_results
            (app_source, order_id, ticket_no, pg_ref_no, amount, transaction_time,
             recon_status, notes, data_sources)

        -- Part A: App-led records
        SELECT 
            'MetroConnect3' AS app_source,
            NULL AS order_id,
            m.ticket_no AS ticket_no,
            p_set.pgi_ref_no AS pg_ref_no,
            m.amount AS amount,
            m.created_at AS transaction_time,
            CASE 
                -- Rule 1: Refunded
                WHEN EXISTS (
                    SELECT 1 FROM stg_pg_transactions p_ref 
                    WHERE p_ref.ref_1 = m.ticket_no 
                    AND p_ref.transaction_type = 'REFUND'
                    AND p_ref.app_source = 'MetroConnect3'
                ) OR m.status = 'refunded' THEN 'Refunded'

                -- Rule 2: Settled
                WHEN p_set.id IS NOT NULL AND a.slave_qr_no IS NOT NULL THEN 'Settled'

                -- Rule 3: Liable for Refund
                WHEN p_set.id IS NOT NULL AND a.slave_qr_no IS NULL THEN 'Liable for Refund'

                -- Rule 4: Failed Transaction (App only)
                WHEN p_set.id IS NULL AND a.slave_qr_no IS NULL THEN 'Failed Transaction'

                ELSE 'Discrepancy'
            END AS recon_status,
            CASE
                WHEN EXISTS (
                    SELECT 1 FROM stg_pg_transactions p_ref 
                    WHERE p_ref.ref_1 = m.ticket_no 
                    AND p_ref.transaction_type = 'REFUND'
                    AND p_ref.app_source = 'MetroConnect3'
                ) OR m.status = 'refunded'
                    THEN 'Refund confirmed. Present in App' || CASE WHEN p_set.id IS NOT NULL THEN ', PG' ELSE '' END || CASE WHEN a.slave_qr_no IS NOT NULL THEN ', AFC' ELSE '' END || '.'
                WHEN p_set.id IS NOT NULL AND a.slave_qr_no IS NOT NULL
                    THEN 'Matched across all 3 systems: App, PG, and AFC gates.'
                WHEN p_set.id IS NOT NULL AND a.slave_qr_no IS NULL
                    THEN 'Present in App and PG but missing in AFC gates. Passenger may have travelled without gate scan.'
                WHEN p_set.id IS NULL AND a.slave_qr_no IS NULL
                    THEN 'Failed or aborted payment. Record only in App – no PG settlement, no AFC gate scan.'
                ELSE 'Unclassified state. Manual review required.'
            END AS notes,
            CASE
                WHEN p_set.id IS NOT NULL AND a.slave_qr_no IS NOT NULL THEN 'App,PG,AFC'
                WHEN p_set.id IS NOT NULL AND a.slave_qr_no IS NULL THEN 'App,PG'
                WHEN p_set.id IS NULL AND a.slave_qr_no IS NOT NULL THEN 'App,AFC'
                ELSE 'App'
            END AS data_sources
        FROM stg_mobile_metroconnect3 m
        LEFT JOIN stg_pg_transactions p_set 
            ON m.ticket_no = p_set.ref_1 
            AND p_set.transaction_type = 'SETTLED'
            AND p_set.app_source = 'MetroConnect3'
        LEFT JOIN stg_afc_transactions a 
            ON m.ticket_no = a.slave_qr_no

        UNION ALL

        -- Part B: PG-only records for MetroConnect3
        SELECT
            'MetroConnect3' AS app_source,
            NULL AS order_id,
            p.ref_1 AS ticket_no,
            p.pgi_ref_no AS pg_ref_no,
            p.gross_amount AS amount,
            p.date_of_txn AS transaction_time,
            'Failed Transaction' AS recon_status,
            'Payment settled in PG but no matching App record found. No AFC gate scan detected either.' AS notes,
            'PG' AS data_sources
        FROM stg_pg_transactions p
        WHERE p.transaction_type = 'SETTLED'
          AND p.app_source = 'MetroConnect3'
          AND NOT EXISTS (
              SELECT 1 FROM stg_mobile_metroconnect3 m2
              WHERE m2.ticket_no = p.ref_1
          );
        """
        conn.execute(text(mc3_query))

        # -------------------------------------------------------------------------
        # 4. Reconcile ONDC (No PG)
        #    App Key: order_id <-> AFC: order_id
        # -------------------------------------------------------------------------
        print("Reconciling ONDC...")
        ondc_query = """
        INSERT INTO reconciliation_results
            (app_source, order_id, ticket_no, pg_ref_no, amount, transaction_time,
             recon_status, notes, data_sources)
        SELECT 
            'ONDC' AS app_source,
            m.order_id AS order_id,
            NULL AS ticket_no,
            m.transaction_id AS pg_ref_no,
            m.price_rs AS amount,
            m.date AS transaction_time,
            CASE 
                -- Rule 1: Settled (Present in both App and AFC)
                WHEN a.order_id IS NOT NULL THEN 'Settled'

                -- Rule 2: Liable for Refund (Present in App but not in AFC)
                ELSE 'Liable for Refund'
            END AS recon_status,
            CASE
                WHEN a.order_id IS NOT NULL
                    THEN 'Matched across App and AFC gates. No PG involved (ONDC direct payment).'
                ELSE 'Present in ONDC App but missing in AFC gates. Liable for refund.'
            END AS notes,
            CASE
                WHEN a.order_id IS NOT NULL THEN 'App,AFC'
                ELSE 'App'
            END AS data_sources
        FROM stg_mobile_ondc m
        LEFT JOIN (
            SELECT DISTINCT order_id 
            FROM stg_afc_transactions 
            WHERE operator_name = 'MQR ONDC APP'
        ) a ON m.order_id = a.order_id;
        """
        conn.execute(text(ondc_query))
        
        # 4. Apply Persistent Manual Tag Updates
        print("Applying persistent manual refunds...")
        apply_refunds_query = """
        UPDATE reconciliation_results r
        SET recon_status = m.updated_status,
            notes = COALESCE(r.notes || ' | ', '') || 'Manual Refund: ' || m.note
        FROM manual_refunds m
        WHERE (NULLIF(r.order_id, '') = NULLIF(m.order_id, '') OR (NULLIF(r.order_id, '') IS NULL AND NULLIF(m.order_id, '') IS NULL))
          AND (NULLIF(r.ticket_no, '') = NULLIF(m.ticket_no, '') OR (NULLIF(r.ticket_no, '') IS NULL AND NULLIF(m.ticket_no, '') IS NULL))
          AND r.recon_status = m.original_status;
        """
        conn.execute(text(apply_refunds_query))
        
        print("Reconciliation classifying completed.")

    # 5. Refresh Materialized View Concurrently for dashboard widgets
    try:
        print("Refreshing materialized view concurrently...")
        with engine.begin() as conn:
            conn.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_reconciliation_summary;"))
    except Exception as re:
        print(f"Warning: Failed to refresh materialized view concurrently: {re}")
        # Fallback to non-concurrent refresh if unique index is not ready
        try:
            with engine.begin() as conn:
                conn.execute(text("REFRESH MATERIALIZED VIEW mv_reconciliation_summary;"))
        except Exception as re2:
            print(f"Error: Failed fallback refresh of materialized view: {re2}")

    # 6. Calculate summaries
    return get_reconciliation_summaries()

def get_reconciliation_summaries() -> List[Dict[str, Any]]:
    """
    Fetches the cached summaries from the materialized view mv_reconciliation_summary.
    """
    summaries = []
    with engine.connect() as conn:
        query = text("""
            SELECT 
                app_source,
                total_records,
                settled,
                liable_for_refund,
                failed_transaction,
                refunded,
                discrepancy,
                revenue,
                settled_revenue,
                afc_revenue,
                refund_amount
            FROM mv_reconciliation_summary;
        """)
        results = conn.execute(query).mappings().all()
        for r in results:
            summaries.append({
                "app_source": r["app_source"],
                "total_records": r["total_records"],
                "settled": r["settled"],
                "liable_for_refund": r["liable_for_refund"],
                "failed_transaction": r["failed_transaction"],
                "refunded": r["refunded"],
                "discrepancy": r["discrepancy"],
                "revenue": float(r["revenue"] or 0.0),
                "settled_revenue": float(r["settled_revenue"] or 0.0),
                "afc_revenue": float(r["afc_revenue"] or 0.0),
                "refund_amount": float(r["refund_amount"] or 0.0)
            })
    return summaries
