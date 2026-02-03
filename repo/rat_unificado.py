# repo/rat_unificado.py
"""
RAT MAM UNIFICADA – App principal
- Usa layout em ui_unificado.py (modo escuro, full width, logo Evernex).
- Controla steps (1..5) sem precisar clicar 2x.
- Gera PDF baseado no template RAT_MAM_UNIFICADA_VF.pdf
  Página 1: Bloco 1 + 2
  Página 2: Bloco 3 + 4 + 5
  Página 3+ : Fotos de seriais (uma por página)
"""

import os
import sys
from io import BytesIO
from datetime import date, time, datetime
from zoneinfo import ZoneInfo

import streamlit as st
import fitz  # PyMuPDF

# ---------- PATH / IMPORTS COMUNS ----------
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common.state import init_defaults
from common.pdf import (
    open_pdf_template,
    insert_right_of,
    insert_textbox,
    add_image_page,
)
import ui_unificado


# ---------- CONFIG PDF ----------
PDF_DIR = os.path.join(PROJECT_ROOT, "pdf_templates")
UNIF_PDF_PATH = os.path.join(PDF_DIR, "RAT_MAM_UNIFICADA_VF.pdf")
DEFAULT_TZ = "America/Sao_Paulo"


# ---------- DEFAULTS DE SESSÃO ----------
def _init_rat_defaults():
    """
    Define apenas defaults para chaves que ainda não existem em st.session_state.
    Não reseta nada a cada rerun.
    """
    init_defaults(
        {
            # Controle de steps / geração
            "step": 1,
            "trigger_generate": False,

            # 1) Dados do Relatório & Local de Atendimento
            "numero_relatorio": "",
            "numero_chamado": "",
            "operadora_contrato": "",
            "cliente_razao": "",
            "data_atendimento": date.today(),
            "hora_inicio": time(8, 0),
            "hora_termino": time(10, 0),
            "contato_nome": "",
            "endereco_completo": "",
            "telefone_email": "",
            "distancia_km": 0.0,

            # 2) Atendimento & Testes
            "analista_suporte": "",
            "analista_integradora": "",
            "analista_validador": "",
            "tipo_atendimento": [],
            "anormalidade": "",
            "checklist_tecnico_ok": "SIM",  # SIM / NAO

            # 3) Materiais & Equipamentos
            "material_utilizado": "",
            "equip_instalados": "",
            "equip_retirados": "",

            # 4) Observações
            "testes_realizados": [],
            "descricao_atendimento": "",
            "observacoes_pendencias": "",

            # 5) Aceite & Assinaturas
            "nome_tecnico": "",
            "doc_tecnico": "",
            "tel_tecnico": "",
            "data_hora_tecnico": "",
            "nome_cliente": "",
            "doc_cliente": "",
            "tel_cliente": "",
            "data_hora_cliente": "",

            # Assinaturas (se você quiser usar depois com common.ui.assinatura_dupla_png)
            "sig_tec_png": None,
            "sig_cli_png": None,

            # Fotos de seriais (evidências)
            "fotos_seriais": [],
            # Fuso do navegador (opcional, se quiser usar depois)
            "browser_tz": "",
        }
    )


# ---------- GERAÇÃO DO PDF ----------
def _get_now_with_tz(ss) -> datetime:
    """Retorna datetime com base no browser_tz se existir, senão DEFAULT_TZ."""
    tzname = ss.get("browser_tz", "").strip() or DEFAULT_TZ
    try:
        tz = ZoneInfo(tzname)
    except Exception:
        tz = ZoneInfo(DEFAULT_TZ)
    return datetime.now(tz=tz)


