# repo/rat_unificado.py — RAT MAM UNIFICADA
# Layout em 5 etapas (wizard), modo "dark", logo Evernex e geração de PDF base.
# Campos incluídos:
# - Número do Relatório
# - Operadora / Contrato
# - Analista Suporte
# - Analista Validador (NOC / Projetos)
# - Tipo de Atendimento (checklist)
# - Distância (KM)
# - Testes executados (ping, chamadas, navegação, etc.) — checklist
# - Material utilizado
# - Equipamentos Retirados
# - Equipamentos (Instalados / Existentes no Cliente)
# - Dados cliente/técnico para assinatura (nome, documento, telefone)
# OBS: Geração de PDF ainda não está preenchendo campos, apenas baixa o template.

import os
import sys
from datetime import date, time, datetime
from io import BytesIO
from zoneinfo import ZoneInfo

import streamlit as st
import fitz  # PyMuPDF

# ---------- PATH / IMPORTS COMUNS ----------
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common.state import init_defaults
from common.pdf import open_pdf_template

# ---------- CONSTANTES ----------
DEFAULT_TZ = "America/Sao_Paulo"
PDF_DIR = os.path.join(PROJECT_ROOT, "pdf_templates")
PDF_BASE_PATH = os.path.join(PDF_DIR, "RAT_MAM_UNIFICADA_VF.pdf")

LOGO_PATH = os.path.join(PROJECT_ROOT, "assets", "evernex_logo.png")


# ========== ESTILO DARK ==========
def _apply_dark_theme():
    """
    Pequeno ajuste visual para fundo escuro.
    O tema dark principal ainda é o do Streamlit (configuração de tema),
    mas isso aqui dá uma forcinha nas áreas principais.
    """
    st.markdown(
        """
        <style>
        /* Fundo principal escuro */
        .stApp {
            background-color: #020617;
        }
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
            max-width: 1200px;
        }
        /* Caixas "cards" */
        .rat-card {
            background: #020617;
            border: 1px solid #1f2937;
            border-radius: 18px;
            padding: 1.2rem 1.4rem;
            box-shadow: 0 0 0 1px rgba(15,23,42,0.8), 0 10px 30px rgba(0,0,0,0.6);
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
        </style>
        """,
        unsafe_allow_html=True,
    )


# ========== DEFAULTS ==========

def _init_rat_defaults():
    """
    Seta todos os defaults da RAT unificada.
    Usa common.state.init_defaults para não sobrescrever o que já existir.
    """
    init_defaults(
        {
            # Controle interno
            "rat_step": 1,

            # Etapa 1 - Identificação / Local
            "numero_relatorio": "",
            "operadora_contrato": "",
            "cliente": "",
            "site_id": "",
            "data_atendimento": date.today(),
            "distancia_km": 0.0,
            "endereco": "",
            "cidade": "",
            "uf": "",
            "tipo_atendimento": [],  # multiselect

            # Etapa 2 - Equipe / Operação
            "analista_suporte": "",
            "analista_validador": "",
            "tecnico_nome": "",
            "hora_inicio": time(8, 0),
            "hora_termino": time(10, 0),
            "numero_chamado": "",
            "dados_operacionais": "",

            # Etapa 3 - Testes / Resultado
            "testes_executados": [],  # multiselect
            "testes_outros": "",
            "descricao_testes": "",
            "produtivo": "Produtivo",
            "motivo_improdutividade": "",

            # Etapa 4 - Materiais / Equipamentos
            "materiais_utilizados": "",
            "equip_instalados": "",
            "equip_retirados": "",

            # Etapa 5 - Assinaturas / Observações / Fotos
            "cliente_nome": "",
            "cliente_doc": "",
            "cliente_telefone": "",
            "tecnico_doc": "",
            "tecnico_telefone": "",
            "analista_suporte_conf": "",
            "observacoes_finais": "",

            # Fuso & geração
            "browser_tz": "",
            "usar_agora": True,
        }
    )


# ========== COMPONENTES DE LAYOUT ==========

def _step_indicator(step: int, total: int = 5):
    labels = [
        "1\nIdentificação",
        "2\nEquipe\n/ Operação",
        "3\nTestes\n/ Resultado",
        "4\nMateriais\n/ Equipamentos",
        "5\nAssinaturas\n/ Observações",
    ]
    cols = st.columns(total)
    for i in range(total):
        active = (i + 1) == step
        bg = "#22c55e" if active else "#020617"
        border = "#22c55e" if active else "#4b5563"
        color = "#020617" if active else "#e5e7eb"
        with cols[i]:
            st.markdown(
                f"""
                <div style="
                    padding: 8px 4px;
                    border-radius: 999px;
                    text-align: center;
                    background-color: {bg};
                    border: 1px solid {border};
                    color: {color};
                    font-size: 11px;
                    line-height: 1.2;
                    white-space: pre-line;
                    font-weight: 600;
                ">
                    {labels[i]}
                </div>
                """,
                unsafe_allow_html=True,
            )


