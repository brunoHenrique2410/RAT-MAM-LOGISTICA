# repo/rat_oi_cpe.py — RAT OI CPE (preenche IDENTIFICAÇÃO – ACEITE; assinaturas +3 cm; equipamentos com selects; produtivo/BA/motivo)

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
    """Região (x0,y0,x1,y1) desde o título 'start' até o início do próximo bloco 'end'."""
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
    Insere assinatura (PNG) procurando 'Assinatura' SOMENTE dentro da região.
    rel_rect relativo ao label encontrado: (x0, dy0, x1, dy1) somados ao x0/y1 da âncora.
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


# ===================== Equipamentos =====================

def _normalize_equip_rows(rows):
    """Garante chaves fixas e evita perda de valores ao editar."""
    out = []
    for r in rows or []:
        out.append({
            "tipo": r.get("tipo", ""),
            "numero_serie": r.get("numero_serie", ""),
            "fabricante": r.get("fabricante", ""),
            "modelo": r.get("modelo", ""),
            "status": r.get("status", ""),
        })
    if not out:
        out = [{"tipo": "", "numero_serie": "", "fabricante": "", "modelo": "", "status": ""}]
    return out

def equipamentos_texto(rows):
    """
    Texto simples para o bloco 'EQUIPAMENTOS NO CLIENTE' (não redesenha tabela).
    Ex.: "- Tipo: ONT | Nº Série: ABC | Fab: XYZ | Mod: SynWay | Status: instalado pelo técnico"
    """
    rows = _normalize_equip_rows(rows)
    linhas = []
    for it in rows:
        if not (it.get("tipo") or it.get("numero_serie") or it.get("fabricante") or it.get("modelo") or it.get("status")):
            continue
        linhas.append(
            f"- Tipo: {it.get('tipo','')} | Nº Série: {it.get('numero_serie','')} | "
            f"Fab: {it.get('fabricante','')} | Mod: {it.get('modelo','')} | Status: {it.get('status','')}"
        )
    return "\n".join(linhas)


# ===================== UI + Geração =====================

