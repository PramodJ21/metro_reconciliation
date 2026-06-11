import io
import pandas as pd
from typing import Union, Optional, List
from app.utils import safe_read_excel, _clean_str_cols, to_datetime_robust

# ---------------------------------------------------------------------------
# Parsers (path_or_buffer = str path OR BytesIO / file-like object)
# ---------------------------------------------------------------------------

def parse_mobile_mumbaione(path_or_buffer: Union[str, io.BytesIO]) -> pd.DataFrame:
    """
    Parses Mobile MumbaiOne Excel file.
    Skips metadata rows by finding the row starting with 'Ticket Number'.
    Accepts a file path (str) or an in-memory BytesIO buffer.
    """
    src = path_or_buffer
    print(f"Parsing Mobile MumbaiOne file: {getattr(src, 'name', str(src))[:80]}")

    # Read without header to locate the real header row in memory (Single-Read optimization)
    df_raw = safe_read_excel(src, header=None)

    # Vectorized / generator-based header locator
    header_row_idx = next(
        (i for i, row in df_raw.iterrows() if len(row) > 0 and row.iloc[0] == "Ticket Number"),
        None
    )

    if header_row_idx is None:
        raise ValueError(
            "Wrong file headers. Could not find critical header row starting with "
            "'Ticket Number' in Mobile MumbaiOne sheet."
        )

    # Slice in memory — no second disk/buffer read (Single-Read optimization)
    df = df_raw.iloc[header_row_idx + 1:].copy()
    df.columns = df_raw.iloc[header_row_idx].values
    df = df.reset_index(drop=True)

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

    if 'ticket_number' not in df.columns or 'pg_reference_no' not in df.columns:
        raise ValueError(
            "Missing critical columns ('Ticket Number' or 'PG Reference No') in Mobile MumbaiOne sheet. "
            "Ensure you uploaded the correct file."
        )

    available_cols = [c for c in column_mapping.values() if c in df.columns]
    df = df[available_cols]

    if 'no_of_passenger' in df.columns:
        df['no_of_passenger'] = pd.to_numeric(df['no_of_passenger'], errors='coerce').fillna(0).astype(int)
    if 'payment_amount' in df.columns:
        df['payment_amount'] = pd.to_numeric(df['payment_amount'], errors='coerce').fillna(0.0)
    if 'transaction_date_time' in df.columns:
        df['transaction_date_time'] = to_datetime_robust(df['transaction_date_time'])

    df = _clean_str_cols(df)
    _before = len(df)
    df = df.dropna(subset=['pg_reference_no'])
    _trash = _before - len(df)
    if _trash > 0:
        print(f"[TRASH] MumbaiOne mobile: dropped {_trash} row(s) with null/empty pg_reference_no (header/footer junk).")
    print(f"[PARSE] MumbaiOne mobile: {len(df)} clean rows after trash removal (was {_before}).")
    return df


def parse_mobile_metroconnect3(path_or_buffer: Union[str, io.BytesIO]) -> pd.DataFrame:
    """
    Parses Mobile MetroConnect3 CSV file.
    Accepts a file path (str) or an in-memory BytesIO buffer.
    """
    print(f"Parsing Mobile MetroConnect3 CSV file: {getattr(path_or_buffer, 'name', str(path_or_buffer))[:80]}")

    try:
        df = pd.read_csv(path_or_buffer)
    except Exception as se:
        raise ValueError(f"Failed to read CSV spreadsheet. Ensure you uploaded a valid CSV file. Details: {se}")

    if not any(col in df.columns for col in ['ticket_no', 'journey_id', 'amount']):
        raise ValueError(
            "Wrong CSV structure. Missing critical columns (like 'ticket_no', 'journey_id', 'amount'). "
            "Ensure you uploaded the correct Mobile MetroConnect3 CSV."
        )

    expected_cols = [
        'ticket_no', 'journey_id', 'booking_type', 'no_of_tickets', 'status', 'amount',
        'total_distance', 'total_time', 'total_stations', 'booking_time', 'valid_till',
        'requested_from', 'trip_pass_id', 'created_at', 'updated_at'
    ]
    df = df[[c for c in expected_cols if c in df.columns]]

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

    # Convert all datetime fields
    for col in ['booking_time', 'valid_till', 'created_at', 'updated_at']:
        if col in df.columns:
            df[col] = to_datetime_robust(df[col])

    df = _clean_str_cols(df)
    _before = len(df)
    df = df.dropna(subset=['ticket_no'])
    _trash = _before - len(df)
    if _trash > 0:
        print(f"[TRASH] MetroConnect3 mobile: dropped {_trash} row(s) with null/empty ticket_no (header/footer junk).")
    print(f"[PARSE] MetroConnect3 mobile: {len(df)} clean rows after trash removal (was {_before}).")
    return df


