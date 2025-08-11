# Chatstat (Streamlit Cloud)

En mobilvennlig, kilde-agnostisk app for å vise, rangere og dele statistikk fra mange kilder (Udir, SSB, kommuner, m.m.).
Klar til å deployes på **Streamlit Community Cloud**.

## Funksjoner
- Last opp CSV eller importer direkte fra URL (CSV/JSON)
- Kartlegg kolonner til standard felter: `region, år, indikator, verdi, enhet, kilde`
- Datasett-bibliotek med søk, filtre, grafer (Altair) og nedlasting
- Rangering på tvers av indikatorer med vekt (lavt vs. høyt er bra)
- Lagring i `data/`-mappen (per session i Streamlit Cloud kan være ephemeral – men fungerer for deling i økta)

## Deploy (Streamlit Cloud)
1. Opprett et nytt GitHub-repo, last opp filene i denne mappen.
2. Gå til https://share.streamlit.io/, koble repoet, og velg `app.py` som hovedfil.
3. Trykk **Deploy**.

