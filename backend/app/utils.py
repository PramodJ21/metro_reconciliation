import io
import csv
import pandas as pd
from typing import List, Union, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

def safe_read_excel(
    src: Union[str, io.BytesIO], 
    sheet_name: Optional[Union[str, int]] = None, 
    header: Optional[Union[int, List[int]]] = None, 
    usecols: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Reads an Excel spreadsheet safely.
    Attempts to use the high-performance 'calamine' engine first.
    If that fails, falls back to openpyxl/xlrd.
    """
    kwargs = {}
    if sheet_name is not None:
        kwargs['sheet_name'] = sheet_name
    if header is not None:
        kwargs['header'] = header
    if usecols is not None:
        kwargs['usecols'] = usecols

    try:
        return pd.read_excel(src, engine='calamine', **kwargs)
    except Exception as e:
        print(f"[WARN] calamine engine failed, falling back to openpyxl/xlrd. Details: {e}")
        if hasattr(src, 'seek'):
            src.seek(0)
        try:
            return pd.read_excel(src, **kwargs)
        except Exception as se:
            raise ValueError(f"Failed to read spreadsheet. Ensure the file format is valid. Details: {se}")

def _clean_str_cols(df: pd.DataFrame) -> pd.DataFrame:
    """
    Vectorised string-column cleaner.
    Strips whitespace, then converts 'nan' / 'none' / '' -> None (SQL NULL).
    """
    str_cols = df.select_dtypes(include=['object']).columns
    if len(str_cols) == 0:
        return df

    for col in str_cols:
        if df[col].isna().all():
            continue
        s = df[col].astype(str).str.strip()
        df[col] = s.where(~s.str.lower().isin({'nan', 'none', ''}), other=None)
    return df

def to_datetime_robust(series: pd.Series) -> pd.Series:
    """
    Robustly parses a Series of date/time strings into a Series of datetime objects.
    Vectorized string cleaning and Millisecond format priority for ultra-high performance.
    """
    if series.empty:
        return series
        
    if pd.api.types.is_datetime64_any_dtype(series):
        return series

    # Vectorized check for nan-like values
    s = series.astype(str).str.strip()
    null_mask = series.isna() | s.str.lower().isin({'nan', 'none', '', 'nat'})
    
    # Vectorized clean for lacking date component (e.g. MM:SS.f or HH:MM:SS.f)
    no_date_mask = s.str.contains(':', regex=False) & ~s.str.contains('-', regex=False) & ~s.str.contains('/', regex=False) & ~null_mask
    
    if no_date_mask.any():
        # Count parts by colons
        parts_count = s[no_date_mask].str.count(':') + 1
        
        # 2 parts: MM:SS.f -> prepend '2026-04-01 00:'
        mask_2parts = no_date_mask & (parts_count == 2)
        if mask_2parts.any():
            split_df = s[mask_2parts].str.split(':', n=1, expand=True)
            minutes = split_df[0].str.strip().str.zfill(2)
            seconds = split_df[1].str.strip()
            s.loc[mask_2parts] = "2026-04-01 00:" + minutes + ":" + seconds
            
        # 3 parts: HH:MM:SS.f -> prepend '2026-04-01 '
        mask_3parts = no_date_mask & (parts_count == 3)
        if mask_3parts.any():
            s.loc[mask_3parts] = "2026-04-01 " + s[mask_3parts]
            
    # Set null mask to None so pd.to_datetime handles them as NaT
    s[null_mask] = None
    
    formats = [
        '%Y-%m-%d %H:%M:%S.%f', # Millisecond format first for high-performance direct hits
        '%Y-%m-%d %H:%M:%S',
        '%d.%m.%Y %H:%M:%S',
        '%d-%m-%Y %H:%M:%S',
        '%Y-%m-%d',
        '%d.%m.%Y',
        '%d-%m-%Y',
        '%Y/%m/%d %H:%M:%S',
        '%d/%m/%Y %H:%M:%S',
        '%d/%m/%Y'
    ]
    
    parsed = pd.Series(pd.NaT, index=series.index)
    
    for fmt in formats:
        unparsed_mask = parsed.isna() & ~null_mask
        if not unparsed_mask.any():
            break
        try:
            parsed_sub = pd.to_datetime(s[unparsed_mask], format=fmt, errors='coerce')
            parsed.update(parsed_sub)
        except Exception:
            pass
            
    unparsed_mask = parsed.isna() & ~null_mask
    if unparsed_mask.any():
        try:
            parsed_sub = pd.to_datetime(s[unparsed_mask], errors='coerce')
            parsed.update(parsed_sub)
        except Exception:
            pass
            
    return parsed

def normalize_key_series(series: pd.Series) -> pd.Series:
    """
    Vectorised normalization of a string key Series.
    Strips whitespace, and converts typical missing values ('nan', 'none', '') to pd.NA.
    """
    s = series.astype(str).str.strip()
    return s.where(~s.str.lower().isin({'nan', 'none', ''}), other=pd.NA)

def fetch_existing_keys_chunked(
    db: Session,
    query_template: str,
    keys: List[str],
    is_tuple: bool = False,
    chunk_size: int = 10000
) -> set:
    """
    Executes a SELECT query in chunks to find existing keys in the database.
    Prevents database planner overhead and parameter binding limits for large sets.
    """
    if not keys:
        return set()

    existing = set()
    for i in range(0, len(keys), chunk_size):
        chunk = tuple(keys[i : i + chunk_size])
        res = db.execute(text(query_template), {"k": chunk})
        if is_tuple:
            existing.update((str(r[0]).strip(), str(r[1]).strip()) for r in res)
        else:
            existing.update(str(r[0]).strip() for r in res)

    return existing

def deduplicate_dataframe(combined_df: pd.DataFrame, table_name: str, db: Session) -> pd.DataFrame:
    """
    Deduplicates a DataFrame against existing keys in the PostgreSQL database.
    """
    original_len = len(combined_df)
    if original_len == 0:
        return combined_df

    if table_name == 'stg_mobile_mumbaione' and 'pg_reference_no' in combined_df.columns:
        clean_col = normalize_key_series(combined_df['pg_reference_no'])
        clean_keys = clean_col.dropna().unique().tolist()
        existing = fetch_existing_keys_chunked(
            db,
            "SELECT pg_reference_no FROM stg_mobile_mumbaione WHERE pg_reference_no IN :k",
            clean_keys
        )
        if existing:
            sample = sorted(list(existing)[:100])[:20]
            print(f"[DUPLICATE] stg_mobile_mumbaione: {len(existing)} duplicate pg_reference_no value(s) found in DB.")
            print(f"[DUPLICATE] Sample keys (up to 20): {sample}")
        combined_df = combined_df[clean_col.notna() & ~clean_col.isin(existing)]

    elif table_name == 'stg_mobile_metroconnect3' and 'ticket_no' in combined_df.columns:
        clean_col = normalize_key_series(combined_df['ticket_no'])
        clean_keys = clean_col.dropna().unique().tolist()
        existing = fetch_existing_keys_chunked(
            db,
            "SELECT ticket_no FROM stg_mobile_metroconnect3 WHERE ticket_no IN :k",
            clean_keys
        )
        if existing:
            sample = sorted(list(existing)[:100])[:20]
            print(f"[DUPLICATE] stg_mobile_metroconnect3: {len(existing)} duplicate ticket_no value(s) found in DB.")
            print(f"[DUPLICATE] Sample keys (up to 20): {sample}")
        combined_df = combined_df[clean_col.notna() & ~clean_col.isin(existing)]

    elif table_name == 'stg_mobile_ondc' and 'order_id' in combined_df.columns:
        clean_col = normalize_key_series(combined_df['order_id'])
        clean_keys = clean_col.dropna().unique().tolist()
        existing = fetch_existing_keys_chunked(
            db,
            "SELECT order_id FROM stg_mobile_ondc WHERE order_id IN :k",
            clean_keys
        )
        if existing:
            sample = sorted(list(existing)[:100])[:20]
            print(f"[DUPLICATE] stg_mobile_ondc: {len(existing)} duplicate order_id value(s) found in DB.")
            print(f"[DUPLICATE] Sample keys (up to 20): {sample}")
        combined_df = combined_df[clean_col.notna() & ~clean_col.isin(existing)]

    elif table_name == 'stg_pg_transactions' and 'pgi_ref_no' in combined_df.columns:
        clean_pgi = normalize_key_series(combined_df['pgi_ref_no'])
        clean_type = normalize_key_series(combined_df['transaction_type'])
        clean_keys = clean_pgi.dropna().unique().tolist()
        existing = fetch_existing_keys_chunked(
            db,
            "SELECT pgi_ref_no, transaction_type FROM stg_pg_transactions WHERE pgi_ref_no IN :k",
            clean_keys,
            is_tuple=True
        )
        if existing:
            sample = sorted(list(existing)[:100])[:20]
            print(f"[DUPLICATE] stg_pg_transactions: {len(existing)} duplicate (pgi_ref_no, transaction_type) pair(s) found in DB.")
            print(f"[DUPLICATE] Sample pairs (up to 20): {sample}")
        combo = list(zip(clean_pgi.fillna(''), clean_type.fillna('')))
        mask = pd.Series(
            [pair in existing for pair in combo],
            index=combined_df.index
        )
        combined_df = combined_df[clean_pgi.notna() & clean_type.notna() & ~mask]

    elif table_name == 'stg_afc_transactions' and 'slave_qr_no' in combined_df.columns:
        clean_col = normalize_key_series(combined_df['slave_qr_no'])
        clean_keys = clean_col.dropna().unique().tolist()
        existing = fetch_existing_keys_chunked(
            db,
            "SELECT slave_qr_no FROM stg_afc_transactions WHERE slave_qr_no IN :k",
            clean_keys
        )
        if existing:
            sample = sorted(list(existing)[:100])[:20]
            print(f"[DUPLICATE] stg_afc_transactions: {len(existing)} duplicate slave_qr_no value(s) found in DB.")
            print(f"[DUPLICATE] Sample keys (up to 20): {sample}")
        combined_df = combined_df[clean_col.notna() & ~clean_col.isin(existing)]

    dups = original_len - len(combined_df)
    if dups > 0:
        print(f"[DEDUP SUMMARY] {dups:,} row(s) removed total ({original_len:,} in -> {len(combined_df):,} net new).")
    else:
        print(f"[DEDUP SUMMARY] No duplicates found. All {original_len:,} row(s) are new.")

    return combined_df
