# repo/rat_unificado.py
#
# RAT MAM UNIFICADA – lógica de estado + geração de PDF.
# Template: RAT_MAM_UNIFICADA_VF.pdf (1 página)
#
# Este módulo:
#  - Inicializa o session_state da RAT
#  - Usa ui_unificado.render_layout() para desenhar o formulário em abas
#  - Gera o PDF preenchendo a própria página 1 do template

import os
from io import BytesIO
from datetime import datetime, date

import streamlit as st
import fitz  # PyMuPDF

from common.state import init_defaults
from common.pdf import (
    open_pdf_template,
    insert_right_of,
    insert_textbox,
)
import ui_unificado  # layout em abas (modo escuro, etc.)


# =============== PATHS / CONSTANTES ===============

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)

PDF_DIR = os.path.join(PROJECT_ROOT, "pdf_templates")
PDF_BASE_PATH = os.path.join(PDF_DIR, "RAT_MAM_UNIFICADA_VF.pdf")


# =============== STATE DEFAULTS ===============


def _init_rat_defaults() -> None:
    """
    Inicializa todos os campos usados pela UI + geração de PDF,
    para evitar KeyError em st.session_state.
    """
    init_defaults(
        {
            # --------- BLOCO 1 – Identificação / Local ---------
            "num_relatorio": "",
            "num_chamado": "",
            "operadora_contrato": "",
            "cliente_razao": "",
            "cnpj_cpf": "",
            "contato_nome": "",
            "contato_telefone_email": "",
            "endereco_completo": "",
            "distancia_km": "",
            "inicio_atend": "",
            "termino_atend": "",
            "data_atendimento": datetime.now().date().isoformat(),
            # --------- BLOCO 2 – Atendimento & Testes ---------
            "analista_suporte": "",
            "analista_integradora": "",
            "analista_validador": "",
            "tipo_atendimento": "",
            "motivo_chamado": "",
            "checklist_tecnico": [],  # lista de strings
            # --------- BLOCO 3 – Materiais & Equipamentos ---------
            "material_utilizado": "",
            "equip_instalados": "",
            "equip_retirados": "",
            # --------- BLOCO 4 – Observações ---------
            "testes_realizados": [],  # lista de strings
            "descricao_atendimento": "",
            "observacoes_pendencias": "",
            # --------- BLOCO 5 – Aceite & Assinaturas ---------
            "nome_tecnico": "",
            "doc_tecnico": "",
            "tel_tecnico": "",
            "dt_tecnico": "",
            "nome_cliente": "",
            "doc_cliente": "",
            "tel_cliente": "",
            "dt_cliente": "",
            # Assinaturas em PNG – se você usar depois
            "sig_tec_png": None,
            "sig_cli_png": None,
            # --------- CONTROLE ---------
            "trigger_generate": False,
        }
    )


# =============== PREENCHIMENTO DO PDF (1 PÁGINA) ===============


