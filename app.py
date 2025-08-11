import streamlit as st
import pandas as pd
import altair as alt
import requests
from io import StringIO
from datetime import datetime
from dateutil.parser import parse as date_parse

st.set_page_config(page_title="Chatstat", page_icon="📊", layout="wide")

# --- Logo og tittel ---
st.markdown("""
<style>
    [data-testid="stSidebar"] {background-color: #f5f5f5;}
    .main-title {font-size: 2.4rem; font-weight: 700;}
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='main-title'>📊 Chatstat</div>", unsafe_allow_html=True)
st.write("Importer, analyser og vis data — sømløst fra ChatGPT.")

# --- Hent data ---
def load_data():
    import_url = st.query_params.get("import")
    if import_url:
        try:
            r = requests.get(import_url)
            r.raise_for_status()
            return pd.read_csv(StringIO(r.text))
        except Exception as e:
            st.error(f"Kunne ikke hente data: {e}")
    return None

df = load_data()

# --- Hvis ingen data lastet ---
if df is None:
    st.info("Last opp en CSV-fil eller bruk en ?import=URL for å starte.")
    uploaded_file = st.file_uploader("Last opp CSV", type=["csv"])
    if uploaded_file:
        df = pd.read_csv(uploaded_file)

# --- Hvis vi har data ---
if df is not None:
    st.subheader("📄 Datasett")
    st.dataframe(df)

    # Prøv å finne kolonner automatisk
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    date_cols = df.select_dtypes(include="datetime").columns.tolist()
    if not date_cols:
        for col in df.columns:
            try:
                df[col] = pd.to_datetime(df[col])
                date_cols.append(col)
                break
            except:
                pass

    # Velg kolonner for graf
    x_col = st.selectbox("X-akse", df.columns, index=0)
    y_col = st.selectbox("Y-akse", numeric_cols, index=0 if numeric_cols else None)

    if y_col:
        chart = alt.Chart(df).mark_line(point=True).encode(
            x=x_col,
            y=y_col,
            tooltip=list(df.columns)
        ).interactive()
        st.altair_chart(chart, use_container_width=True)