def parse_mobile_ondc(path_or_buffer: Union[str, io.BytesIO]) -> pd.DataFrame:
    """
    Parses Mobile ONDC Excel file.
    Accepts a file path (str) or an in-memory BytesIO buffer.
    """
    print(f"Parsing Mobile ONDC file: {getattr(path_or_buffer, 'name', str(path_or_buffer))[:80]}")

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

    try:
        df = safe_read_excel(path_or_buffer, sheet_name='Orders', usecols=list(column_mapping.keys()))
    except Exception as se:
        raise ValueError(
            f"Could not find sheet named 'Orders' in spreadsheet. "
            f"Ensure you uploaded the correct ONDC orders report. Details: {se}"
        )

    df = df.rename(columns=column_mapping)

    if 'order_id' not in df.columns or 'price_rs' not in df.columns:
        raise ValueError(
            "Missing critical columns ('OrderId' or 'Price_Rs') in ONDC Orders sheet. "
            "Ensure you uploaded the correct ONDC orders report."
        )

    available_cols = [c for c in column_mapping.values() if c in df.columns]
    df = df[available_cols]

    if 'number_of_tickets' in df.columns:
        df['number_of_tickets'] = pd.to_numeric(df['number_of_tickets'], errors='coerce').fillna(0).astype(int)
    if 'price_rs' in df.columns:
        df['price_rs'] = pd.to_numeric(df['price_rs'], errors='coerce').fillna(0.0)
    if 'refund_amount' in df.columns:
        df['refund_amount'] = pd.to_numeric(df['refund_amount'], errors='coerce').fillna(0.0)
    if 'date' in df.columns:
        df['date'] = to_datetime_robust(df['date'])

    df = _clean_str_cols(df)
    _before = len(df)
    df = df.dropna(subset=['order_id'])
    _trash = _before - len(df)
    if _trash > 0:
        print(f"[TRASH] ONDC mobile: dropped {_trash} row(s) with null/empty order_id (header/footer junk).")
    print(f"[PARSE] ONDC mobile: {len(df)} clean rows after trash removal (was {_before}).")
    return df


def parse_afc(path_or_buffer: Union[str, io.BytesIO], app_name: str) -> pd.DataFrame:
    """
    Parses AFC Gate Transaction Excel file (MumbaiOne or ONDC).
    Accepts a file path (str) or an in-memory BytesIO buffer.
    """
    print(f"Parsing AFC file ({app_name}): {getattr(path_or_buffer, 'name', str(path_or_buffer))[:80]}")

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

    try:
        df = safe_read_excel(path_or_buffer, sheet_name='MQR Report', usecols=list(column_mapping.keys()))
    except Exception as se:
        raise ValueError(
            f"Could not find sheet named 'MQR Report' in spreadsheet. "
            f"Ensure you uploaded the correct AFC gates spreadsheet. Details: {se}"
        )

    df = df.rename(columns=column_mapping)

    if 'order_id' not in df.columns or 'slave_qr_no' not in df.columns:
        raise ValueError(
            "Missing critical columns ('Order ID' or 'Slave Qr No') in AFC gates spreadsheet. "
            "Ensure you uploaded the correct AFC report."
        )

    available_cols = [c for c in column_mapping.values() if c in df.columns]
    df = df[available_cols]

    if 's_no' in df.columns:
        df['s_no'] = pd.to_numeric(df['s_no'], errors='coerce').fillna(0).astype(int)
    if 'units' in df.columns:
        df['units'] = pd.to_numeric(df['units'], errors='coerce').fillna(0).astype(int)
    if 'total_price' in df.columns:
        df['total_price'] = pd.to_numeric(df['total_price'], errors='coerce').fillna(0.0)
    if 'date' in df.columns:
        df['date'] = to_datetime_robust(df['date'])

    df = _clean_str_cols(df)
    _before = len(df)
    df = df.dropna(subset=['slave_qr_no'])
    _trash = _before - len(df)
    if _trash > 0:
        print(f"[TRASH] AFC ({app_name}): dropped {_trash} row(s) with null/empty slave_qr_no (header/footer junk).")
    print(f"[PARSE] AFC ({app_name}): {len(df)} clean rows after trash removal (was {_before}).")
    return df


