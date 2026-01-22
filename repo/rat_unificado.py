# repo/rat_unificado.py
import os
import sys
from datetime import datetime

import streamlit as st

# Ajuste de PATH para achar 'common'
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common.state import init_defaults
from common import pdf as pdf_utils  # para depois usar open_pdf_template etc.
import ui_unificado  # layout visual


PDF_DIR = os.path.join(PROJECT_ROOT, "pdf_templates")
PDF_BASE_PATH = os.path.join(PDF_DIR, "RAT_MAM_UNIFICADA_VF.pdf")


def _init_rat_defaults():
    """
    Inicializa todos os campos usados na RAT unificada.
    """
    init_defaults({
        # === Identificação do chamado / relatório ===
        "numero_relatorio": "",
        "numero_chamado": "",
        "operadora_contrato": "",
        "cliente_nome": "",
        "codigo_ul_circuito": "",
        "localidade": "",

        # === Equipe técnica ===
        "analista_suporte": "",
        "analista_validador": "",

        # === Atendimento / operação ===
        "tipo_atendimento": [],  # checklist (lista de strings)
        "distancia_km": 0.0,
        "testes_executados": [],  # checklist (lista de strings)
        "resumo_atividade": "",
        "observacoes_gerais": "",

        # === Materiais / equipamentos ===
        "material_utilizado": "",
        "equipamentos_retirados": "",
        "equipamentos_instalados": "",

        # === Assinaturas ===
        "tecnico_nome": "",
        "tecnico_telefone": "",
        "tecnico_documento": "",
        "cliente_ass_nome": "",
        "cliente_ass_telefone": "",
        "cliente_ass_documento": "",

        # === Fluxo de tela ===
        "rat_step": 1,          # 1 = preencher, 2 = revisar/gerar
        "trigger_generate": False,
    })


def generate_pdf_unificado(ss: st.session_state):
    """
    ⚠️ STUB por enquanto.
    Aqui vamos mapear os campos da RAT unificada para o template
    RAT_MAM_UNIFICADA_VF.pdf usando common.pdf / PyMuPDF.

    Por enquanto, só mostra uma mensagem.
    """
    st.warning(
        "Gatilho de geração de PDF recebido. "
        "A etapa de mapeamento para o template 'RAT_MAM_UNIFICADA_VF.pdf' "
        "ainda será implementada."
    )

    # Exemplo de como será no futuro (comentado):
    # try:
    #     doc, page1 = pdf_utils.open_pdf_template(PDF_BASE_PATH, hint="RAT_MAM_UNIFICADA")
    #     # TODO: usar pdf_utils.insert_right_of, insert_textbox, etc.
    #     #       para preencher o template com os campos de ss.
    #     out = BytesIO()
    #     doc.save(out)
    #     doc.close()
    #     st.download_button(
    #         "⬇️ Baixar RAT Unificada",
    #         data=out.getvalue(),
    #         file_name=f"RAT_UNIFICADA_{ss.numero_chamado or 'sem_chamado'}.pdf",
    #         mime="application/pdf",
    #     )
    # except Exception as e:
    #     st.error("Falha ao gerar PDF da RAT Unificada.")
    #     st.exception(e)


def render():
    """
    Função principal chamada pelo app.py
    """
    _init_rat_defaults()
    ui_unificado.render_layout()  # desenha layout + controla step / botões

    ss = st.session_state
    if ss.get("trigger_generate"):
        # Reseta o gatilho e chama a geração (stub por enquanto)
        ss.trigger_generate = False
        generate_pdf_unificado(ss)
