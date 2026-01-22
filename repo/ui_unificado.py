# repo/ui_rat_unificada.py
# Layout da RAT MAM UNIFICADA
# - modo escuro
# - largura "quase" full
# - logo Evernex no topo
# - abas por seção
# - cards bonitinhos

import os
import streamlit as st

# Descobre paths relativos ao projeto
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")

# candidatos de logo (ajuste os nomes se usar outro arquivo)
LOGO_CANDIDATOS = [
    os.path.join(ASSETS_DIR, "logo_evernex.png"),
    os.path.join(ASSETS_DIR, "logo_evernex_maminfo.png"),
    os.path.join(ASSETS_DIR, "selo_evernex_maminfo.png"),
]


def _get_logo_path() -> str:
    for p in LOGO_CANDIDATOS:
        if os.path.exists(p):
            return p
    return ""


def apply_dark_full_layout():
    """
    CSS pra:
      - fundo escuro
      - largura quase total
      - cards com sombra
      - inputs escuros
    """
    st.markdown(
        """
        <style>
        /* fundo principal */
        .main {
            background-color: #050608;
        }

        /* largura quase total */
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 3rem;
            padding-left: 2rem;
            padding-right: 2rem;
            max-width: 98%;
        }

        /* títulos */
        h1, h2, h3, h4, h5, h6 {
            color: #f5f5f7 !important;
        }

        /* texto geral */
        .stMarkdown, label, .stTextInput label, .stSelectbox label, .stDateInput label {
            color: #e5e5ea !important;
        }

        /* inputs escuros */
        .stTextInput > div > div > input,
        .stDateInput > div > div > input,
        .stTimeInput > div > div > input,
        .stNumberInput input,
        .stSelectbox > div > div,
        textarea {
            background-color: #111216 !important;
            color: #f5f5f7 !important;
        }

        /* borda/hover inputs */
        .stTextInput > div > div,
        .stDateInput > div > div,
        .stTimeInput > div > div,
        .stSelectbox > div > div {
            border-radius: 10px;
            border: 1px solid #262738;
        }

        /* cards customizados */
        .rat-card {
            background: #111216;
            border-radius: 14px;
            padding: 1.1rem 1.2rem;
            border: 1px solid #262738;
            box-shadow: 0 12px 30px rgba(0,0,0,0.45);
            margin-bottom: 1.2rem;
        }

        .rat-section-title {
            font-size: 1.0rem;
            font-weight: 600;
            color: #ffffff;
            margin-bottom: 0.4rem;
        }

        .rat-section-sub {
            font-size: 0.78rem;
            color: #a1a1b3;
            margin-bottom: 0.8rem;
        }

        /* botão principal */
        .stButton>button {
            border-radius: 999px;
            padding: 0.5rem 1.4rem;
            border: 1px solid #3b82f6;
            background: linear-gradient(90deg, #2563eb, #1d4ed8);
            color: #f9fafb;
            font-weight: 600;
        }

        .stButton>button:hover {
            filter: brightness(1.1);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def header_bar():
    """Barra do topo com logo Evernex + título."""
    logo_path = _get_logo_path()

    col_logo, col_title = st.columns([1, 4])
    with col_logo:
        if logo_path:
            st.image(logo_path, use_container_width=True)
        else:
            st.markdown("### Evernex")

    with col_title:
        st.markdown(
            """
            <div style="padding-left:0.5rem; padding-top:0.2rem;">
              <h1 style="margin-bottom:0.1rem;">RAT MAM – Unificada</h1>
              <p style="color:#a1a1b3; font-size:0.9rem; margin-top:0;">
                Registro de Atendimento Técnico com fluxo unificado de identificação, operação e aceite.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ================== SEÇÕES ==================


def sec_identificacao(ss):
    st.markdown('<div class="rat-card">', unsafe_allow_html=True)
    st.markdown('<div class="rat-section-title">1) Identificação do Atendimento</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="rat-section-sub">Dados gerais do chamado, cliente e responsável.</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([1.2, 1.2, 1])
    with c1:
        ss.data_atendimento = st.date_input(
            "Data do atendimento",
            value=ss.get("data_atendimento", None),
        )
        ss.hora_inicio = st.time_input(
            "Horário início",
            value=ss.get("hora_inicio", None),
        )
    with c2:
        ss.numero_chamado = st.text_input(
            "Número do Chamado",
            value=ss.get("numero_chamado", ""),
        )
        ss.hora_termino = st.time_input(
            "Horário término",
            value=ss.get("hora_termino", None),
        )
    with c3:
        ss.analista_mam = st.text_input(
            "Analista MAMINFO",
            value=ss.get("analista_mam", ""),
        )
        ss.tipo_atendimento = st.text_input(
            "Tipo de atendimento",
            value=ss.get("tipo_atendimento", ""),
        )

    st.markdown("---")

    c4, c5 = st.columns([2.5, 1.5])
    with c4:
        ss.cliente = st.text_input("Cliente / Razão Social", value=ss.get("cliente", ""))
        ss.cnpj = st.text_input("CNPJ / Identificação", value=ss.get("cnpj", ""))
        ss.endereco = st.text_input("Endereço", value=ss.get("endereco", ""))
        ss.cidade_uf = st.text_input("Cidade / UF", value=ss.get("cidade_uf", ""))
    with c5:
        ss.contato_local = st.text_input("Contato local (nome)", value=ss.get("contato_local", ""))
        ss.telefone_local = st.text_input("Telefone do contato", value=ss.get("telefone_local", ""))
        ss.email_local = st.text_input("E-mail do contato (opcional)", value=ss.get("email_local", ""))

    st.markdown("</div>", unsafe_allow_html=True)


def sec_dados_operacionais(ss):
    st.markdown('<div class="rat-card">', unsafe_allow_html=True)
    st.markdown('<div class="rat-section-title">2) Dados Operacionais</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="rat-section-sub">Informações técnicas do local, link e equipamentos.</div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        ss.site_id = st.text_input("ID / Código do Site", value=ss.get("site_id", ""))
        ss.operadora = st.text_input("Operadora / Cliente final", value=ss.get("operadora", ""))
        ss.tipo_link = st.text_input("Tipo de link (ex.: MPLS, Internet, 4G)", value=ss.get("tipo_link", ""))

    with c2:
        ss.endereco_ip = st.text_input("Endereço IP / Faixa", value=ss.get("endereco_ip", ""))
        ss.vlan = st.text_input("VLAN / Tag", value=ss.get("vlan", ""))
        ss.gw = st.text_input("Gateway", value=ss.get("gw", ""))

    st.markdown("---")

    st.markdown("#### Equipamentos envolvidos")
    colA, colB, colC, colD = st.columns([1.4, 1.2, 1.2, 1.2])
    with colA:
        ss.eq_tipo = st.text_input("Tipo", value=ss.get("eq_tipo", "Roteador / Switch / AP"))
    with colB:
        ss.eq_fabricante = st.text_input("Fabricante", value=ss.get("eq_fabricante", ""))
    with colC:
        ss.eq_modelo = st.text_input("Modelo", value=ss.get("eq_modelo", ""))
    with colD:
        ss.eq_serial = st.text_input("Nº de Série", value=ss.get("eq_serial", ""))

    st.markdown("</div>", unsafe_allow_html=True)


def sec_execucao(ss):
    st.markdown('<div class="rat-card">', unsafe_allow_html=True)
    st.markdown('<div class="rat-section-title">3) Execução do Serviço</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="rat-section-sub">Atividades realizadas, testes e resultados.</div>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        ss.servicos_realizados = st.text_area(
            "Serviços realizados (passo a passo)",
            value=ss.get("servicos_realizados", ""),
            height=160,
        )
    with col2:
        ss.testes_executados = st.text_area(
            "Testes executados (ping, chamadas, navegação, etc.)",
            value=ss.get("testes_executados", ""),
            height=160,
        )

    st.markdown("---")
    ss.obs_gerais = st.text_area(
        "Observações gerais (informações adicionais, restrições, pendências tratadas em tempo real)",
        value=ss.get("obs_gerais", ""),
        height=120,
    )

    st.markdown("</div>", unsafe_allow_html=True)


def sec_produtividade_aceite(ss):
    st.markdown('<div class="rat-card">', unsafe_allow_html=True)
    st.markdown('<div class="rat-section-title">4) Produtividade & Aceite</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="rat-section-sub">Resultado final do atendimento e validação junto ao cliente.</div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([1.5, 2])
    with c1:
        ss.produtivo = st.selectbox(
            "Status do atendimento",
            ["sim-totalmente produtivo", "produtivo parcial", "não-improdutivo"],
            index=["sim-totalmente produtivo", "produtivo parcial", "não-improdutivo"].index(
                ss.get("produtivo", "sim-totalmente produtivo")
            ),
        )
        ss.teste_final_wan = st.selectbox(
            "Teste final com equipamento do cliente?",
            ["S", "N", "NA"],
            index=["S", "N", "NA"].index(ss.get("teste_final_wan", "NA")),
        )
    with c2:
        ss.resumo_resultado = st.text_area(
            "Resumo do resultado para o cliente",
            value=ss.get("resumo_resultado", ""),
            height=110,
        )

    st.markdown("---")

    c3, c4 = st.columns(2)
    with c3:
        st.markdown("##### Assinatura do Técnico")
        ss.tecnico_nome = st.text_input("Nome do técnico", value=ss.get("tecnico_nome", ""))
        # a captura da assinatura em si você já tem em common.ui, depois encaixa aqui
    with c4:
        st.markdown("##### Aceite do Cliente")
        ss.cliente_validador_nome = st.text_input("Nome do validador", value=ss.get("cliente_validador_nome", ""))
        ss.validador_tel = st.text_input("Telefone do validador", value=ss.get("validador_tel", ""))

    st.markdown("</div>", unsafe_allow_html=True)


def sec_fotos(ss):
    st.markdown('<div class="rat-card">', unsafe_allow_html=True)
    st.markdown('<div class="rat-section-title">5) Evidências Fotográficas</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="rat-section-sub">'
        'Envie as principais fotos do ambiente, rack, equipamentos e telas de teste. '
        'Essas imagens serão anexadas ao PDF final.'
        '</div>',
        unsafe_allow_html=True,
    )

    # Aqui você pluga seu componente existente (ex.: foto_gateway_uploader)
    st.info("Use o componente de upload de fotos do módulo principal (ex.: foto_gateway_uploader).")

    st.markdown("</div>", unsafe_allow_html=True)


# ================== ENTRADA PRINCIPAL ==================


def render_layout():
    """
    Monta o layout completo da RAT Unificada.
    - Não mexe em PDF, só UI.
    - Usa st.session_state (ss).
    """
    apply_dark_full_layout()
    header_bar()

    ss = st.session_state

    tabs = st.tabs(
        [
            "Identificação",
            "Dados Operacionais",
            "Execução",
            "Produtividade & Aceite",
            "Fotos",
        ]
    )

    with tabs[0]:
        sec_identificacao(ss)
    with tabs[1]:
        sec_dados_operacionais(ss)
    with tabs[2]:
        sec_execucao(ss)
    with tabs[3]:
        sec_produtividade_aceite(ss)
    with tabs[4]:
        sec_fotos(ss)
