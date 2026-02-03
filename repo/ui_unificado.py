# repo/ui_unificado.py
# Layout unificado em 5 etapas (modo escuro, largura full)
# Etapas:
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
        /* fundo principal */
        .main {
            background-color: #020617;
        }
        body {
            background-color: #020617;
            color: #e5e7eb;
        }

        /* textos dos labels */
        .stTextInput > label,
        .stTextArea > label,
        .stSelectbox > label,
        .stMultiselect > label {
            font-weight: 600;
            color: #e5e7eb !important;
        }

        /* títulos */
        h1, h2, h3, h4 {
            color: #f9fafb !important;
        }

        /* caixas */
        .stTextInput, .stTextArea, .stSelectbox, .stMultiselect {
            color: #e5e7eb;
        }

        /* botões */
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

    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "selo_evernex_maminfo.png")
    with col_logo:
        if os.path.exists(logo_path):
            st.image(logo_path)  # sem use_container_width pra evitar erro
        else:
            st.markdown("### Evernex")

    with col_title:
        st.markdown("## RAT MAM – Unificada (Modo Escuro)")
        st.caption(
            "Preencha as etapas na ordem. Ao final, clique em **Gerar RAT** para criar o PDF "
            "baseado no modelo RAT_MAM_UNIFICADA_VF.pdf."
        )


def _get_step() -> int:
    ss = st.session_state
    if "step" not in ss:
        ss.step = 1
    try:
        s = int(ss.step)
    except Exception:
        s = 1
    if s < 1:
        s = 1
    if s > 5:
        s = 5
    ss.step = s
    return s


def _step_indicator(step: int) -> None:
    st.markdown(f"### Etapa {step} de 5")
    st.progress(step / 5.0)


# =============== ETAPAS ===============

def _etapa_1():
    """
    1) Dados do Relatório & Local de Atendimento

    N° Relatório
    N° Chamado
    Operadora / Contrato
    Cliente / Razão Social
    Início
    Contato
    Endereço Completo (Rua, n°, compl., bairro, cidade/UF)
    Término
    Telefone / E-mail
    Distância (KM)
    Data
    """
    ss = st.session_state

    st.markdown("## 1) Dados do Relatório & Local de Atendimento")

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


def _etapa_2():
    """
    2 — Atendimento & Testes

    Analista Suporte
    Analista Integradora (MAMINFO)
    Analista validador (NOC / Projetos)
    Tipo de Atendimento
    Anormalidade / Motivo do Chamado
    Checklist Técnico (SIM / NÃO)
    """
    ss = st.session_state

    st.markdown("## 2) Atendimento & Testes")

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

    st.markdown("### Checklist Técnico (SIM / NÃO)")
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


def _etapa_3():
    """
    3 — Materiais & Equipamentos

    Material utilizado
    Equipamentos (Instalados)
    Equipamentos Retirados (se houver)
    """
    ss = st.session_state

    st.markdown("## 3) Materiais & Equipamentos")

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


def _etapa_4():
    """
    4 — Observações

    Testes realizados (check list)
    Descrição do Atendimento (o que foi feito / resultado / evidências)
    Observações / Pendências
    """
    ss = st.session_state

    st.markdown("## 4) Observações & Testes")

    st.markdown("### Testes realizados (check list)")
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


def _etapa_5():
    """
    5 — Aceite & Assinaturas

    Técnico MAMINFO:
        Nome Técnico
        Documento Técnico
        Telefone Técnico
        data e hora
        assinatura
    Cliente:
        Nome cliente
        Documento cliente
        Telefone cliente
        data e hora
        assinatura
    """
    ss = st.session_state

    st.markdown("## 5) Aceite & Assinaturas")

    # --- Técnico MAMINFO ---
    st.markdown("### Técnico MAMINFO")
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
    st.markdown("### Cliente")
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

    st.markdown("### Assinaturas (opcional)")
    st.caption(
        "Você pode coletar as assinaturas digitais aqui, ou deixar para assinar manualmente "
        "no papel após a impressão."
    )
    # Essa função normalmente grava ss.sig_tec_png e ss.sig_cli_png
    assinatura_dupla_png()


# =============== LAYOUT PRINCIPAL ===============

def render_layout() -> None:
    """
    Função chamada por rat_unificado.render()
    - Aplica tema escuro
    - Desenha header
    - Mostra etapa atual
    - Renderiza navegação (Voltar / Próxima / Gerar RAT)
    """
    apply_dark_full_layout()
    header_bar()

    ss = st.session_state
    step = _get_step()
    _step_indicator(step)

    # ---------- Conteúdo da etapa ----------
    if step == 1:
        _etapa_1()
    elif step == 2:
        _etapa_2()
    elif step == 3:
        _etapa_3()
    elif step == 4:
        _etapa_4()
    elif step == 5:
        _etapa_5()

    st.markdown("---")

    # ---------- Navegação ----------
    col_back, col_next, col_generate = st.columns([1, 1, 1])

    with col_back:
        if step > 1:
            if st.button("⬅️ Voltar", key="btn_voltar"):
                ss.step = step - 1

    with col_next:
        if step < 5:
            if st.button("Próxima etapa ➡️", key="btn_proxima"):
                ss.step = step + 1

    with col_generate:
        if step == 5:
            gerar = st.button("🧾 Gerar RAT", key="btn_gerar_rat")
            ss.trigger_generate = bool(gerar)
        else:
            ss.trigger_generate = False