# ---------------------------------------------------------------------------
# Payment Gateway Parser & Helper Subroutines
# ---------------------------------------------------------------------------

def _get_str_series(df: pd.DataFrame, key: str, optional: bool = False) -> pd.Series:
    """Helper to extract and clean string series from dataframe columns safely"""
    if optional and key not in df.columns:
        return pd.Series('', index=df.index)
    if key in df.columns:
        return df[key].fillna('').astype(str).str.strip()
    return pd.Series('', index=df.index)


def _get_num_series(df: pd.DataFrame, key: str) -> pd.Series:
    """Helper to extract and clean numeric series from dataframe columns safely"""
    if key in df.columns:
        return pd.to_numeric(df[key], errors='coerce').fillna(0.0)
    return pd.Series(0.0, index=df.index)


def _parse_settled_section(
    df_raw: pd.DataFrame, 
    settled_start_idx: int, 
    refund_start_idx: Optional[int], 
    app_source: str
) -> pd.DataFrame:
    """Parses the SETTLED TRANSACTIONS section from the PG Excel sheet"""
    headers_raw = df_raw.iloc[settled_start_idx + 1].tolist()
    headers = [str(h).strip() if pd.notna(h) else f"Col_{i}" for i, h in enumerate(headers_raw)]

    end_settled = refund_start_idx if refund_start_idx is not None else len(df_raw)
    settled_rows = df_raw.iloc[settled_start_idx + 2 : end_settled].dropna(how='all')
    settled_df = pd.DataFrame(settled_rows.values, columns=headers)

    if 'Biller Id' in settled_df.columns:
        settled_df = settled_df[
            settled_df['Biller Id'].notna() &
            (settled_df['Biller Id'].astype(str).str.strip() != "")
        ]

    print(f"Parsed {len(settled_df)} Settled Transactions from PG Excel.")

    if 'PGI Ref. No.' not in settled_df.columns or 'Biller Id' not in settled_df.columns:
        raise ValueError(
            "Missing critical columns ('PGI Ref. No.' or 'Biller Id') in "
            "Settled transactions section of PG report."
        )

    if settled_df.empty:
        return pd.DataFrame()

    settled_out = pd.DataFrame(index=settled_df.index)
    settled_out['biller_id'] = _get_str_series(settled_df, 'Biller Id')
    settled_out['bank_id'] = _get_str_series(settled_df, 'Bank Id')
    settled_out['bank_ref_no'] = _get_str_series(settled_df, 'Bank Ref. No.')
    settled_out['pgi_ref_no'] = _get_str_series(settled_df, 'PGI Ref. No.')
    settled_out['ref_1'] = _get_str_series(settled_df, 'Ref. 1')
    settled_out['ref_2'] = _get_str_series(settled_df, 'Ref. 2', optional=True)
    settled_out['ref_3'] = _get_str_series(settled_df, 'Ref. 3', optional=True)
    settled_out['ref_4'] = _get_str_series(settled_df, 'Ref. 4', optional=True)
    settled_out['ref_5'] = _get_str_series(settled_df, 'Ref. 5', optional=True)
    settled_out['ref_6'] = _get_str_series(settled_df, 'Ref. 6', optional=True)
    settled_out['ref_7'] = _get_str_series(settled_df, 'Ref. 7', optional=True)
    settled_out['ref_8'] = _get_str_series(settled_df, 'Ref. 8', optional=True)
    settled_out['filler'] = _get_str_series(settled_df, 'Filler', optional=True)
    settled_out['date_of_txn'] = to_datetime_robust(_get_str_series(settled_df, 'Date of Txn'))
    settled_out['settlement_date'] = to_datetime_robust(_get_str_series(settled_df, 'Settlement Date'))
    
    settled_out['gross_amount'] = _get_num_series(settled_df, 'Gross Amount(Rs.Ps)')
    settled_out['charges'] = _get_num_series(settled_df, 'Charges (Rs.Ps)')
    settled_out['gst'] = _get_num_series(settled_df, 'GST (Rs Ps)')
    settled_out['net_amount'] = _get_num_series(settled_df, 'Net Amount(Rs.Ps)')
    
    settled_out['sub_txn_id'] = _get_str_series(settled_df, 'Sub Txn Id', optional=True)
    settled_out['refund_id'] = None
    settled_out['refund_date'] = None
    settled_out['refund_amount'] = 0.0
    settled_out['transaction_type'] = 'SETTLED'
    settled_out['app_source'] = app_source

    return settled_out


