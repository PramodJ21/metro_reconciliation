import os
import pandas as pd
import numpy as np

def parse_mobile_mumbaione(path: str) -> pd.DataFrame:
    """
    Parses Mobile MumbaiOne Excel file.
    Skips the metadata rows by finding the row starting with 'Ticket Number'.
    """
    print(f"Parsing Mobile MumbaiOne file: {path}")
    
    # Read without header to find where 'Ticket Number' starts
    try:
        try:
            df_raw = pd.read_excel(path, header=None, engine='calamine')
        except Exception:
            df_raw = pd.read_excel(path, header=None)
    except Exception as se:
        raise ValueError(f"Failed to read spreadsheet. Ensure you uploaded a valid Excel file. Details: {se}")

    header_row_idx = None
    for idx, row in df_raw.iterrows():
        if len(row) > 0 and row.iloc[0] == "Ticket Number":
            header_row_idx = idx
            break

    if header_row_idx is None:
        raise ValueError("Wrong file headers. Could not find critical header row starting with 'Ticket Number' in Mobile MumbaiOne sheet.")

    print(f"Found header row at index: {header_row_idx}")
    
    # Read again skipping the rows before header_row_idx
    try:
        df = pd.read_excel(path, skiprows=header_row_idx, engine='calamine')
    except Exception:
        df = pd.read_excel(path, skiprows=header_row_idx)

    # Rename columns to match database schema
    column_mapping = {
        'Ticket Number': 'ticket_number',
        'PG Reference No': 'pg_reference_no',
        'Mumbai One': 'mumbai_one_id',
        'Source Station': 'source_station',
        'Destination Station': 'destination_station',
        'Transportation Mode': 'transportation_mode',
        'PTO Name': 'pto_name',
        'Service Type': 'service_type',
        'Passenger Type': 'passenger_type',
        'No. of Passenger': 'no_of_passenger',
        'Payment Amount': 'payment_amount',
        'Ticket Type': 'ticket_type',
        'Transaction Id': 'transaction_id',
        'Transaction Date & Time': 'transaction_date_time',
        'User Email ID': 'user_email_id',
        'User Mobile No.': 'user_mobile_no',
        'App Environment': 'app_environment',
        'Payment Status': 'payment_status',
        'Ticket Status': 'ticket_status'
    }
    
    df = df.rename(columns=column_mapping)
    
    # Check if we have key columns mapped
    if 'ticket_number' not in df.columns or 'pg_reference_no' not in df.columns:
        raise ValueError("Missing critical columns ('Ticket Number' or 'PG Reference No') in Mobile MumbaiOne sheet. Ensure you uploaded the correct file.")
        
    # Filter to only keep columns that are in our mapping
    available_cols = [c for c in column_mapping.values() if c in df.columns]
    df = df[available_cols]

    # Convert numeric fields
    if 'no_of_passenger' in df.columns:
        df['no_of_passenger'] = pd.to_numeric(df['no_of_passenger'], errors='coerce').fillna(0).astype(int)
    if 'payment_amount' in df.columns:
        df['payment_amount'] = pd.to_numeric(df['payment_amount'], errors='coerce').fillna(0.0)

    # Clean string data — convert 'nan', 'None', '' to Python None for SQL NULL
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].map(lambda x: None if x.lower() in ('nan', 'none', '') else x)

    # Drop rows where the primary dedup key is null (junk/header/footer rows)
    df = df.dropna(subset=['pg_reference_no'])

    return df

def parse_mobile_metroconnect3(path: str) -> pd.DataFrame:
    """
    Parses Mobile MetroConnect3 CSV file.
    Handles large files.
    """
    print(f"Parsing Mobile MetroConnect3 CSV file: {path}")
    
    try:
        df = pd.read_csv(path)
    except Exception as se:
        raise ValueError(f"Failed to read CSV spreadsheet. Ensure you uploaded a valid CSV file. Details: {se}")

    # Check for critical columns
    if not any(col in df.columns for col in ['ticket_no', 'journey_id', 'amount']):
        raise ValueError("Wrong CSV structure. Missing critical columns (like 'ticket_no', 'journey_id', 'amount'). Ensure you uploaded the correct Mobile MetroConnect3 CSV.")

    expected_cols = [
        'ticket_no', 'journey_id', 'booking_type', 'no_of_tickets', 'status', 'amount', 
        'total_distance', 'total_time', 'total_stations', 'booking_time', 'valid_till', 
        'requested_from', 'trip_pass_id', 'created_at', 'updated_at'
    ]
    
    df = df[[c for c in expected_cols if c in df.columns]]

    # Type Conversions
    if 'journey_id' in df.columns:
        df['journey_id'] = pd.to_numeric(df['journey_id'], errors='coerce').fillna(0).astype(int)
    if 'no_of_tickets' in df.columns:
        df['no_of_tickets'] = pd.to_numeric(df['no_of_tickets'], errors='coerce').fillna(0).astype(int)
    if 'amount' in df.columns:
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
    if 'total_distance' in df.columns:
        df['total_distance'] = pd.to_numeric(df['total_distance'], errors='coerce').fillna(0.0)
    if 'total_time' in df.columns:
        df['total_time'] = pd.to_numeric(df['total_time'], errors='coerce').fillna(0.0)

    # Clean string data — convert 'nan', 'None', '' to Python None for SQL NULL
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].map(lambda x: None if x.lower() in ('nan', 'none', '') else x)

    # Drop rows where the primary dedup key is null
    df = df.dropna(subset=['ticket_no'])

    return df

