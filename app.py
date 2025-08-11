
import streamlit as st
import pandas as pd
import altair as alt
import requests, io, json, os, math
from datetime import datetime

APP_TITLE = "Chatstat"
LOGO_PATH = "assets/logo.png"

st.set_page_config(page_title=APP_TITLE, page_icon=LOGO_PATH, layout="wide")
# --- One-click import via URL parameters ---
params = st.experimental_get_query_params()
auto_url = params.get("import", [None])[0]
auto_title = params.get("title", [None])[0]
auto_source = params.get("source", [None])[0]
auto_source_url = params.get("source_url", [None])[0]

auto_map = {
    "region": params.get("map_region", [None])[0],
    "indikator": params.get("map_indicator", [None])[0],
    "år": params.get("map_year", [None])[0],
    "verdi": params.get("map_value", [None])[0],
    "enhet": params.get("map_unit", [None])[0],
    "kilde": params.get("map_source", [None])[0],
}
if auto_url:
    try:
        r = requests.get(auto_url, timeout=30)
        ct = r.headers.get("Content-Type","").lower()
        if "json" in ct or auto_url.lower().endswith(".json"):
            j = r.json()
            if isinstance(j, list):
                df_auto = pd.DataFrame(j)
            elif isinstance(j, dict):
                if "data" in j and isinstance(j["data"], list):
                    df_auto = pd.DataFrame(j["data"])
                else:
                    df_auto = pd.json_normalize(j)
            else:
                df_auto = None
        else:
            df_auto = pd.read_csv(io.BytesIO(r.content), dtype=str, encoding="utf-8-sig")
        if df_auto is not None and len(df_auto):
            title0 = auto_title or "Datasett"
            meta0 = {
                "title": title0,
                "source": auto_source or "ukjent",
                "source_url": auto_source_url or auto_url,
                "method": "url-import(auto)",
                "licence": "Unknown",
                "tags": ["auto"],
                "description": f"Automatisk import fra URL via query-param: {auto_url}",
                "retrieved_at": datetime.utcnow().isoformat()+"Z",
            }
            df_save = df_auto
            # if any mapping is provided, try to standardize
            if any(v for v in auto_map.values()):
                df_save = map_to_standard(df_auto, auto_map)
            name0 = re.sub(r'\\W+','_', (title0 or 'datasett')).strip('_').lower()
            save_dataset(name0, df_save, meta0)
            st.success(f"Automatisk importert: {title0}")
            st.experimental_set_query_params()  # clear params after import
    except Exception as e:
        st.warning(f"Kunne ikke auto-importere: {e}")


# --- Styling / header
col_logo, col_title = st.columns([1,6])
with col_logo:
    st.image(LOGO_PATH, width=72)
with col_title:
    st.markdown(f"### {APP_TITLE}")
    st.caption("Én app for alle tall: importer, standardiser, filtrer, visualiser og ranger.")

# --- Simple 'storage' helpers (file-based; ephemeral on Streamlit Cloud)
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def save_dataset(name: str, df: pd.DataFrame, meta: dict):
    csv_path = os.path.join(DATA_DIR, f"{name}.csv")
    meta_path = os.path.join(DATA_DIR, f"{name}.meta.json")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    meta = dict(meta or {})
    meta.update({
        "name": name,
        "rows": int(len(df)),
        "saved_at": datetime.utcnow().isoformat() + "Z",
    })
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return csv_path, meta_path

def list_datasets():
    items = []
    for fn in os.listdir(DATA_DIR):
        if fn.endswith(".meta.json"):
            with open(os.path.join(DATA_DIR, fn), "r", encoding="utf-8") as f:
                meta = json.load(f)
            csv = fn.replace(".meta.json", ".csv")
            csv_path = os.path.join(DATA_DIR, csv)
            if os.path.exists(csv_path):
                items.append((csv_path, meta))
    items.sort(key=lambda x: x[1].get("saved_at",""), reverse=True)
    return items

def read_dataset(csv_path: str) -> pd.DataFrame:
    return pd.read_csv(csv_path, dtype=str, encoding="utf-8-sig")

