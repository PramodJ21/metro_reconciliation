import io
import time
import pandas as pd
from typing import Tuple, Optional
from app.parser import (
    parse_mobile_mumbaione,
    parse_mobile_metroconnect3,
    parse_mobile_ondc,
    parse_afc,
    parse_payment_gateway
)

def parse_ingested_file(
    filename: str, 
    file_bytes: bytes, 
    app_name: str, 
    channel: str
) -> Tuple[str, Optional[pd.DataFrame], dict]:
    """
    Pickle-safe file parsing task that runs inside ProcessPoolExecutor.
    Receives raw file bytes, wraps them in a BytesIO buffer, parses,
    and returns telemetry logs.
    """
    start_time = time.time()
    buf = io.BytesIO(file_bytes)
    
    _app = app_name.strip().lower()
    _ch  = channel.strip().lower()
    
    df = None
    try:
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
            rows_parsed = len(df)
        else:
            rows_parsed = 0
            
        success = True
        error_message = None
    except Exception as e:
        success = False
        rows_parsed = 0
        error_message = str(e)
        df = None

    duration = time.time() - start_time
    
    telemetry = {
        "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        "filename": filename,
        "app_name": app_name,
        "channel": channel,
        "duration_seconds": round(duration, 4),
        "rows_parsed": rows_parsed,
        "success": success,
        "error": error_message
    }
    
    # Print structured telemetry stdout log for observability
    print(f"[TELEMETRY] {telemetry}")
    
    return filename, df, telemetry
