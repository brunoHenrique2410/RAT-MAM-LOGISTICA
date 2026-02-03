# repo/rat_unificado.py
#
# RAT MAM UNIFICADA – 2 PÁGINAS
# Template: pdf_templates/RAT_MAM_UNIFICADA_VF.pdf
#
# Página 1:
#   1. Identificação do Atendimento
#   2. Dados Operacionais
#   3. Horários e Deslocamento
#   4. Anormalidade / Motivo do Chamado
#   5. Checklist Técnico (SIM / NÃO)
#
# Página 2:
#   3. Materiais & Equipamentos
#   4. Observações
#   5. Aceite & Assinaturas

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
import ui_unificado  # layout / abas / modo escuro


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
            # --------- BLOCO 1 – Dados do Relatório & Local ---------
            "num_relatorio": "",
            "num_chamado": "",
            "operadora_contrato": "",
            "cliente_razao": "",
            "cnpj_cpf": "",
            "contato_nome": "",
            "contato_telefone_email": "",
            "endereco_completo": "",
            "distancia_km": "",
            "inicio_atend": "",   # "10:00"
            "termino_atend": "",  # "11:15"
            "data_atendimento": datetime.now().date().isoformat(),
            # --------- BLOCO 2 – Atendimento & Testes ---------
            "analista_suporte": "",
            "analista_integradora": "",
            "analista_validador": "",
            "tipo_atendimento": "",
            "motivo_chamado": "",
            "checklist_tecnico": [],  # lista de strings (UI marca SIM)
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
            "sig_tec_png": None,
            "sig_cli_png": None,
            # --------- CONTROLE ---------
            "trigger_generate": False,
        }
    )


# =============== HELPERS ===============


def _safe_date_to_str(value) -> str:
    try:
        if isinstance(value, date):
            d = value
        else:
            d = date.fromisoformat(str(value))
        return d.strftime("%d/%m/%Y")
    except Exception:
        return str(value or "")


def _safe_distancia_txt(ss) -> str:
    """
    Converte distancia_km para string com 1 casa e vírgula.
    Aceita '12,5', '12.5', '12', etc. Se não conseguir, retorna o valor cru.
    """
    try:
        raw = str(getattr(ss, "distancia_km", "")).strip()
        val = float(raw.replace(",", "."))
        return f"{val:.1f}".replace(".", ",")
    except Exception:
        return str(getattr(ss, "distancia_km", ""))


# =============== PÁGINA 1 ===============


