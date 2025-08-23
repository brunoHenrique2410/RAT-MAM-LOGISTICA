import streamlit as st
from urllib.parse import urlencode

def init_defaults(defaults: dict):
    ss = st.session_state
    for k, v in defaults.items():
        if k not in ss:
            ss[k] = v

BASIC_KEYS = ["cliente", "numero_chamado", "hora_inicio", "hora_termino"]

def get_initial_payload_url(base_url: str) -> str:
    params = {}
    ss = st.session_state
    for k in BASIC_KEYS:
        val = ss.get(k)
        if val is None:
            continue
        params[k] = str(val)
    return f"{base_url}?{urlencode(params)}"

def load_from_query_params():
    qs = st.query_params
    ss = st.session_state
    for k in BASIC_KEYS:
        if k in qs and k not in ss:
            ss[k] = qs.get(k)
