# pages/data_viewer.py
import streamlit as st
import pandas as pd
import altair as alt
import requests
from io import BytesIO
import json, itertools, base64
from typing import Dict, Any

st.set_page_config(page_title="Chatstat – Data Viewer", layout="wide")

st.title("📊 Chatstat – Data Viewer")
st.caption("Upload a file or provide a URL. Works with CSV, Excel (.xlsx), JSON, and SSB JSON-stat (via POST).")

# -----------------------------
# Helpers: robust data loading
# -----------------------------
def _looks_like_excel(b: bytes) -> bool:
    # XLSX files are ZIP containers (start with "PK")
    return b[:2] == b"PK"

def _try_read_csv_bytes(b: bytes):
    import io
    for sep in [",", ";", "\t", "|"]:
        try:
            df = pd.read_csv(io.BytesIO(b), dtype=str, sep=sep, engine="python")
            if df.shape[1] >= 1:
                return df
        except Exception:
            pass
    return None

def load_data(file_or_url):
    # URL case
    if isinstance(file_or_url, str):
        r = requests.get(file_or_url, timeout=30)
        r.raise_for_status()
        ct = (r.headers.get("content-type") or "").lower()
        b = r.content

        # Excel?
        if "excel" in ct or _looks_like_excel(b):
            return pd.read_excel(BytesIO(b), dtype=str)

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
        # default: try CSV with delimiter sniff
        file_or_url.seek(0)
        df = _try_read_csv_bytes(file_or_url.read())
        if df is not None:
            return df
        raise ValueError("Unsupported file format.")

# -----------------------------
# SSB JSON-stat helpers (POST)
# -----------------------------
def jsonstat_to_df(js: Dict[str, Any]):
    """
    Flatten JSON-stat v2 into a tidy DataFrame: columns = each dimension + 'value'.
    Works for common SSB/OECD JSON-stat responses.
    """
    ds = js.get("dataset") or js  # some APIs return dataset directly
    dim = ds["dimension"]
    ids = dim["id"]                  # e.g. ["region","contentscode","time"]
    dims = []
    for d in ids:
        cat = dim[d]["category"]
        # Prefer label if present; else use index keys
        if "label" in cat and isinstance(cat["label"], dict):
            labels = list(cat["label"].values())
            keys = list(cat["label"].keys())
        else:
            if isinstance(cat.get("index"), dict):
                keys = list(cat["index"].keys())
            else:
                keys = cat.get("index") or list((cat.get("label") or {}).keys()) or []
            labels = keys
        s = pd.Series(labels, index=keys, name=d).reset_index(drop=True)
        dims.append(s)

    # Cartesian product of all dimension values
    grid = list(itertools.product(*[list(s.values) for s in dims]))
    df = pd.DataFrame(grid, columns=ids)

    # Values (flat list, same order)
    vals = ds.get("value", [])
    df["value"] = pd.to_numeric(pd.Series(vals), errors="coerce")
    return df

def ssb_post_to_df(url: str, payload: Dict[str, Any]):
    r = requests.post(url, json=payload, timeout=30, headers={"Accept": "application/json"})
    r.raise_for_status()
    js = r.json()
    try:
        return jsonstat_to_df(js)
    except Exception:
        return pd.json_normalize(js)

# -----------------------------
# Query params (new/old API)
# -----------------------------
df = None  # make sure df exists
try:
    # Newer Streamlit: st.query_params (Mapping[str, str|list[str]])
    qp = st.query_params
    params = {k: ([v] if isinstance(v, str) else list(v)) for k, v in qp.items()}
except Exception:
    try:
        params = st.experimental_get_query_params()
    except Exception:
        params = {}

# Auto-load from URL (?url=...)
if df is None and "url" in params:
    try:
        df = load_data(params["url"][0])
        st.success(f"Data loaded from {params['url'][0]}")
    except Exception as e:
        st.error(f"Could not load from URL: {e}")

# Auto-load from SSB POST (?ssb_url=...&ssb=<base64url_payload>)
if df is None and "ssb_url" in params and "ssb" in params:
    try:
        ssb_url = params["ssb_url"][0]
        payload_b64 = params["ssb"][0]
        payload_json = json.loads(base64.urlsafe_b64decode(payload_b64 + "==").decode("utf-8"))
        df = ssb_post_to_df(ssb_url, payload_json)
        st.success(f"Loaded via SSB POST: {ssb_url}")
    except Exception as e:
        st.error(f"SSB POST failed: {e}")