def _fill_page1(page1: fitz.Page, ss):
    """
    Preenche Página 1 do template:
    1) Dados do Relatório & Local
    2) Atendimento & Testes
    Usa labels aproximados; se não achar algum, simplesmente ignora.
    """

    # --- Bloco 1: Dados do Relatório & Local ---
    insert_right_of(page1, ["N° Relatório", "Nº Relatório", "No Relatório"], ss.numero_relatorio, dx=8, dy=1)
    insert_right_of(page1, ["N° Chamado", "Nº Chamado", "No Chamado"], ss.numero_chamado, dx=8, dy=1)
    insert_right_of(page1, ["Operadora / Contrato", "Operadora/Contrato"], ss.operadora_contrato, dx=8, dy=1)
    insert_right_of(page1, ["Cliente / Razão Social", "Cliente / Razao Social"], ss.cliente_razao, dx=8, dy=1)

    # Data, Início, Término
    if isinstance(ss.data_atendimento, date):
        data_txt = ss.data_atendimento.strftime("%d/%m/%Y")
    else:
        data_txt = str(ss.data_atendimento or "")

    insert_right_of(page1, ["Data do Atendimento", "Data"], data_txt, dx=8, dy=1)
    insert_right_of(page1, ["Início", "Inicio"], ss.hora_inicio.strftime("%H:%M"), dx=8, dy=1)
    insert_right_of(page1, ["Término", "Termino"], ss.hora_termino.strftime("%H:%M"), dx=8, dy=1)

    insert_right_of(page1, ["Contato"], ss.contato_nome, dx=8, dy=1)
    insert_textbox(
        page1,
        ["Endereço Completo", "Endereco Completo"],
        ss.endereco_completo,
        width=520,
        y_offset=10,
        fontsize=9,
    )
    insert_right_of(page1, ["Telefone / E-mail", "Telefone/E-mail"], ss.telefone_email, dx=8, dy=1)

   # --- DISTÂNCIA (KM) ---  (rat_unificado.py, dentro do _fill_page1)
      try:
          # converte string tipo "12,5" ou "12.5" para float
          dist_raw = str(getattr(ss, "distancia_km", "")).strip()
          dist_val = float(dist_raw.replace(",", "."))
          dist_txt = f"{dist_val:.1f}".replace(".", ",")  # formata 1 casa, com vírgula
      except Exception:
          # se não conseguir converter, usa o texto cru
          dist_txt = str(getattr(ss, "distancia_km", ""))

      insert_right_of(
          page1,
          ["Distância (KM)", "Distancia (KM)"],
          dist_txt,
          dx=8,
          dy=1,
      )

    # --- Bloco 2: Atendimento & Testes ---
    insert_right_of(page1, ["Analista Suporte"], ss.analista_suporte, dx=8, dy=1)
    insert_right_of(page1, ["Analista Integradora", "Analista Integradora (MAMINFO)"], ss.analista_integradora, dx=8, dy=1)
    insert_right_of(page1, ["Analista validador", "Analista Validador"], ss.analista_validador, dx=8, dy=1)

    # Tipo de Atendimento (multiselect → string)
    if ss.tipo_atendimento:
        tipo_txt = " / ".join(ss.tipo_atendimento)
        insert_textbox(
            page1,
            ["Tipo de Atendimento"],
            tipo_txt,
            width=520,
            y_offset=10,
            fontsize=9,
        )

    insert_textbox(
        page1,
        ["Anormalidade / Motivo do Chamado", "Anormalidade / motivo do chamado"],
        ss.anormalidade,
        width=520,
        y_offset=10,
        fontsize=9,
    )

    # Checklist Técnico (SIM/NÃO)
    # Se o template tiver "Checklist Técnico" ou similar, você pode marcar X depois;
    # aqui, por enquanto, escrevemos o valor ao lado do label.
    insert_right_of(page1, ["Checklist Técnico", "Checklist Tecnico"], ss.checklist_tecnico_ok, dx=8, dy=1)


