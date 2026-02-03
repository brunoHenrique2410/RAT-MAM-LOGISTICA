# repo/rat_unificado.py
#
# RAT MAM UNIFICADA – lógica de estado + geração de PDF.
# Usa:
#  - ui_unificado.render_layout() para desenhar o formulário (abas)
#  - RAT_MAM_UNIFICADA_VF.pdf como template base

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
import ui_unificado  # nosso layout em abas


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
            # --------- ETAPA 1 ---------
            "num_relatorio": "",
            "num_chamado": "",
            "operadora_contrato": "",
            "cliente_razao": "",
            "distancia_km": "",
            "inicio_atend": "",
            "termino_atend": "",
            "contato_nome": "",
            "contato_telefone_email": "",
            "endereco_completo": "",
            "data_atendimento": datetime.now().date().isoformat(),
            # --------- ETAPA 2 ---------
            "analista_suporte": "",
            "analista_integradora": "",
            "analista_validador": "",
            "tipo_atendimento": "",
            "motivo_chamado": "",
            "checklist_tecnico": [],
            # --------- ETAPA 3 ---------
            "material_utilizado": "",
            "equip_instalados": "",
            "equip_retirados": "",
            # --------- ETAPA 4 ---------
            "testes_realizados": [],
            "descricao_atendimento": "",
            "observacoes_pendencias": "",
            # --------- ETAPA 5 ---------
            "nome_tecnico": "",
            "doc_tecnico": "",
            "tel_tecnico": "",
            "dt_tecnico": "",
            "nome_cliente": "",
            "doc_cliente": "",
            "tel_cliente": "",
            "dt_cliente": "",
            "sig_tec_png": None,
            "sig_cli_png": None,
            # --------- CONTROLE ---------
            "trigger_generate": False,
        }
    )


# =============== PREENCHIMENTO DO PDF ===============


def _fill_page1(page: fitz.Page, ss) -> None:
    """
    Preenche a PÁGINA 1 da RAT unificada:
    1) Dados do Relatório & Local de Atendimento.
    """

    # Nº Relatório / Nº Chamado / Operadora / Cliente
    insert_right_of(
        page,
        ["Nº Relatório", "N° Relatório", "No Relatório", "Numero Relatório"],
        ss.num_relatorio,
        dx=8,
        dy=1,
    )
    insert_right_of(
        page,
        ["Nº Chamado", "N° Chamado", "No Chamado", "Numero Chamado"],
        ss.num_chamado,
        dx=8,
        dy=1,
    )
    insert_right_of(
        page,
        ["Operadora / Contrato", "Operadora/Contrato", "Operadora Contrato"],
        ss.operadora_contrato,
        dx=8,
        dy=1,
    )
    insert_right_of(
        page,
        ["Cliente / Razão Social", "Cliente/Razão Social", "Cliente / Razao Social"],
        ss.cliente_razao,
        dx=8,
        dy=1,
    )

    # Início / Término (como texto livre HH:MM)
    insert_right_of(
        page,
        ["Início", "Inicio"],
        ss.inicio_atend,
        dx=8,
        dy=1,
    )
    insert_right_of(
        page,
        ["Término", "Termino"],
        ss.termino_atend,
        dx=8,
        dy=1,
    )

    # Contato + Telefone / E-mail
    insert_right_of(
        page,
        ["Contato", "Contato (nome)"],
        ss.contato_nome,
        dx=8,
        dy=1,
    )
    insert_right_of(
        page,
        ["Telefone / E-mail", "Telefone/E-mail", "Telefone / Email"],
        ss.contato_telefone_email,
        dx=8,
        dy=1,
    )

    # Endereço completo – geralmente é um bloco maior
    insert_textbox(
        page,
        ["Endereço Completo", "Endereço completo", "Endereco Completo"],
        ss.endereco_completo,
        width=520,
        y_offset=20,
        height=80,
        fontsize=9,
        align=0,
    )

    # --- DISTÂNCIA (KM) ---
    try:
        # converte string tipo "12,5" ou "12.5" para float
        dist_raw = str(getattr(ss, "distancia_km", "")).strip()
        dist_val = float(dist_raw.replace(",", "."))
        dist_txt = f"{dist_val:.1f}".replace(".", ",")  # 1 casa, vírgula
    except Exception:
        # se não conseguir converter, usa o texto cru
        dist_txt = str(getattr(ss, "distancia_km", ""))

    insert_right_of(
        page,
        ["Distância (KM)", "Distancia (KM)"],
        dist_txt,
        dx=8,
        dy=1,
    )

    # Data do atendimento
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
        ["Data do atendimento", "Data do Atendimento", "Data"],
        data_str,
        dx=8,
        dy=1,
    )


