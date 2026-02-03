# repo/ui_unificado.py
"""
Layout (UI) da RAT MAM Unificada
- Modo escuro
- Largura full
- Logo Evernex
- 5 etapas (steps):
  1) Dados do Relatório & Local
  2) Atendimento & Testes
  3) Materiais & Equipamentos
  4) Observações
  5) Aceite & Assinaturas + botão Gerar RAT
"""

import os
import sys
import streamlit as st
from datetime import date, time
from common.ui import assinatura_dupla_png


# ---------- PATH ROOT (para achar assets) ----------
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

LOGO_PATH = os.path.join(PROJECT_ROOT, "assets", "evernex_logo.png")  # ajuste o nome se for diferente


# ---------- ESTILO DARK FULL ----------
def apply_dark_full_layout():
    """
    CSS para modo escuro e largura mais ampla, com cards bonitos.
    """
    st.markdown(
        """
        <style>
        /* Full width do container principal */
        .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
            max-width: 1200px;
        }
        /* Fundo escuro geral */
        body, .stApp {
            background-color: #0b1120;
            color: #e5e7eb;
        }
        /* Cards (expander, etc.) */
        .stExpander {
            background-color: #111827 !important;
            border-radius: 12px !important;
            border: 1px solid #1f2937 !important;
        }
        .stExpander > div {
            background-color: #111827 !important;
        }
        /* Inputs */
        .stTextInput, .stTextArea, .stNumberInput, .stTimeInput, .stDateInput, .stMultiSelect, .stSelectbox {
            color: #e5e7eb !important;
        }
        /* Títulos */
        h1, h2, h3, h4 {
            color: #f9fafb;
        }
        /* Botões */
        .stButton>button {
            border-radius: 9999px;
            border: 1px solid #374151;
            background: linear-gradient(90deg, #10b981, #22c55e);
            color: white;
            font-weight: 600;
        }
        .stButton>button:hover {
            filter: brightness(1.05);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------- HEADER ----------
def header_bar():
    st.markdown("### ")
    col_logo, col_title = st.columns([1, 4])

    with col_logo:
        if os.path.exists(LOGO_PATH):
            # Para compatibilidade com versões mais antigas de Streamlit, usar só "width="
            st.image(LOGO_PATH, width=120)
        else:
            st.markdown("### Evernex")

    with col_title:
        st.markdown(
            """
            ### 🧾 RAT MAM Unificada
            <span style="color:#9ca3af;">Relatório de Atendimento Técnico – Modo escuro</span>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")


# ---------- ETAPAS (FORM) ----------

def render_step1(ss):
    """
    1) Dados do Relatório & Local de Atendimento
    """
    with st.container():
        st.subheader("1) Dados do Relatório & Local de Atendimento")

        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            ss.numero_relatorio = st.text_input("N° Relatório", value=ss.get("numero_relatorio", ""))
        with c2:
            ss.numero_chamado = st.text_input("N° Chamado", value=ss.get("numero_chamado", ""))
        with c3:
            ss.operadora_contrato = st.text_input("Operadora / Contrato", value=ss.get("operadora_contrato", ""))

        ss.cliente_razao = st.text_input("Cliente / Razão Social", value=ss.get("cliente_razao", ""))

        c4, c5, c6 = st.columns([1, 1, 1])
        with c4:
            ss.data_atendimento = st.date_input(
                "Data",
                value=ss.get("data_atendimento", date.today()),
            )
        with c5:
            ss.hora_inicio = st.time_input(
                "Início",
                value=ss.get("hora_inicio", time(8, 0)),
            )
        with c6:
            ss.hora_termino = st.time_input(
                "Término",
                value=ss.get("hora_termino", time(10, 0)),
            )

        c7, c8 = st.columns([2, 1])
        with c7:
            ss.contato_nome = st.text_input("Contato", value=ss.get("contato_nome", ""))
        with c8:
            ss.telefone_email = st.text_input("Telefone / E-mail", value=ss.get("telefone_email", ""))

        ss.endereco_completo = st.text_area(
            "Endereço Completo (Rua, nº, compl., bairro, cidade/UF)",
            value=ss.get("endereco_completo", ""),
            height=80,
        )

        ss.distancia_km = st.number_input(
            "Distância (KM)",
            min_value=0.0,
            max_value=10000.0,
            step=0.5,
            value=float(ss.get("distancia_km", 0.0)),
        )


def render_step2(ss):
    """
    2) Atendimento & Testes
    """
    with st.container():
        st.subheader("2) Atendimento & Testes")

        c1, c2, c3 = st.columns(3)
        with c1:
            ss.analista_suporte = st.text_input("Analista Suporte", value=ss.get("analista_suporte", ""))
        with c2:
            ss.analista_integradora = st.text_input(
                "Analista Integradora (MAMINFO)",
                value=ss.get("analista_integradora", ""),
            )
        with c3:
            ss.analista_validador = st.text_input(
                "Analista validador (NOC / Projetos)",
                value=ss.get("analista_validador", ""),
            )

        tipo_opts = [
            "Instalação",
            "Ativação",
            "Manutenção",
            "Retirada",
            "Visita técnica",
            "Outros",
        ]
        ss.tipo_atendimento = st.multiselect(
            "Tipo de Atendimento",
            options=tipo_opts,
            default=[opt for opt in ss.get("tipo_atendimento", []) if opt in tipo_opts],
        )

        ss.anormalidade = st.text_area(
            "Anormalidade / Motivo do Chamado",
            value=ss.get("anormalidade", ""),
            height=100,
        )

        ss.checklist_tecnico_ok = st.radio(
            "Checklist Técnico concluído?",
            options=["SIM", "NÃO"],
            index=(0 if ss.get("checklist_tecnico_ok", "SIM") == "SIM" else 1),
            horizontal=True,
        )


def render_step3(ss):
    """
    3) Materiais & Equipamentos
    """
    with st.container():
        st.subheader("3) Materiais & Equipamentos")

        ss.material_utilizado = st.text_area(
            "Material utilizado",
            value=ss.get("material_utilizado", ""),
            height=130,
        )

        ss.equip_instalados = st.text_area(
            "Equipamentos (Instalados)",
            value=ss.get("equip_instalados", ""),
            height=130,
        )

        ss.equip_retirados = st.text_area(
            "Equipamentos Retirados (se houver)",
            value=ss.get("equip_retirados", ""),
            height=130,
        )


def render_step4(ss):
    """
    4) Observações + Fotos de seriais
    """
    with st.container():
        st.subheader("4) Observações & Evidências")

        testes_opts = [
            "Ping",
            "Chamadas",
            "Navegação",
            "Velocidade",
            "VPN",
            "Outros",
        ]
        ss.testes_realizados = st.multiselect(
            "Testes realizados (check list)",
            options=testes_opts,
            default=[t for t in ss.get("testes_realizados", []) if t in testes_opts],
        )

        ss.descricao_atendimento = st.text_area(
            "Descrição do Atendimento (o que foi feito / resultado / evidências)",
            value=ss.get("descricao_atendimento", ""),
            height=160,
        )

        ss.observacoes_pendencias = st.text_area(
            "Observações / Pendências",
            value=ss.get("observacoes_pendencias", ""),
            height=120,
        )

        st.markdown("#### 📸 Fotos dos seriais (serão usadas a partir da página 3)")
        uploaded = st.file_uploader(
            "Anexe as fotos dos seriais (JPG, PNG, WEBP)",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
        )
        if uploaded:
            ss.fotos_seriais = [f.read() for f in uploaded]


def render_step5(ss):
    
elif step == 5:
        st.markdown("### 5) Aceite & Assinaturas ↩")
    
        # --- Dados do técnico ---
        st.markdown("#### Técnico MAMINFO")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            ss.nome_tecnico = st.text_input("Nome Técnico", value=ss.get("nome_tecnico", ""))
        with c2:
            ss.doc_tecnico = st.text_input("Documento Técnico", value=ss.get("doc_tecnico", ""))
        with c3:
            ss.tel_tecnico = st.text_input("Telefone Técnico", value=ss.get("tel_tecnico", ""))
        with c4:
            ss.dt_tecnico = st.text_input("Data e hora (Técnico)", value=ss.get("dt_tecnico", ""))

        st.markdown("---")  

    # --- Dados do cliente ---
        st.markdown("#### Cliente")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            ss.nome_cliente = st.text_input("Nome cliente", value=ss.get("nome_cliente", ""))
        with c2:
            ss.doc_cliente = st.text_input("Documento cliente", value=ss.get("doc_cliente", ""))
        with c3:
            ss.tel_cliente = st.text_input("Telefone cliente", value=ss.get("tel_cliente", ""))
        with c4:
            ss.dt_cliente = st.text_input("Data e hora (Cliente)", value=ss.get("dt_cliente", ""))

        st.markdown("---")

    # --- Assinaturas digitais ---
        st.markdown("#### Assinaturas (opcional)")
        st.caption(
            "Você pode coletar as assinaturas digitais aqui, ou deixar para assinar manualmente "
            "no papel após a impressão."
        )

        #   Essa função já cuida de dois campos: assinatura do técnico e do cliente
        assinatura_dupla_png()



# ---------- LAYOUT PRINCIPAL COM STEPPER ----------
def render_layout():
    """
    Função chamada pelo rat_unificado.render().
    Desenha header, etapas e controla step (sem precisar clicar 2x).
    """
    apply_dark_full_layout()
    header_bar()

    ss = st.session_state
    step = int(ss.get("step", 1))

    st.markdown(f"#### Etapa {step} de 5")

    # Renderiza a etapa atual
    if step == 1:
        render_step1(ss)
    elif step == 2:
        render_step2(ss)
    elif step == 3:
        render_step3(ss)
    elif step == 4:
        render_step4(ss)
    elif step == 5:
        render_step5(ss)

    st.markdown("---")

    col_back, col_next, col_generate = st.columns([1, 1, 2])

    # Botão Voltar
    with col_back:
        if step > 1:
            if st.button("⬅️ Voltar", key="btn_voltar"):
                ss.step = step - 1
                st.rerun()

    # Botão Próxima etapa
    with col_next:
        if step < 5:
            if st.button("Próxima etapa ➡️", key="btn_proxima"):
                ss.step = step + 1
                st.rerun()

    # Botão Gerar RAT (apenas na última etapa)
    with col_generate:
        if step == 5:
            if st.button("🧾 Gerar RAT", key="btn_gerar_rat"):
                ss.trigger_generate = True
                # Não dou rerun aqui; o rat_unificado.render() é quem
                # detecta trigger_generate e mostra o download
