# repo/ui_unificado.py
import os
from datetime import date, time

import streamlit as st

# Descobre raiz do projeto para tentar achar o logo
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
LOGO_PATH = os.path.join(PROJECT_ROOT, "assets", "evernex_logo.png")


# ================== ESTILO / LAYOUT GLOBAL ==================

def _apply_dark_full_layout():
    """Aplica modo escuro customizado e largura full."""
    st.markdown(
        """
        <style>
        .stApp {
            background-color: #020617;
            color: #e5e7eb;
        }
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
            max-width: 1200px;
        }
        .rat-card {
            background: #020617;
            border: 1px solid #1f2937;
            border-radius: 18px;
            padding: 1.2rem 1.4rem;
            box-shadow: 0 0 0 1px rgba(15,23,42,0.8), 
                        0 10px 30px rgba(0,0,0,0.6);
        }
        .rat-label {
            font-size: 0.83rem;
            font-weight: 500;
            color: #e5e7eb;
        }
        .rat-caption {
            font-size: 0.75rem;
            color: #9ca3af;
        }
        .step-pill {
            border-radius: 999px;
            padding: 0.20rem 0.7rem;
            font-size: 0.78rem;
            border: 1px solid #4b5563;
            margin-right: 0.35rem;
        }
        .step-pill-active {
            background: #22c55e1a;
            border-color: #22c55e;
            color: #bbf7d0;
        }
        .step-pill-done {
            border-color: #22c55e;
            color: #22c55e;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _step_indicator(current_step: int):
    steps = {
        1: "Dados do Relatório / Site",
        2: "Atendimento & Testes",
        3: "Materiais & Equipamentos",
        4: "Observações",
        5: "Aceite & Assinaturas",
    }
    cols = st.columns(len(steps))
    for i, (num, label) in enumerate(steps.items(), start=0):
        cls = "step-pill"
        if num == current_step:
            cls += " step-pill-active"
        elif num < current_step:
            cls += " step-pill-done"
        html = f'<span class="{cls}">{num} — {label}</span>'
        cols[i].markdown(html, unsafe_allow_html=True)


def _header_bar():
    col_logo, col_title = st.columns([1, 4])
    with col_logo:
        if os.path.exists(LOGO_PATH):
            # Sem use_container_width (não é aceito na sua versão)
            st.image(LOGO_PATH, width=120)
        else:
            st.markdown("### Evernex")
    with col_title:
        st.markdown("## RAT MAM – Unificada")
        st.caption("Relatório de Atendimento Técnico — layout digital")


# ================== ETAPAS DO FORMULÁRIO ==================

def _ensure_defaults_ss():
    """Garante que alguns campos principais existam no session_state."""
    ss = st.session_state

    # Controle do passo
    if "current_step" not in ss:
        ss.current_step = 1

    # Campos gerais (só garante que existam; valores reais podem vir do init_defaults)
    ss.setdefault("data_atendimento", date.today())
    ss.setdefault("hora_inicio", time(8, 0))
    ss.setdefault("hora_termino", time(10, 0))

    ss.setdefault("numero_relatorio", "")
    ss.setdefault("operadora_contrato", "")
    ss.setdefault("analista_suporte", "")
    ss.setdefault("analista_validador", "")

    ss.setdefault("site_id", "")
    ss.setdefault("site_nome", "")
    ss.setdefault("site_endereco", "")
    ss.setdefault("site_cidade", "")
    ss.setdefault("site_uf", "")

    ss.setdefault("tipo_atendimento", [])
    ss.setdefault("distancia_km", 0.0)
    ss.setdefault("testes_executados", [])

    ss.setdefault("descricao_atividade", "")
    ss.setdefault("produtivo_status", "Produtivo")

    ss.setdefault("material_utilizado", "")
    ss.setdefault("equip_ret", "")
    ss.setdefault("equip_instalados", "")

    ss.setdefault("observacoes_gerais", "")

    # Dados de aceite / assinaturas
    ss.setdefault("tec_nome", "")
    ss.setdefault("tec_telefone", "")
    ss.setdefault("tec_documento", "")

    ss.setdefault("cli_nome", "")
    ss.setdefault("cli_telefone", "")
    ss.setdefault("cli_documento", "")


def _render_step1():
    """Etapa 1: Dados do Relatório + Site (mapeando seções 1 e 3 do PDF)."""
    ss = st.session_state
    st.markdown("### 1) Dados do Relatório & Local de Atendimento")
    st.markdown('<div class="rat-card">', unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1.2, 1.2, 1])
    with c1:
        st.markdown('<span class="rat-label">Número do Relatório</span>', unsafe_allow_html=True)
        ss.numero_relatorio = st.text_input(
            label="Número do Relatório",
            label_visibility="collapsed",
            value=ss.numero_relatorio,
            key="numero_relatorio_input",
        )

    with c2:
        st.markdown('<span class="rat-label">Operadora / Contrato</span>', unsafe_allow_html=True)
        ss.operadora_contrato = st.text_input(
            "Operadora / Contrato",
            label_visibility="collapsed",
            value=ss.operadora_contrato,
            key="operadora_contrato_input",
        )

    with c3:
        st.markdown('<span class="rat-label">Data do Atendimento</span>', unsafe_allow_html=True)
        ss.data_atendimento = st.date_input(
            "Data do Atendimento",
            label_visibility="collapsed",
            value=ss.data_atendimento,
            key="data_atendimento_input",
        )

    st.markdown("---")

    c4, c5 = st.columns(2)
    with c4:
        st.markdown('<span class="rat-label">Analista Suporte</span>', unsafe_allow_html=True)
        ss.analista_suporte = st.text_input(
            "Analista Suporte",
            label_visibility="collapsed",
            value=ss.analista_suporte,
            key="analista_suporte_input",
        )

        st.markdown('<span class="rat-label">Analista Validador (NOC / Projetos)</span>', unsafe_allow_html=True)
        ss.analista_validador = st.text_input(
            "Analista Validador (NOC / Projetos)",
            label_visibility="collapsed",
            value=ss.analista_validador,
            key="analista_validador_input",
        )

    with c5:
        st.markdown('<span class="rat-label">Horário Início / Término</span>', unsafe_allow_html=True)
        col_hi, col_ht = st.columns(2)
        with col_hi:
            ss.hora_inicio = st.time_input(
                "Horário Início",
                label_visibility="collapsed",
                value=ss.hora_inicio,
                key="hora_inicio_input",
            )
        with col_ht:
            ss.hora_termino = st.time_input(
                "Horário Término",
                label_visibility="collapsed",
                value=ss.hora_termino,
                key="hora_termino_input",
            )

    st.markdown("---")

    st.markdown('<span class="rat-label">Dados do Site / Local de Atendimento</span>', unsafe_allow_html=True)
    c6, c7 = st.columns([1.3, 1.3])
    with c6:
        ss.site_id = st.text_input(
            "ID / Código do Site",
            label_visibility="collapsed",
            value=ss.site_id,
            key="site_id_input",
        )
        ss.site_nome = st.text_input(
            "Nome / Razão Social",
            label_visibility="collapsed",
            value=ss.site_nome,
            key="site_nome_input",
        )
    with c7:
        ss.site_endereco = st.text_input(
            "Endereço",
            label_visibility="collapsed",
            value=ss.site_endereco,
            key="site_endereco_input",
        )
        col_cidade, col_uf = st.columns([2, 1])
        with col_cidade:
            ss.site_cidade = st.text_input(
                "Cidade",
                label_visibility="collapsed",
                value=ss.site_cidade,
                key="site_cidade_input",
            )
        with col_uf:
            ss.site_uf = st.text_input(
                "UF",
                label_visibility="collapsed",
                value=ss.site_uf,
                max_chars=2,
                key="site_uf_input",
            )

    st.markdown("</div>", unsafe_allow_html=True)


def _render_step2():
    """
    Etapa 2: Tipo de atendimento + testes executados
    (mapeando seções 2, 4 e 5 do PDF).
    """
    ss = st.session_state
    st.markdown("### 2) Atendimento & Testes")
    st.markdown('<div class="rat-card">', unsafe_allow_html=True)

    st.markdown('<span class="rat-label">Tipo de Atendimento</span>', unsafe_allow_html=True)
    tipo_opts = [
        "Instalação",
        "Manutenção corretiva",
        "Manutenção preventiva",
        "Ativação / Migração",
        "Retirada de equipamento",
        "Vistoria técnica",
    ]
    ss.tipo_atendimento = st.multiselect(
        "Tipo de Atendimento",
        tipo_opts,
        default=ss.get("tipo_atendimento", []),
        label_visibility="collapsed",
        key="tipo_atendimento_ms",
    )

    st.markdown("---")

    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown('<span class="rat-label">Distância (KM)</span>', unsafe_allow_html=True)
        ss.distancia_km = st.number_input(
            "Distância (KM)",
            label_visibility="collapsed",
            min_value=0.0,
            step=1.0,
            value=float(ss.get("distancia_km", 0.0)),
            key="distancia_km_input",
        )

    with c2:
        st.markdown('<span class="rat-label">Testes executados</span>', unsafe_allow_html=True)
        testes_opts = [
            "Ping",
            "Chamadas (voz)",
            "Navegação (web)",
            "Testes de banda",
            "VPN",
            "Outros",
        ]
        ss.testes_executados = st.multiselect(
            "Testes executados (ping, chamadas, navegação, etc.)",
            testes_opts,
            default=ss.get("testes_executados", []),
            label_visibility="collapsed",
            key="testes_executados_ms",
        )

    st.markdown("---")

    st.markdown('<span class="rat-label">Descrição das atividades realizadas</span>', unsafe_allow_html=True)
    ss.descricao_atividade = st.text_area(
        "Descrição das atividades realizadas",
        label_visibility="collapsed",
        value=ss.descricao_atividade,
        height=140,
        key="descricao_atividade_ta",
    )

    st.markdown("---")

    st.markdown('<span class="rat-label">Produtividade do atendimento</span>', unsafe_allow_html=True)
    ss.produtivo_status = st.radio(
        "Produtividade do atendimento",
        ["Produtivo", "Produtivo parcial", "Improdutivo"],
        label_visibility="collapsed",
        index=["Produtivo", "Produtivo parcial", "Improdutivo"].index(
            ss.get("produtivo_status", "Produtivo")
        ),
        key="produtivo_status_radio",
    )

    st.markdown("</div>", unsafe_allow_html=True)


def _render_step3():
    """Etapa 3: Materiais & Equipamentos (seções 7–9 do PDF)."""
    ss = st.session_state
    st.markdown("### 3) Materiais & Equipamentos")
    st.markdown('<div class="rat-card">', unsafe_allow_html=True)

    st.markdown('<span class="rat-label">Material utilizado</span>', unsafe_allow_html=True)
    ss.material_utilizado = st.text_area(
        "Material utilizado",
        label_visibility="collapsed",
        value=ss.material_utilizado,
        height=120,
        key="material_utilizado_ta",
    )

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<span class="rat-label">Equipamentos Retirados (se houver)</span>', unsafe_allow_html=True)
        ss.equip_ret = st.text_area(
            "Equipamentos Retirados (se houver)",
            label_visibility="collapsed",
            value=ss.equip_ret,
            height=120,
            key="equip_ret_ta",
        )
    with col2:
        st.markdown('<span class="rat-label">Equipamentos (Instalados / Existentes no Cliente)</span>',
                    unsafe_allow_html=True)
        ss.equip_instalados = st.text_area(
            "Equipamentos (Instalados / Existentes no Cliente)",
            label_visibility="collapsed",
            value=ss.equip_instalados,
            height=120,
            key="equip_instalados_ta",
        )

    st.markdown("</div>", unsafe_allow_html=True)


def _render_step4():
    """Etapa 4: Observações gerais (seções 10–12 do PDF)."""
    ss = st.session_state
    st.markdown("### 4) Observações adicionais")
    st.markdown('<div class="rat-card">', unsafe_allow_html=True)

    st.markdown('<span class="rat-label">Observações gerais</span>', unsafe_allow_html=True)
    ss.observacoes_gerais = st.text_area(
        "Observações gerais",
        label_visibility="collapsed",
        value=ss.observacoes_gerais,
        height=200,
        key="observacoes_gerais_ta",
    )

    st.markdown(
        '<p class="rat-caption">Use este campo para registrar qualquer informação adicional relevante: '
        'pendências, acordos com o cliente, riscos, etc.</p>',
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)


def _render_step5():
    """Etapa 5: Aceite & Assinaturas (seções 6 e 13 do PDF)."""
    ss = st.session_state
    st.markdown("### 5) Aceite & Assinaturas")
    st.markdown('<div class="rat-card">', unsafe_allow_html=True)

    st.markdown("#### Dados do Técnico")
    col1, col2, col3 = st.columns([1.6, 1.2, 1.2])
    with col1:
        ss.tec_nome = st.text_input(
            "Nome do técnico",
            value=ss.tec_nome,
            key="tec_nome_input",
        )
    with col2:
        ss.tec_telefone = st.text_input(
            "Telefone do técnico",
            value=ss.tec_telefone,
            key="tec_telefone_input",
        )
    with col3:
        ss.tec_documento = st.text_input(
            "Documento (CPF / RG)",
            value=ss.tec_documento,
            key="tec_documento_input",
        )

    st.markdown("---")

    st.markdown("#### Dados do Cliente / Responsável pelo aceite")
    col4, col5, col6 = st.columns([1.6, 1.2, 1.2])
    with col4:
        ss.cli_nome = st.text_input(
            "Nome do cliente / responsável",
            value=ss.cli_nome,
            key="cli_nome_input",
        )
    with col5:
        ss.cli_telefone = st.text_input(
            "Telefone do cliente",
            value=ss.cli_telefone,
            key="cli_telefone_input",
        )
    with col6:
        ss.cli_documento = st.text_input(
            "Documento (CPF / RG)",
            value=ss.cli_documento,
            key="cli_documento_input",
        )

    st.markdown(
        '<p class="rat-caption">As assinaturas propriamente ditas podem ser coletadas na versão PDF gerada '
        'ou via outro fluxo de assinatura digital.</p>',
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)


# ================== FUNÇÃO PRINCIPAL CHAMADA PELO rat_unificado.py ==================

def render_layout():
    """
    Função que o rat_unificado.py chama.
    Desenha o layout, controla steps e seta o gatilho de geração (trigger_generate).
    """
    _apply_dark_full_layout()
    _ensure_defaults_ss()

    ss = st.session_state

    _header_bar()
    _step_indicator(ss.current_step)

    st.write("")  # pequeno espaçamento

    # Renderiza etapa atual
    if ss.current_step == 1:
        _render_step1()
    elif ss.current_step == 2:
        _render_step2()
    elif ss.current_step == 3:
        _render_step3()
    elif ss.current_step == 4:
        _render_step4()
    else:
        _render_step5()

    st.write("")
    st.write("")

    # Navegação (Anterior / Próxima / Gerar)
    col_prev, col_next, _ = st.columns([1, 1, 4])

    with col_prev:
        if st.button("⬅️ Etapa anterior", disabled=(ss.current_step == 1)):
            if ss.current_step > 1:
                ss.current_step -= 1

    with col_next:
        if ss.current_step < 5:
            label = "Próxima etapa ➜"
        else:
            label = "✅ Gerar RAT"

        if st.button(label):
            if ss.current_step < 5:
                ss.current_step += 1
            else:
                # Gatilho para o rat_unificado.render()
                ss.trigger_generate = True
                st.success("Gerando RAT com os dados preenchidos...")