def _fill_page1(page: fitz.Page, ss) -> None:
    """
    Preenche página 1 da RAT unificada:
    1. Identificação
    2. Dados Operacionais
    3. Horários e Deslocamento
    4. Anormalidade / Motivo
    5. Checklist Técnico
    """

    # ---------- 1) Identificação do Atendimento ----------

    insert_right_of(
        page,
        ["Nº Chamado", "N° Chamado", "No Chamado", "Numero Chamado"],
        ss.num_chamado,
        dx=8,
        dy=1,
    )

    insert_right_of(
        page,
        ["Nº Relatório", "N° Relatório", "No Relatório", "Numero Relatório"],
        ss.num_relatorio,
        dx=8,
        dy=1,
    )

    # Operadora / Contrato -> um pouco mais pra esquerda e mais baixo
    insert_right_of(
        page,
        ["Operadora / Contrato", "Operadora/Contrato", "Operadora Contrato"],
        ss.operadora_contrato,
        dx=2,   # encosta mais
        dy=3,   # desce um pouco
    )

    insert_right_of(
        page,
        ["Cliente / Razão Social", "Cliente/Razão Social", "Cliente / Razao Social"],
        ss.cliente_razao,
        dx=8,
        dy=1,
    )

    if getattr(ss, "cnpj_cpf", ""):
        insert_right_of(
            page,
            ["CNPJ/CPF", "CNPJ / CPF"],
            ss.cnpj_cpf,
            dx=8,
            dy=1,
        )

    # Contato nome – descer um pouco
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

    # Endereço Completo – subir ~1cm
    insert_textbox(
        page,
        ["Endereço Completo", "Endereço completo", "Endereco Completo"],
        ss.endereco_completo,
        width=520,
        y_offset=-20,  # sobe a caixa
        height=70,
        fontsize=9,
        align=0,
    )

    # ---------- 2) Dados Operacionais ----------

    # Campos individuais nos retângulos
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
        ["Analista validador (NOC / Projetos)", "Analista validador"],
        ss.analista_validador,
        dx=8,
        dy=1,
    )
    insert_right_of(
        page,
        ["Tipo de Atendimento"],
        ss.tipo_atendimento,
        dx=8,
        dy=1,
    )

    # ---------- 3) Horários e Deslocamento ----------

    data_str = _safe_date_to_str(ss.data_atendimento)

    insert_right_of(
        page,
        ["Data", "Data do atendimento", "Data do Atendimento"],
        data_str,
        dx=8,
        dy=6,  # desce ~0,5cm em relação ao label
    )

    insert_right_of(
        page,
        ["Início", "Inicio"],
        ss.inicio_atend,
        dx=8,
        dy=6,
    )

    insert_right_of(
        page,
        ["Término", "Termino"],
        ss.termino_atend,
        dx=8,
        dy=6,
    )

    insert_right_of(
        page,
        ["Distância (KM)", "Distancia (KM)"],
        _safe_distancia_txt(ss),
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
        height=80,
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


# =============== PÁGINA 2 ===============


def _fill_page2(page: fitz.Page, ss) -> None:
    """
    Preenche página 2:
      3. Materiais & Equipamentos
      4. Observações
      5. Aceite & Assinaturas
    (Os rótulos exatos dependem do seu PDF; ajustamos pelos textos.)
    """

    # ---------- 3) Materiais & Equipamentos ----------

    insert_textbox(
        page,
        ["Material utilizado", "Material Utilizado"],
        ss.material_utilizado,
        width=520,
        y_offset=20,
        height=80,
        fontsize=9,
        align=0,
    )

    insert_textbox(
        page,
        [
            "Equipamentos (Instalados / Existentes no Cliente)",
            "Equipamentos (Instalados)",
            "Equipamentos Instalados",
        ],
        ss.equip_instalados,
        width=520,
        y_offset=110,
        height=80,
        fontsize=9,
        align=0,
    )

    insert_textbox(
        page,
        ["Equipamentos Retirados (se houver)", "Equipamentos Retirados"],
        ss.equip_retirados,
        width=520,
        y_offset=200,
        height=80,
        fontsize=9,
        align=0,
    )

    # ---------- 4) Observações ----------

    testes_txt = ""
    if isinstance(ss.testes_realizados, list) and ss.testes_realizados:
        testes_txt = " | ".join(ss.testes_realizados)

    insert_textbox(
        page,
        ["Testes realizados", "Testes executados"],
        testes_txt,
        width=520,
        y_offset=20,
        height=70,
        fontsize=9,
        align=0,
        occurrence=2,  # se existir mais de um label parecido
    )

    insert_textbox(
        page,
        ["Descrição do Atendimento", "Descrição do atendimento"],
        ss.descricao_atendimento,
        width=520,
        y_offset=100,
        height=120,
        fontsize=9,
        align=0,
    )

    insert_textbox(
        page,
        ["Observações / Pendências", "Observacoes / Pendencias"],
        ss.observacoes_pendencias,
        width=520,
        y_offset=20,
        height=100,
        fontsize=9,
        align=0,
    )

    # ---------- 5) Aceite & Assinaturas ----------

    # Técnico MAMINFO
    insert_right_of(
        page,
        ["Nome Técnico", "Nome Tecnico"],
        ss.nome_tecnico,
        dx=8,
        dy=1,
    )
    insert_right_of(
        page,
        ["Documento Técnico", "Documento Tecnico"],
        ss.doc_tecnico,
        dx=8,
        dy=1,
    )
    insert_right_of(
        page,
        ["Telefone Técnico", "Telefone Tecnico"],
        ss.tel_tecnico,
        dx=8,
        dy=1,
    )
    insert_right_of(
        page,
        ["Data e hora (Técnico)", "Data e hora (Tecnico)"],
        ss.dt_tecnico,
        dx=8,
        dy=1,
    )

    # Cliente
    insert_right_of(
        page,
        ["Nome cliente", "Nome Cliente"],
        ss.nome_cliente,
        dx=8,
        dy=1,
    )
    insert_right_of(
        page,
        ["Documento cliente", "Documento Cliente"],
        ss.doc_cliente,
        dx=8,
        dy=1,
    )
    insert_right_of(
        page,
        ["Telefone cliente", "Telefone Cliente"],
        ss.tel_cliente,
        dx=8,
        dy=1,
    )
    insert_right_of(
        page,
        ["Data e hora (Cliente)", "Data e hora (cliente)"],
        ss.dt_cliente,
        dx=8,
        dy=1,
    )

    # (Se quiser depois, dá pra inserir assinaturas PNG aqui usando common.pdf.insert_signature_png)


# =============== GERAÇÃO DO PDF ===============


def generate_pdf_from_state(ss) -> bytes:
    """
    Abre o template RAT_MAM_UNIFICADA_VF.pdf (2 páginas),
    preenche e retorna os bytes do PDF.
    """
    doc, page1 = open_pdf_template(PDF_BASE_PATH, hint="RAT_MAM_UNIFICADA")

    _fill_page1(page1, ss)

    if doc.page_count >= 2:
        page2 = doc[1]
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

    # UI em abas / passos (modo escuro) – definido em ui_unificado.py
    ui_unificado.render_layout()

    ss = st.session_state

    # Gatilho do botão "Gerar RAT" vindo da UI
    if ss.get("trigger_generate"):
        try:
            pdf_bytes = generate_pdf_from_state(ss)
            st.success("RAT gerada com sucesso! ✅")

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
            ss.trigger_generate = False
