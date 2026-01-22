# repo/rat_mam_unificada.py
import streamlit as st
from datetime import date, time
from common.state import init_defaults
from ui_rat_unificada import render_layout
from common.pdf import open_pdf_template  # depois você usa para gerar o PDF

def render():
    init_defaults({
        "data_atendimento": date.today(),
        "hora_inicio": time(8, 0),
        "hora_termino": time(10, 0),
        "cliente": "",
        "numero_chamado": "",
        "analista_mam": "",
        # ... (resto dos campos que o layout usa, se quiser default)
    })

    render_layout()   # desenha só a UI

    st.divider()
    if st.button("🧾 Gerar RAT Unificada (PDF)"):
        st.warning("Aqui entra a lógica de geração do PDF usando o RAT_MAM_UNIFICADA_VF.pdf.")
        # pdf_bytes = gerar_pdf_unificado(st.session_state)
        # st.download_button(...)


# e no app.py:
# import rat_mam_unificada
# ...
# if modo == "RAT MAM Unificada":
#     rat_mam_unificada.render()
