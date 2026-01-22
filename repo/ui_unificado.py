# repo/ui_unificado.py
import os
import sys
import streamlit as st

# Ajuste de PATH (se precisar de coisas do projeto)
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------- helpers de layout / tema ----------

def get_logo_path() -> str:
    """
    Tenta resolver o caminho do logo da Evernex.
    Ex: <project_root>/assets/evernex_logo.png
    """
    root = PROJECT_ROOT
    candidates = [
        os.path.join(root, "assets", "evernex_logo.png"),
        os.path.join(root, "assets", "logo_evernex.png"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return ""


def apply_dark_full_layout():
    """
    Injeta CSS para modo escuro custom + largura full.
    """
    st.markdown(
        """
        <style>
        html, body, [data-testid="stAppViewContainer"] {
            background-color: #0b0f17;
        }
        [data-testid="stSidebar"] {
            background-color: #05070c;
        }
        .ever-card {
            background: #151b26;
            border-radius: 14px;
            padding: 18px 20px;
            border: 1px solid #273044;
        }
        .ever-section-title {
            font-weight: 600;
            font-size: 1.0rem;
            color: #f3f4f6;
            margin-bottom: 6px;
        }
        .ever-section-subtitle {
            font-size: 0.82rem;
            color: #9ca3af;
            margin-bottom: 8px;
        }
        .ever-tag-pill {
            display: inline-block;
            padding: 2px 10px;
            border-radius: 999px;
            font-size: 0.72rem;
            background: #1f2937;
            color: #9ca3af;
            margin-right: 6px;
        }
        .ever-header-title {
            font-size: 1.4rem;
            font-weight: 700;
            color: #e5e7eb;
            margin-bottom: 2px;
        }
        .ever-header-subtitle {
            font-size: 0.85rem;
            color: #9ca3af;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def header_bar():
    """
    Cabeçalho superior: logo + título RAT.
    """
    logo_path = get_logo_path()
    col_logo, col_title = st.columns([1, 4])
    with col_logo:
        if logo_path:
            # Sem use_container_width para evitar erro na sua versão
            st.image(logo_path)
        else:
            st.markdown("### Evernex")
    with col_title:
        st.markdown('<div class="ever-header-title">RAT MAM – Unificada</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ever-header-subtitle">Registro de Atendimento Técnico • Layout unificado Evernex/MAMINFO</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<span class="ever-tag-pill">Modo escuro</span>'
            '<span class="ever-tag-pill">Layout full</span>',
            unsafe_allow_html=True,
        )


# ---------- helpers de campos ----------

def _text_input(label, key, cols=None, placeholder=""):
    """
    Helper para text_input com tema escuro.
    """
    if cols is None:
        return st.text_input(label, key=key, placeholder=placeholder)
    else:
        with cols:
            return st.text_input(label, key=key, placeholder=placeholder)


def _number_input(label, key, min_value=0.0, max_value=100000.0, step=0.1, cols=None):
    if cols is None:
        return st.number_input(label, key=key, min_value=min_value, max_value=max_value, step=step)
    else:
        with cols:
            return st.number_input(label, key=key, min_value=min_value, max_value=max_value, step=step)


def _textarea(label, key, height=80, placeholder=""):
    return st.text_area(label, key=key, height=height, placeholder=placeholder)


# ---------- layout principal ----------

def render_layout():
    """
    Desenha o layout inteiro da RAT unificada + controle de etapas.
    Usa st.session_state (ss) para armazenar os valores.
    """
    apply_dark_full_layout()
    header_bar()

    ss = st.session_state
    if "rat_step" not in ss:
        ss.rat_step = 1

    st.markdown("")

    # ================== FORM PRINCIPAL (ETAPA 1) ==================
    with st.form("rat_unificada_form", clear_on_submit=False):
        # ---------- Card 1: Identificação ----------
        st.markdown('<div class="ever-card">', unsafe_allow_html=True)
        st.markdown('<div class="ever-section-title">1) Identificação do Chamado</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ever-section-subtitle">Informe os dados principais do relatório e do chamado.</div>',
            unsafe_allow_html=True,
        )

        c1, c2, c3 = st.columns([1.2, 1.2, 1])
        with c1:
            _text_input("Número do Relatório", key="numero_relatorio", placeholder="Ex.: RAT-2026-0001")
        with c2:
            _text_input("Número do Chamado / Ticket", key="numero_chamado", placeholder="Ex.: 21-000000-0")
        with c3:
            _text_input("Operadora / Contrato", key="operadora_contrato", placeholder="Ex.: Oi / Bradesco")

        c4, c5 = st.columns([2, 1])
        with c4:
            _text_input("Cliente / Unidade", key="cliente_nome", placeholder="Ex.: Agência Bradesco XYZ")
        with c5:
            _text_input("Código UL / Circuito", key="codigo_ul_circuito", placeholder="Ex.: UL 21-000000-0")

        _text_input("Cidade / UF ou Localidade", key="localidade", placeholder="Ex.: São Paulo / SP")

        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("")

        # ---------- Card 2: Equipe Técnica ----------
        st.markdown('<div class="ever-card">', unsafe_allow_html=True)
        st.markdown('<div class="ever-section-title">2) Equipe Técnica</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ever-section-subtitle">Identificação dos analistas envolvidos no atendimento.</div>',
            unsafe_allow_html=True,
        )

        cA, cB = st.columns(2)
        with cA:
            _text_input("Analista Suporte", key="analista_suporte", placeholder="Nome do analista de suporte")
        with cB:
            _text_input(
                "Analista Validador (NOC / Projetos)",
                key="analista_validador",
                placeholder="Nome de quem validou o atendimento",
            )

        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("")

        # ---------- Card 3: Informações do Atendimento (substitui Dados Operacionais) ----------
        st.markdown('<div class="ever-card">', unsafe_allow_html=True)
        st.markdown('<div class="ever-section-title">3) Informações do Atendimento</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ever-section-subtitle">Resumo técnico do que foi realizado em campo ou remoto.</div>',
            unsafe_allow_html=True,
        )

        # Tipo de atendimento (checklist)
        tipo_opts = [
            "Instalação",
            "Ativação",
            "Manutenção corretiva",
            "Manutenção preventiva",
            "Retirada de equipamento",
            "Vistoria técnica",
            "Atendimento remoto",
        ]
        ss.tipo_atendimento = st.multiselect(
            "Tipo de Atendimento",
            options=tipo_opts,
            default=ss.get("tipo_atendimento", []),
            help="Selecione um ou mais tipos que descrevem melhor o atendimento.",
        )

        cD, cT = st.columns([1, 2])
        with cD:
            _number_input("Distância percorrida (KM)", key="distancia_km", min_value=0.0, max_value=9999.0, step=0.5)
        with cT:
            testes_opts = [
                "Ping",
                "Chamadas de voz",
                "Navegação Web",
                "Speedtest",
                "Teste de VPN",
                "Outros",
            ]
            ss.testes_executados = st.multiselect(
                "Testes executados (ping, chamadas, navegação, etc.)",
                options=testes_opts,
                default=ss.get("testes_executados", []),
            )

        _textarea(
            "Resumo da atividade executada",
            key="resumo_atividade",
            height=100,
            placeholder="Descreva de forma objetiva o que foi feito (configurações, testes, ajustes, etc.)",
        )

        _textarea(
            "Observações gerais (opcional)",
            key="observacoes_gerais",
            height=80,
            placeholder="Informações adicionais relevantes para o chamado.",
        )

        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("")

        # ---------- Card 4: Materiais e Equipamentos ----------
        st.markdown('<div class="ever-card">', unsafe_allow_html=True)
        st.markdown('<div class="ever-section-title">4) Materiais e Equipamentos</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ever-section-subtitle">Liste os materiais e equipamentos utilizados, retirados ou existentes.</div>',
            unsafe_allow_html=True,
        )

        _textarea(
            "Material utilizado",
            key="material_utilizado",
            height=80,
            placeholder="Ex.: 2x patch cord CAT6 2m, 1x conector RJ45, etc.",
        )
        _textarea(
            "Equipamentos Retirados (se houver)",
            key="equipamentos_retirados",
            height=80,
            placeholder="Ex.: 1x roteador antigo, 1x modem substituído, etc.",
        )
        _textarea(
            "Equipamentos (Instalados / Existentes no Cliente)",
            key="equipamentos_instalados",
            height=80,
            placeholder="Ex.: 1x Gateway Aligera, 2x AP Intelbras, 1x Switch Datacom...",
        )

        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("")

        # ---------- Card 5: Assinaturas ----------
        st.markdown('<div class="ever-card">', unsafe_allow_html=True)
        st.markdown('<div class="ever-section-title">5) Assinaturas</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ever-section-subtitle">Dados para assinatura do técnico e do responsável do cliente.</div>',
            unsafe_allow_html=True,
        )

        colTec, colCli = st.columns(2)

        with colTec:
            st.markdown("**Técnico**")
            _text_input("Nome do Técnico", key="tecnico_nome")
            _text_input("Telefone do Técnico", key="tecnico_telefone", placeholder="(DDD) 99999-9999")
            _text_input("Documento do Técnico (CPF / RG)", key="tecnico_documento")

        with colCli:
            st.markdown("**Cliente / Responsável**")
            _text_input("Nome do Cliente / Responsável", key="cliente_ass_nome")
            _text_input("Telefone do Cliente", key="cliente_ass_telefone", placeholder="(DDD) 99999-9999")
            _text_input("Documento do Cliente (CPF / CNPJ)", key="cliente_ass_documento")

        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("")

        # ---------- Rodapé do FORM: Botão de Próxima Etapa ----------
        c_next, c_dummy = st.columns([1, 3])
        with c_next:
            next_clicked = st.form_submit_button("➡️ Próxima etapa")

        if next_clicked:
            ss.rat_step = 2

    # ================== ETAPA 2: Revisão + botão Gerar RAT ==================
    if ss.rat_step >= 2:
        st.markdown("")
        st.markdown('<div class="ever-card">', unsafe_allow_html=True)
        st.markdown('<div class="ever-section-title">Etapa 2) Revisar e gerar RAT</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ever-section-subtitle">'
            'Revise as informações preenchidas acima. '
            'Se estiver tudo correto, clique em <b>Gerar RAT (PDF)</b>.'
            '</div>',
            unsafe_allow_html=True,
        )

        col_gen, col_back = st.columns([1, 1])
        with col_gen:
            if st.button("🧾 Gerar RAT (PDF)"):
                ss.trigger_generate = True
        with col_back:
            if st.button("⬅️ Voltar e editar"):
                ss.rat_step = 1

        st.markdown('</div>', unsafe_allow_html=True)
