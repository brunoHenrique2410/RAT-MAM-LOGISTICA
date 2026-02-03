# repo/ui_unificado.py
#
# Layout em modo escuro para a RAT MAM Unificada.
# - Navegação por etapas via st.radio (topo)
# - Preenche st.session_state com os campos usados em rat_unificado.py
#   (NÃO mexe em nenhuma posição do PDF, só nos valores).

import os
from datetime import date

import streamlit as st

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
LOGO_PATH = os.path.join(PROJECT_ROOT, "assets", "selo_evernex_maminfo.png")


# ----------------- ESTILO / CABEÇALHO -----------------


def apply_dark_full_layout() -> None:
    """CSS básico de modo escuro + largura full."""
    st.markdown(
        """
        <style>
            /* fundo geral */
            .stApp {
                background-color: #050816;
            }
            .block-container {
                padding-top: 1.5rem;
                padding-bottom: 2rem;
                max-width: 1200px;
            }
            /* campos */
            .stTextInput>div>div>input,
            .stTextArea textarea,
            .stDateInput input,
            .stMultiselect>div>div>input,
            .stSelectbox>div>div>select {
                background-color: #111827 !important;
                color: #e5e7eb !important;
            }
            /* labels */
            label, .stRadio>div {
                color: #e5e7eb !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def header_bar() -> None:
    """Logo + título."""
    col_logo, col_title = st.columns([1, 4])
    with col_logo:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=140)
        else:
            st.markdown("### Evernex / MAMINFO")
    with col_title:
        st.markdown("## RAT MAM Unificada")
        st.caption("Relatório de Atendimento Técnico – Modelo Unificado")


def _step_selector() -> int:
    """Radio superior para escolher a etapa (sem mexer em PDF)."""
    ss = st.session_state
    if "current_step" not in ss:
        ss.current_step = 1

    steps = {
        1: "1) Dados do Relatório & Local",
        2: "2) Atendimento & Testes",
        3: "3) Checklist Técnico",
        4: "4) Materiais & Observações",
        5: "5) Aceite & Assinaturas",
    }

    step = st.radio(
        "Etapas",
        options=list(steps.keys()),
        index=list(steps.keys()).index(ss.current_step),
        format_func=lambda x: steps[x],
        horizontal=True,
    )
    ss.current_step = step
    st.divider()
    return step


# ----------------- ETAPA 1 -----------------


def step1_dados_relatorio() -> None:
    ss = st.session_state
    st.subheader("1) Dados do Relatório & Local de Atendimento")

    c1, c2, c3 = st.columns(3)
    with c1:
        ss.num_chamado = st.text_input("Nº Chamado", value=ss.num_chamado)
    with c2:
        ss.num_relatorio = st.text_input("Nº Relatório", value=ss.num_relatorio)
    with c3:
        ss.operadora_contrato = st.text_input(
            "Operadora / Contrato", value=ss.operadora_contrato
        )

    st.markdown("---")

    c4, c5 = st.columns([2, 1])
    with c4:
        ss.cliente_razao = st.text_input(
            "Cliente / Razão Social", value=ss.cliente_razao
        )
    with c5:
        ss.cnpj_cpf = st.text_input("CNPJ/CPF", value=ss.cnpj_cpf)

    c6, c7, c8 = st.columns([2, 1, 1])
    with c6:
        ss.contato_nome = st.text_input("Contato (nome)", value=ss.contato_nome)
    with c7:
        ss.contato_telefone_email = st.text_input(
            "Telefone / E-mail", value=ss.contato_telefone_email
        )
    with c8:
        # Distância em texto (PDF converte para float se possível)
        ss.distancia_km = st.text_input(
            "Distância (KM)", value=str(ss.distancia_km or "")
        )

    st.text("")  # pequeno espaçamento

    ss.endereco_completo = st.text_area(
        "Endereço Completo (Rua, nº, compl., bairro, cidade/UF)",
        value=ss.endereco_completo,
        height=80,
    )

    st.markdown("### Horários e Deslocamento")

    # Data do atendimento
    try:
        default_data = (
            date.fromisoformat(ss.data_atendimento)
            if ss.data_atendimento
            else date.today()
        )
    except Exception:
        default_data = date.today()

    c9, c10, c11 = st.columns(3)
    with c9:
        ss.data_atendimento = st.date_input("Data", value=default_data)
    with c10:
        ss.inicio_atend = st.text_input(
            "Início (hh:mm)", value=str(ss.inicio_atend or "")
        )
    with c11:
        ss.termino_atend = st.text_input(
            "Término (hh:mm)", value=str(ss.termino_atend or "")
        )


# ----------------- ETAPA 2 -----------------


ANORMALIDADE_OPCOES = [
    "Interrupção total",
    "Sem sincronismo",
    "Mensagem com erro",
    "Intermitência / Quedas",
    "Taxa de erro",
    "Sem portadora",
    "Lentidão",
    "Ruído",
    "Outros",
]

TIPO_ATENDIMENTO_OPCOES = [
    "",
    "Instalação",
    "Ativação",
    "Manut. Corretiva",
    "Manut. Preventiva",
    "Verificação",
    "Retirada",
    "Passagem de cabo",
    "Outros",
]


def step2_atendimento_testes() -> None:
    ss = st.session_state
    st.subheader("2) Atendimento & Testes")

    c1, c2, c3 = st.columns(3)
    with c1:
        ss.analista_suporte = st.text_input(
            "Analista Suporte", value=ss.analista_suporte
        )
    with c2:
        ss.analista_integradora = st.text_input(
            "Analista Integradora (MAMINFO)", value=ss.analista_integradora
        )
    with c3:
        ss.analista_validador = st.text_input(
            "Analista validador (NOC / Projetos)", value=ss.analista_validador
        )

    st.markdown("### Tipo de Atendimento")

    ss.tipo_atendimento = st.selectbox(
        "Tipo de Atendimento",
        options=TIPO_ATENDIMENTO_OPCOES,
        index=TIPO_ATENDIMENTO_OPCOES.index(ss.tipo_atendimento)
        if ss.tipo_atendimento in TIPO_ATENDIMENTO_OPCOES
        else 0,
    )

    st.markdown("### Anormalidade / Motivo do Chamado")

    # multiselect -> anormalidade_flags (lista de strings)
    default_flags = (
        [f for f in getattr(ss, "anormalidade_flags", []) if f in ANORMALIDADE_OPCOES]
        if isinstance(getattr(ss, "anormalidade_flags", []), list)
        else []
    )

    ss.anormalidade_flags = st.multiselect(
        "Selecione as anormalidades encontradas",
        options=ANORMALIDADE_OPCOES,
        default=default_flags,
        help="Essas opções serão usadas para marcar os X no PDF.",
    )

    ss.motivo_chamado = st.text_area(
        "Descrição adicional / Observações do motivo do chamado",
        value=ss.motivo_chamado,
        height=80,
    )


# ----------------- ETAPA 3 – CHECKLIST TÉCNICO -----------------


CHECKLIST_ITENS = [
    "Circuito corretamente instalado",
    "Teste de circuito comutado",
    "Alimentação adequada",
    "Aterramento adequado",
    "Mensagem com erro",
    "Intermitência / Quedas",
    "Sem portadora",
    "Fiação interna adequada",
    "Cabo de rede adequado",
    "Equipamentos em condições",
    "Ambiente/infra adequada",
]


def step3_checklist_tecnico() -> None:
    ss = st.session_state
    st.subheader("3) Checklist Técnico (SIM / NÃO)")

    # garante que é dict
    if not isinstance(getattr(ss, "checklist_tecnico", None), dict):
        ss.checklist_tecnico = {}

    for item in CHECKLIST_ITENS:
        atual = ss.checklist_tecnico.get(item, "")
        opts = ["", "Sim", "Não"]
        idx = opts.index(atual) if atual in opts else 0
        escolha = st.radio(
            item,
            options=opts,
            index=idx,
            horizontal=True,
            key=f"chk_{item}",
        )
        ss.checklist_tecnico[item] = escolha

    st.caption(
        "As respostas serão consolidadas em texto no campo de Checklist do PDF. "
        "Se quiser evoluir para marcar X em cada Sim/Não, depois mapeamos item a item."
    )


# ----------------- ETAPA 4 – MATERIAIS & OBSERVAÇÕES -----------------


TESTES_OPCOES = [
    "Ping",
    "Chamadas",
    "Navegação",
    "Teste de voz",
    "Teste de dados",
    "Velocidade",
    "Outros",
]


def step4_materiais_obs() -> None:
    ss = st.session_state
    st.subheader("4) Materiais & Observações")

    st.markdown("### Materiais & Equipamentos")

    ss.material_utilizado = st.text_area(
        "Material utilizado",
        value=ss.material_utilizado,
        height=80,
    )

    ss.equip_instalados = st.text_area(
        "Equipamentos (Instalados / Existentes no Cliente)",
        value=ss.equip_instalados,
        height=80,
    )

    ss.equip_retirados = st.text_area(
        "Equipamentos Retirados (se houver)",
        value=ss.equip_retirados,
        height=80,
    )

    st.markdown("### Observações do Atendimento")

    default_testes = (
        [t for t in getattr(ss, "testes_realizados", []) if t in TESTES_OPCOES]
        if isinstance(getattr(ss, "testes_realizados", []), list)
        else []
    )
    ss.testes_realizados = st.multiselect(
        "Testes realizados (check list)",
        options=TESTES_OPCOES,
        default=default_testes,
        help="Essas opções serão listadas em 'Testes realizados' no PDF.",
    )

    ss.descricao_atendimento = st.text_area(
        "Descrição do Atendimento (o que foi feito / resultado / evidências)",
        value=ss.descricao_atendimento,
        height=120,
    )

    ss.observacoes_pendencias = st.text_area(
        "Observações / Pendências",
        value=ss.observacoes_pendencias,
        height=100,
    )


# ----------------- ETAPA 5 – ACEITE & ASSINATURAS -----------------


def step5_aceite_assinaturas() -> None:
    ss = st.session_state
    st.subheader("5) Aceite & Assinaturas")

    st.markdown("#### Técnico MAMINFO")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ss.nome_tecnico = st.text_input(
            "Nome Técnico", value=ss.nome_tecnico
        )
    with c2:
        ss.doc_tecnico = st.text_input(
            "Documento Técnico", value=ss.doc_tecnico
        )
    with c3:
        ss.tel_tecnico = st.text_input(
            "Telefone Técnico", value=ss.tel_tecnico
        )
    with c4:
        ss.dt_tecnico = st.text_input(
            "Data e hora (Técnico)", value=ss.dt_tecnico
        )

    st.markdown("---")
    st.markdown("#### Cliente")

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        ss.nome_cliente = st.text_input(
            "Nome cliente", value=ss.nome_cliente
        )
    with c6:
        ss.doc_cliente = st.text_input(
            "Documento cliente", value=ss.doc_cliente
        )
    with c7:
        ss.tel_cliente = st.text_input(
            "Telefone cliente", value=ss.tel_cliente
        )
    with c8:
        ss.dt_cliente = st.text_input(
            "Data e hora (Cliente)", value=ss.dt_cliente
        )

    st.caption(
        "As assinaturas poderão ser coletadas digitalmente ou manualmente na impressão, "
        "conforme sua necessidade."
    )


# ----------------- RENDER PRINCIPAL -----------------


def render_layout() -> None:
    """
    Função chamada por rat_unificado.render().
    Apenas desenha o layout e seta ss.trigger_generate quando clicar em Gerar RAT.
    """
    apply_dark_full_layout()
    header_bar()

    step = _step_selector()

    if step == 1:
        step1_dados_relatorio()
    elif step == 2:
        step2_atendimento_testes()
    elif step == 3:
        step3_checklist_tecnico()
    elif step == 4:
        step4_materiais_obs()
    elif step == 5:
        step5_aceite_assinaturas()

    st.markdown("---")
    col_info, col_btn = st.columns([3, 1])
    with col_info:
        st.caption("Preencha as etapas necessárias e clique em **Gerar RAT**.")
    with col_btn:
        if st.button("🧾 Gerar RAT", type="primary"):
            st.session_state.trigger_generate = True
