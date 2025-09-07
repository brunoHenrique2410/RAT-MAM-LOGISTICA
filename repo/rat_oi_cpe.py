# repo/rat_oi_cpe.py — RAT OI CPE (ancoras por REGIÃO, assinaturas +3 cm, equipamentos como texto)

# --- PATH FIX: permite importar common/ e pdf_templates/ a partir da raiz ---
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
# ---------------------------------------------------------------------------

from io import BytesIO
from datetime import date, time
import streamlit as st
import fitz  # PyMuPDF

from common.state import init_defaults
from common.ui import assinatura_dupla_png, foto_gateway_uploader
from common.pdf import (
    open_pdf_template, insert_right_of, insert_textbox, mark_X_left_of,
    add_image_page, CM
)

PDF_DIR = os.path.join(PROJECT_ROOT, "pdf_templates")
PDF_BASE_PATH = os.path.join(PDF_DIR, "RAT_OI_CPE_NOVO.pdf")


# ===================== Helpers de busca / região =====================

def _first_hit(page, labels):
    """Primeira ocorrência de qualquer label (Rect) na página."""
    if isinstance(labels, str):
        labels = [labels]
    for lbl in labels:
        try:
            hits = page.search_for(lbl)
        except Exception:
            hits = []
        if hits:
            return hits[0]
    return None


def _all_hits(page, labels):
    """Todas as ocorrências (lista de Rects) para qualquer label."""
    rects = []
    if isinstance(labels, str):
        labels = [labels]
    for lbl in labels:
        try:
            rects.extend(page.search_for(lbl))
        except Exception:
            pass
    return rects


def _find_region_between(page, start_labels, end_labels):
    """
    Retorna uma 'região' (x0,y0,x1,y1) da página:
      - y0 = base do título/âncora de start_labels
      - y1 = topo do primeiro end_labels encontrado abaixo; se não achar, vai até o fim da página.
    """
    start = _first_hit(page, start_labels)
    if not start:
        return None
    y_top = start.y1
    ends = [r for r in _all_hits(page, end_labels) if r.y0 > y_top]
    y_bottom = min([r.y0 for r in ends], default=page.rect.y1)
    return (page.rect.x0, y_top, page.rect.x1, y_bottom)


def _rect_center(r):
    return ((r.x0 + r.x1) / 2.0, (r.y0 + r.y1) / 2.0)


def _rect_in_region(r, region):
    x0, y0, x1, y1 = region
    cx, cy = _rect_center(r)
    return (x0 <= cx <= x1) and (y0 <= cy <= y1)


def insert_right_of_in_region(page, region, field_labels, content, dx=8, dy=1, fontsize=10):
    """Insere à direita do rótulo mais próximo, limitado à 'region' (tuple x0,y0,x1,y1)."""
    if not content or not region:
        return
    if isinstance(field_labels, str):
        field_labels = [field_labels]
    candidates = []
    for lbl in field_labels:
        for r in page.search_for(lbl):
            if _rect_in_region(r, region):
                candidates.append(r)
    if not candidates:
        return
    y_top = region[1]
    target = min(candidates, key=lambda r: (r.y0 - y_top, abs(r.x0 - region[0])))
    x = target.x1 + dx
    y = target.y0 + target.height / 1.5 + dy
    page.insert_text((x, y), str(content), fontsize=fontsize)


def mark_X_left_of_in_region(page, region, field_labels, dx=-12, dy=0, fontsize=12):
    """Marca 'X' à esquerda do rótulo, limitado à região."""
    if not region:
        return
    if isinstance(field_labels, str):
        field_labels = [field_labels]
    candidates = []
    for lbl in field_labels:
        for r in page.search_for(lbl):
            if _rect_in_region(r, region):
                candidates.append(r)
    if not candidates:
        return
    y_top = region[1]
    target = min(candidates, key=lambda r: (r.y0 - y_top, abs(r.x0 - region[0])))
    page.insert_text((target.x0 + dx, target.y0 + dy), "X", fontsize=fontsize)


def insert_signature_png_in_region(page, region, label_variants, png_bytes, rel_rect, occurrence=1):
    """
    Insere assinatura (PNG) procurando o label (ex.: 'Assinatura') SOMENTE dentro da região.
    rel_rect é relativo ao âncora: (x0, dy0, x1, dy1), onde x0/x1 são relativos ao x0 do label
    e dy0/dy1 relativos ao y1 do label (logo abaixo do rótulo).
    """
    if not png_bytes or not region:
        return
    if isinstance(label_variants, str):
        label_variants = [label_variants]

    anchors = []
    for lbl in label_variants:
        for r in page.search_for(lbl):
            if _rect_in_region(r, region):
                anchors.append(r)
    if not anchors:
        return
    anchors = sorted(anchors, key=lambda r: (r.y0, r.x0))
    idx = max(0, min(len(anchors) - 1, occurrence - 1))
    base = anchors[idx]

    x0 = base.x0 + rel_rect[0]
    y0 = base.y1 + rel_rect[1]
    x1 = base.x0 + rel_rect[2]
    y1 = base.y1 + rel_rect[3]
    rect = fitz.Rect(x0, y0, x1, y1)

    page.insert_image(rect, stream=png_bytes, keep_proportion=True)