def parse_mobile_ondc(path: str) -> pd.DataFrame:
    """
    Parses Mobile ONDC Excel file.
    """
    print(f"Parsing Mobile ONDC file: {path}")
    
    try:
        try:
            df = pd.read_excel(path, sheet_name='Orders', engine='calamine')
        except Exception:
            df = pd.read_excel(path, sheet_name='Orders')
    except Exception as se:
        raise ValueError(f"Could not find sheet named 'Orders' in spreadsheet. Ensure you uploaded the correct ONDC orders report. Details: {se}")

    column_mapping = {
        'OrderId': 'order_id',
        'Date': 'date',
        'TransactionId': 'transaction_id',
        'Buyer': 'buyer',
        'NumberOfTickets': 'number_of_tickets',
        'Price_Rs': 'price_rs',
        'Status': 'status',
        'StartStation': 'start_station',
        'EndStation': 'end_station',
        'RefundAmount': 'refund_amount'
    }

    df = df.rename(columns=column_mapping)
    
    # Check for critical columns
    if 'order_id' not in df.columns or 'price_rs' not in df.columns:
        raise ValueError("Missing critical columns ('OrderId' or 'Price_Rs') in ONDC Orders sheet. Ensure you uploaded the correct ONDC orders report.")

    available_cols = [c for c in column_mapping.values() if c in df.columns]
    df = df[available_cols]

    if 'number_of_tickets' in df.columns:
        df['number_of_tickets'] = pd.to_numeric(df['number_of_tickets'], errors='coerce').fillna(0).astype(int)
    if 'price_rs' in df.columns:
        df['price_rs'] = pd.to_numeric(df['price_rs'], errors='coerce').fillna(0.0)
    if 'refund_amount' in df.columns:
        df['refund_amount'] = pd.to_numeric(df['refund_amount'], errors='coerce').fillna(0.0)

    # Clean string data — convert 'nan', 'None', '' to Python None for SQL NULL
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].map(lambda x: None if x.lower() in ('nan', 'none', '') else x)

    # Drop rows where the primary dedup key is null
    df = df.dropna(subset=['order_id'])

    return df

def parse_afc(path: str, app_name: str) -> pd.DataFrame:
    """
    Parses AFC Gate Transaction Excel file (MumbaiOne or ONDC).
    """
    print(f"Parsing AFC file ({app_name}): {path}")
    
    try:
        try:
            df = pd.read_excel(path, sheet_name='MQR Report', engine='calamine')
        except Exception:
            df = pd.read_excel(path, sheet_name='MQR Report')
    except Exception as se:
        raise ValueError(f"Could not find sheet named 'MQR Report' in spreadsheet. Ensure you uploaded the correct AFC gates spreadsheet. Details: {se}")

    column_mapping = {
        'S No': 's_no',
        'Date': 'date',
        'Pass Name': 'pass_name',
        'Operator Name': 'operator_name',
        'Order ID': 'order_id',
        'MS QR No': 'ms_qr_no',
        'Source Stn': 'source_stn',
        'Destination Stn': 'destination_stn',
        'Slave Qr No': 'slave_qr_no',
        'Units': 'units',
        'Total Price': 'total_price'
    }

    df = df.rename(columns=column_mapping)
    
    # Check for critical columns
    if 'order_id' not in df.columns or 'slave_qr_no' not in df.columns:
        raise ValueError("Missing critical columns ('Order ID' or 'Slave Qr No') in AFC gates spreadsheet. Ensure you uploaded the correct AFC report.")

    available_cols = [c for c in column_mapping.values() if c in df.columns]
    df = df[available_cols]

    if 's_no' in df.columns:
        df['s_no'] = pd.to_numeric(df['s_no'], errors='coerce').fillna(0).astype(int)
    if 'units' in df.columns:
        df['units'] = pd.to_numeric(df['units'], errors='coerce').fillna(0).astype(int)
    if 'total_price' in df.columns:
        df['total_price'] = pd.to_numeric(df['total_price'], errors='coerce').fillna(0.0)

    # Clean string data — convert 'nan', 'None', '' to Python None for SQL NULL
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].map(lambda x: None if x.lower() in ('nan', 'none', '') else x)

    # Drop rows where the primary dedup key is null (header/footer rows)
    df = df.dropna(subset=['slave_qr_no'])

    return df