def _fill_page(page: fitz.Page, ss) -> None:
    """
    Preenche a única página da RAT unificada (RAT_MAM_UNIFICADA_VF.pdf)
    com TODOS os blocos (1 a 6 do modelo).
    """

    # ---------- 1) Identificação do Atendimento ----------

    # Nº Chamado
    insert_right_of(
        page,
        ["Nº Chamado", "N° Chamado", "No Chamado", "Numero Chamado"],
        ss.num_chamado,
        dx=8,
        dy=1,
    )

    # Nº Relatório
    insert_right_of(
        page,
        ["Nº Relatório", "N° Relatório", "No Relatório", "Numero Relatório"],
        ss.num_relatorio,
        dx=8,
        dy=1,
    )

    # Operadora / Contrato – descer e ir um pouco mais pra esquerda
    insert_right_of(
        page,
        ["Operadora / Contrato", "Operadora/Contrato", "Operadora Contrato"],
        ss.operadora_contrato,
        dx=2,   # mais perto do rótulo
        dy=3,   # um pouco mais baixo
    )

    # Cliente / Razão Social
    insert_right_of(
        page,
        ["Cliente / Razão Social", "Cliente/Razão Social", "Cliente / Razao Social"],
        ss.cliente_razao,
        dx=8,
        dy=1,
    )

    # CNPJ/CPF (se você quiser usar – está no template)
    if getattr(ss, "cnpj_cpf", ""):
        insert_right_of(
            page,
            ["CNPJ/CPF", "CNPJ / CPF"],
            ss.cnpj_cpf,
            dx=8,
            dy=1,
        )

    # Contato (nome) – descer um pouco
    insert_right_of(
        page,
        ["Contato (nome)", "Contato", "Contato (Nome)"],
        ss.contato_nome,
        dx=8,
        dy=3,
    )

    # Telefone / E-mail – descer um pouco
    insert_right_of(
        page,
        ["Telefone / E-mail", "Telefone/E-mail", "Telefone / Email"],
        ss.contato_telefone_email,
        dx=8,
        dy=3,
    )

    # Endereço Completo – subir ~1 cm (offset negativo)
    insert_textbox(
        page,
        ["Endereço Completo", "Endereço completo", "Endereco Completo"],
        ss.endereco_completo,
        width=520,
        y_offset=-20,   # antes era ~20; negativo sobe a caixa
        height=70,
        fontsize=9,
        align=0,
    )

    # ---------- 2) Dados Operacionais ----------

    # Campo-resumo embaixo do título "2. Dados Operacionais"
    resumo_oper = ""
    if any(
        [
            ss.analista_suporte,
            ss.analista_integradora,
            ss.analista_validador,
            ss.tipo_atendimento,
        ]
    ):
        partes = []
        if ss.analista_suporte:
            partes.append(f"Suporte: {ss.analista_suporte}")
        if ss.analista_integradora:
            partes.append(f"Integradora: {ss.analista_integradora}")
        if ss.analista_validador:
            partes.append(f"Validador: {ss.analista_validador}")
        if ss.tipo_atendimento:
            partes.append(f"Tipo: {ss.tipo_atendimento}")
        resumo_oper = " | ".join(partes)

    if resumo_oper:
        insert_textbox(
            page,
            ["2. Dados Operacionais", "Dados Operacionais"],
            resumo_oper,
            width=520,
            y_offset=12,
            height=40,
            fontsize=8,
            align=0,
        )

    # Analista Suporte (caixa própria logo abaixo do título)
    insert_right_of(
        page,
        ["Analista Suporte"],
        ss.analista_suporte,
        dx=8,
        dy=1,
    )

    # Analista Integradora (MAMINFO)
    insert_right_of(
        page,
        ["Analista Integradora (MAMINFO)", "Analista Integradora"],
        ss.analista_integradora,
        dx=8,
        dy=1,
    )

    # Analista validador (NOC / Projetos)
    insert_right_of(
        page,
        ["Analista validador (NOC / Projetos)", "Analista validador"],
        ss.analista_validador,
        dx=8,
        dy=1,
    )

    # Tipo de Atendimento (texto, mesmo o template tendo checkboxes)
    insert_right_of(
        page,
        ["Tipo de Atendimento"],
        ss.tipo_atendimento,
        dx=8,
        dy=1,
    )

    # ---------- 3) Horários e Deslocamento ----------

    # Data
    data_str = ""
    try:
        if isinstance(ss.data_atendimento, date):
            d = ss.data_atendimento
        else:
            d = date.fromisoformat(str(ss.data_atendimento))
        data_str = d.strftime("%d/%m/%Y")
    except Exception:
        data_str = str(ss.data_atendimento or "")

    insert_right_of(
        page,
        ["Data", "Data do atendimento", "Data do Atendimento"],
        data_str,
        dx=8,
        dy=6,  # desce ~0,5 cm
    )

    # Início
    insert_right_of(
        page,
        ["Início", "Inicio"],
        ss.inicio_atend,
        dx=8,
        dy=6,
    )

    # Término
    insert_right_of(
        page,
        ["Término", "Termino"],
        ss.termino_atend,
        dx=8,
        dy=6,
    )

    # Distância (KM) – com tratamento numérico seguro
    try:
        dist_raw = str(getattr(ss, "distancia_km", "")).strip()
        dist_val = float(dist_raw.replace(",", "."))
        dist_txt = f"{dist_val:.1f}".replace(".", ",")
    except Exception:
        dist_txt = str(getattr(ss, "distancia_km", ""))

    insert_right_of(
        page,
        ["Distância (KM)", "Distancia (KM)"],
        dist_txt,
        dx=8,
        dy=6,
    )

    # ---------- 4) Anormalidade / Motivo do Chamado ----------

    insert_textbox(
        page,
        [
            "4. Anormalidade / Motivo do Chamado",
            "Anormalidade / Motivo do Chamado",
            "Anormalidade/Motivo do Chamado",
        ],
        ss.motivo_chamado,
        width=520,
        y_offset=20,
        height=90,
        fontsize=9,
        align=0,
    )

    # ---------- 5) Checklist Técnico (SIM / NÃO) ----------

    checklist_txt = ""
    if isinstance(ss.checklist_tecnico, list) and ss.checklist_tecnico:
        checklist_txt = " | ".join(ss.checklist_tecnico)

    insert_textbox(
        page,
        [
            "5. Checklist Técnico (SIM / NÃO)",
            "Checklist Técnico (SIM / NÃO)",
            "Checklist Técnico",
            "Checklist Tecnico",
        ],
        checklist_txt,
        width=520,
        y_offset=20,
        height=90,
        fontsize=9,
        align=0,
    )

    # ---------- 6) Aceite ----------

    # No template atual, há apenas os campos do CLIENTE.
    # Vamos mapear os dados do cliente diretamente, e usar os dados do técnico
    # como observação extra logo abaixo dos campos.

    insert_right_of(
        page,
        ["Nome do cliente", "Nome do Cliente"],
        ss.nome_cliente,
        dx=8,
        dy=1,
    )

    insert_right_of(
        page,
        ["Documento", "Documento "],
        ss.doc_cliente,
        dx=8,
        dy=1,
    )

    insert_right_of(
        page,
        ["Telefone", "Telefone "],
        ss.tel_cliente,
        dx=8,
        dy=1,
    )

    # Observação com dados do técnico (fica no bloco de aceite, perto do texto de declaração)
    tecnico_info = ""
    if ss.nome_tecnico or ss.doc_tecnico or ss.tel_tecnico or ss.dt_tecnico:
        tecnico_info = (
            "Dados do Técnico MAMINFO:\n"
            f"Nome: {ss.nome_tecnico or ''}\n"
            f"Documento: {ss.doc_tecnico or ''}\n"
            f"Telefone: {ss.tel_tecnico or ''}\n"
            f"Data/hora: {ss.dt_tecnico or ''}"
        )

    if tecnico_info:
        insert_textbox(
            page,
            [
                "Declaro que recebi as orientações técnicas necessárias",
                "Declaro que recebi as orientacoes tecnicas necessarias",
            ],
            tecnico_info,
            width=260,
            y_offset=-60,  # sobe um pouco, ficando acima/ao lado do texto
            height=80,
            fontsize=7,
            align=0,
        )