# ===================== Helpers de conteúdo =====================

def _normalize_equip_rows(rows):
    """Garante que toda linha tenha as 4 chaves, evitando apagar colunas ao editar."""
    out = []
    for r in rows or []:
        out.append({
            "tipo": r.get("tipo", ""),
            "numero_serie": r.get("numero_serie", ""),
            "fabricante": r.get("fabricante", ""),
            "status": r.get("status", ""),
        })
    if not out:
        out = [{"tipo": "", "numero_serie": "", "fabricante": "", "status": ""}]
    return out


def equipamentos_texto(rows):
    """
    Constrói um texto simples (sem CSV) para o bloco 'EQUIPAMENTOS NO CLIENTE',
    uma linha por item.
    Ex.: "- Tipo: ONT | Nº Série: ABC123 | Fabricante: XYZ | Status: OK"
    """
    rows = _normalize_equip_rows(rows)
    linhas = []
    for it in rows:
        if not (it.get("tipo") or it.get("numero_serie") or it.get("fabricante") or it.get("status")):
            continue
        linhas.append(
            f"- Tipo: {it.get('tipo','')} | Nº Série: {it.get('numero_serie','')} | "
            f"Fabricante: {it.get('fabricante','')} | Status: {it.get('status','')}"
        )
    return "\n".join(linhas)


# ===================== UI + Geração =====================