def parse_payment_gateway(path: str, app_source: str) -> pd.DataFrame:
    """
    Parses vertically stacked Payment Gateway excel sheet.
    Splits it into settled and refund transactions.
    """
    print(f"Parsing PG file ({app_source}): {path}")
    
    try:
        try:
            df_raw = pd.read_excel(path, sheet_name='Transaction Records', header=None, engine='calamine')
        except Exception:
            df_raw = pd.read_excel(path, sheet_name='Transaction Records', header=None)
    except Exception as se:
        raise ValueError(f"Could not find sheet named 'Transaction Records' in PG spreadsheet. Ensure you uploaded the correct Payment Gateway report. Details: {se}")

    settled_start_idx = None
    refund_start_idx = None
    chargeback_start_idx = None

    for idx, row in df_raw.iterrows():
        val = str(row.iloc[0]).strip().upper() if pd.notna(row.iloc[0]) else ""
        if val == "SETTLED TRANSACTIONS":
            settled_start_idx = idx
        elif val == "REFUND TRANSACTIONS":
            refund_start_idx = idx
        elif val == "CHARGEBACK TRANSACTIONS":
            chargeback_start_idx = idx

    print(f"Markers - Settled Row: {settled_start_idx}, Refund Row: {refund_start_idx}, Chargeback Row: {chargeback_start_idx}")

    if settled_start_idx is None and refund_start_idx is None:
        raise ValueError("Wrong PG spreadsheet. Could not locate 'SETTLED TRANSACTIONS' or 'REFUND TRANSACTIONS' sections. Ensure you uploaded the correct PG settlement spreadsheet.")

    records_to_load = []

    # 1. Parse Settled Transactions Section
    if settled_start_idx is not None:
        headers_raw = df_raw.iloc[settled_start_idx + 1].tolist()
        headers = [str(h).strip() if pd.notna(h) else f"Col_{i}" for i, h in enumerate(headers_raw)]
        
        end_settled = refund_start_idx if refund_start_idx is not None else len(df_raw)
        settled_rows = df_raw.iloc[settled_start_idx + 2 : end_settled].dropna(how='all')
        
        settled_df = pd.DataFrame(settled_rows.values, columns=headers)
        if 'Biller Id' in settled_df.columns:
            settled_df = settled_df[settled_df['Biller Id'].notna() & (settled_df['Biller Id'].astype(str).str.strip() != "")]
            
        print(f"Parsed {len(settled_df)} Settled Transactions from PG Excel.")
        
        # Check critical PG columns
        if 'PGI Ref. No.' not in settled_df.columns or 'Biller Id' not in settled_df.columns:
            raise ValueError("Missing critical columns ('PGI Ref. No.' or 'Biller Id') in Settled transactions section of PG report.")
        
        # Map settled df columns to DB schema fields
        for _, row in settled_df.iterrows():
            rec = {
                'biller_id': str(row.get('Biller Id', '')).strip(),
                'bank_id': str(row.get('Bank Id', '')).strip(),
                'bank_ref_no': str(row.get('Bank Ref. No.', '')).strip(),
                'pgi_ref_no': str(row.get('PGI Ref. No.', '')).strip(),
                'ref_1': str(row.get('Ref. 1', '')).strip(),
                'ref_2': str(row.get('Ref. 2', '')).strip() if 'Ref. 2' in row else None,
                'ref_3': str(row.get('Ref. 3', '')).strip() if 'Ref. 3' in row else None,
                'ref_4': str(row.get('Ref. 4', '')).strip() if 'Ref. 4' in row else None,
                'ref_5': str(row.get('Ref. 5', '')).strip() if 'Ref. 5' in row else None,
                'ref_6': str(row.get('Ref. 6', '')).strip() if 'Ref. 6' in row else None,
                'ref_7': str(row.get('Ref. 7', '')).strip() if 'Ref. 7' in row else None,
                'ref_8': str(row.get('Ref. 8', '')).strip() if 'Ref. 8' in row else None,
                'filler': str(row.get('Filler', '')).strip() if 'Filler' in row else None,
                'date_of_txn': str(row.get('Date of Txn', '')).strip(),
                'settlement_date': str(row.get('Settlement Date', '')).strip(),
                'gross_amount': pd.to_numeric(row.get('Gross Amount(Rs.Ps)', 0.0), errors='coerce'),
                'charges': pd.to_numeric(row.get('Charges (Rs.Ps)', 0.0), errors='coerce'),
                'gst': pd.to_numeric(row.get('GST (Rs Ps)', 0.0), errors='coerce'),
                'net_amount': pd.to_numeric(row.get('Net Amount(Rs.Ps)', 0.0), errors='coerce'),
                'sub_txn_id': str(row.get('Sub Txn Id', '')).strip() if 'Sub Txn Id' in row else None,
                'refund_id': None,
                'refund_date': None,
                'refund_amount': 0.0,
                'transaction_type': 'SETTLED',
                'app_source': app_source
            }
            records_to_load.append(rec)

    # 2. Parse Refund Transactions Section
    if refund_start_idx is not None:
        headers_raw = df_raw.iloc[refund_start_idx + 1].tolist()
        headers = [str(h).strip() if pd.notna(h) else f"Col_{i}" for i, h in enumerate(headers_raw)]
        
        end_refund = chargeback_start_idx if chargeback_start_idx is not None else len(df_raw)
        for r_idx in range(refund_start_idx + 2, len(df_raw)):
            val = str(df_raw.iloc[r_idx, 0]).strip()
            if "Net Credit" in val or "Settled Transactions --" in val:
                end_refund = r_idx
                break
                
        refund_rows = df_raw.iloc[refund_start_idx + 2 : end_refund].dropna(how='all')
        refund_df = pd.DataFrame(refund_rows.values, columns=headers)
        
        if 'Biller Id' in refund_df.columns:
            refund_df = refund_df[refund_df['Biller Id'].notna() & (refund_df['Biller Id'].astype(str).str.strip() != "")]
            
        print(f"Parsed {len(refund_df)} Refund Transactions from PG Excel.")
        
        # Map refund df columns to DB schema fields
        for _, row in refund_df.iterrows():
            rec = {
                'biller_id': str(row.get('Biller Id', '')).strip(),
                'bank_id': str(row.get('Bank Id', '')).strip(),
                'bank_ref_no': str(row.get('Bank Ref. No.', '')).strip(),
                'pgi_ref_no': str(row.get('PGI Ref. No.', '')).strip(),
                'ref_1': str(row.get('Ref. 1', '')).strip(),
                'ref_2': str(row.get('Ref. 2', '')).strip() if 'Ref. 2' in row else None,
                'ref_3': str(row.get('Ref. 3', '')).strip() if 'Ref. 3' in row else None,
                'ref_4': str(row.get('Ref. 4', '')).strip() if 'Ref. 4' in row else None,
                'ref_5': str(row.get('Ref. 5', '')).strip() if 'Ref. 5' in row else None,
                'ref_6': str(row.get('Ref. 6', '')).strip() if 'Ref. 6' in row else None,
                'ref_7': str(row.get('Ref. 7', '')).strip() if 'Ref. 7' in row else None,
                'ref_8': str(row.get('Ref. 8', '')).strip() if 'Ref. 8' in row else None,
                'filler': str(row.get('Filler', '')).strip() if 'Filler' in row else None,
                'date_of_txn': str(row.get('Date of Transaction', row.get('Date of Txn', ''))).strip(),
                'settlement_date': str(row.get('Settlement Date', '')).strip(),
                'gross_amount': pd.to_numeric(row.get('Gross Amount(Rs.Ps)', 0.0), errors='coerce'),
                'charges': 0.0,
                'gst': 0.0,
                'net_amount': 0.0,
                'sub_txn_id': str(row.get('Sub Txn Id', '')).strip() if 'Sub Txn Id' in row else None,
                'refund_id': str(row.get('Refund ID', '')).strip(),
                'refund_date': str(row.get('Refund Date', '')).strip(),
                'refund_amount': pd.to_numeric(row.get('Refund Amount (Rs. Ps.)', 0.0), errors='coerce'),
                'transaction_type': 'REFUND',
                'app_source': app_source
            }
            records_to_load.append(rec)

    # Convert results list to DataFrame
    if len(records_to_load) == 0:
        return pd.DataFrame()
        
    df = pd.DataFrame(records_to_load)
    
    # Clean string data — convert 'nan', 'None', '' to Python None for proper SQL NULL
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].map(lambda x: None if x.lower() in ('nan', 'none', '') else x)

    # Drop rows where pgi_ref_no is null — these are footer/summary rows, not real transactions
    df = df.dropna(subset=['pgi_ref_no'])

    return df