def render():
    st.header("🔌 RAT OI CPE NOVO")

    # ---------- Estado inicial ----------
    init_defaults({
        # Cabeçalho
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
        "teste_wan": "NA",  # (UI renomeada: "Teste final com equipamento do cliente?")
        "tecnico_nome": "",
        "cliente_ciente_nome": "",
        "contato": "",
        "data_aceite": date.today(),
        "horario_aceite": time(10, 0),
        "aceitacao_resp": "",
        "sig_tec_png": None,
        "sig_cli_png": None,

        # Equipamentos
        "equip_cli": [{"tipo": "", "numero_serie": "", "fabricante": "", "modelo": "", "status": ""}],

        # Textos
        "problema_encontrado": "",
        "observacoes": "",

        # Produtividade / suporte
        "suporte_mam": "",
        "produtivo": "sim-totalmente produtivo",
        "ba_num": "",
        "motivo_improdutivo": "",

        # Fotos (gateway)
        "fotos_gateway": [],
    })

    ss = st.session_state

    # ---------- 1) Cabeçalho ----------
    with st.expander("1) Cabeçalho", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            ss.cliente = st.text_input("Cliente", value=ss.cliente)
            ss.numero_chamado = st.text_input("Número do Chamado (preenche Bilhete/Designação)", value=ss.numero_chamado)
            ss.hora_inicio = st.time_input("Horário Início", value=ss.hora_inicio)
        with c2:
            ss.hora_termino = st.time_input("Horário Término", value=ss.hora_termino)
            ss.suporte_mam = st.text_input("Nome do suporte MAM", value=ss.suporte_mam)

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
            "Teste final com equipamento do cliente?",
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

        assinatura_dupla_png()  # ss.sig_tec_png / ss.sig_cli_png

    # ---------- 4) Equipamentos no Cliente ----------
    with st.expander("4) Equipamentos no Cliente", expanded=True):
        st.caption("Preencha ao menos 1 linha. (Modelo e Status têm opções fixas.)")
        ss.equip_cli = _normalize_equip_rows(ss.equip_cli)

        modelo_opts = ["", "aligera", "SynWay"]
        status_opts = ["", "equipamento no local", "instalado pelo técnico", "retirado pelo técnico",
                       "spare técnico", "técnico não levou equipamento"]

        data = st.data_editor(
            ss.equip_cli,
            num_rows="dynamic",
            use_container_width=True,
            key="equip_cli_editor",
            column_config={
                "tipo": st.column_config.TextColumn("Tipo"),
                "numero_serie": st.column_config.TextColumn("Nº de Série"),
                "fabricante": st.column_config.TextColumn("Fabricante"),
                "modelo": st.column_config.SelectboxColumn("Modelo", options=modelo_opts, required=False),
                "status": st.column_config.SelectboxColumn("Status", options=status_opts, required=False),
            },
        )
        ss.equip_cli = _normalize_equip_rows(data)

    # ---------- 5) Produtividade / Textos ----------
    with st.expander("5) Produtividade & Textos", expanded=True):
        ss.produtivo = st.selectbox(
            "Produtivo",
            ["sim-totalmente produtivo", "sim-com BA", "não-improdutivo"],
            index=["sim-totalmente produtivo", "sim-com BA", "não-improdutivo"].index(ss.produtivo)
        )
        if ss.produtivo == "sim-com BA":
            ss.ba_num = st.text_input("Informe o nº do BA (obrigatório p/ 'sim-com BA')", value=ss.ba_num)
        else:
            ss.ba_num = st.text_input("Informe o nº do BA (se aplicável)", value=ss.ba_num)

        if ss.produtivo == "não-improdutivo":
            ss.motivo_improdutivo = st.text_input("Motivo da improdutividade (obrigatório p/ 'não-improdutivo')", value=ss.motivo_improdutivo)
        else:
            ss.motivo_improdutivo = st.text_input("Motivo da improdutividade (se aplicável)", value=ss.motivo_improdutivo)

        ss.problema_encontrado = st.text_area("Problema Encontrado (texto adicional)", value=ss.problema_encontrado, height=100)
        ss.observacoes = st.text_area("Observações (texto adicional)", value=ss.observacoes, height=100)

    # ---------- 6) Foto do Gateway ----------
    with st.expander("6) Foto do Gateway", expanded=True):
        foto_gateway_uploader()

    # ---------- Geração do PDF ----------
    if st.button("🧾 Gerar PDF (OI CPE)"):
        try:
            doc, page1 = open_pdf_template(PDF_BASE_PATH, hint="RAT OI CPE NOVO")
            page2 = doc[1] if doc.page_count >= 2 else page1  # normalmente a região alvo está na 2ª página

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
            if ss.svc_vistoria:        mark_X_left_of(page1, "Vistoria Tecnica", dx=-16, dy=0); mark_X_left_of(page1, "Vistoria Técnica", dx=-16, dy=0)
            if ss.svc_alteracao:       mark_X_left_of(page1, "Alteração Tecnica", dx=-16, dy=0); mark_X_left_of(page1, "Alteração Técnica", dx=-16, dy=0)
            if ss.svc_mudanca:         mark_X_left_of(page1, "Mudança de Endereço", dx=-16, dy=0); mark_X_left_of(page1, "Mudanca de Endereco", dx=-16, dy=0)
            if ss.svc_teste_conjunto:  mark_X_left_of(page1, "Teste em conjunto", dx=-16, dy=0)
            if ss.svc_servico_interno: mark_X_left_of(page1, "Serviço interno", dx=-16, dy=0); mark_X_left_of(page1, "Servico interno", dx=-16, dy=0)

            # ===== PARTE 2: IDENTIFICAÇÃO – ACEITE / Equip / Textos =====
            target = page2

            ident_region = _find_region_between(
                target,
                start_labels=["IDENTIFICAÇÃO – ACEITE DA ATIVIDADE", "Identificação – Aceite da Atividade",
                              "IDENTIFICACAO - ACEITE DA ATIVIDADE", "Identificacao - Aceite da Atividade"],
                end_labels=["EQUIPAMENTOS NO CLIENTE", "Equipamentos no Cliente",
                            "INFORMAÇÕES TECNICAS DO CIRCUITO", "INFORMACOES TECNICAS DO CIRCUITO",
                            "PROBLEMA ENCONTRADO", "Problema Encontrado",
                            "OBSERVAÇÕES", "Observacoes", "Observações"]
            )
            # Fallback: se não achou o título (variações), usa metade inferior da página
            if ident_region is None:
                r = target.rect
                ident_region = (r.x0, r.y0 + (r.height * 0.35), r.x1, r.y1)

            # Campos dentro da região (exatamente como no seu template)
            insert_right_of_in_region(target, ident_region, ["Técnico", "Tecnico"], ss.tecnico_nome, dx=8, dy=1)
            insert_right_of_in_region(target, ident_region, ["Cliente Ciente", "Cliente  Ciente"], ss.cliente_ciente_nome, dx=8, dy=1)
            insert_right_of_in_region(target, ident_region, ["Contato"], ss.contato, dx=8, dy=1)
            insert_right_of_in_region(target, ident_region, ["Data"], ss.data_aceite.strftime("%d/%m/%Y"), dx=8, dy=1)
            insert_right_of_in_region(target, ident_region, ["Horario", "Horário"], ss.horario_aceite.strftime("%H:%M"), dx=8, dy=1)
            insert_right_of_in_region(
                target, ident_region,
                ["Aceitação do serviço pelo responsável", "Aceitacao do servico pelo responsavel",
                 "Aceitação do serviço", "Aceitacao do servico"],
                ss.aceitacao_resp, dx=8, dy=1
            )

            # S / N / N/A (pergunta do template: “Teste de conectividade WAN realizado com sucesso? S N N/A”)
            # Marcamos X nos rótulos S / N / N/A dentro da região.
            if ss.teste_wan == "S":
                mark_X_left_of_in_region(target, ident_region, ["S", " S "], dx=-12, dy=0)
            elif ss.teste_wan == "N":
                mark_X_left_of_in_region(target, ident_region, ["N", " N "], dx=-12, dy=0)
            else:
                mark_X_left_of_in_region(target, ident_region, ["N/A", "NA", "N / A"], dx=-12, dy=0)

            # Assinaturas (duas âncoras "Assinatura" na região) — sobem 3 cm
            up3 = 3 * CM
            labels_ass = ["Assinatura", "ASSINATURA"]
            insert_signature_png_in_region(target, ident_region, labels_ass, ss.sig_tec_png,
                                           (80, 20 - up3, 280, 90 - up3), occurrence=1)
            insert_signature_png_in_region(target, ident_region, labels_ass, ss.sig_cli_png,
                                           (80, 20 - up3, 280, 90 - up3), occurrence=2)

            # "EQUIPAMENTOS NO CLIENTE" — texto simples no bloco
            eq_text = equipamentos_texto(ss.equip_cli)
            if eq_text.strip():
                insert_textbox(
                    target,
                    ["EQUIPAMENTOS NO CLIENTE", "Equipamentos no Cliente"],
                    eq_text,
                    width=540, y_offset=28, height=220, fontsize=9, align=0
                )

            # Regras Produtivo/BA/Motivo + textos livres
            obs_lines = []
            if ss.produtivo:
                linha = f"Produtivo: {ss.produtivo}"
                if (ss.suporte_mam or "").strip():
                    linha += f" – acompanhado pelo analista {ss.suporte_mam}"
                else:
                    linha += " – acompanhado pelo analista"
                obs_lines.append(linha)

            problema_extra = ""
            acao_extra = ""
            if ss.produtivo == "sim-com BA":
                acao_extra = f"BA: {ss.ba_num.strip() or '(não informado)'}"
            elif ss.produtivo == "não-improdutivo":
                problema_extra = f"Motivo: {ss.motivo_improdutivo.strip() or '(não informado)'}"

            problema_final = "\n".join([t for t in [problema_extra, (ss.problema_encontrado or "").strip()] if t])
            if problema_final:
                insert_textbox(target, ["PROBLEMA ENCONTRADO", "Problema Encontrado"],
                               problema_final, width=540, y_offset=20, height=160, fontsize=10)

            if acao_extra:
                insert_textbox(target, ["AÇÃO CORRETIVA", "Acao Corretiva", "Ação Corretiva"],
                               acao_extra, width=540, y_offset=20, height=120, fontsize=10)

            obs_final = "\n".join([t for t in [("\n".join(obs_lines)).strip(), (ss.observacoes or "").strip()] if t])
            if obs_final:
                insert_textbox(target, ["OBSERVAÇÕES", "Observacoes", "Observações"],
                               obs_final, width=540, y_offset=20, height=160, fontsize=10)

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
