import streamlit as st

def init_defaults():
    defaults = {
        "equipamentos": [],
        "fotos": [],
        "assinatura_tecnico": None,
        "assinatura_cliente": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
