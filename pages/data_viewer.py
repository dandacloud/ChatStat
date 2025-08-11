import json, itertools, base64
from typing import Dict, Any


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

def jsonstat_to_df(js: Dict[str, Any]):
    """
    Flatten JSON-stat v2 into a tidy pandas DataFrame:
    columns = each dimension + 'value'
    Works for common SSB/OECD JSON-stat responses.
    """
    import pandas as pd

    ds = js.get("dataset") or js  # some APIs return dataset directly
    dim = ds["dimension"]
    ids = dim["id"]                  # e.g. ["region","contentscode","time"]
    dims = []
    for d in ids:
        cat = dim[d]["category"]
        # Prefer label if present, else index keys
        if "label" in cat and isinstance(cat["label"], dict):
            labels = list(cat["label"].values())
            keys = list(cat["label"].keys())
        else:
            # index may be dict (key->pos) or list (ordered)
            if isinstance(cat.get("index"), dict):
                keys = list(cat["index"].keys())
            else:
                keys = cat.get("index") or cat.get("label", {}).keys() or []
            labels = keys
        dims.append(pd.Series(labels, index=keys, name=d).reset_index(drop=True))

    # All combinations
    grid = list(itertools.product(*[list(s.values) for s in dims]))
    df = pd.DataFrame(grid, columns=ids)

    # Values (flat list aligned to cartesian product order)
    vals = ds.get("value", [])
    # JSON-stat sometimes has nulls; keep as NaN
    df["value"] = pd.to_numeric(pd.Series(vals), errors="coerce")

    return df

def ssb_post_to_df(url: str, payload: Dict[str, Any]):
    import requests
    r = requests.post(url, json=payload, timeout=30, headers={"Accept":"application/json"})
    r.raise_for_status()
    js = r.json()
    try:
        return jsonstat_to_df(js)
    except Exception:
        # Fall back to a generic normalize if not JSON-stat
        import pandas as pd
        return pd.json_normalize(js)

# ---- Query params (compatible across Streamlit versions)
try:
    # Newer Streamlit (1.25+): .query_params
    qp = st.query_params
    # Convert to the same structure as experimental_get_query_params
    params = {k: ([v] if isinstance(v, str) else list(v)) for k, v in qp.items()}
except Exception:
    try:
        # Older API (still present in many builds)
        params = st.experimental_get_query_params()
    except Exception:
        params = {}


# Existing: ?url=...
if "url" in params and df is None:
    try:
        df = load_data(params["url"][0])
        st.success(f"Data loaded from {params['url'][0]}")
    except Exception as e:
        st.error(f"Could not load from URL: {e}")

# NEW: ?ssb_url=<POST endpoint>&ssb=<base64url_encoded_json_payload>
if df is None and "ssb_url" in params and "ssb" in params:
    try:
        ssb_url = params["ssb_url"][0]
        payload_b64 = params["ssb"][0]
        payload_json = json.loads(base64.urlsafe_b64decode(payload_b64 + "==").decode("utf-8"))
        df = ssb_post_to_df(ssb_url, payload_json)
        st.success(f"Loaded via SSB POST: {ssb_url}")
    except Exception as e:
        st.error(f"SSB POST failed: {e}")

with st.expander("SSB JSON-stat query (advanced)"):
    ssb_url_in = st.text_input("SSB JSON-stat POST URL (ends with .json)", placeholder="https://api.statbank.no:443/statbank-api-no-no/table/XXXX?contentType=JSON")
    payload_txt = st.text_area("Payload (JSON)", height=180, placeholder='{"query":[...],"response":{"format":"JSON-STAT2"}}')
    if st.button("Run SSB query"):
        try:
            payload_obj = json.loads(payload_txt)
            df = ssb_post_to_df(ssb_url_in, payload_obj)
            st.success("SSB query loaded.")
        except Exception as e:
            st.error(f"Bad URL or payload: {e}")