def coerce_float(x):
    try:
        return float(str(x).replace(",", "."))
    except Exception:
        return None

def map_to_standard(df: pd.DataFrame, mapping: dict):
    out = pd.DataFrame()
    out["region"] = df.get(mapping.get("region",""),"")
    out["år"] = df.get(mapping.get("år",""),"")
    out["indikator"] = df.get(mapping.get("indikator",""),"")
    out["verdi"] = df.get(mapping.get("verdi",""),"").apply(lambda v: str(v))
    out["enhet"] = df.get(mapping.get("enhet",""),"")
    out["kilde"] = df.get(mapping.get("kilde",""),"")
    return out

tab1, tab2, tab3 = st.tabs(["Datasett", "Importer", "Rangering"])

with tab1:
    st.subheader("Datasett-bibliotek")
    q = st.text_input("Søk i tittel/tags/kilde …", "")
    tag_filter = st.text_input("Filter på tags (kommaseparert)", "")
    tagset = {t.strip().lower() for t in tag_filter.split(",") if t.strip()}

    for csv_path, meta in list_datasets():
        textblob = " ".join([meta.get("title",""), meta.get("source","")] + meta.get("tags",[])).lower()
        if q and q.lower() not in textblob:
            continue
        if tagset and not tagset.issubset({t.lower() for t in meta.get("tags",[])}):
            continue
        with st.expander(f"📁 {meta.get('title') or meta.get('name')}  •  {meta.get('rows','?')} rader"):
            left, right = st.columns([2,1])
            df = read_dataset(csv_path)
            with left:
                st.write("**Beskrivelse**:", meta.get("description",""))
                st.write("**Kilde**:", meta.get("source",""), meta.get("source_url",""))
                st.write("**Metode**:", meta.get("method",""))
                st.write("**Hentet**:", meta.get("retrieved_at",""))
                st.write("**Etiketter**:", ", ".join(meta.get("tags", [])))
                st.dataframe(df, use_container_width=True, hide_index=True)
                if all(c in df.columns for c in ["region","år","indikator","verdi"]):
                    num = df.assign(verdi_num=df["verdi"].apply(coerce_float)).dropna(subset=["verdi_num"])
                    if len(num):
                        st.write("**Hurtiggraf:**")
                        chart = alt.Chart(num).mark_bar().encode(
                            x=alt.X("år:O", sort=None),
                            y="verdi_num:Q",
                            color="indikator:N",
                            tooltip=["region","år","indikator","verdi"]
                        ).interactive()
                        st.altair_chart(chart, use_container_width=True)
            with right:
                st.download_button("⬇️ Last ned CSV", data=open(csv_path,"rb").read(), file_name=os.path.basename(csv_path))
                st.json(meta)