def _parse_refund_section(
    df_raw: pd.DataFrame, 
    refund_start_idx: int, 
    chargeback_start_idx: Optional[int], 
    first_col: pd.Series, 
    app_source: str
) -> pd.DataFrame:
    """Parses the REFUND TRANSACTIONS section from the PG Excel sheet"""
    headers_raw = df_raw.iloc[refund_start_idx + 1].tolist()
    headers = [str(h).strip() if pd.notna(h) else f"Col_{i}" for i, h in enumerate(headers_raw)]

    # Vectorized search for the refund section end marker
    tail_col = first_col.iloc[refund_start_idx + 2:]
    end_matches = tail_col[tail_col.str.contains("NET CREDIT|SETTLED TRANSACTIONS --", na=False)]
    end_refund = end_matches.index[0] if len(end_matches) else len(df_raw)
    if chargeback_start_idx is not None:
        end_refund = min(end_refund, chargeback_start_idx)

    refund_rows = df_raw.iloc[refund_start_idx + 2 : end_refund].dropna(how='all')
    refund_df = pd.DataFrame(refund_rows.values, columns=headers)

    if 'Biller Id' in refund_df.columns:
        refund_df = refund_df[
            refund_df['Biller Id'].notna() &
            (refund_df['Biller Id'].astype(str).str.strip() != "")
        ]

    print(f"Parsed {len(refund_df)} Refund Transactions from PG Excel.")

    if refund_df.empty:
        return pd.DataFrame()

    refund_out = pd.DataFrame(index=refund_df.index)
    refund_out['biller_id'] = _get_str_series(refund_df, 'Biller Id')
    refund_out['bank_id'] = _get_str_series(refund_df, 'Bank Id')
    refund_out['bank_ref_no'] = _get_str_series(refund_df, 'Bank Ref. No.')
    refund_out['pgi_ref_no'] = _get_str_series(refund_df, 'PGI Ref. No.')
    refund_out['ref_1'] = _get_str_series(refund_df, 'Ref. 1')
    refund_out['ref_2'] = _get_str_series(refund_df, 'Ref. 2', optional=True)
    refund_out['ref_3'] = _get_str_series(refund_df, 'Ref. 3', optional=True)
    refund_out['ref_4'] = _get_str_series(refund_df, 'Ref. 4', optional=True)
    refund_out['ref_5'] = _get_str_series(refund_df, 'Ref. 5', optional=True)
    refund_out['ref_6'] = _get_str_series(refund_df, 'Ref. 6', optional=True)
    refund_out['ref_7'] = _get_str_series(refund_df, 'Ref. 7', optional=True)
    refund_out['ref_8'] = _get_str_series(refund_df, 'Ref. 8', optional=True)
    refund_out['filler'] = _get_str_series(refund_df, 'Filler', optional=True)
    
    date_col = 'Date of Transaction' if 'Date of Transaction' in refund_df.columns else 'Date of Txn'
    refund_out['date_of_txn'] = to_datetime_robust(_get_str_series(refund_df, date_col))
    refund_out['settlement_date'] = to_datetime_robust(_get_str_series(refund_df, 'Settlement Date'))
    
    refund_out['gross_amount'] = _get_num_series(refund_df, 'Gross Amount(Rs.Ps)')
    refund_out['charges'] = 0.0
    refund_out['gst'] = 0.0
    refund_out['net_amount'] = 0.0
    
    refund_out['sub_txn_id'] = _get_str_series(refund_df, 'Sub Txn Id', optional=True)
    refund_out['refund_id'] = _get_str_series(refund_df, 'Refund ID')
    refund_out['refund_date'] = to_datetime_robust(_get_str_series(refund_df, 'Refund Date'))
    refund_out['refund_amount'] = _get_num_series(refund_df, 'Refund Amount (Rs. Ps.)')
    
    refund_out['transaction_type'] = 'REFUND'
    refund_out['app_source'] = app_source

    return refund_out


