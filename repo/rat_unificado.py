# repo/rat_unificado.py
#
# RAT MAM UNIFICADA – 2 PÁGINAS
# Template: pdf_templates/RAT_MAM_UNIFICADA_VF.pdf
#
# Pág. 1:
#   1) Identificação do Atendimento
#   2) Dados Operacionais
#   3) Horários e Deslocamento
#   4) Anormalidade / Motivo do Chamado
#   5) Checklist Técnico (SIM / NÃO)
#
# Pág. 2:
#   3) Materiais & Equipamentos
#   4) Observações
#   5) Aceite & Assinaturas

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
    mark_X_left_of,
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
            "tipo_atendimento": "",          # ex.: "Instalação", "Ativação"...
            # para futuro: lista de flags de anormalidade
            "anormalidade_flags": [],        # ex.: ["Interrupção total", "Lentidão"]
            "motivo_chamado": "",            # fallback texto livre
            # checklist técnico – por enquanto texto; no futuro pode virar dict
            "checklist_tecnico": [],
            # --------- BLOCO 3 – Materiais & Equipamentos ---------
            "material_utilizado": "",
            "equip_instalados": "",
            "equip_retirados": "",
            # --------- BLOCO 4 – Observações ---------
            "testes_realizados": [],
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
        # formato separado, com mais espaço entre dia/mes/ano
        return f"{d.day:02d}   {d.month:02d}   {d.year:04d}"
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


def _mark_tipo_atendimento(page: fitz.Page, tipo: str) -> None:
    """
    Marca X no checkbox do Tipo de Atendimento, de acordo com o valor vindo da UI.
    Se não bater nenhuma opção, não faz nada (ou deixamos fallback em texto).
    """
    if not tipo:
        return

    t = tipo.strip().lower()

    def mx(label: str):
        # pequeno deslocamento pra encaixar na caixinha
        mark_X_left_of(page, label, dx=-10, dy=0, fontsize=11)

    if "instala" in t:
        mx("Instalação")
    elif "ativ" in t:
        mx("Ativação")
    elif "manut" in t and "corre" in t:
        mx("Manut. Corretiva")
    elif "manut" in t and "preven" in t:
        mx("Manut. Preventiva")
    elif "verif" in t:
        mx("Verificação")
    elif "retir" in t:
        mx("Retirada")
    elif "pass" in t and "cabo" in t:
        mx("Passagem de cabo")
    elif "outro" in t:
        mx("Outros")
    # senão, deixa passar em branco (pode complementar com texto manual se quiser)


def _mark_anormalidades(page: fitz.Page, flags) -> None:
    """
    Marca X nas opções de "Anormalidade / Motivo do Chamado"
    se receber uma lista de strings (flags). Caso contrário, não faz nada.
    """
    if not flags or not isinstance(flags, (list, tuple, set)):
        return

    # normaliza para lower
    norm = [str(f).strip().lower() for f in flags]

    def mx(label: str):
        mark_X_left_of(page, label, dx=-10, dy=0, fontsize=11)

    # mapeamento bem solto, para pegar as principais frases
    for f in norm:
        if "interrup" in f or "total" in f:
            mx("Interrupção total")
        if "sincron" in f:
            mx("Sem sincronismo")
        if "mensagem" in f or "erro" in f:
            mx("Mensagem com erro")
        if "intermit" in f or "queda" in f:
            mx("Intermitência / Quedas")
        if "taxa" in f:
            mx("Taxa de erro")
        if "portadora" in f:
            mx("Sem portadora")
        if "lentidao" in f or "lentidão" in f:
            mx("Lentidão")
        if "ruido" in f or "ruído" in f:
            mx("Ruído")
        if "outro" in f:
            mx("Outros")


# (Checklist Técnico em X é mais chato porque depende dos "Sim"/"Não" do template.
#  Por enquanto mantemos em texto, mas dá pra evoluir depois.)


# =============== PÁGINA 1 ===============


