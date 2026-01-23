# repo/ui_unificado.py
"""
Camada de UI da RAT Unificada:
- Layout dark, largura full
- Navegação em 5 etapas
- Campos organizados conforme especificação
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

from common.ui import assinatura_dupla_png  # type: ignore

# ---------- opções de select / checklist ----------
TIPO_ATENDIMENTO_OPCOES = [
    "Instalação",
    "Manutenção",
    "Ativação",
    "Migração",
    "Suporte remoto",
    "Outro",
]

CHECKLIST_TECNICO_OPCOES = [
    "Checklist físico (cabos, patch panel, rack)",
    "Checklist lógico (IPs, VLANs, roteamento)",
    "Checklist de segurança (firewall, senhas)",
]

TESTES_REALIZADOS_OPCOES = [
    "PING",
    "Navegação",
    "Speedtest",
    "Testes de voz / chamadas",
    "Teste de acesso a sistemas do cliente",
]


# ========= helpers de layout =========
def apply_dark_full_layout():
    """
    CSS pra modo escuro mais bonitinho e cards full width.
    """
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 0.5rem !important;
            padding-bottom: 2rem !important;
            max-width: 1200px;
        }
        body {
            background-color: #020617;
            color: #e5e7eb;
        }
        .rat-card {
            background: radial-gradient(circle at top left, #0f172a, #020617);
            border-radius: 18px;
            padding: 1.25rem 1.4rem;
            border: 1px solid rgba(148, 163, 184, 0.4);
            box-shadow: 0 18px 50px rgba(15, 23, 42, 0.85);
        }
        .rat-header {
            padding: 0.75rem 0 0.25rem 0;
            border-bottom: 1px solid rgba(148, 163, 184, 0.35);
            margin-bottom: 0.2rem;
        }
        .rat-title {
            font-size: 1.35rem;
            font-weight: 600;
            color: #e5e7eb;
        }
        .rat-subtitle {
            font-size: 0.9rem;
            color: #9ca3af;
        }
        .step-pill {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.25rem 0.7rem;
            border-radius: 999px;
            margin-right: 0.4rem;
            font-size: 0.8rem;
            border: 1px solid rgba(148,163,184,0.4);
        }
        .step-pill-active {
            background: linear-gradient(90deg, #22c55e, #4ade80);
            color: #022c22;
            border-color: transparent;
            font-weight: 600;
        }
        .step-pill-done {
            background: linear-gradient(90deg, #0ea5e9, #38bdf8);
            color: #02131f;
            border-color: transparent;
        }
        .step-pill-pending {
            background: transparent;
            color: #9ca3af;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _resolve_logo_path() -> str:
    root = PROJECT_ROOT
    # ajuste se o nome do arquivo for outro
    for name in ["evernex_logo_branco.png", "evernex_logo.png", "logo_evernex.png"]:
        p = os.path.join(root, "assets", name)
        if os.path.exists(p):
            return p
    return ""


def header_bar():
    logo_path = _resolve_logo_path()
    with st.container():
        col_logo, col_title = st.columns([1, 4])
        with col_logo:
            if logo_path:
                st.image(logo_path)
            else:
                st.markdown("### Evernex")
        with col_title:
            st.markdown(
                "<div class='rat-header'>"
                "<div class='rat-title'>RAT MAMINFO – Relatório Unificado</div>"
                "<div class='rat-subtitle'>Registro padronizado de atendimento técnico em campo</div>"
                "</div>",
                unsafe_allow_html=True,
            )


def step_indicator(current_step: int):
    labels = {
        1: "Dados do Relatório & Local",
        2: "Atendimento & Testes",
        3: "Materiais & Equipamentos",
        4: "Observações",
        5: "Aceite & Assinaturas",
    }
    pills = []
    for i in range(1, 6):
        if i < current_step:
            cls = "step-pill step-pill-done"
        elif i == current_step:
            cls = "step-pill step-pill-active"
        else:
            cls = "step-pill step-pill-pending"
        pills.append(
            f"<span class='{cls}'>Etapa {i} – {labels[i]}</span>"
        )
    st.markdown(" ".join(pills), unsafe_allow_html=True)


# ========= ETAPAS =========
def step_1_dados_relatorio(ss):
    st.subheader("1) Dados do Relatório & Local de Atendimento")

    c1, c2, c3 = st.columns([1.2, 1.2, 1])
    with c1:
        ss.rel_numero = st.text_input("N° Relatório", value=ss.get("rel_numero", ""))
        ss.chamado_numero = st.text_input("N° Chamado", value=ss.get("chamado_numero", ""))
        ss.operadora_contrato = st.text_input(
            "Operadora / Contrato", value=ss.get("operadora_contrato", "")
        )
    with c2:
        ss.cliente_razao = st.text_input(
            "Cliente / Razão Social", value=ss.get("cliente_razao", "")
        )
        ss.contato = st.text_input("Contato", value=ss.get("contato", ""))
        ss.telefone_email = st.text_input(
            "Telefone / E-mail", value=ss.get("telefone_email", "")
        )
    with c3:
        ss.data_atendimento = st.date_input(
            "Data", value=ss.get("data_atendimento", date.today())
        )
        ss.hora_inicio = st.time_input(
            "Início", value=ss.get("hora_inicio", time(8, 0))
        )
        ss.hora_termino = st.time_input(
            "Término", value=ss.get("hora_termino", time(10, 0))
        )
        ss.distancia_km = st.number_input(
            "Distância (KM)", min_value=0.0, step=0.5, value=float(ss.get("distancia_km", 0.0))
        )

    ss.endereco_completo = st.text_area(
        "Endereço Completo (Rua, n°, compl., bairro, cidade/UF)",
        value=ss.get("endereco_completo", ""),
        height=70,
    )


def step_2_atendimento_testes(ss):
    st.subheader("2) Atendimento & Testes")

    c1, c2 = st.columns(2)
    with c1:
        ss.analista_suporte = st.text_input(
            "Analista Suporte", value=ss.get("analista_suporte", "")
        )
        ss.analista_integradora = st.text_input(
            "Analista Integradora (MAMINFO)", value=ss.get("analista_integradora", "")
        )
    with c2:
        ss.analista_validador = st.text_input(
            "Analista validador (NOC / Projetos)",
            value=ss.get("analista_validador", ""),
        )

    # Tipo de atendimento (checklist)
    default_tipo = ss.get("tipo_atendimento", [])
    default_tipo = [x for x in default_tipo if x in TIPO_ATENDIMENTO_OPCOES]
    ss.tipo_atendimento = st.multiselect(
        "Tipo de Atendimento",
        options=TIPO_ATENDIMENTO_OPCOES,
        default=default_tipo,
    )

    ss.motivo_chamado = st.text_area(
        "Anormalidade / Motivo do Chamado",
        value=ss.get("motivo_chamado", ""),
        height=90,
    )

    default_check = ss.get("checklist_tecnico_ok", [])
    default_check = [x for x in default_check if x in CHECKLIST_TECNICO_OPCOES]
    ss.checklist_tecnico_ok = st.multiselect(
        "Checklist Técnico (SIM / NÃO)",
        options=CHECKLIST_TECNICO_OPCOES,
        default=default_check,
        help="Selecione os itens verificados durante o atendimento.",
    )


def step_3_materiais_equip(ss):
    st.subheader("3) Materiais & Equipamentos")

    ss.material_utilizado = st.text_area(
        "Material utilizado",
        value=ss.get("material_utilizado", ""),
        height=90,
        placeholder="Ex.: 20m cabo UTP cat.6, 10 conectores RJ45, patch cords, etc.",
    )

    ss.equip_instalados = st.text_area(
        "Equipamentos (Instalados)",
        value=ss.get("equip_instalados", ""),
        height=100,
        placeholder="Ex.: AP Intelbras 3650 SN XXXXX, Switch Datacom DM2100 SN YYYYY...",
    )

    ss.equip_retirados = st.text_area(
        "Equipamentos Retirados (se houver)",
        value=ss.get("equip_retirados", ""),
        height=80,
        placeholder="Liste equipamentos retirados, se aplicável.",
    )


def step_4_observacoes(ss):
    st.subheader("4) Observações")

    default_testes = ss.get("testes_realizados", [])
    default_testes = [x for x in default_testes if x in TESTES_REALIZADOS_OPCOES]
    ss.testes_realizados = st.multiselect(
        "Testes realizados (check list)",
        options=TESTES_REALIZADOS_OPCOES,
        default=default_testes,
    )

    ss.descricao_atendimento = st.text_area(
        "Descrição do Atendimento (o que foi feito / resultado / evidências)",
        value=ss.get("descricao_atendimento", ""),
        height=140,
    )

    ss.observacoes_pendencias = st.text_area(
        "Observações / Pendências",
        value=ss.get("observacoes_pendencias", ""),
        height=100,
    )


def step_5_aceite_assinaturas(ss):
    st.subheader("5) Aceite & Assinaturas")

    st.markdown("### Técnico MAMINFO")
    col1, col2, col3, col4 = st.columns([1.5, 1.5, 1.2, 1.2])
    with col1:
        ss.tec_nome = st.text_input("Nome Técnico", value=ss.get("tec_nome", ""))
    with col2:
        ss.tec_documento = st.text_input(
            "Documento Técnico", value=ss.get("tec_documento", "")
        )
    with col3:
        ss.tec_telefone = st.text_input(
            "Telefone Técnico", value=ss.get("tec_telefone", "")
        )
    with col4:
        ss.tec_data = st.date_input(
            "Data", value=ss.get("tec_data", date.today())
        )
        ss.tec_hora = st.time_input(
            "Hora", value=ss.get("tec_hora", time(10, 0))
        )

    st.markdown("---")

    st.markdown("### Cliente / Responsável local")
    c1, c2, c3, c4 = st.columns([1.5, 1.5, 1.2, 1.2])
    with c1:
        ss.cli_nome = st.text_input("Nome cliente", value=ss.get("cli_nome", ""))
    with c2:
        ss.cli_documento = st.text_input(
            "Documento cliente", value=ss.get("cli_documento", "")
        )
    with c3:
        ss.cli_telefone = st.text_input(
            "Telefone cliente", value=ss.get("cli_telefone", "")
        )
    with c4:
        ss.cli_data = st.date_input(
            "Data ", value=ss.get("cli_data", date.today())
        )
        ss.cli_hora = st.time_input(
            "Hora ", value=ss.get("cli_hora", time(10, 30))
        )

    st.markdown("---")
    st.markdown("### Assinaturas (técnico e cliente)")

    # Usa o mesmo componente de assinaturas que você já tem no projeto
    assinatura_dupla_png()


# ========= RENDER PRINCIPAL =========
def render_layout():
    """
    Renderiza todo o layout em modo escuro, controla steps e botão de gerar.
    Usa st.session_state.step_unificado (1..5).
    """
    apply_dark_full_layout()
    header_bar()

    ss = st.session_state

    if "step_unificado" not in ss:
        ss.step_unificado = 1
    step = int(ss.step_unificado)
    step = max(1, min(5, step))
    ss.step_unificado = step

    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
    step_indicator(step)
    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)

    # Card principal
    with st.container():
        st.markdown("<div class='rat-card'>", unsafe_allow_html=True)

        if step == 1:
            step_1_dados_relatorio(ss)
        elif step == 2:
            step_2_atendimento_testes(ss)
        elif step == 3:
            step_3_materiais_equip(ss)
        elif step == 4:
            step_4_observacoes(ss)
        elif step == 5:
            step_5_aceite_assinaturas(ss)

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)

    # Navegação + botão Gerar RAT
    col_back, col_step, col_next = st.columns([1, 2, 1])

    with col_back:
        if step > 1:
            if st.button(
                "⬅️ Voltar",
                key=f"btn_back_step_{step}",
                use_container_width=True,
            ):
                ss.step_unificado = max(1, step - 1)

    with col_step:
        st.markdown(
            f"<p style='text-align:center; color:#9ca3af;'>Etapa {step} de 5</p>",
            unsafe_allow_html=True,
        )

    with col_next:
        if step < 5:
            if st.button(
                "Próxima etapa ➡️",
                key=f"btn_next_step_{step}",
                use_container_width=True,
            ):
                ss.step_unificado = min(5, step + 1)
        else:
            if st.button(
                "✅ Gerar RAT",
                key="btn_gerar_rat",
                use_container_width=True,
            ):
                ss.trigger_generate = True
