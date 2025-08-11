def _looks_like_excel(b: bytes) -> bool:
    # XLSX is a zip (PK), XLSB/XLS variants vary; this covers .xlsx reliably
    return b[:2] == b"PK"

def _try_read_csv_bytes(b: bytes):
    import pandas as pd, io, csv
    for sep in [",", ";", "\t", "|"]:
        try:
            df = pd.read_csv(io.BytesIO(b), dtype=str, sep=sep, engine="python")
            # sanity: at least 1 column
            if df.shape[1] >= 1:
                return df
        except Exception:
            pass
    return None

def load_data(file_or_url):
    import pandas as pd, io, json, requests

    # URL case
    if isinstance(file_or_url, str):
        r = requests.get(file_or_url, timeout=30)
        r.raise_for_status()
        ct = (r.headers.get("content-type") or "").lower()
        b = r.content

        # Excel?
        if "excel" in ct or _looks_like_excel(b):
            return pd.read_excel(io.BytesIO(b))

        # JSON (also try if URL has ?format=JSON or content looks like JSON)
        if "json" in ct:
            try:
                j = json.loads(b.decode("utf-8", errors="ignore"))
                if isinstance(j, list):
                    return pd.DataFrame(j)
                if isinstance(j, dict):
                    # common patterns
                    if "data" in j and isinstance(j["data"], list):
                        return pd.DataFrame(j["data"])
                    return pd.json_normalize(j)
            except Exception:
                pass  # fall through to CSV try

        # CSV/TSV (or unknown → try CSV anyway)
        df = _try_read_csv_bytes(b)
        if df is not None:
            return df

        raise ValueError("Could not parse URL content as CSV/Excel/JSON.")

    # Uploaded file
    else:
        name = (file_or_url.name or "").lower()
        if name.endswith(".xlsx") or name.endswith(".xls"):
            return pd.read_excel(file_or_url, dtype=str)
        if name.endswith(".json"):
            import json
            try:
                j = json.load(file_or_url)
                if isinstance(j, list):
                    return pd.DataFrame(j)
                if isinstance(j, dict):
                    if "data" in j and isinstance(j["data"], list):
                        return pd.DataFrame(j["data"])
                    return pd.json_normalize(j)
            except Exception:
                file_or_url.seek(0)
        # default to CSV with delimiter sniff
        file_or_url.seek(0)
        df = _try_read_csv_bytes(file_or_url.read())
        if df is not None:
            return df
        raise ValueError("Unsupported file format.")