def _nav_buttons(step: int):
    ss = st.session_state
    st.markdown("---")
    c1, c2, c3 = st.columns([1, 2, 1])

    with c1:
        if step > 1 and st.button("⬅ Voltar", key=f"btn_back_{step}"):
            ss.rat_step = step - 1

    with c3:
        if step < 5:
            if st.button("Próxima etapa ➜", key=f"btn_next_{step}"):
                ss.rat_step = step + 1
        else:
            if st.button("🧾 Gerar RAT (PDF)", key="btn_generate"):
                _generate_pdf()


# ========== RENDER DE CADA ETAPA ==========

def _render_step1():
    ss = st.session_state
    st.markdown("### 1) Identificação do Chamado e Local")

    with st.container():
        col_logo, col_title = st.columns([1, 4])
        with col_logo:
            if os.path.exists(LOGO_PATH):
                st.image(LOGO_PATH, width=110)
            else:
                st.markdown("#### Evernex")
        with col_title:
            st.markdown(
                "<div style='font-size: 1.4rem; font-weight: 600;'>RAT MAM Unificada</div>"
                "<div style='font-size: 0.85rem; color:#9ca3af;'>Relatório de Atendimento Técnico</div>",
                unsafe_allow_html=True,
            )

    st.markdown("<div class='rat-card'>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        ss.numero_relatorio = st.text_input(
            "Número do Relatório",
            value=ss.numero_relatorio,
        )
        ss.operadora_contrato = st.text_input(
            "Operadora / Contrato",
            value=ss.operadora_contrato,
        )
        ss.cliente = st.text_input(
            "Cliente / Estabelecimento",
            value=ss.cliente,
        )
    with c2:
        ss.site_id = st.text_input(
            "ID / Código do Site",
            value=ss.site_id,
        )
        ss.data_atendimento = st.date_input(
            "Data do atendimento",
            value=ss.data_atendimento,
        )
        ss.distancia_km = st.number_input(
            "Distância (km)",
            min_value=0.0,
            step=1.0,
            value=float(ss.distancia_km) if isinstance(ss.distancia_km, (int, float)) else 0.0,
        )

    st.markdown("**Endereço do local**")
    ss.endereco = st.text_input(
        "Endereço (rua, nº, complemento)",
        value=ss.endereco,
    )
    c3, c4 = st.columns(2)
    with c3:
        ss.cidade = st.text_input("Cidade", value=ss.cidade)
    with c4:
        ss.uf = st.text_input("UF", value=ss.uf, max_chars=2)

    st.markdown("---")

    tipo_opts = [
        "Instalação",
        "Manutenção corretiva",
        "Manutenção preventiva",
        "Retirada de equipamento",
        "Vistoria técnica",
        "Mudança de endereço",
        "Ativação / Migração",
        "Outro",
    ]
    current = [v for v in ss.tipo_atendimento if v in tipo_opts]
    ss.tipo_atendimento = st.multiselect(
        "Tipo de Atendimento",
        options=tipo_opts,
        default=current,
    )

    st.markdown("</div>", unsafe_allow_html=True)


def _render_step2():
    ss = st.session_state
    st.markdown("### 2) Equipe, Horário e Dados Operacionais")
    st.markdown("<div class='rat-card'>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        ss.analista_suporte = st.text_input(
            "Analista Suporte",
            value=ss.analista_suporte,
        )
        ss.analista_validador = st.text_input(
            "Analista validador (NOC / Projetos)",
            value=ss.analista_validador,
        )
        ss.tecnico_nome = st.text_input(
            "Técnico em campo",
            value=ss.tecnico_nome,
        )
    with c2:
        ss.hora_inicio = st.time_input(
            "Horário de início",
            value=ss.hora_inicio,
        )
        ss.hora_termino = st.time_input(
            "Horário de término",
            value=ss.hora_termino,
        )
        ss.numero_chamado = st.text_input(
            "Número do chamado / ticket",
            value=ss.numero_chamado,
        )

    st.markdown("---")

    ss.dados_operacionais = st.text_area(
        "Resumo operacional / contexto da atividade",
        value=ss.dados_operacionais,
        height=140,
    )

    st.markdown("</div>", unsafe_allow_html=True)


