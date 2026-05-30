import psycopg2
from psycopg2.extras import execute_values
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

# Create standard SQLAlchemy connection elements
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def execute_ddl():
    """Executes staging and reconciliation DDL statements to set up tables and indices"""
    ddl_statements = [
        # 1. Mobile MumbaiOne Staging
        """
        CREATE TABLE IF NOT EXISTS stg_mobile_mumbaione (
            id SERIAL PRIMARY KEY,
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
            transaction_date_time VARCHAR,
            user_email_id VARCHAR,
            user_mobile_no VARCHAR,
            app_environment VARCHAR,
            payment_status VARCHAR,
            ticket_status VARCHAR,
            file_source VARCHAR
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_stg_mob_m1_tkt_no ON stg_mobile_mumbaione(ticket_number);",
        "CREATE INDEX IF NOT EXISTS idx_stg_mob_m1_pg_ref ON stg_mobile_mumbaione(pg_reference_no);",
        "CREATE INDEX IF NOT EXISTS idx_stg_mob_m1_ord_id ON stg_mobile_mumbaione(mumbai_one_id);",
        "CREATE INDEX IF NOT EXISTS idx_stg_mob_m1_filesrc ON stg_mobile_mumbaione(file_source);",
        
        # 2. Mobile MetroConnect3 Staging
        """
        CREATE TABLE IF NOT EXISTS stg_mobile_metroconnect3 (
            id SERIAL PRIMARY KEY,
            ticket_no VARCHAR,
            journey_id INTEGER,
            booking_type VARCHAR,
            no_of_tickets INTEGER,
            status VARCHAR,
            amount NUMERIC,
            total_distance NUMERIC,
            total_time NUMERIC,
            total_stations VARCHAR,
            booking_time VARCHAR,
            valid_till VARCHAR,
            requested_from VARCHAR,
            trip_pass_id VARCHAR,
            created_at VARCHAR,
            updated_at VARCHAR,
            file_source VARCHAR
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_stg_mob_mc3_tno ON stg_mobile_metroconnect3(ticket_no);",
        "CREATE INDEX IF NOT EXISTS idx_stg_mob_mc3_filesrc ON stg_mobile_metroconnect3(file_source);",

        # 3. Mobile ONDC Staging
        """
        CREATE TABLE IF NOT EXISTS stg_mobile_ondc (
            id SERIAL PRIMARY KEY,
            order_id VARCHAR,
            date VARCHAR,
            transaction_id VARCHAR,
            buyer VARCHAR,
            number_of_tickets INTEGER,
            price_rs NUMERIC,
            status VARCHAR,
            start_station VARCHAR,
            end_station VARCHAR,
            refund_amount NUMERIC,
            file_source VARCHAR
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_stg_mob_ondc_ord ON stg_mobile_ondc(order_id);",
        "CREATE INDEX IF NOT EXISTS idx_stg_mob_ondc_filesrc ON stg_mobile_ondc(file_source);",

        # 4. Payment Gateway Staging
        """
        CREATE TABLE IF NOT EXISTS stg_pg_transactions (
            id SERIAL PRIMARY KEY,
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
            date_of_txn VARCHAR,
            settlement_date VARCHAR,
            gross_amount NUMERIC,
            charges NUMERIC,
            gst NUMERIC,
            net_amount NUMERIC,
            refund_id VARCHAR,
            refund_date VARCHAR,
            refund_amount NUMERIC,
            sub_txn_id VARCHAR,
            transaction_type VARCHAR, -- 'SETTLED' or 'REFUND'
            app_source VARCHAR,         -- 'MetroConnect3' or 'MumbaiOne'
            file_source VARCHAR
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_stg_pg_pgi_ref ON stg_pg_transactions(pgi_ref_no);",
        "CREATE INDEX IF NOT EXISTS idx_stg_pg_ref_1 ON stg_pg_transactions(ref_1);",
        "CREATE INDEX IF NOT EXISTS idx_stg_pg_type_src ON stg_pg_transactions(transaction_type, app_source);",
        "CREATE INDEX IF NOT EXISTS idx_stg_pg_filesrc ON stg_pg_transactions(file_source);",

        # 5. AFC Staging
        """
        CREATE TABLE IF NOT EXISTS stg_afc_transactions (
            id SERIAL PRIMARY KEY,
            s_no INTEGER,
            date VARCHAR,
            pass_name VARCHAR,
            operator_name VARCHAR,
            order_id VARCHAR,
            ms_qr_no VARCHAR,
            source_stn VARCHAR,
            destination_stn VARCHAR,
            slave_qr_no VARCHAR,
            units INTEGER,
            total_price NUMERIC,
            file_source VARCHAR
        );
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

        # 7. Reconciliation Results Table
        """
        CREATE TABLE IF NOT EXISTS reconciliation_results (
            id SERIAL PRIMARY KEY,
            app_source VARCHAR,
            order_id VARCHAR,
            ticket_no VARCHAR,
            pg_ref_no VARCHAR,
            amount NUMERIC,
            transaction_time VARCHAR,
            recon_status VARCHAR,
            notes VARCHAR,
            data_sources VARCHAR,
            reconciled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_recon_res_status ON reconciliation_results(recon_status);",
        "CREATE INDEX IF NOT EXISTS idx_recon_res_app ON reconciliation_results(app_source);",
        "CREATE INDEX IF NOT EXISTS idx_recon_res_ord_tkt ON reconciliation_results(order_id, ticket_no);",
        # Migration: add data_sources column to existing DBs
        "ALTER TABLE reconciliation_results ADD COLUMN IF NOT EXISTS data_sources VARCHAR;",
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
        # Convert all staging tables to UNLOGGED for massive insertion speedup (WAL bypass)
        "ALTER TABLE stg_mobile_mumbaione SET UNLOGGED;",
        "ALTER TABLE stg_mobile_metroconnect3 SET UNLOGGED;",
        "ALTER TABLE stg_mobile_ondc SET UNLOGGED;",
        "ALTER TABLE stg_pg_transactions SET UNLOGGED;",
        "ALTER TABLE stg_afc_transactions SET UNLOGGED;"
    ]

    with engine.begin() as connection:
        print("Executing DDL statements to set up tables and indices...")
        for stmt in ddl_statements:
            connection.execute(text(stmt))
        print("All tables and indices verified successfully.")

def bulk_insert_df(table_name: str, df, truncate: bool = False):
    """
    Ultra-Performance concurrency-safe bulk insert of a pandas DataFrame into a specified table.
    Bypasses standard insert overhead:
    1. Bypasses WAL overhead using PostgreSQL UNLOGGED tables defined in DDL.
    2. Streams raw TSV directly into PostgreSQL using copy_expert (zero SQL planning).
    3. Keeps staging indexes active to prevent AccessExclusiveLock starvations/deadlocks,
       maintaining 100% database concurrency read/write compatibility.
    """
    import io
    import csv

    if df.empty:
        return 0

    columns = list(df.columns)
    
    # 1. Fast TSV serialization in Pandas (minimal string escaping overhead, writes NaNs as \N)
    buffer = io.StringIO()
    df.to_csv(buffer, sep='\t', index=False, header=False, na_rep='\\N', quoting=csv.QUOTE_MINIMAL)
    buffer.seek(0)
    
    copy_query = f"COPY {table_name} ({','.join(columns)}) FROM STDIN WITH (FORMAT CSV, DELIMITER '\t', NULL '\\N')"

    # 2. Establish direct connection using settings DATABASE_URL
    conn = psycopg2.connect(settings.DATABASE_URL)
    try:
        with conn:
            with conn.cursor() as cur:
                # Session tuning for ultra-high performance writes
                cur.execute("SET synchronous_commit = OFF;")
                cur.execute("SET work_mem = '256MB';")
                
                if truncate:
                    print(f"Truncating table {table_name}...")
                    cur.execute(f"TRUNCATE TABLE {table_name} CASCADE;")
                
                # Stream CSV/TSV directly into PostgreSQL using copy_expert
                print(f"Bulk copy streaming {len(df):,} records into {table_name}...")
                cur.copy_expert(copy_query, buffer)
                
        # Commit the transaction block
        conn.commit()
        return len(df)
    finally:
        conn.close()
