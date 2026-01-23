# repo/rat_unificado.py
"""
RAT UNIFICADA – núcleo lógico:
- Define defaults da sessão
- Chama o layout (ui_unificado.render_layout)
- Dispara geração de PDF quando ss.trigger_generate = True
"""

import os
import sys
from datetime import date, time

import streamlit as st

# ---------- PATHS ----------
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common.state import init_defaults  # type: ignore
import ui_unificado  # type: ignore
# no momento só preparamos o template; geração vem depois
from common.pdf import open_pdf_template  # type: ignore

PDF_DIR = os.path.join(PROJECT_ROOT, "pdf_templates")
RAT_UNIFICADA_TEMPLATE = os.path.join(PDF_DIR, "RAT_MAM_UNIFICADA_VF.pdf")


def _init_rat_defaults():
    """
    Inicializa somente os campos de dados.
    step_unificado e trigger_generate são controlados manualmente.
    """
    init_defaults({
        # ========= 1) Dados do Relatório & Local =========
        "rel_numero": "",
        "chamado_numero": "",
        "operadora_contrato": "",
        "cliente_razao": "",
        "contato": "",
        "endereco_completo": "",
        "telefone_email": "",
        "distancia_km": 0.0,
        "data_atendimento": date.today(),
        "hora_inicio": time(8, 0),
        "hora_termino": time(10, 0),

        # ========= 2) Atendimento & Testes =========
        "analista_suporte": "",
        "analista_integradora": "",
        "analista_validador": "",
        "tipo_atendimento": [],
        "motivo_chamado": "",
        "checklist_tecnico_ok": [],

        # ========= 3) Materiais & Equipamentos =========
        "material_utilizado": "",
        "equip_instalados": "",
        "equip_retirados": "",

        # ========= 4) Observações & Testes =========
        "testes_realizados": [],
        "descricao_atendimento": "",
        "observacoes_pendencias": "",

        # ========= 5) Aceite & Assinaturas =========
        "tec_nome": "",
        "tec_documento": "",
        "tec_telefone": "",
        "tec_data": date.today(),
        "tec_hora": time(10, 0),

        "cli_nome": "",
        "cli_documento": "",
        "cli_telefone": "",
        "cli_data": date.today(),
        "cli_hora": time(10, 30),

        "sig_tec_png": None,
        "sig_cli_png": None,
    })

    ss = st.session_state
    if "step_unificado" not in ss:
        ss.step_unificado = 1
    if "trigger_generate" not in ss:
        ss.trigger_generate = False


def _generate_pdf_from_state():
    """
    Placeholder de geração de PDF.
    Aqui depois a gente mapeia os campos para RAT_MAM_UNIFICADA_VF.pdf.
    Por enquanto só mostra uma mensagem pra não quebrar o app.
    """
    st.info("🧾 Geração do PDF da RAT Unificada ainda não está implementada aqui.\n"
            "Os dados da tela já estão prontos para serem mapeados para o template "
            "`RAT_MAM_UNIFICADA_VF.pdf`.")


def render():
    """
    Função principal chamada pelo app.py
    """
    _init_rat_defaults()

    # desenha layout + controla navegação / botões
    ui_unificado.render_layout()

    ss = st.session_state

    # Se o botão 'Gerar RAT' da etapa 5 for clicado
    if ss.get("trigger_generate"):
        ss.trigger_generate = False  # reseta flag
        _generate_pdf_from_state()