def _render_step3():
    ss = st.session_state
    st.markdown("### 3) Testes executados e Resultado")
    st.markdown("<div class='rat-card'>", unsafe_allow_html=True)

    test_opts = [
        "Ping",
        "Navegação",
        "Chamadas de voz",
        "Chamadas de vídeo",
        "Teste de VPN",
        "Teste de URA / discador",
        "Outros",
    ]
    current = [v for v in ss.testes_executados if v in test_opts]
    ss.testes_executados = st.multiselect(
        "Testes executados",
        options=test_opts,
        default=current,
    )
    ss.testes_outros = st.text_input(
        "Se marcou 'Outros', detalhar aqui",
        value=ss.testes_outros,
    )

    ss.descricao_testes = st.text_area(
        "Descrição dos testes e resultados (ping, chamadas, navegação, etc.)",
        value=ss.descricao_testes,
        height=160,
    )

    st.markdown("---")

    prod_opts = ["Produtivo", "Produtivo parcial", "Improdutivo"]
    if ss.produtivo not in prod_opts:
        ss.produtivo = "Produtivo"
    ss.produtivo = st.selectbox(
        "Situação final do atendimento",
        prod_opts,
        index=prod_opts.index(ss.produtivo),
    )

    ss.motivo_improdutividade = st.text_area(
        "Motivo da improdutividade / pendências (caso não seja totalmente produtivo)",
        value=ss.motivo_improdutividade,
        height=120,
    )

    st.markdown("</div>", unsafe_allow_html=True)


def _render_step4():
    ss = st.session_state
    st.markdown("### 4) Materiais e Equipamentos")
    st.markdown("<div class='rat-card'>", unsafe_allow_html=True)

    ss.materiais_utilizados = st.text_area(
        "Material utilizado",
        value=ss.materiais_utilizados,
        height=140,
    )

    ss.equip_instalados = st.text_area(
        "Equipamentos (Instalados / Existentes no Cliente)",
        value=ss.equip_instalados,
        height=140,
    )

    ss.equip_retirados = st.text_area(
        "Equipamentos Retirados (se houver)",
        value=ss.equip_retirados,
        height=140,
    )

    st.markdown("</div>", unsafe_allow_html=True)


def _render_step5():
    ss = st.session_state
    st.markdown("### 5) Contatos, Assinaturas e Observações Finais")
    st.markdown("<div class='rat-card'>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Dados do Cliente / Responsável local**")
        ss.cliente_nome = st.text_input(
            "Nome do cliente / responsável",
            value=ss.cliente_nome,
        )
        ss.cliente_doc = st.text_input(
            "Documento do cliente (CPF / CNPJ)",
            value=ss.cliente_doc,
        )
        ss.cliente_telefone = st.text_input(
            "Telefone do cliente",
            value=ss.cliente_telefone,
        )
    with c2:
        st.markdown("**Dados do Técnico**")
        ss.tecnico_doc = st.text_input(
            "Documento do técnico (CPF)",
            value=ss.tecnico_doc,
        )
        ss.tecnico_telefone = st.text_input(
            "Telefone do técnico",
            value=ss.tecnico_telefone,
        )
        ss.analista_suporte_conf = st.text_input(
            "Analista responsável pelo relatório (opcional)",
            value=ss.analista_suporte_conf,
        )

    st.markdown("---")

    ss.observacoes_finais = st.text_area(
        "Observações gerais / instruções adicionais",
        value=ss.observacoes_finais,
        height=160,
    )

    st.markdown("**Fotos / evidências (opcional)**")
    st.file_uploader(
        "Selecione uma ou mais fotos (não impacta o PDF ainda, apenas para evidência visual no app)",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="fotos_unificada",
    )

    st.markdown("</div>", unsafe_allow_html=True)


# ========== GERAÇÃO DE PDF ==========

def _generate_pdf():
    """
    Por enquanto, apenas abre o template RAT_MAM_UNIFICADA_VF.pdf e oferece download.
    Depois fazemos o mapeamento dos campos para dentro do PDF (como nos outros RATs).
    """
    ss = st.session_state
    try:
        doc, page1 = open_pdf_template(PDF_BASE_PATH, hint="RAT_MAM_UNIFICADA")
    except Exception as e:
        st.error("Não consegui abrir o template PDF da RAT unificada.")
        st.exception(e)
        return

    # Futuro: aqui entra a lógica de preencher campos no page1/page2/etc usando fitz.

    out = BytesIO()
    doc.save(out)
    doc.close()

    st.success("RAT (template) gerada com sucesso! (preenchimento automático ainda não implementado).")
    st.download_button(
        "⬇️ Baixar RAT MAM Unificada",
        data=out.getvalue(),
        file_name=f"RAT_MAM_UNIFICADA_{(ss.numero_relatorio or 'sem_num')}.pdf",
        mime="application/pdf",
    )


# ========== FUNÇÃO PRINCIPAL CHAMADA PELO app.py ==========

def render():
    _apply_dark_theme()
    _init_rat_defaults()

    ss = st.session_state
    step = ss.rat_step if 1 <= ss.rat_step <= 5 else 1
    ss.rat_step = step  # normaliza

    _step_indicator(step)

    if step == 1:
        _render_step1()
    elif step == 2:
        _render_step2()
    elif step == 3:
        _render_step3()
    elif step == 4:
        _render_step4()
    else:
        _render_step5()

    _nav_buttons(step)
