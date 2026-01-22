# repo/ui_unificado.py
"""
UI da RAT MAMINFO UNIFICADA (modo escuro, largura full, steps)

Etapas:
 1) Dados do Relatório & Local de Atendimento
 2) Atendimento & Testes
 3) Materiais & Equipamentos
 4) Observações
 5) Aceite & Assinaturas + botão Gerar RAT
"""

import os
from datetime import date, time

import streamlit as st

from common.ui import assinatura_dupla_png

# Caminho do logo (ajuste se o arquivo tiver outro nome)
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
LOGO_PATH = os.path.join(PROJECT_ROOT, "assets", "evernex_maminfo.png")


# ========== Helpers de layout ==========

def apply_dark_full_layout():
    """
    CSS para modo escuro "full width".
    """
    st.markdown(
        """
        <style>
        .main {
            background-color: #020617;
        }
        [data-testid="stAppViewContainer"] {
            background-color: #020617;
        }
        [data-testid="stHeader"] {
            background-color: transparent;
        }
        .block-container {
            padding-top: 1rem;
            padding-bottom: 3rem;
            max-width: 1200px;
        }
        .rat-card {
            background: #0f172a;
            border-radius: 18px;
            padding: 18px 22px;
            border: 1px solid #1e293b;
        }
        .step-pill {
            padding: 6px 12px;
            border-radius: 999px;
            border: 1px solid #1e293b;
            color: #e5e7eb;
            font-size: 0.78rem;
            margin-right: 6px;
        }
        .step-pill-active {
            background: linear-gradient(135deg, #0ea5e9, #22c55e);
            border-color: transparent;
            color: #0b1120;
            font-weight: 600;
        }
        .step-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: #e5e7eb;
            margin-bottom: 0.4rem;
        }
        .step-subtitle {
            font-size: 0.85rem;
            color: #9ca3af;
        }
        label, .stTextInput label, .stNumberInput label, .stDateInput label, .stTimeInput label {
            color: #e5e7eb !important;
        }
        textarea, input {
            background-color: #020617 !important;
            color: #e5e7eb !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def header_bar():
    """
    Topo com logo + título.
    """
    col_logo, col_title = st.columns([1, 4])
    with col_logo:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH)
        else:
            st.markdown("### Evernex / maminfo")

    with col_title:
        st.markdown(
            "<h2 style='color:#e5e7eb; margin-bottom:0;'>RAT MAMINFO – Modelo Unificado</h2>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='color:#9ca3af; font-size:0.9rem;'>Relatório de Atendimento Técnico – preenchimento digital organizado em etapas.</p>",
            unsafe_allow_html=True,
        )


def step_indicator(current_step: int):
    steps = {
        1: "Dados do Relatório & Local",
        2: "Atendimento & Testes",
        3: "Materiais & Equipamentos",
        4: "Observações",
        5: "Aceite & Assinaturas",
    }
    row = ""
    for i, label in steps.items():
        cls = "step-pill step-pill-active" if i == current_step else "step-pill"
        row += f"<span class='{cls}'>{i}. {label}</span>"
    st.markdown(row, unsafe_allow_html=True)


def _ensure_multiselect_list(value, options):
    """
    Garante que o valor salvo no session_state é uma lista
    e só contém itens válidos.
    """
    if value is None or value == "":
        return []
    if not isinstance(value, (list, tuple)):
        value = [value]
    return [v for v in value if v in options]


# ========== Etapas ==========

def step_1_dados_relatorio(ss):
    st.markdown("<div class='step-title'>1) Dados do Relatório & Local de Atendimento</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='step-subtitle'>Identificação do atendimento, cliente e deslocamento.</div>",
        unsafe_allow_html=True,
    )

    with st.container():
        with st.container():
            c1, c2, c3 = st.columns([1.2, 1.2, 1.2])
            with c1:
                ss.rel_numero = st.text_input("N° Relatório", value=ss.rel_numero)
            with c2:
                ss.chamado_numero = st.text_input("N° Chamado", value=ss.chamado_numero)
            with c3:
                ss.operadora_contrato = st.text_input("Operadora / Contrato", value=ss.operadora_contrato)

        ss.cliente_razao = st.text_input("Cliente / Razão Social", value=ss.cliente_razao)

        c4, c5 = st.columns([1, 1])
        with c4:
            ss.contato = st.text_input("Contato", value=ss.contato)
        with c5:
            ss.telefone_email = st.text_input("Telefone / E-mail", value=ss.telefone_email)

        ss.endereco_completo = st.text_input(
            "Endereço Completo (Rua, n°, compl., bairro, cidade/UF)",
            value=ss.endereco_completo,
        )

        c6, c7, c8 = st.columns([1, 1, 1])
        with c6:
            ss.data_atendimento = st.date_input(
                "Data",
                value=ss.data_atendimento if isinstance(ss.data_atendimento, date) else date.today(),
            )
        with c7:
            ss.hora_inicio = st.time_input(
                "Início",
                value=ss.hora_inicio if isinstance(ss.hora_inicio, time) else time(8, 0),
            )
            ss.hora_termino = st.time_input(
                "Término",
                value=ss.hora_termino if isinstance(ss.hora_termino, time) else time(10, 0),
            )
        with c8:
            ss.distancia_km = st.number_input(
                "Distância (KM)",
                min_value=0.0,
                step=1.0,
                value=float(ss.distancia_km) if ss.distancia_km is not None else 0.0,
            )


def step_2_atendimento_testes(ss):
    st.markdown("<div class='step-title'>2) Atendimento & Testes</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='step-subtitle'>Responsáveis técnicos, motivo e checklists de condição do circuito.</div>",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        ss.analista_suporte = st.text_input("Analista Suporte", value=ss.analista_suporte)
    with c2:
        ss.analista_integradora = st.text_input("Analista Integradora (MAMINFO)", value=ss.analista_integradora)
    with c3:
        ss.analista_validador = st.text_input("Analista validador (NOC / Projetos)", value=ss.analista_validador)

    tipo_opts = [
        "Instalação",
        "Verificação",
        "Ativação",
        "Retirada",
        "Manut. Corretiva",
        "Passagem de cabo",
        "Manut. Preventiva",
        "Outros",
    ]
    current_tipo = _ensure_multiselect_list(ss.tipo_atendimento, tipo_opts)
    ss.tipo_atendimento = st.multiselect(
        "Tipo de Atendimento",
        options=tipo_opts,
        default=current_tipo,
        help="Você pode marcar mais de um tipo, se necessário.",
    )

    ss.motivo_chamado = st.text_area(
        "Anormalidade / Motivo do Chamado",
        value=ss.motivo_chamado,
        height=90,
    )

    st.markdown("**Checklist Técnico (SIM / NÃO)** – marque os itens que estão *OK* (Sim):")
    checklist_opts = [
        "Circuito corretamente instalado",
        "Teste de circuito normal",
        "Alimentação adequada",
        "Aterramento adequado",
        "Mensagem com erro",
        "Sem portadora",
        "Fiação interna adequada",
        "Cabo de rede adequado",
        "Equipamentos em condições",
        "Ambiente/infra adequada",
    ]
    current_ck = _ensure_multiselect_list(ss.checklist_tecnico_ok, checklist_opts)
    ss.checklist_tecnico_ok = st.multiselect(
        "Itens em condição adequada (Sim):",
        options=checklist_opts,
        default=current_ck,
    )


def step_3_materiais_equip(ss):
    st.markdown("<div class='step-title'>3) Materiais & Equipamentos</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='step-subtitle'>Materiais aplicados e situação dos equipamentos no cliente.</div>",
        unsafe_allow_html=True,
    )

    ss.material_utilizado = st.text_area(
        "Material utilizado",
        value=ss.material_utilizado,
        height=100,
        placeholder="Ex.: Cabo UTP cat.6 – 30m; Conector RJ45 – 8 unidades; Patch cord – 2 unidades; etc.",
    )

    ss.equip_instalados = st.text_area(
        "Equipamentos (Instalados / Existentes no Cliente)",
        value=ss.equip_instalados,
        height=120,
        placeholder="Ex.: Switch Datacom DM2100 – S/N XXXXX; Gateway Aligera – S/N XXXXX; etc.",
    )

    ss.equip_retirados = st.text_area(
        "Equipamentos Retirados (se houver)",
        value=ss.equip_retirados,
        height=100,
        placeholder="Descreva equipamentos retirados, se aplicável.",
    )


def step_4_observacoes(ss):
    st.markdown("<div class='step-title'>4) Observações</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='step-subtitle'>Resultados de testes, descrição do atendimento e pendências.</div>",
        unsafe_allow_html=True,
    )

    testes_opts = [
        "Autenticação",
        "Navegação",
        "Sincronismo",
        "Ping/Latência",
        "Throughput",
    ]
    current_testes = _ensure_multiselect_list(ss.testes_realizados, testes_opts)
    ss.testes_realizados = st.multiselect(
        "Testes realizados (check list)",
        options=testes_opts,
        default=current_testes,
    )

    ss.descricao_atendimento = st.text_area(
        "Descrição do Atendimento (o que foi feito / resultado / evidências)",
        value=ss.descricao_atendimento,
        height=180,
    )

    ss.observacoes_pendencias = st.text_area(
        "Observações / Pendências",
        value=ss.observacoes_pendencias,
        height=120,
    )


def step_5_aceite_assinaturas(ss):
    st.markdown("<div class='step-title'>5) Aceite & Assinaturas</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='step-subtitle'>Dados de aceite do técnico MAMINFO e do cliente, com assinaturas.</div>",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Técnico MAMINFO**")
        ss.tec_nome = st.text_input("Nome Técnico", value=ss.tec_nome)
        ss.tec_documento = st.text_input("Documento Técnico", value=ss.tec_documento)
        ss.tec_telefone = st.text_input("Telefone Técnico", value=ss.tec_telefone)
        ss.tec_data = st.date_input(
            "Data (técnico)",
            value=ss.tec_data if isinstance(ss.tec_data, date) else date.today(),
        )
        ss.tec_hora = st.time_input(
            "Hora (técnico)",
            value=ss.tec_hora if isinstance(ss.tec_hora, time) else time(10, 0),
        )

    with c2:
        st.markdown("**Cliente**")
        ss.cli_nome = st.text_input("Nome cliente", value=ss.cli_nome)
        ss.cli_documento = st.text_input("Documento cliente", value=ss.cli_documento)
        ss.cli_telefone = st.text_input("Telefone cliente", value=ss.cli_telefone)
        ss.cli_data = st.date_input(
            "Data (cliente)",
            value=ss.cli_data if isinstance(ss.cli_data, date) else date.today(),
        )
        ss.cli_hora = st.time_input(
            "Hora (cliente)",
            value=ss.cli_hora if isinstance(ss.cli_hora, time) else time(10, 30),
        )

    st.markdown("---")
    st.markdown("**Assinaturas (técnico e cliente)**")
    assinatura_dupla_png()  # usa sig_tec_png e sig_cli_png em session_state


# ========== Layout principal ==========

def render_layout():
    """
    Renderiza todo o layout em modo escuro, controla steps e botão de gerar.
    Usa st.session_state.step_unificado (1..5).
    """
    apply_dark_full_layout()
    header_bar()

    ss = st.session_state
    step = int(ss.get("step_unificado", 1))

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

    # Navegação entre etapas + Gerar RAT
    col_back, col_step, col_next = st.columns([1, 2, 1])
    with col_back:
        if step > 1:
            if st.button("⬅️ Voltar", use_container_width=True):
                ss.step_unificado = step - 1

    with col_step:
        st.markdown(
            f"<p style='text-align:center; color:#9ca3af;'>Etapa {step} de 5</p>",
            unsafe_allow_html=True,
        )

    with col_next:
        if step < 5:
            if st.button("Próxima etapa ➡️", use_container_width=True):
                ss.step_unificado = step + 1
        else:
            if st.button("✅ Gerar RAT", use_container_width=True):
                ss.trigger_generate = True
