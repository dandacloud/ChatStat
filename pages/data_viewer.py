import streamlit as st
import pandas as pd
import altair as alt
from urllib.parse import urlparse, parse_qs
import requests
from io import BytesIO

st.set_page_config(page_title="Chatstat Data Viewer", layout="wide")

st.title("📊 Chatstat – Data Viewer")
st.markdown("Last opp en fil eller oppgi en URL for å se data i ulike diagrammer.")

# --- Funksjon for å laste data ---
def load_data(file_or_url):
    if isinstance(file_or_url, str):
        # Hent fra URL
        resp = requests.get(file_or_url)
        resp.raise_for_status()
        if file_or_url.endswith(".csv"):
            return pd.read_csv(BytesIO(resp.content))
        elif file_or_url.endswith(".xlsx"):
            return pd.read_excel(BytesIO(resp.content))
        elif file_or_url.endswith(".json"):
            return pd.read_json(BytesIO(resp.content))
        else:
            st.error("Filformat ikke støttet fra URL.")
            return None
    else:
        # Lokal fil
        if file_or_url.name.endswith(".csv"):
            return pd.read_csv(file_or_url)
        elif file_or_url.name.endswith(".xlsx"):
            return pd.read_excel(file_or_url)
        elif file_or_url.name.endswith(".json"):
            return pd.read_json(file_or_url)
        else:
            st.error("Filformat ikke støttet.")
            return None

# --- Sjekk om URL-parameter finnes ---
query_params = st.experimental_get_query_params()
df = None
if "url" in query_params:
    try:
        df = load_data(query_params["url"][0])
        st.success(f"Data lastet fra {query_params['url'][0]}")
    except Exception as e:
        st.error(f"Klarte ikke å laste fra URL: {e}")

# --- Filopplasting hvis ikke data allerede er lastet ---
if df is None:
    uploaded_file = st.file_uploader("Velg en fil (CSV, Excel, JSON)", type=["csv", "xlsx", "json"])
    if uploaded_file:
        try:
            df = load_data(uploaded_file)
            st.success("Fil lastet opp!")
        except Exception as e:
            st.error(f"Klarte ikke å lese fil: {e}")

if df is not None:
    st.subheader("Dataforhåndsvisning")
    st.dataframe(df.head())

    # --- Kolonnegjetting ---
    columns = df.columns.tolist()
    col_x = st.selectbox("X-akse (kategori eller dato)", options=columns)
    col_y = st.selectbox("Y-akse (verdi)", options=columns)
    col_group = st.selectbox("Gruppe/farge (valgfritt)", options=["Ingen"] + columns)

    # --- Filtrering av grupper ---
    if col_group != "Ingen":
        unique_groups = sorted(df[col_group].dropna().unique().tolist())
        selected_groups = st.multiselect("Velg grupper å vise", options=unique_groups, default=unique_groups)
        df = df[df[col_group].isin(selected_groups)]

    # --- Velg diagramtype ---
    chart_type = st.radio(
        "Velg diagramtype",
        ["Linje", "Stolpe", "Pizza", "Gruppert stolpe"],
        horizontal=True
    )

    # --- Plotting ---
    if chart_type == "Linje":
        chart = alt.Chart(df).mark_line(point=True).encode(
            x=col_x,
            y=col_y,
            color=col_group if col_group != "Ingen" else alt.value("steelblue"),
            tooltip=columns
        ).interactive()

    elif chart_type == "Stolpe":
        chart = alt.Chart(df).mark_bar().encode(
            x=col_x,
            y=col_y,
            color=col_group if col_group != "Ingen" else alt.value("steelblue"),
            tooltip=columns
        ).interactive()

    elif chart_type == "Pizza":
        if col_group == "Ingen":
            st.warning("Pizza krever at du velger en gruppekolonne.")
            chart = None
        else:
            chart = alt.Chart(df).mark_arc().encode(
                theta=alt.Theta(field=col_y, type="quantitative"),
                color=col_group,
                tooltip=columns
            )

    elif chart_type == "Gruppert stolpe":
        if col_group == "Ingen":
            st.warning("Gruppert stolpe krever at du velger en gruppekolonne.")
            chart = None
        else:
            chart = alt.Chart(df).mark_bar().encode(
                x=alt.X(f"{col_x}:N", axis=alt.Axis(title=col_x)),
                y=alt.Y(f"{col_y}:Q", axis=alt.Axis(title=col_y)),
                color=col_group,
                tooltip=columns
            ).properties(width=600).configure_axisX(labelAngle=-45)

    # --- Vis graf ---
    if chart:
        st.altair_chart(chart, use_container_width=True)

else:
    st.info("Last opp en fil eller oppgi en URL-parameter (?url=...) for å begynne.")
