def _looks_like_excel(b: bytes) -> bool:
    # XLSX files are ZIP containers (start with "PK")
    return b[:2] == b"PK"

def _try_read_csv_bytes(b: bytes):
    import pandas as pd, io
    for sep in [",", ";", "\t", "|"]:
        try:
            df = pd.read_csv(io.BytesIO(b), dtype=str, sep=sep, engine="python")
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
            return pd.read_excel(io.BytesIO(b), dtype=str)

        # JSON?
        if "json" in ct:
            try:
                j = json.loads(b.decode("utf-8", errors="ignore"))
                if isinstance(j, list):
                    return pd.DataFrame(j)
                if isinstance(j, dict):
                    if "data" in j and isinstance(j["data"], list):
                        return pd.DataFrame(j["data"])
                    return pd.json_normalize(j)
            except Exception:
                pass  # fall through to CSV attempt

        # CSV/unknown → try multiple delimiters
        df = _try_read_csv_bytes(b)
        if df is not None:
            return df

        raise ValueError("Could not parse URL content as CSV/Excel/JSON.")

    # Uploaded file
    else:
        name = (file_or_url.name or "").lower()
        if name.endswith((".xlsx", ".xls")):
            return pd.read_excel(file_or_url, dtype=str)
        if name.endswith(".json"):
            import json as _json
            try:
                j = _json.load(file_or_url)
                if isinstance(j, list):
                    return pd.DataFrame(j)
                if isinstance(j, dict):
                    if "data" in j and isinstance(j["data"], list):
                        return pd.DataFrame(j["data"])
                    return pd.json_normalize(j)
            except Exception:
                file_or_url.seek(0)
        # default: try CSV with delimiter sniff
        file_or_url.seek(0)
        df = _try_read_csv_bytes(file_or_url.read())
        if df is not None:
            return df
        raise ValueError("Unsupported file format.")