def generate_pdf_from_state(ss) -> bytes:
    """
    Abre o template RAT_MAM_UNIFICADA_VF.pdf, preenche e retorna bytes do PDF.
    (somente página 1)
    """
    doc, page1 = open_pdf_template(PDF_BASE_PATH, hint="RAT_MAM_UNIFICADA")
    _fill_page(page1, ss)

    out = BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()


# =============== ENTRYPOINT PARA O APP ===============


def render():
    """
    Função principal chamada pelo app.py
    """
    _init_rat_defaults()

    # Desenha layout (abas, modo escuro, etc.) – toda a UI fica em ui_unificado
    ui_unificado.render_layout()

    ss = st.session_state

    # Se o botão "Gerar RAT" foi clicado na UI (ui_unificado seta trigger_generate=True)
    if ss.get("trigger_generate"):
        try:
            pdf_bytes = generate_pdf_from_state(ss)
            st.success("RAT gerada com sucesso! ✅")

            # Nome de arquivo amigável
            nome_base = (
                ss.num_relatorio
                or ss.num_chamado
                or ss.cliente_razao
                or "RAT_MAM"
            )
            nome_base = (
                str(nome_base)
                .strip()
                .replace(" ", "_")
                .replace("/", "-")
            )

            st.download_button(
                "⬇️ Baixar RAT (PDF)",
                data=pdf_bytes,
                file_name=f"{nome_base}.pdf",
                mime="application/pdf",
            )
        except Exception as e:
            st.error("Falha ao gerar o PDF da RAT.")
            st.exception(e)
        finally:
            # reseta o gatilho para não ficar gerando em todos os reruns
            ss.trigger_generate = False