def _fill_page2(page2: fitz.Page, ss, now: datetime):
    """
    Preenche Página 2:
    3) Materiais & Equipamentos
    4) Observações
    5) Aceite & Assinaturas
    """

    # --- Bloco 3: Materiais & Equipamentos ---
    insert_textbox(
        page2,
        ["Material utilizado", "Material Utilizado"],
        ss.material_utilizado,
        width=540,
        y_offset=10,
        fontsize=9,
        height=120,
    )

    insert_textbox(
        page2,
        ["Equipamentos (Instalados)", "Equipamentos Instalados"],
        ss.equip_instalados,
        width=540,
        y_offset=10,
        fontsize=9,
        height=120,
    )

    insert_textbox(
        page2,
        ["Equipamentos Retirados", "Equipamentos Retirados (se houver)"],
        ss.equip_retirados,
        width=540,
        y_offset=10,
        fontsize=9,
        height=120,
    )

    # --- Bloco 4: Observações ---
    # Testes realizados (check list)
    if ss.testes_realizados:
        testes_txt = ", ".join(ss.testes_realizados)
    else:
        testes_txt = ""

    insert_textbox(
        page2,
        ["Testes realizados", "Testes executados"],
        testes_txt,
        width=540,
        y_offset=10,
        fontsize=9,
        height=80,
    )

    insert_textbox(
        page2,
        ["Descrição do Atendimento", "Descricao do Atendimento"],
        ss.descricao_atendimento,
        width=540,
        y_offset=10,
        fontsize=9,
        height=150,
    )

    insert_textbox(
        page2,
        ["Observações / Pendências", "Observacoes / Pendencias"],
        ss.observacoes_pendencias,
        width=540,
        y_offset=10,
        fontsize=9,
        height=120,
    )

    # --- Bloco 5: Aceite & Assinaturas ---
    # Aqui assumo que o PDF tem campos com esses rótulos ou parecidos.
    insert_right_of(page2, ["Nome Técnico", "Nome Tecnico"], ss.nome_tecnico, dx=8, dy=1)
    insert_right_of(page2, ["Documento Técnico", "Documento Tecnico"], ss.doc_tecnico, dx=8, dy=1)
    insert_right_of(page2, ["Telefone Técnico", "Telefone Tecnico"], ss.tel_tecnico, dx=8, dy=1)

    # Se não preencher manual, usamos agora
    dt_tec = ss.data_hora_tecnico.strip() if isinstance(ss.data_hora_tecnico, str) else ""
    if not dt_tec:
        dt_tec = now.strftime("%d/%m/%Y %H:%M")

    insert_right_of(page2, ["Data e hora técnico", "Data e hora Tecnico", "Data/Hora Técnico"], dt_tec, dx=8, dy=1)

    insert_right_of(page2, ["Nome cliente", "Nome Cliente"], ss.nome_cliente, dx=8, dy=1)
    insert_right_of(page2, ["Documento cliente", "Documento Cliente"], ss.doc_cliente, dx=8, dy=1)
    insert_right_of(page2, ["Telefone cliente", "Telefone Cliente"], ss.tel_cliente, dx=8, dy=1)

    dt_cli = ss.data_hora_cliente.strip() if isinstance(ss.data_hora_cliente, str) else ""
    if not dt_cli:
        dt_cli = now.strftime("%d/%m/%Y %H:%M")

    insert_right_of(page2, ["Data e hora cliente", "Data/Hora Cliente"], dt_cli, dx=8, dy=1)

    # Assinaturas em imagem (opcional – se quiser usar depois com sig_tec_png/sig_cli_png)
    # Aqui deixo preparado para evoluir depois, pois depende de onde estão as âncoras no PDF.


def _append_fotos_seriais(doc: fitz.Document, ss):
    """
    Cria páginas extras a partir das fotos dos seriais:
    - Página 3 = 1ª foto
    - Página 4 = 2ª foto
    - ...
    Utiliza common.pdf.add_image_page.
    """
    fotos = ss.get("fotos_seriais") or []
    for img_bytes in fotos:
        if not img_bytes:
            continue
        add_image_page(doc, img_bytes)


def generate_pdf_from_state(ss) -> bytes:
    """
    Abre o template RAT_MAM_UNIFICADA_VF.pdf e gera o PDF final.
    """
    doc, page1 = open_pdf_template(UNIF_PDF_PATH, hint="RAT_MAM_UNIFICADA_VF")
    now = _get_now_with_tz(ss)

    # Garante que haja ao menos 2 páginas (template costuma ter 2)
    if doc.page_count >= 2:
        page2 = doc[1]
    else:
        page2 = doc.new_page()

    # Preenche páginas
    _fill_page1(page1, ss)
    _fill_page2(page2, ss, now)
    _append_fotos_seriais(doc, ss)

    # Salva para bytes
    out = BytesIO()
    doc.save(out)
    doc.close()
    out.seek(0)
    return out.getvalue()


# ---------- ENTRYPOINT STREAMLIT ----------
def render():
    """
    Função principal chamada pelo app.py
    """
    _init_rat_defaults()
    ss = st.session_state

    # Desenha layout (modo escuro, steps, etc.)
    ui_unificado.render_layout()

    # Se o botão "Gerar RAT" foi clicado na última etapa:
    if ss.get("trigger_generate"):
        try:
            pdf_bytes = generate_pdf_from_state(ss)
            st.success("✅ RAT MAM Unificada gerada com sucesso!")

            nome_rel = ss.numero_relatorio or "sem_numero"
            st.download_button(
                "⬇️ Baixar RAT MAM Unificada",
                data=pdf_bytes,
                file_name=f"RAT_MAM_UNIFICADA_{nome_rel}.pdf",
                mime="application/pdf",
            )
        except Exception as e:
            st.error("Falha ao gerar a RAT Unificada.")
            st.exception(e)
        finally:
            # Reseta o gatilho para não gerar de novo sozinho
            ss.trigger_generate = False


if __name__ == "__main__":
    # Se estiver rodando direto este arquivo:
    render()
