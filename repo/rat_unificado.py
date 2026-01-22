# repo/rat_unificado.py
"""
RAT MAMINFO UNIFICADA - Lado Python (estado + gatilho de geração)

- Define valores padrão em st.session_state
- Chama o layout em ui_unificado.render_layout()
"""

import os
import sys
from datetime import date, time

import streamlit as st

# Garante que a pasta raiz (onde fica common/) está no sys.path
THIS_DIR = os.path.dirname(os.path.abspath(__file__))      # .../repo
PROJECT_ROOT = os.path.dirname(THIS_DIR)                   # raiz do projeto
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common.state import init_defaults
import ui_unificado  # arquivo de UI em repo/ui_unificado.py


def _init_rat_defaults():
    """
    Inicializa todos os campos da RAT Unificada no session_state.
    Assim evitamos erro de default em multiselect / etc.
    """

    init_defaults({
        # ========= 1) Dados do Relatório & Local de Atendimento =========
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
        "tipo_atendimento": [],     # multiselect
        "motivo_chamado": "",
        "checklist_tecnico_ok": [],  # multiselect de itens OK

        # ========= 3) Materiais & Equipamentos =========
        "material_utilizado": "",
        "equip_instalados": "",
        "equip_retirados": "",

        # ========= 4) Observações =========
        "testes_realizados": [],    # multiselect (Autenticação / Navegação / etc.)
        "descricao_atendimento": "",
        "observacoes_pendencias": "",

        # ========= 5) Aceite & Assinaturas =========
        # Técnico
        "tec_nome": "",
        "tec_documento": "",
        "tec_telefone": "",
        "tec_data": date.today(),
        "tec_hora": time(10, 0),

        # Cliente
        "cli_nome": "",
        "cli_documento": "",
        "cli_telefone": "",
        "cli_data": date.today(),
        "cli_hora": time(10, 30),

        # Assinaturas (common.ui.assinatura_dupla_png usa esses campos)
        "sig_tec_png": None,
        "sig_cli_png": None,

        # Controle de steps e geração
        "step_unificado": 1,
        "trigger_generate": False,
    })


def render():
    """
    Função principal chamada pelo app.py
    """
    _init_rat_defaults()

    ui_unificado.render_layout()  # desenha layout + controla step / botão

    ss = st.session_state
    if ss.get("trigger_generate"):
        # Aqui no futuro você chama a função de gerar PDF usando RAT_MAM_UNIFICADA_VF.pdf
        st.success("✅ RAT pronta para geração (a lógica de PDF entra aqui depois).")
        # Reseta o gatilho pra não ficar gerando em loop
        ss.trigger_generate = False