with tab2:
    st.subheader("Importer fra fil eller URL")
    up = st.file_uploader("Last opp CSV", type=["csv"])
    url = st.text_input("…eller importer fra URL (CSV eller JSON)", placeholder="https://…")
    title = st.text_input("Tittel")
    source = st.text_input("Kilde (navn)", value="ukjent")
    source_url = st.text_input("Kilde-URL", value=url or "")
    tags = st.text_input("Etiketter (komma-separert)", value="opplasting")
    desc = st.text_area("Beskrivelse", value="Lastet inn via Chatstat")
    standard_map = st.checkbox("Kartlegg til standard felter (region, år, indikator, verdi, enhet, kilde)?", value=True)

    df = None
    if up is not None:
        df = pd.read_csv(up, dtype=str, encoding="utf-8-sig")
    elif url:
        try:
            r = requests.get(url, timeout=30)
            ct = r.headers.get("Content-Type","").lower()
            if "json" in ct or url.lower().endswith(".json"):
                j = r.json()
                if isinstance(j, list):
                    df = pd.DataFrame(j)
                elif isinstance(j, dict):
                    if "data" in j and isinstance(j["data"], list):
                        df = pd.DataFrame(j["data"])
                    else:
                        df = pd.json_normalize(j)
                else:
                    st.error("Ukjent JSON-format.")
            else:
                df = pd.read_csv(io.BytesIO(r.content), dtype=str, encoding="utf-8-sig")
        except Exception as e:
            st.error(f"Kunne ikke hente fra URL: {e}")

    if df is not None:
        st.write("Forhåndsvisning:", df.head(20))
        mapping = {}
        if standard_map:
            cols = ["(ingen)"] + list(df.columns)
            c1,c2,c3 = st.columns(3)
            with c1:
                mapping["region"] = st.selectbox("Region-kolonne", cols, index=0)
                mapping["indikator"] = st.selectbox("Indikator-kolonne", cols, index=0)
            with c2:
                mapping["år"] = st.selectbox("År-kolonne", cols, index=0)
                mapping["verdi"] = st.selectbox("Verdi-kolonne", cols, index=0)
            with c3:
                mapping["enhet"] = st.selectbox("Enhet-kolonne", cols, index=0)
                mapping["kilde"] = st.selectbox("Kilde-kolonne", cols, index=0)
        if st.button("Lagre datasett"):
            name = (title or "datasett").strip().lower().replace(" ","_")
            meta = {
                "title": title or "Datasett",
                "source": source,
                "source_url": source_url,
                "method": "upload" if up else "url-import",
                "licence": "Unknown",
                "tags": [t.strip() for t in tags.split(",") if t.strip()],
                "description": desc,
                "retrieved_at": datetime.utcnow().isoformat()+"Z",
            }
            to_save = df
            if standard_map and any(mapping.values()):
                to_save = map_to_standard(df, mapping)
            save_dataset(name, to_save, meta)
            st.success("Lagret! Gå til fanen 'Datasett'.")

with tab3:
    st.subheader("Rangering (krever standardfelt)")
    # samle alle standardiserte rader
    frames = []
    for csv_path, meta in list_datasets():
        df = read_dataset(csv_path)
        if all(c in df.columns for c in ["region","år","indikator","verdi"]):
            df["kilde_nav"] = meta.get("source","")
            frames.append(df)
    if frames:
        full = pd.concat(frames, ignore_index=True)
        full["verdi_num"] = full["verdi"].apply(coerce_float)
        regions = sorted(full["region"].dropna().unique().tolist())
        indik = sorted(full["indikator"].dropna().unique().tolist())
        colA, colB = st.columns(2)
        with colA:
            valgt_år = st.selectbox("År", sorted(full["år"].dropna().unique().tolist())[::-1])
            valgt_indikatorer = st.multiselect("Indikatorer", indik, default=indik[:1])
        with colB:
            pos_indik = st.multiselect("Indikatorer der høy verdi er bra", valgt_indikatorer, default=valgt_indikatorer)
            neg_indik = [i for i in valgt_indikatorer if i not in pos_indik]
            neg_weight = st.slider("Vekt for **negative** indikatorer (lavt er bra)", 0.0, 1.0, 0.5, 0.05)

        sub = full[(full["år"]==valgt_år) & (full["indikator"].isin(valgt_indikatorer))].copy()
        pivot = sub.pivot_table(index="region", columns="indikator", values="verdi_num", aggfunc="mean")
        score = pd.Series(0.0, index=pivot.index)
        for col in valgt_indikatorer:
            s = pivot[col]
            if s.notna().sum() < 2:  # for lite data
                continue
            norm = (s - s.min()) / (s.max() - s.min())
            if col in pos_indik:
                score += (1 - neg_weight) * norm / max(1,len(valgt_indikatorer))
            else:
                score += neg_weight * (1 - norm) / max(1,len(valgt_indikatorer))
        out = pivot.copy()
        out["Score"] = score
        out = out.sort_values("Score", ascending=False).reset_index()
        st.dataframe(out, use_container_width=True, hide_index=True)
        st.download_button("⬇️ Last ned rangering (CSV)", out.to_csv(index=False).encode("utf-8-sig"), file_name="chatstat_rangering.csv")
    else:
        st.info("Importer minst ett datasett og kartlegg til standardfeltene i fanen 'Importer'.")