def render():
    st.header("🔌 RAT OI CPE NOVO")

    # ---------- Estado inicial ----------
    init_defaults({
        "cliente": "",
        "numero_chamado": "",
        "hora_inicio": time(8, 0),
        "hora_termino": time(10, 0),

        # Serviços
        "svc_instalacao": False,
        "svc_retirada": False,
        "svc_vistoria": False,
        "svc_alteracao": False,
        "svc_mudanca": False,
        "svc_teste_conjunto": False,
        "svc_servico_interno": False,

        # Identificação – Aceite
        "teste_wan": "NA",
        "tecnico_nome": "",
        "cliente_ciente_nome": "",
        "contato": "",
        "data_aceite": date.today(),
        "horario_aceite": time(10, 0),
        "aceitacao_resp": "",
        "sig_tec_png": None,
        "sig_cli_png": None,

        # Tabela Equipamentos
        "equip_cli": [{"tipo": "", "numero_serie": "", "fabricante": "", "status": ""}],

        # Textos
        "problema_encontrado": "",
        "observacoes": "",

        # Fotos (gateway)
        "fotos_gateway": [],
    })

    ss = st.session_state

    # ---------- 1) Cabeçalho ----------
    with st.expander("1) Cabeçalho", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            ss.cliente = st.text_input("Cliente", value=ss.cliente)
            ss.numero_chamado = st.text_input("Número do Chamado", value=ss.numero_chamado)
            ss.hora_inicio = st.time_input("Horário Início", value=ss.hora_inicio)
        with c2:
            st.caption("“Número do Bilhete” e “Designação do Circuito” receberão o Nº do Chamado.")
            ss.hora_termino = st.time_input("Horário Término", value=ss.hora_termino)

    # ---------- 2) Serviços ----------
    with st.expander("2) Serviços e Atividades Solicitadas", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            ss.svc_instalacao = st.checkbox("Instalação", value=ss.svc_instalacao)
            ss.svc_retirada = st.checkbox("Retirada", value=ss.svc_retirada)
            ss.svc_vistoria = st.checkbox("Vistoria Técnica", value=ss.svc_vistoria)
        with c2:
            ss.svc_alteracao = st.checkbox("Alteração Técnica", value=ss.svc_alteracao)
            ss.svc_mudanca = st.checkbox("Mudança de Endereço", value=ss.svc_mudanca)
        with c3:
            ss.svc_teste_conjunto = st.checkbox("Teste em conjunto", value=ss.svc_teste_conjunto)
            ss.svc_servico_interno = st.checkbox("Serviço interno", value=ss.svc_servico_interno)

    # ---------- 3) Identificação – Aceite ----------
    with st.expander("3) Identificação – Aceite da Atividade", expanded=True):
        ss.teste_wan = st.radio(
            "Teste de conectividade WAN realizado com sucesso?",
            ["S", "N", "NA"],
            index=["S", "N", "NA"].index(ss.teste_wan)
        )
        c1, c2 = st.columns(2)
        with c1:
            ss.tecnico_nome = st.text_input("Técnico (nome)", value=ss.tecnico_nome)
            ss.cliente_ciente_nome = st.text_input("Cliente ciente (nome)", value=ss.cliente_ciente_nome)
            ss.contato = st.text_input("Contato (telefone)", value=ss.contato)
        with c2:
            ss.data_aceite = st.date_input("Data", value=ss.data_aceite)
            ss.horario_aceite = st.time_input("Horário", value=ss.horario_aceite)
            ss.aceitacao_resp = st.text_input("Aceitação do serviço pelo responsável", value=ss.aceitacao_resp)

        # Captura das assinaturas (PNG com transparência)
        assinatura_dupla_png()  # ss.sig_tec_png / ss.sig_cli_png

    # ---------- 4) Equipamentos ----------
    with st.expander("4) Equipamentos no Cliente", expanded=True):
        st.caption("Preencha ao menos 1 linha.")
        ss.equip_cli = _normalize_equip_rows(ss.equip_cli)
        data = st.data_editor(
            ss.equip_cli,
            num_rows="dynamic",
            use_container_width=True,
            key="equip_cli_editor",
            column_config={
                "tipo": st.column_config.TextColumn("Tipo"),
                "numero_serie": st.column_config.TextColumn("Nº de Série"),
                "fabricante": st.column_config.TextColumn("Fabricante"),
                "status": st.column_config.TextColumn("Status"),
            },
        )
        ss.equip_cli = _normalize_equip_rows(data)

    # ---------- 5) Problema / Observações ----------
    with st.expander("5) Problema Encontrado & Observações", expanded=True):
        ss.problema_encontrado = st.text_area("Problema Encontrado", value=ss.problema_encontrado, height=120)
        ss.observacoes = st.text_area("Observações", value=ss.observacoes, height=120)

    # ---------- 6) Foto(s) do Gateway ----------
    with st.expander("6) Foto do Gateway", expanded=True):
        foto_gateway_uploader()

    # ---------- Geração do PDF ----------
    if st.button("🧾 Gerar PDF (OI CPE)"):
        try:
            doc, page1 = open_pdf_template(PDF_BASE_PATH, hint="RAT OI CPE NOVO")
            page2 = doc[1] if doc.page_count >= 2 else page1

            # ===== PÁGINA 1: Cabeçalho + Serviços =====
            insert_right_of(page1, ["Cliente"], ss.cliente, dx=8, dy=1)
            insert_right_of(page1, ["Número do Bilhete", "Numero do Bilhete"], ss.numero_chamado, dx=8, dy=1)
            insert_right_of(page1, ["Designação do Circuito", "Designacao do Circuito"], ss.numero_chamado, dx=8, dy=1)

            insert_right_of(page1, ["Horário Início", "Horario Inicio", "Horario Início"],
                            ss.hora_inicio.strftime("%H:%M"), dx=8, dy=1)
            insert_right_of(page1, ["Horário Término", "Horario Termino", "Horário termino"],
                            ss.hora_termino.strftime("%H:%M"), dx=8, dy=1)

            if ss.svc_instalacao:      mark_X_left_of(page1, "Instalação", dx=-16, dy=0)
            if ss.svc_retirada:        mark_X_left_of(page1, "Retirada", dx=-16, dy=0)
            if ss.svc_vistoria:        mark_X_left_of(page1, "Vistoria Técnica", dx=-16, dy=0); mark_X_left_of(page1, "Vistoria Tecnica", dx=-16, dy=0)
            if ss.svc_alteracao:       mark_X_left_of(page1, "Alteração Técnica", dx=-16, dy=0); mark_X_left_of(page1, "Alteracao Tecnica", dx=-16, dy=0)
            if ss.svc_mudanca:         mark_X_left_of(page1, "Mudança de Endereço", dx=-16, dy=0); mark_X_left_of(page1, "Mudanca de Endereco", dx=-16, dy=0)
            if ss.svc_teste_conjunto:  mark_X_left_of(page1, "Teste em conjunto", dx=-16, dy=0)
            if ss.svc_servico_interno: mark_X_left_of(page1, "Serviço interno", dx=-16, dy=0);    mark_X_left_of(page1, "Servico interno", dx=-16, dy=0)

            # ===== PARTE 2 (normalmente página 2): Identificação – Aceite / Equip / Textos =====
            target = page2

            # REGIÃO "Identificação – Aceite da Atividade"
            ident_region = _find_region_between(
                target,
                start_labels=[
                    "Identificação – Aceite da Atividade",
                    "Identificacao - Aceite da Atividade",
                    "IDENTIFICAÇÃO – ACEITE DA ATIVIDADE",
                    "IDENTIFICACAO - ACEITE DA ATIVIDADE",
                ],
                end_labels=[
                    "EQUIPAMENTOS NO CLIENTE", "Equipamentos no Cliente",
                    "PROBLEMA ENCONTRADO", "Problema Encontrado",
                    "OBSERVAÇÕES", "Observacoes", "Observações",
                ],
            )

            # Campos de texto ANCORADOS À REGIÃO (com/sem “:”, com/sem acento)
            insert_right_of_in_region(target, ident_region,
                ["Técnico:", "Tecnico:", "Técnico", "Tecnico"],
                ss.tecnico_nome, dx=8, dy=1)

            insert_right_of_in_region(target, ident_region,
                ["Cliente Ciente:", "Cliente Ciente", "Cliente  Ciente"],
                ss.cliente_ciente_nome, dx=8, dy=1)

            insert_right_of_in_region(target, ident_region,
                ["Contato:", "Contato"],
                ss.contato, dx=8, dy=1)

            insert_right_of_in_region(target, ident_region,
                ["Data:", "Data"],
                ss.data_aceite.strftime("%d/%m/%Y"), dx=8, dy=1)

            insert_right_of_in_region(target, ident_region,
                ["Horário:", "Horario:", "Horário", "Horario"],
                ss.horario_aceite.strftime("%H:%M"), dx=8, dy=1)

            insert_right_of_in_region(target, ident_region,
                ["Aceitação do serviço", "Aceitacao do servico",
                 "Aceitação do serviço pelo responsável", "Aceitacao do servico pelo responsavel"],
                ss.aceitacao_resp, dx=8, dy=1)

            # Teste WAN (S/N/NA) dentro da região — tolera variações
            labels_S  = [" S ", "S", "Sim"]
            labels_N  = [" N ", "N", "Não", "Nao"]
            labels_NA = ["N/A", "NA", "N / A"]
            if ss.teste_wan == "S":
                mark_X_left_of_in_region(target, ident_region, labels_S, dx=-12, dy=0)
            elif ss.teste_wan == "N":
                mark_X_left_of_in_region(target, ident_region, labels_N, dx=-12, dy=0)
            else:
                mark_X_left_of_in_region(target, ident_region, labels_NA, dx=-12, dy=0)

            # Assinaturas (sobem 3 cm) — 1ª = Técnico, 2ª = Cliente
            up3 = 3 * CM
            labels_ass = ["Assinatura", "ASSINATURA"]
            insert_signature_png_in_region(target, ident_region, labels_ass, ss.sig_tec_png,
                                           (80, 20 - up3, 280, 90 - up3), occurrence=1)
            insert_signature_png_in_region(target, ident_region, labels_ass, ss.sig_cli_png,
                                           (80, 20 - up3, 280, 90 - up3), occurrence=2)

            # "EQUIPAMENTOS NO CLIENTE" — texto simples no bloco da seção
            eq_text = equipamentos_texto(ss.equip_cli)
            if eq_text.strip():
                insert_textbox(
                    target,
                    ["EQUIPAMENTOS NO CLIENTE", "Equipamentos no Cliente"],
                    eq_text,
                    width=540, y_offset=28, height=220, fontsize=9, align=0
                )

            # Problema / Observações
            if (ss.problema_encontrado or "").strip():
                insert_textbox(target, ["PROBLEMA ENCONTRADO", "Problema Encontrado"],
                               ss.problema_encontrado, width=540, y_offset=20, height=160, fontsize=10)
            if (ss.observacoes or "").strip():
                insert_textbox(target, ["OBSERVAÇÕES", "Observacoes", "Observações"],
                               ss.observacoes, width=540, y_offset=20, height=160, fontsize=10)

            # Fotos do gateway — 1 página por foto
            for b in ss.fotos_gateway:
                if b:
                    add_image_page(doc, b)

            out = BytesIO()
            doc.save(out)
            doc.close()
            st.success("PDF (OI CPE) gerado!")
            st.download_button(
                "⬇️ Baixar RAT OI CPE",
                data=out.getvalue(),
                file_name=f"RAT_OI_CPE_{(ss.numero_chamado or 'sem_num')}.pdf",
                mime="application/pdf",
            )
        except Exception as e:
            st.error("Falha ao gerar PDF OI CPE.")
            st.exception(e)
