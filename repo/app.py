# repo/app.py — Hub de RATs (indentação limpa, sem tabs)

# --- PATH FIX: permite importar common/ e pdf_templates/ a partir da raiz ---
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)  # sobe 1 nível (raiz do repo)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
# ---------------------------------------------------------------------------

import streamlit as st

# Imports do app (depois do PATH FIX)
import rat_mam
import rat_oi_cpe
from common.state import load_from_query_params, get_initial_payload_url

st.set_page_config(page_title="RAT – Hub", layout="centered")
st.title("📄 Hub de RATs")

# Carrega dados vindos por query params (se abriu via link)
load_from_query_params()

# Seletor de modelo
modelo = st.selectbox("Escolha o modelo de RAT", ["RAT MAM", "RAT OI CPE NOVO"])

# (Opcional) URLs para abrir cada fluxo em deploy isolado
ISOLATED_URLS = {
    "RAT MAM": None,          # ex.: "https://rat-mam.seuapp.streamlit.app"
    "RAT OI CPE NOVO": None,  # ex.: "https://rat-oi-cpe.seuapp.streamlit.app"
}

col1, col2 = st.columns([3, 2])

with col1:
    st.caption("Preencher aqui no Hub")
    try:
        if modelo == "RAT MAM":
            rat_mam.render()
        else:
            rat_oi_cpe.render()
    except Exception as e:
        st.error("Falha ao renderizar a página selecionada, mas o Hub continua ativo.")
        st.exception(e)

with col2:
    st.caption("Ou abrir em app isolado")
    url = ISOLATED_URLS.get(modelo)
    if url:
        st.link_button("Abrir em app isolado ↗", get_initial_payload_url(url))
    else:
        st.info("Deploy isolado não configurado. Defina a URL em ISOLATED_URLS se quiser.")
