import psycopg2
from psycopg2.extras import execute_values
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings
from typing import Generator
from sqlalchemy.orm import Session
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# Create standard SQLAlchemy connection elements with connection pooling and pre-ping safety
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,        # Bounded pool size for corporate resource sharing
    max_overflow=5,
    pool_recycle=3600,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 10, "options": "-c statement_timeout=30000"} # Statement timeout of 30 seconds
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def execute_ddl() -> None:
    """Executes staging and reconciliation DDL statements to set up partitioned tables, indices, and materialized views"""
    # Check if table is already partitioned. If not, drop tables to reconstruct them.
    is_partitioned = False
    try:
        with engine.connect() as conn:
            res = conn.execute(text("SELECT relkind FROM pg_class WHERE relname = 'reconciliation_results'")).first()
            if res and res[0] == 'p':
                is_partitioned = True
    except Exception:
        # Table might not exist yet
        pass

    migration_statements = []
    if not is_partitioned:
        logger.info("[MIGRATION] Dropping old regular tables to recreate partitioned tables...")
        migration_statements = [
            "DROP TABLE IF EXISTS stg_mobile_mumbaione CASCADE;",
            "DROP TABLE IF EXISTS stg_mobile_metroconnect3 CASCADE;",
            "DROP TABLE IF EXISTS stg_mobile_ondc CASCADE;",
            "DROP TABLE IF EXISTS stg_pg_transactions CASCADE;",
            "DROP TABLE IF EXISTS stg_afc_transactions CASCADE;",
            "DROP TABLE IF EXISTS reconciliation_results CASCADE;",
            "DROP MATERIALIZED VIEW IF EXISTS mv_reconciliation_summary CASCADE;"
        ]

    ddl_statements = migration_statements + [
        # 1. Mobile MumbaiOne Staging (Partitioned by transaction_date_time)
        """
        CREATE TABLE IF NOT EXISTS stg_mobile_mumbaione (
            id SERIAL,
            ticket_number VARCHAR,
            pg_reference_no VARCHAR,
            mumbai_one_id VARCHAR,
            source_station VARCHAR,
            destination_station VARCHAR,
            transportation_mode VARCHAR,
            pto_name VARCHAR,
            service_type VARCHAR,
            passenger_type VARCHAR,
            no_of_passenger INTEGER,
            payment_amount NUMERIC,
            ticket_type VARCHAR,
            transaction_id VARCHAR,
            transaction_date_time TIMESTAMP NOT NULL,
            user_email_id VARCHAR,
            user_mobile_no VARCHAR,
            app_environment VARCHAR,
            payment_status VARCHAR,
            ticket_status VARCHAR,
            file_source VARCHAR,
            PRIMARY KEY (id, transaction_date_time)
        ) PARTITION BY RANGE (transaction_date_time);
        """,
        # Active months partitions
        """
        CREATE TABLE IF NOT EXISTS stg_mobile_mumbaione_y2026m04 PARTITION OF stg_mobile_mumbaione
            FOR VALUES FROM ('2026-04-01 00:00:00') TO ('2026-05-01 00:00:00');
        """,
        """
        CREATE TABLE IF NOT EXISTS stg_mobile_mumbaione_y2026m05 PARTITION OF stg_mobile_mumbaione
            FOR VALUES FROM ('2026-05-01 00:00:00') TO ('2026-06-01 00:00:00');
        """,
        # Default partition to catch out of bounds dates gracefully
        """
        CREATE TABLE IF NOT EXISTS stg_mobile_mumbaione_default PARTITION OF stg_mobile_mumbaione DEFAULT;
        """,
        "CREATE INDEX IF NOT EXISTS idx_stg_mob_m1_tkt_no ON stg_mobile_mumbaione(ticket_number);",
        "CREATE INDEX IF NOT EXISTS idx_stg_mob_m1_pg_ref ON stg_mobile_mumbaione(pg_reference_no);",
        "CREATE INDEX IF NOT EXISTS idx_stg_mob_m1_filesrc ON stg_mobile_mumbaione(file_source);",
        
        # 2. Mobile MetroConnect3 Staging (Partitioned by created_at)
        """
        CREATE TABLE IF NOT EXISTS stg_mobile_metroconnect3 (
            id SERIAL,
            ticket_no VARCHAR,
            journey_id INTEGER,
            booking_type VARCHAR,
            no_of_tickets INTEGER,
            status VARCHAR,
            amount NUMERIC,
            total_distance NUMERIC,
            total_time NUMERIC,
            total_stations VARCHAR,
            booking_time TIMESTAMP,
            valid_till TIMESTAMP,
            requested_from VARCHAR,
            trip_pass_id VARCHAR,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP,
            file_source VARCHAR,
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at);
        """,
        # Active months partitions
        """
        CREATE TABLE IF NOT EXISTS stg_mobile_metroconnect3_y2026m04 PARTITION OF stg_mobile_metroconnect3
            FOR VALUES FROM ('2026-04-01 00:00:00') TO ('2026-05-01 00:00:00');
        """,
        """
        CREATE TABLE IF NOT EXISTS stg_mobile_metroconnect3_y2026m05 PARTITION OF stg_mobile_metroconnect3
            FOR VALUES FROM ('2026-05-01 00:00:00') TO ('2026-06-01 00:00:00');
        """,
        # Default partition
        """
        CREATE TABLE IF NOT EXISTS stg_mobile_metroconnect3_default PARTITION OF stg_mobile_metroconnect3 DEFAULT;
        """,
        "CREATE INDEX IF NOT EXISTS idx_stg_mob_mc3_tno ON stg_mobile_metroconnect3(ticket_no);",
        "CREATE INDEX IF NOT EXISTS idx_stg_mob_mc3_filesrc ON stg_mobile_metroconnect3(file_source);",

        # 3. Mobile ONDC Staging (Partitioned by date)
        """
        CREATE TABLE IF NOT EXISTS stg_mobile_ondc (
            id SERIAL,
            order_id VARCHAR,
            date TIMESTAMP NOT NULL,
            transaction_id VARCHAR,
            buyer VARCHAR,
            number_of_tickets INTEGER,
            price_rs NUMERIC,
            status VARCHAR,
            start_station VARCHAR,
            end_station VARCHAR,
            refund_amount NUMERIC,
            file_source VARCHAR,
            PRIMARY KEY (id, date)
        ) PARTITION BY RANGE (date);
        """,
        # Active months partitions
        """
        CREATE TABLE IF NOT EXISTS stg_mobile_ondc_y2026m04 PARTITION OF stg_mobile_ondc
            FOR VALUES FROM ('2026-04-01 00:00:00') TO ('2026-05-01 00:00:00');
        """,
        """
        CREATE TABLE IF NOT EXISTS stg_mobile_ondc_y2026m05 PARTITION OF stg_mobile_ondc
            FOR VALUES FROM ('2026-05-01 00:00:00') TO ('2026-06-01 00:00:00');
        """,
        # Default partition
        """
        CREATE TABLE IF NOT EXISTS stg_mobile_ondc_default PARTITION OF stg_mobile_ondc DEFAULT;
        """,
        "CREATE INDEX IF NOT EXISTS idx_stg_mob_ondc_ord ON stg_mobile_ondc(order_id);",
        "CREATE INDEX IF NOT EXISTS idx_stg_mob_ondc_filesrc ON stg_mobile_ondc(file_source);",

        # 4. Payment Gateway Staging (Partitioned by date_of_txn)
        """
        CREATE TABLE IF NOT EXISTS stg_pg_transactions (
            id SERIAL,
            biller_id VARCHAR,
            bank_id VARCHAR,
            bank_ref_no VARCHAR,
            pgi_ref_no VARCHAR,
            ref_1 VARCHAR,
            ref_2 VARCHAR,
            ref_3 VARCHAR,
            ref_4 VARCHAR,
            ref_5 VARCHAR,
            ref_6 VARCHAR,
            ref_7 VARCHAR,
            ref_8 VARCHAR,
            filler VARCHAR,
            date_of_txn TIMESTAMP NOT NULL,
            settlement_date TIMESTAMP,
            gross_amount NUMERIC,
            charges NUMERIC,
            gst NUMERIC,
            net_amount NUMERIC,
            refund_id VARCHAR,
            refund_date TIMESTAMP,
            refund_amount NUMERIC,
            sub_txn_id VARCHAR,
            transaction_type VARCHAR, -- 'SETTLED' or 'REFUND'
            app_source VARCHAR,         -- 'MetroConnect3' or 'MumbaiOne'
            file_source VARCHAR,
            PRIMARY KEY (id, date_of_txn)
        ) PARTITION BY RANGE (date_of_txn);
        """,
        # Active months partitions
        """
        CREATE TABLE IF NOT EXISTS stg_pg_transactions_y2026m04 PARTITION OF stg_pg_transactions
            FOR VALUES FROM ('2026-04-01 00:00:00') TO ('2026-05-01 00:00:00');
        """,
        """
        CREATE TABLE IF NOT EXISTS stg_pg_transactions_y2026m05 PARTITION OF stg_pg_transactions
            FOR VALUES FROM ('2026-05-01 00:00:00') TO ('2026-06-01 00:00:00');
        """,
        # Default partition
        """
        CREATE TABLE IF NOT EXISTS stg_pg_transactions_default PARTITION OF stg_pg_transactions DEFAULT;
        """,
        "CREATE INDEX IF NOT EXISTS idx_stg_pg_pgi_ref ON stg_pg_transactions(pgi_ref_no);",
        "CREATE INDEX IF NOT EXISTS idx_stg_pg_ref_1 ON stg_pg_transactions(ref_1);",
        "CREATE INDEX IF NOT EXISTS idx_stg_pg_type_src ON stg_pg_transactions(transaction_type, app_source);",
        "CREATE INDEX IF NOT EXISTS idx_stg_pg_filesrc ON stg_pg_transactions(file_source);",

        # 5. AFC Staging (Partitioned by date)
        """
        CREATE TABLE IF NOT EXISTS stg_afc_transactions (
            id SERIAL,
            s_no INTEGER,
            date TIMESTAMP NOT NULL,
            pass_name VARCHAR,
            operator_name VARCHAR,
            order_id VARCHAR,
            ms_qr_no VARCHAR,
            source_stn VARCHAR,
            destination_stn VARCHAR,
            slave_qr_no VARCHAR,
            units INTEGER,
            total_price NUMERIC,
            file_source VARCHAR,
            PRIMARY KEY (id, date)
        ) PARTITION BY RANGE (date);
        """,
        # Active months partitions
        """
        CREATE TABLE IF NOT EXISTS stg_afc_transactions_y2026m04 PARTITION OF stg_afc_transactions
            FOR VALUES FROM ('2026-04-01 00:00:00') TO ('2026-05-01 00:00:00');
        """,
        """
        CREATE TABLE IF NOT EXISTS stg_afc_transactions_y2026m05 PARTITION OF stg_afc_transactions
            FOR VALUES FROM ('2026-05-01 00:00:00') TO ('2026-06-01 00:00:00');
        """,
        # Default partition
        """
        CREATE TABLE IF NOT EXISTS stg_afc_transactions_default PARTITION OF stg_afc_transactions DEFAULT;
        """,
        "CREATE INDEX IF NOT EXISTS idx_stg_afc_sqr ON stg_afc_transactions(slave_qr_no);",
        "CREATE INDEX IF NOT EXISTS idx_stg_afc_ord ON stg_afc_transactions(order_id);",
        "CREATE INDEX IF NOT EXISTS idx_stg_afc_op ON stg_afc_transactions(operator_name);",
        "CREATE INDEX IF NOT EXISTS idx_stg_afc_filesrc ON stg_afc_transactions(file_source);",

        # 6. Ingestion Logs Table
        """
        CREATE TABLE IF NOT EXISTS ingestion_logs (
            id SERIAL PRIMARY KEY,
            filename VARCHAR NOT NULL,
            app_name VARCHAR NOT NULL,
            channel VARCHAR NOT NULL,
            table_name VARCHAR NOT NULL,
            row_count INTEGER NOT NULL,
            status VARCHAR NOT NULL DEFAULT 'STAGED', -- 'STAGED' or 'REVERTED'
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reverted_at TIMESTAMP
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_ing_logs_status ON ingestion_logs(status);",

        # 7. Reconciliation Results Table (Partitioned by transaction_time)
        """
        CREATE TABLE IF NOT EXISTS reconciliation_results (
            id SERIAL,
            app_source VARCHAR,
            order_id VARCHAR,
            ticket_no VARCHAR,
            pg_ref_no VARCHAR,
            amount NUMERIC,
            transaction_time TIMESTAMP NOT NULL,
            recon_status VARCHAR,
            notes VARCHAR,
            data_sources VARCHAR,
            reconciled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id, transaction_time)
        ) PARTITION BY RANGE (transaction_time);
        """,
        # Active months partitions
        """
        CREATE TABLE IF NOT EXISTS reconciliation_results_y2026m04 PARTITION OF reconciliation_results
            FOR VALUES FROM ('2026-04-01 00:00:00') TO ('2026-05-01 00:00:00');
        """,
        """
        CREATE TABLE IF NOT EXISTS reconciliation_results_y2026m05 PARTITION OF reconciliation_results
            FOR VALUES FROM ('2026-05-01 00:00:00') TO ('2026-06-01 00:00:00');
        """,
        # Default partition
        """
        CREATE TABLE IF NOT EXISTS reconciliation_results_default PARTITION OF reconciliation_results DEFAULT;
        """,
        "CREATE INDEX IF NOT EXISTS idx_recon_res_status ON reconciliation_results(recon_status);",
        "CREATE INDEX IF NOT EXISTS idx_recon_res_app ON reconciliation_results(app_source);",
        "CREATE INDEX IF NOT EXISTS idx_recon_res_ord_tkt ON reconciliation_results(order_id, ticket_no);",

        # 8. Manual Refunds Table (Audit Log of Tag Updates)
        """
        CREATE TABLE IF NOT EXISTS manual_refunds (
            id SERIAL PRIMARY KEY,
            order_id VARCHAR,
            ticket_no VARCHAR,
            amount NUMERIC,
            original_status VARCHAR DEFAULT 'Liable for Refund',
            updated_status VARCHAR DEFAULT 'Manually Refunded',
            note VARCHAR,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_man_ref_ord_tkt ON manual_refunds(order_id, ticket_no);",

        # 9. Materialized View for Dashboard Summaries
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_reconciliation_summary AS
        SELECT 
            app_source,
            COUNT(*) as total_records,
            COUNT(CASE WHEN recon_status = 'Settled' THEN 1 END) as settled,
            COUNT(CASE WHEN recon_status = 'Liable for Refund' THEN 1 END) as liable_for_refund,
            COUNT(CASE WHEN recon_status = 'Failed Transaction' THEN 1 END) as failed_transaction,
            COUNT(CASE WHEN recon_status IN ('Refunded', 'Manually Refunded') THEN 1 END) as refunded,
            COUNT(CASE WHEN recon_status = 'Discrepancy' THEN 1 END) as discrepancy,
            COALESCE(SUM(amount), 0) as revenue,
            COALESCE(SUM(CASE WHEN recon_status = 'Settled' THEN amount ELSE 0 END), 0) as settled_revenue,
            COALESCE(SUM(CASE WHEN data_sources LIKE '%AFC%' THEN amount ELSE 0 END), 0) as afc_revenue,
            COALESCE(SUM(CASE WHEN recon_status IN ('Refunded', 'Manually Refunded') THEN amount ELSE 0 END), 0) as refund_amount
        FROM reconciliation_results
        GROUP BY app_source;
        """,
        # Unique index on app_source (required for REFRESH CONCURRENTLY)
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_recon_sum_app ON mv_reconciliation_summary (app_source);"
    ]

    with engine.begin() as connection:
        logger.info("Executing DDL statements to set up tables and indices...")
        for stmt in ddl_statements:
            connection.execute(text(stmt))
        logger.info("All tables and indices verified successfully.")

def bulk_insert_df(table_name: str, df: pd.DataFrame, truncate: bool = False) -> int:
    """
    Ultra-Performance concurrency-safe bulk insert of a pandas DataFrame into a specified table.
    Bypasses standard insert overhead using COPY STDIN.
    """
    import io
    import csv

    if df.empty:
        return 0

    columns = list(df.columns)
    
    # 1. Fast TSV serialization in Pandas
    buffer = io.StringIO()
    df.to_csv(buffer, sep='\t', index=False, header=False, na_rep='\\N', quoting=csv.QUOTE_MINIMAL)
    buffer.seek(0)
    
    copy_query = f"COPY {table_name} ({','.join(columns)}) FROM STDIN WITH (FORMAT CSV, DELIMITER '\t', NULL '\\N')"

    # 2. Establish connection using engine pool
    conn = engine.raw_connection()
    try:
        with conn.cursor() as cur:
            if truncate:
                logger.info(f"Truncating table {table_name}...")
                cur.execute(f"TRUNCATE TABLE {table_name} CASCADE;")
            
            # Stream CSV/TSV directly into PostgreSQL using copy_expert
            logger.info(f"Bulk copy streaming {len(df):,} records into {table_name}...")
            cur.copy_expert(copy_query, buffer)
            
        # Commit the transaction block
        conn.commit()
        return len(df)
    except Exception as e:
        logger.exception(f"Bulk insert failed for {table_name}: {str(e)}")
        conn.rollback()
        raise e
    finally:
        conn.close()