# Manual SSB query (advanced users)
with st.expander("SSB JSON-stat query (advanced)"):
    ssb_url_in = st.text_input(
        "SSB JSON-stat POST URL (ends with .json)",
        placeholder="https://api.statbank.no:443/statbank-api-no-no/table/XXXX?contentType=JSON"
    )
    payload_txt = st.text_area(
        "Payload (JSON)",
        height=180,
        placeholder='{"query":[...],"response":{"format":"JSON-STAT2"}}'
    )
    if st.button("Run SSB query"):
        try:
            payload_obj = json.loads(payload_txt)
            df = ssb_post_to_df(ssb_url_in, payload_obj)
            st.success("SSB query loaded.")
        except Exception as e:
            st.error(f"Bad URL or payload: {e}")

# -----------------------------
# File upload (fallback)
# -----------------------------
if df is None:
    up = st.file_uploader("Upload a file (CSV, XLSX, JSON)", type=["csv", "xlsx", "json"])
    if up:
        try:
            df = load_data(up)
            st.success("File loaded.")
        except Exception as e:
            st.error(f"Could not read file: {e}")

# -----------------------------
# Visualisation UI
# -----------------------------
if df is not None:
    st.subheader("Preview")
    st.dataframe(df.head(50), use_container_width=True)

    columns = df.columns.tolist()
    if not columns:
        st.warning("No columns found.")
        st.stop()

    # Try to auto-suggest common columns
    def guess(colnames, keys):
        for k in keys:
            for c in colnames:
                if k.lower() in c.lower():
                    return c
        return colnames[0]

    x_default = guess(columns, ["time", "år", "date", "periode"])
    y_default = guess(columns, ["value", "verdi", "values", "antall", "prosent"])
    group_default = None
    for k in ["contents", "indicator", "indikator", "kategori", "sex", "kjønn", "region"]:
        g = [c for c in columns if k.lower() in c.lower()]
        if g:
            group_default = g[0]
            break

    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        col_x = st.selectbox("X-axis (time/category)", options=columns, index=columns.index(x_default))
    with c2:
        col_y = st.selectbox("Y-axis (value)", options=columns, index=columns.index(y_default))
    with c3:
        col_group = st.selectbox("Group/color (optional)", options=["None"] + columns,
                                 index=(0 if not group_default else (columns.index(group_default) + 1)))

    # Filter by groups (if group chosen)
    if col_group != "None":
        groups = sorted(df[col_group].dropna().unique().tolist())
        picked = st.multiselect("Choose groups to compare", groups, default=groups[: min(4, len(groups))])
        if picked:
            df = df[df[col_group].isin(picked)]

    chart_type = st.radio("Chart type", ["Line", "Bar", "Pie", "Grouped bar"], horizontal=True)

    # Ensure numeric y
    df_plot = df.copy()
    df_plot[col_y] = pd.to_numeric(df_plot[col_y], errors="coerce")

    chart = None
    if chart_type == "Line":
        chart = alt.Chart(df_plot).mark_line(point=True).encode(
            x=alt.X(col_x, sort=None),
            y=alt.Y(col_y, title=col_y),
            color=col_group if col_group != "None" else alt.value(None),
            tooltip=list(df_plot.columns)
        ).interactive()

    elif chart_type == "Bar":
        chart = alt.Chart(df_plot).mark_bar().encode(
            x=alt.X(col_x, sort=None),
            y=alt.Y(col_y, title=col_y),
            color=col_group if col_group != "None" else alt.value(None),
            tooltip=list(df_plot.columns)
        ).interactive()

    elif chart_type == "Pie":
        if col_group == "None":
            st.warning("Pie requires a group column. Pick a 'Group/color' field above.")
        else:
            # Aggregate by group for the current selection on x (if x exists)
            agg = df_plot.copy()
            # If x looks like time, ignore it for pie (sum over selection)
            pie = alt.Chart(agg).mark_arc().encode(
                theta=alt.Theta(field=col_y, type="quantitative"),
                color=alt.Color(col_group, legend=True),
                tooltip=list(df_plot.columns)
            )
            chart = pie

    elif chart_type == "Grouped bar":
        if col_group == "None":
            st.warning("Grouped bar requires a group column.")
        else:
            chart = alt.Chart(df_plot).mark_bar().encode(
                x=alt.X(f"{col_x}:N", axis=alt.Axis(title=col_x)),
                y=alt.Y(f"{col_y}:Q", axis=alt.Axis(title=col_y)),
                color=alt.Color(col_group, legend=True),
                tooltip=list(df_plot.columns)
            ).properties(width=650).configure_axisX(labelAngle=-40)

    if chart is not None:
        st.altair_chart(chart, use_container_width=True)

else:
    st.info("Provide a URL via `?url=...` or run an SSB POST query above, or upload a file.")
