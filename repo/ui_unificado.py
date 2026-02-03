# repo/ui_unificado.py
# Layout unificado em 5 blocos (modo escuro, largura full) com ABAS no topo.
# Abas:
# 1) Dados do Relatório & Local de Atendimento
# 2) Atendimento & Testes
# 3) Materiais & Equipamentos
# 4) Observações
# 5) Aceite & Assinaturas

from datetime import datetime
import os

import streamlit as st
from common.ui import assinatura_dupla_png  # já usada em outros módulos


# =============== ESTILO ===============

def apply_dark_full_layout() -> None:
    """Aplica CSS básico de modo escuro e largura 'full'."""
    st.markdown(
        """
        <style>
        .main {
            background-color: #020617;
        }
        body {
            background-color: #020617;
            color: #e5e7eb;
        }
        h1, h2, h3, h4 {
            color: #f9fafb !important;
        }
        .stTextInput > label,
        .stTextArea > label,
        .stSelectbox > label,
        .stMultiselect > label {
            font-weight: 600;
            color: #e5e7eb !important;
        }
        div.stButton > button {
            border-radius: 999px;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def header_bar() -> None:
    """Barra superior com logo Evernex + título."""
    col_logo, col_title = st.columns([1, 4])

    logo_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "assets",
        "selo_evernex_maminfo.png",
    )
    with col_logo:
        if os.path.exists(logo_path):
            st.image(logo_path)
        else:
            st.markdown("### Evernex")

    with col_title:
        st.markdown("## RAT MAM – Unificada (Modo Escuro)")
        st.caption(
            "Preencha as abas na ordem que preferir. Ao final, clique em "
            "**Gerar RAT** para criar o PDF com base na RAT_MAM_UNIFICADA_VF.pdf."
        )


# =============== ETAPAS (ABAS) ===============

def _tab_1_dados_relatorio():
    """
    1) Dados do Relatório & Local de Atendimento
    """
    ss = st.session_state

    st.markdown("### 1) Dados do Relatório & Local de Atendimento")

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        ss.num_relatorio = st.text_input(
            "Nº Relatório",
            value=ss.get("num_relatorio", ""),
        )
    with c2:
        ss.num_chamado = st.text_input(
            "Nº Chamado",
            value=ss.get("num_chamado", ""),
        )
    with c3:
        ss.operadora_contrato = st.text_input(
            "Operadora / Contrato",
            value=ss.get("operadora_contrato", ""),
        )

    c1, c2 = st.columns([2, 1])
    with c1:
        ss.cliente_razao = st.text_input(
            "Cliente / Razão Social",
            value=ss.get("cliente_razao", ""),
        )
    with c2:
        ss.distancia_km = st.text_input(
            "Distância (KM)",
            value=ss.get("distancia_km", ""),
            help="Distância percorrida pelo técnico (ida + volta, se aplicável).",
        )

    c1, c2 = st.columns(2)
    with c1:
        ss.inicio_atend = st.text_input(
            "Início (horário)",
            value=ss.get("inicio_atend", ""),
            placeholder="Ex.: 08:30",
        )
    with c2:
        ss.termino_atend = st.text_input(
            "Término (horário)",
            value=ss.get("termino_atend", ""),
            placeholder="Ex.: 11:15",
        )

    c1, c2 = st.columns(2)
    with c1:
        ss.contato_nome = st.text_input(
            "Contato (nome)",
            value=ss.get("contato_nome", ""),
        )
    with c2:
        ss.contato_telefone_email = st.text_input(
            "Telefone / E-mail",
            value=ss.get("contato_telefone_email", ""),
        )

    ss.endereco_completo = st.text_area(
        "Endereço Completo (Rua, nº, compl., bairro, cidade/UF)",
        value=ss.get("endereco_completo", ""),
    )

    default_data = ss.get("data_atendimento")
    if isinstance(default_data, str) and default_data:
        try:
            default_data = datetime.strptime(default_data, "%Y-%m-%d").date()
        except Exception:
            default_data = None
    if default_data is None:
        default_data = datetime.now().date()

    data_sel = st.date_input(
        "Data do atendimento",
        value=default_data,
    )
    ss.data_atendimento = data_sel.isoformat()


def _tab_2_atendimento_testes():
    """
    2) Atendimento & Testes
    """
    ss = st.session_state

    st.markdown("### 2) Atendimento & Testes")

    c1, c2 = st.columns(2)
    with c1:
        ss.analista_suporte = st.text_input(
            "Analista Suporte",
            value=ss.get("analista_suporte", ""),
        )
        ss.analista_integradora = st.text_input(
            "Analista Integradora (MAMINFO)",
            value=ss.get("analista_integradora", ""),
        )
    with c2:
        ss.analista_validador = st.text_input(
            "Analista validador (NOC / Projetos)",
            value=ss.get("analista_validador", ""),
        )
        ss.tipo_atendimento = st.text_input(
            "Tipo de Atendimento",
            value=ss.get("tipo_atendimento", ""),
            placeholder="Ex.: Instalação, Manutenção, Migração, Visita técnica...",
        )

    ss.motivo_chamado = st.text_area(
        "Anormalidade / Motivo do Chamado",
        value=ss.get("motivo_chamado", ""),
    )

    st.markdown("#### Checklist Técnico (SIM / NÃO)")
    st.caption("Marque os itens verificados durante o atendimento.")

    opcoes_check = [
        "Infraestrutura OK (energia / tomadas)",
        "Rede local OK (switch / cabeamento)",
        "Roteador / CPE OK",
        "Telefonia / PABX OK",
        "Wi-Fi OK",
        "Acesso remoto OK (VPN / gerenciamento)",
        "Documentação atualizada",
    ]
    prev = ss.get("checklist_tecnico", [])
    if not isinstance(prev, list):
        prev = []
    default_vals = [v for v in prev if v in opcoes_check]

    ss.checklist_tecnico = st.multiselect(
        "Itens verificados (opcional)",
        options=opcoes_check,
        default=default_vals,
    )


def _tab_3_materiais_equipamentos():
    """
    3) Materiais & Equipamentos
    """
    ss = st.session_state

    st.markdown("### 3) Materiais & Equipamentos")

    ss.material_utilizado = st.text_area(
        "Material utilizado",
        value=ss.get("material_utilizado", ""),
        placeholder="Ex.: 20m cabo CAT6, 10 RJ-45, 1 patch panel, etc.",
        height=120,
    )

    ss.equip_instalados = st.text_area(
        "Equipamentos (Instalados)",
        value=ss.get("equip_instalados", ""),
        placeholder="Ex.: 1x CPE XYZ S/N 123..., 2x AP modelo..., 1x switch...",
        height=140,
    )

    ss.equip_retirados = st.text_area(
        "Equipamentos Retirados (se houver)",
        value=ss.get("equip_retirados", ""),
        placeholder="Ex.: 1x roteador antigo, 1x ATA, etc. Se não houve retirada, deixe em branco.",
        height=120,
    )


def _tab_4_observacoes():
    """
    4) Observações & Testes
    """
    ss = st.session_state

    st.markdown("### 4) Observações & Testes")

    st.markdown("#### Testes realizados (check list)")
    opcoes_testes = [
        "Ping gateway",
        "Ping DNS público (ex.: 8.8.8.8)",
        "Ping destino do cliente (servidor / matriz)",
        "Navegação web",
        "Chamadas entrantes",
        "Chamadas sortantes",
        "Teste URA / discagem",
        "Teste VPN / túnel",
    ]
    prev = ss.get("testes_realizados", [])
    if not isinstance(prev, list):
        prev = []
    default_vals = [v for v in prev if v in opcoes_testes]

    ss.testes_realizados = st.multiselect(
        "Selecione os testes executados",
        options=opcoes_testes,
        default=default_vals,
    )

    ss.descricao_atendimento = st.text_area(
        "Descrição do Atendimento (o que foi feito / resultado / evidências)",
        value=ss.get("descricao_atendimento", ""),
        height=160,
    )

    ss.observacoes_pendencias = st.text_area(
        "Observações / Pendências",
        value=ss.get("observacoes_pendencias", ""),
        height=140,
    )


def _tab_5_aceite_assinaturas():
    """
    5) Aceite & Assinaturas
    """
    ss = st.session_state

    st.markdown("### 5) Aceite & Assinaturas")

    # --- Técnico MAMINFO ---
    st.markdown("#### Técnico MAMINFO")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ss.nome_tecnico = st.text_input(
            "Nome Técnico",
            value=ss.get("nome_tecnico", ""),
        )
    with c2:
        ss.doc_tecnico = st.text_input(
            "Documento Técnico",
            value=ss.get("doc_tecnico", ""),
        )
    with c3:
        ss.tel_tecnico = st.text_input(
            "Telefone Técnico",
            value=ss.get("tel_tecnico", ""),
        )
    with c4:
        ss.dt_tecnico = st.text_input(
            "Data e hora (Técnico)",
            value=ss.get("dt_tecnico", ""),
            placeholder="Ex.: 08/02/2026 10:30",
        )

    st.markdown("---")

    # --- Cliente ---
    st.markdown("#### Cliente")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ss.nome_cliente = st.text_input(
            "Nome cliente",
            value=ss.get("nome_cliente", ""),
        )
    with c2:
        ss.doc_cliente = st.text_input(
            "Documento cliente",
            value=ss.get("doc_cliente", ""),
        )
    with c3:
        ss.tel_cliente = st.text_input(
            "Telefone cliente",
            value=ss.get("tel_cliente", ""),
        )
    with c4:
        ss.dt_cliente = st.text_input(
            "Data e hora (Cliente)",
            value=ss.get("dt_cliente", ""),
            placeholder="Ex.: 08/02/2026 10:45",
        )

    st.markdown("---")

    st.markdown("#### Assinaturas (opcional)")
    st.caption(
        "Você pode coletar as assinaturas digitais aqui, ou deixar para assinar "
        "manualmente no papel após a impressão."
    )
    # grava ss.sig_tec_png e ss.sig_cli_png
    assinatura_dupla_png()


# =============== LAYOUT PRINCIPAL ===============

def render_layout() -> None:
    """
    Função chamada por rat_unificado.render().
    Agora sem 'step' nem botões de navegação:
    - Usa abas (tabs) para escolher a etapa.
    - Botão 'Gerar RAT' único no rodapé.
    """
    apply_dark_full_layout()
    header_bar()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "1) Dados do Relatório",
        "2) Atendimento & Testes",
        "3) Materiais & Equipamentos",
        "4) Observações",
        "5) Aceite & Assinaturas",
    ])

    with tab1:
        _tab_1_dados_relatorio()
    with tab2:
        _tab_2_atendimento_testes()
    with tab3:
        _tab_3_materiais_equipamentos()
    with tab4:
        _tab_4_observacoes()
    with tab5:
        _tab_5_aceite_assinaturas()

    st.markdown("---")

    # Botão único de geração
    col_spacer_left, col_button, col_spacer_right = st.columns([1, 1, 1])
    with col_button:
        gerar = st.button("🧾 Gerar RAT", key="btn_gerar_rat", use_container_width=True)

    st.session_state.trigger_generate = bool(gerar)