def _fill_page2(page: fitz.Page, ss) -> None:
    """
    Preenche a PÁGINA 2 da RAT unificada:
    2) Atendimento & Testes
    3) Materiais & Equipamentos
    4) Observações
    5) Aceite & Assinaturas
    """

    # --------- Atendimento & Testes ---------
    insert_right_of(
        page,
        ["Analista Suporte"],
        ss.analista_suporte,
        dx=8,
        dy=1,
    )
    insert_right_of(
        page,
        ["Analista Integradora (MAMINFO)", "Analista Integradora"],
        ss.analista_integradora,
        dx=8,
        dy=1,
    )
    insert_right_of(
        page,
        ["Analista validador (NOC / Projetos)", "Analista Validador"],
        ss.analista_validador,
        dx=8,
        dy=1,
    )
    insert_right_of(
        page,
        ["Tipo de Atendimento", "Tipo de atendimento"],
        ss.tipo_atendimento,
        dx=8,
        dy=1,
    )

    insert_textbox(
        page,
        ["Anormalidade / Motivo do Chamado", "Motivo do Chamado"],
        ss.motivo_chamado,
        width=520,
        y_offset=20,
        height=80,
        fontsize=9,
        align=0,
    )

    checklist_txt = ""
    if isinstance(ss.checklist_tecnico, list) and ss.checklist_tecnico:
        checklist_txt = " | ".join(ss.checklist_tecnico)

    insert_textbox(
        page,
        ["Checklist Técnico", "Checklist Tecnico"],
        checklist_txt,
        width=520,
        y_offset=20,
        height=60,
        fontsize=9,
        align=0,
    )

    # --------- Materiais & Equipamentos ---------
    insert_textbox(
        page,
        ["Material utilizado", "Materiais utilizados"],
        ss.material_utilizado,
        width=520,
        y_offset=20,
        height=80,
        fontsize=9,
        align=0,
    )

    insert_textbox(
        page,
        ["Equipamentos (Instalados)", "Equipamentos Instalados"],
        ss.equip_instalados,
        width=520,
        y_offset=20,
        height=80,
        fontsize=9,
        align=0,
    )

    insert_textbox(
        page,
        ["Equipamentos Retirados (se houver)", "Equipamentos Retirados"],
        ss.equip_retirados,
        width=520,
        y_offset=20,
        height=60,
        fontsize=9,
        align=0,
    )

    # --------- Observações ---------
    testes_txt = ""
    if isinstance(ss.testes_realizados, list) and ss.testes_realizados:
        testes_txt = " | ".join(ss.testes_realizados)

    insert_textbox(
        page,
        ["Testes realizados", "Testes executados"],
        testes_txt,
        width=520,
        y_offset=20,
        height=60,
        fontsize=9,
        align=0,
    )

    insert_textbox(
        page,
        ["Descrição do Atendimento", "Descricao do Atendimento"],
        ss.descricao_atendimento,
        width=520,
        y_offset=20,
        height=100,
        fontsize=9,
        align=0,
    )

    insert_textbox(
        page,
        ["Observações / Pendências", "Observacoes / Pendencias"],
        ss.observacoes_pendencias,
        width=520,
        y_offset=20,
        height=80,
        fontsize=9,
        align=0,
    )

    # --------- Aceite & Assinaturas ---------
    # Aqui eu coloco as infos em blocos de texto próximos dos rótulos
    tec_info = ""
    if ss.nome_tecnico or ss.doc_tecnico or ss.tel_tecnico or ss.dt_tecnico:
        tec_info = (
            f"Nome: {ss.nome_tecnico or ''}\n"
            f"Documento: {ss.doc_tecnico or ''}\n"
            f"Telefone: {ss.tel_tecnico or ''}\n"
            f"Data/hora: {ss.dt_tecnico or ''}"
        )

    cli_info = ""
    if ss.nome_cliente or ss.doc_cliente or ss.tel_cliente or ss.dt_cliente:
        cli_info = (
            f"Nome: {ss.nome_cliente or ''}\n"
            f"Documento: {ss.doc_cliente or ''}\n"
            f"Telefone: {ss.tel_cliente or ''}\n"
            f"Data/hora: {ss.dt_cliente or ''}"
        )

    insert_textbox(
        page,
        ["Técnico MAMINFO", "Tecnico MAMINFO"],
        tec_info,
        width=250,
        y_offset=10,
        height=80,
        fontsize=8,
        align=0,
    )

    insert_textbox(
        page,
        ["Cliente", "Cliente "],
        cli_info,
        width=250,
        y_offset=10,
        height=80,
        fontsize=8,
        align=0,
    )

    # Obs.: se no futuro quisermos colocar as assinaturas digitais (PNG),
    # podemos usar common.pdf.insert_signature_png ancorando em algum texto.


def generate_pdf_from_state(ss) -> bytes:
    """
    Abre o template RAT_MAM_UNIFICADA_VF.pdf, preenche e retorna bytes do PDF.
    """
    doc, page1 = open_pdf_template(PDF_BASE_PATH, hint="RAT_MAM_UNIFICADA")
    # page2: se o template tiver 2+ páginas, usa a segunda; senão cria nova
    page2 = doc[1] if doc.page_count >= 2 else doc.new_page()

    _fill_page1(page1, ss)
    _fill_page2(page2, ss)

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

    # Desenha layout (abas, modo escuro, etc.)
    ui_unificado.render_layout()

    ss = st.session_state

    # Se o botão "Gerar RAT" foi clicado na UI:
    if ss.get("trigger_generate"):
        try:
            pdf_bytes = generate_pdf_from_state(ss)
            st.success("RAT gerada com sucesso! ✅")

            # Monta nome de arquivo
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
