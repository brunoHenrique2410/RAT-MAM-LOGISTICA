import streamlit as st
import ui_unificado
from rat_unificado import gerar_pdf
from common.state import init_defaults

st.set_page_config(page_title="RAT MAM – Unificada", layout="wide")

init_defaults({
    "cliente": "",
    "numero_chamado": "",
    "analista": "",
    "cnpj": "",
    "contato_nome": "",
    "contato_tel": "",
    "endereco": "",
    "cidade_uf": "",
})

ss = st.session_state

tabs = st.tabs(["Identificação", "Operacional", "Aceite", "Página 2", "Fotos"])

with tabs[0]:
    ui_unificado.page_identificacao(ss)

st.divider()

if st.button("Gerar RAT MAM Unificada (PDF)"):
    pdf_bytes = gerar_pdf(ss)
    st.download_button(
        "Baixar PDF",
        data=pdf_bytes,
        file_name=f"RAT_MAM_UNIFICADA_{ss.numero_chamado or 'sem_num'}.pdf",
        mime="application/pdf"
    )