def _fill_page1(page: fitz.Page, ss) -> None:
    """
    Preenche página 1 da RAT unificada:
    1. Identificação
    2. Dados Operacionais
    3. Horários e Deslocamento
    4. Anormalidade / Motivo do Chamado
    5. Checklist Técnico
    """

    # ---------- 1) Identificação do Atendimento ----------

    # Nº Chamado – descer 20 "px"
    insert_right_of(
        page,
        ["Nº Chamado", "N° Chamado", "No Chamado", "Numero Chamado"],
        ss.num_chamado,
        dx=8,
        dy=15,
    )

    # Nº Relatório – descer 20 "px"
    insert_right_of(
        page,
        ["Nº Relatório", "N° Relatório", "No Relatório", "Numero Relatório"],
        ss.num_relatorio,
        dx=8,
        dy=15,
    )

    # Operadora / Contrato -> descer 15 e ~100px para a esquerda
    insert_right_of(
        page,
        ["Operadora / Contrato", "Operadora/Contrato", "Operadora Contrato"],
        ss.operadora_contrato,
        dx=-25,   # move pra esquerda
        dy=15,    # desce
    )

    insert_right_of(
        page,
        ["Cliente / Razão Social", "Cliente/Razão Social", "Cliente / Razao Social"],
        ss.cliente_razao,
        dx=8,
        dy=15,
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
        dx=1,
        dy=15,
    )

    # Telefone / E-mail – descer um pouco
    insert_right_of(
        page,
        ["Telefone / E-mail", "Telefone/E-mail", "Telefone / Email"],
        ss.contato_telefone_email,
        dx=8,
        dy=15,
    )

    # Endereço Completo – descer ~39 "px"
    insert_textbox(
        page,
        ["Endereço Completo", "Endereço completo", "Endereco Completo"],
        ss.endereco_completo,
        width=500,
        y_offset=1,
        height=90,
        fontsize=9,
        align=0,
    )

    # ---------- 2) Dados Operacionais ----------

    # Analista Suporte – descer 25 / 40 pra esquerda
    insert_right_of(
        page,
        ["Analista Suporte"],
        ss.analista_suporte,
        dx=-25,
        dy=15,
    )

    # Analista Integradora – descer 25 / 40 pra esquerda
    insert_right_of(
        page,
        ["Analista Integradora (MAMINFO)", "Analista Integradora"],
        ss.analista_integradora,
        dx=-110,
        dy=15,
    )

    # Analista validador – descer 25 / 40 pra esquerda
    insert_right_of(
        page,
        ["Analista validador (NOC / Projetos)", "Analista validador"],
        ss.analista_validador,
        dx=-130,
        dy=15,
    )

    # Tipo de Atendimento – marca X na opção escolhida
    _mark_tipo_atendimento(page, getattr(ss, "tipo_atendimento", ""))

    # ---------- 3) Horários e Deslocamento ----------

    data_str = _safe_date_to_str(ss.data_atendimento)

    # Data – descer 15 e separar mais o espaçamento
    insert_right_of(
        page,
        ["Data", "Data do atendimento", "Data do Atendimento"],
        data_str,
        dx=-2,
        dy=15,
    )

    # Início – descer 15
    insert_right_of(
        page,
        ["Início", "Inicio"],
        ss.inicio_atend,
        dx=1,
        dy=15,
    )

    # Término – descer 15
    insert_right_of(
        page,
        ["Término", "Termino"],
        ss.termino_atend,
        dx=-9,
        dy=15,
    )

    # Distância (KM) – descer 15
    insert_right_of(
        page,
        ["Distância (KM)", "Distancia (KM)"],
        _safe_distancia_txt(ss),
        dx=8,
        dy=15,
    )

    # ---------- 4) Anormalidade / Motivo do Chamado ----------

    # Primeiro tentamos marcar X se vier lista de flags
    flags = getattr(ss, "anormalidade_flags", None)
    _mark_anormalidades(page, flags)

    # Fallback: texto livre (caso ainda não tenha migrado para lista)
    if not flags:
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

    # Por enquanto: texto único com as marcações escolhidas.
    # Se depois você tiver um dict de {item: "Sim"/"Não"}, dá pra evoluir pra marcar X.
    checklist_txt = ""
    cl = getattr(ss, "checklist_tecnico", None)
    if isinstance(cl, dict):
        partes = []
        for k, v in cl.items():
            partes.append(f"{k}: {v}")
        checklist_txt = " | ".join(partes)
    elif isinstance(cl, (list, tuple)):
        checklist_txt = " | ".join(str(x) for x in cl)

    if checklist_txt:
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

    if testes_txt:
        insert_textbox(
            page,
            ["Testes realizados", "Testes executados"],
            testes_txt,
            width=520,
            y_offset=20,
            height=70,
            fontsize=9,
            align=0,
            occurrence=1,
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
