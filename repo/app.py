
# PATH FIX
import os, sys
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import streamlit as st
import rat_mam, rat_oi_cpe
from common.state import load_from_query_params, get_initial_payload_url

st.set_page_config(page_title="RAT – Hub", layout="centered")
st.title("📄 Hub de RATs")

# Carrega query params (se abriu via link com dados)
load_from_query_params()

modelo = st.selectbox("Escolha o modelo de RAT", ["RAT MAM", "RAT OI CPE NOVO"])

# (opcional) Deploys isolados: preencha URLs se quiser abrir em app separado
ISOLATED_URLS = {
    "RAT MAM": None,                 # ex.: "https://rat-mam.seuapp.streamlit.app"
    "RAT OI CPE NOVO": None,         # ex.: "https://rat-oi-cpe.seuapp.streamlit.app"
}

col1, col2 = st.columns([3,2])
with col1:
    st.caption("Preencher aqui no Hub")
    if modelo == "RAT MAM":
        rat_mam.render()
    else:
        rat_oi_cpe.render()

with col2:
    url = ISOLATED_URLS.get(modelo)
    st.caption("Ou abrir em app isolado")
    if url:
        st.link_button("Abrir em app isolado ↗", get_initial_payload_url(url))
    else:
        st.info("Não configurado. Para ativar, defina a URL no dicionário ISOLATED_URLS.")