def parse_payment_gateway(path_or_buffer: Union[str, io.BytesIO], app_source: str) -> pd.DataFrame:
    """
    Parses vertically stacked Payment Gateway excel sheet.
    Splits it into settled and refund transactions.
    Accepts a file path (str) or an in-memory BytesIO buffer.
    """
    print(f"Parsing PG file ({app_source}): {getattr(path_or_buffer, 'name', str(path_or_buffer))[:80]}")

    try:
        df_raw = safe_read_excel(path_or_buffer, sheet_name='Transaction Records', header=None)
    except Exception as se:
        raise ValueError(
            f"Could not find sheet named 'Transaction Records' in PG spreadsheet. "
            f"Ensure you uploaded the correct Payment Gateway report. Details: {se}"
        )

    # Vectorized first column scan for section headers (C-speed in Pandas)
    first_col = df_raw.iloc[:, 0].fillna('').astype(str).str.strip().str.upper()

    settled_matches = first_col[first_col == "SETTLED TRANSACTIONS"].index
    refund_matches = first_col[first_col == "REFUND TRANSACTIONS"].index
    chargeback_matches = first_col[first_col == "CHARGEBACK TRANSACTIONS"].index

    settled_start_idx = settled_matches[0] if len(settled_matches) else None
    refund_start_idx = refund_matches[0] if len(refund_matches) else None
    chargeback_start_idx = chargeback_matches[0] if len(chargeback_matches) else None

    print(f"Markers — Settled: {settled_start_idx}, Refund: {refund_start_idx}, Chargeback: {chargeback_start_idx}")

    if settled_start_idx is None and refund_start_idx is None:
        raise ValueError(
            "Wrong PG spreadsheet. Could not locate 'SETTLED TRANSACTIONS' or 'REFUND TRANSACTIONS' sections. "
            "Ensure you uploaded the correct PG settlement spreadsheet."
        )

    dfs_to_concat = []

    # 1. Parse Settled Transactions
    if settled_start_idx is not None:
        settled_out = _parse_settled_section(df_raw, settled_start_idx, refund_start_idx, app_source)
        if not settled_out.empty:
            dfs_to_concat.append(settled_out)

    # 2. Parse Refund Transactions
    if refund_start_idx is not None:
        refund_out = _parse_refund_section(df_raw, refund_start_idx, chargeback_start_idx, first_col, app_source)
        if not refund_out.empty:
            dfs_to_concat.append(refund_out)

    if not dfs_to_concat:
        return pd.DataFrame()

    df = pd.concat(dfs_to_concat, ignore_index=True)
    df = _clean_str_cols(df)
    _before = len(df)

    # Identify and log trash rows before dropping them
    _trash_mask = df['pgi_ref_no'].isna()
    if _trash_mask.any():
        _trash_rows = df[_trash_mask]
        print(f"[TRASH] PG ({app_source}): {len(_trash_rows)} row(s) have null/empty pgi_ref_no and will be dropped:")
        for i, (_, tr) in enumerate(_trash_rows.iterrows()):
            biller = tr.get('biller_id', '')
            bank_ref = tr.get('bank_ref_no', '')
            ref1 = tr.get('ref_1', '')
            txn_type = tr.get('transaction_type', '')
            date = tr.get('date_of_txn', '')
            print(
                f"  [{i+1}] type={txn_type!r}  biller_id={biller!r}  "
                f"bank_ref_no={bank_ref!r}  ref_1={ref1!r}  date={date!r}"
            )

    df = df.dropna(subset=['pgi_ref_no'])
    _trash = _before - len(df)
    print(f"[PARSE] PG ({app_source}): {len(df)} clean rows after trash removal (was {_before}).")
    return df
