# repo/rat_oi_cpe.py — RAT OI CPE (fuso automático + ajustes finos)
# - Fuso horário AUTOMÁTICO (browser -> fallback America/Sao_Paulo)
# - Checkboxes S/N/N-A por âncora
# - Assinaturas: técnico (dir + leve acima), cliente (mesmo X do técnico, ~0,5" acima)
# - Equipamentos editor vertical
# - Cabeçalho + pág.2 + fotos do gateway

import os, sys
from io import BytesIO
from datetime import date, time, datetime
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components
import fitz  # PyMuPDF

# ---------- path fix ----------
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ---------- deps do projeto ----------
from common.state import init_defaults
from common.ui import assinatura_dupla_png, foto_gateway_uploader
from common.pdf import (
    open_pdf_template, insert_right_of, insert_textbox, mark_X_left_of,
    add_image_page
)

PDF_DIR = os.path.join(PROJECT_ROOT, "pdf_templates")
PDF_BASE_PATH = os.path.join(PDF_DIR, "RAT_OI_CPE_NOVO.pdf")
DEFAULT_TZ = "America/Sao_Paulo"

# ---------- helpers ----------
def _all_hits(page, labels):
    if isinstance(labels, str): labels=[labels]
    out=[]
    for t in labels:
        try: out.extend(page.search_for(t))
        except: pass
    return out

def _first_hit(page, labels):
    r=_all_hits(page, labels)
    return r[0] if r else None

def _normalize_equip_rows(rows):
    out=[]
    for r in rows or []:
        out.append({
            "tipo": r.get("tipo",""),
            "numero_serie": r.get("numero_serie",""),
            "modelo": r.get("modelo",""),
            "status": r.get("status",""),
        })
    if not out:
        out=[{"tipo":"","numero_serie":"","modelo":"","status":""}]
    return out

def equipamentos_editor_vertical():
    """Editor vertical (uma seção por item)."""
    ss = st.session_state
    ss.equip_cli = _normalize_equip_rows(ss.equip_cli)

    modelo_opts  = ["", "aligera", "SynWay"]
    status_opts  = ["", "equipamento no local", "instalado pelo técnico", "retirado pelo técnico",
                    "spare técnico", "técnico não levou equipamento"]

    cA,cB = st.columns(2)
    with cA:
        if st.button("➕ Adicionar item"): ss.equip_cli.append({"tipo":"","numero_serie":"","modelo":"","status":""})
    with cB:
        if st.button("➖ Remover último") and len(ss.equip_cli)>1: ss.equip_cli.pop()

    for i,it in enumerate(ss.equip_cli):
        st.markdown(f"**Item {i+1}**")
        it["tipo"] = st.text_input("Tipo", value=it.get("tipo",""), key=f"equip_{i}_tipo")
        it["numero_serie"] = st.text_input("Nº de Série", value=it.get("numero_serie",""), key=f"equip_{i}_sn")
        it["modelo"] = st.selectbox("Modelo", modelo_opts,
                                    index=(modelo_opts.index(it.get("modelo","")) if it.get("modelo","") in modelo_opts else 0),
                                    key=f"equip_{i}_modelo")
        it["status"] = st.selectbox("Status", status_opts,
                                    index=(status_opts.index(it.get("status","")) if it.get("status","") in status_opts else 0),
                                    key=f"equip_{i}_status")
        st.divider()

    ss.equip_cli = _normalize_equip_rows(ss.equip_cli)

def _try_detect_browser_tz():
    """Preenche st.session_state.browser_tz com o timeZone do navegador (se disponível)."""
    components.html(
        """
        <script>
        (function(){
          try {
            const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
            const doc = window.parent.document;
            const el = doc.querySelector('input[data-testid="__tz_input"]');
            if (el) {
              const setVal = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
              setVal.call(el, tz);
              el.dispatchEvent(new Event('input', { bubbles: true }));
            }
          } catch(e) {}
        })();
        </script>
        <input data-testid="__tz_input" style="display:none" />
        """,
        height=0
    )

def _now_auto_tz():
    """Retorna datetime agora com TZ do navegador (se capturado) ou DEFAULT_TZ."""
    ss = st.session_state
    tzname = (ss.browser_tz.strip() if ss.get("browser_tz") else "") or DEFAULT_TZ
    try:
        tz = ZoneInfo(tzname)
    except Exception:
        tz = ZoneInfo(DEFAULT_TZ)
    return datetime.now(tz=tz)

# ===================== UI + geração =====================
def render():
    st.header("🔌 RAT OI CPE NOVO")

    init_defaults({
        # cabeçalho
        "cliente": "", "numero_chamado": "",
        "hora_inicio": time(8,0), "hora_termino": time(10,0),
        "endereco_ponta_a": "", "numero_ponta_a": "",
        # serviços
        "svc_instalacao": False, "svc_retirada": False, "svc_vistoria": False,
        "svc_alteracao": False, "svc_mudanca": False, "svc_teste_conjunto": False,
        "svc_servico_interno": False,
        # aceite
        "teste_wan": "NA",
        "tecnico_nome": "", "cliente_ciente_nome": "",
        "contato": "", "aceitacao_resp": "",
        "sig_tec_png": None, "sig_cli_png": None,
        # tz auto
        "browser_tz": "",
        # equipamentos
        "equip_cli": [{"tipo":"","numero_serie":"","modelo":"","status":""}],
        # textos e produtividade
        "suporte_mam":"", "produtivo":"sim-totalmente produtivo", "ba_num":"", "motivo_improdutivo":"",
        "problema_encontrado": "", "observacoes": "",
        # fotos
        "fotos_gateway": [],
    })
    ss = st.session_state

    # capturar tz do navegador
    _try_detect_browser_tz()
    st.text_input("browser_tz_hidden", value=ss.browser_tz, key="browser_tz", label_visibility="hidden")

    # 1) Cabeçalho
    with st.expander("1) Cabeçalho", expanded=True):
        c1,c2 = st.columns(2)
        with c1:
            ss.cliente = st.text_input("Cliente", value=ss.cliente)
            ss.numero_chamado = st.text_input("Número do Chamado (preenche Bilhete/Designação)", value=ss.numero_chamado)
            ss.hora_inicio = st.time_input("Horário Início", value=ss.hora_inicio)
        with c2:
            ss.hora_termino = st.time_input("Horário Término", value=ss.hora_termino)
            ss.suporte_mam = st.text_input("Nome do suporte MAM", value=ss.suporte_mam)

        st.markdown("**Endereço Ponta A (preenche ‘Endereço ponta A … N° …’):**")
        c3,c4 = st.columns([4,1])
        with c3: ss.endereco_ponta_a = st.text_input("Endereço Ponta A", value=ss.endereco_ponta_a)
        with c4: ss.numero_ponta_a   = st.text_input("Nº (Ponta A)", value=ss.numero_ponta_a)

    # 2) Serviços
    with st.expander("2) Serviços e Atividades Solicitadas", expanded=True):
        c1,c2,c3 = st.columns(3)
        with c1:
            ss.svc_instalacao = st.checkbox("Instalação", value=ss.svc_instalacao)
            ss.svc_retirada   = st.checkbox("Retirada", value=ss.svc_retirada)
            ss.svc_vistoria   = st.checkbox("Vistoria Técnica", value=ss.svc_vistoria)
        with c2:
            ss.svc_alteracao  = st.checkbox("Alteração Técnica", value=ss.svc_alteracao)
            ss.svc_mudanca    = st.checkbox("Mudança de Endereço", value=ss.svc_mudanca)
        with c3:
            ss.svc_teste_conjunto = st.checkbox("Teste em conjunto", value=ss.svc_teste_conjunto)
            ss.svc_servico_interno= st.checkbox("Serviço interno", value=ss.svc_servico_interno)

    # 3) Identificação – Aceite
    with st.expander("3) Identificação – Aceite da Atividade", expanded=True):
        ss.teste_wan = st.radio("Teste final com equipamento do cliente?", ["S","N","NA"],
                                index=["S","N","NA"].index(ss.teste_wan))
        c1,c2 = st.columns(2)
        with c1:
            ss.tecnico_nome = st.text_input("Técnico (nome)", value=ss.tecnico_nome)
            ss.cliente_ciente_nome = st.text_input("Cliente ciente (nome)", value=ss.cliente_ciente_nome)
            ss.contato = st.text_input("Contato (telefone)", value=ss.contato)
        with c2:
            ss.aceitacao_resp = st.text_input("Aceitação do serviço pelo responsável", value=ss.aceitacao_resp)

        assinatura_dupla_png()  # preenche ss.sig_tec_png / ss.sig_cli_png

    # 4) Equipamentos
    with st.expander("4) Equipamentos no Cliente", expanded=True):
        equipamentos_editor_vertical()

    # 5) Produtividade & Textos
    with st.expander("5) Produtividade & Textos", expanded=True):
        ss.produtivo = st.selectbox("Produtivo?", ["sim-totalmente produtivo","sim-com BA","não-improdutivo"],
                                    index=["sim-totalmente produtivo","sim-com BA","não-improdutivo"].index(ss.produtivo))
        if ss.produtivo=="sim-com BA":
            ss.ba_num = st.text_input("Nº do BA", value=ss.ba_num)
        else:
            ss.ba_num = st.text_input("Nº do BA (se aplicável)", value=ss.ba_num)
        if ss.produtivo=="não-improdutivo":
            ss.motivo_improdutivo = st.text_input("Motivo da improdutividade", value=ss.motivo_improdutivo)
        else:
            ss.motivo_improdutivo = st.text_input("Motivo da improdutividade (se aplicável)", value=ss.motivo_improdutivo)

        ss.problema_encontrado = st.text_area("Problema Encontrado (texto adicional)", value=ss.problema_encontrado, height=100)
        ss.observacoes         = st.text_area("Observações (texto adicional)", value=ss.observacoes, height=100)

    # 6) Foto do Gateway
    with st.expander("6) Foto do Gateway", expanded=True):
        foto_gateway_uploader()

    # -------- PDF --------
    if st.button("🧾 Gerar PDF (OI CPE)"):
        try:
            doc, page1 = open_pdf_template(PDF_BASE_PATH, hint="RAT OI CPE NOVO")

            # ===== PÁGINA 1: Cabeçalho + Serviços + Aceite =====
            insert_right_of(page1, ["Cliente"], ss.cliente, dx=8, dy=1)
            insert_right_of(page1, ["Número do Bilhete","Numero do Bilhete"], ss.numero_chamado, dx=8, dy=1)
            insert_right_of(page1, ["Designação do Circuito","Designacao do Circuito"], ss.numero_chamado, dx=8, dy=1)

            insert_right_of(page1, ["Horário Início","Horario Inicio","Horario Início"], ss.hora_inicio.strftime("%H:%M"), dx=8, dy=1)
            insert_right_of(page1, ["Horário Término","Horario Termino","Horário termino"], ss.hora_termino.strftime("%H:%M"), dx=8, dy=1)

            insert_right_of(page1, ["Endereço ponta A","Endereço Ponta A"], ss.endereco_ponta_a, dx=8, dy=1)
            # N° (mesma linha do endereço)
            no_rects = _all_hits(page1, ["N°","Nº","N o","N °"])
            base_rect = _first_hit(page1, ["Endereço ponta A","Endereço Ponta A"])
            if no_rects and base_rect:
                same_line=[r for r in no_rects if abs((r.y0+r.height/2)-(base_rect.y0+base_rect.height/2))<12]
                target_no = same_line[0] if same_line else no_rects[0]
                x=target_no.x1+6; y=target_no.y0+target_no.height/1.5+1
                page1.insert_text((x,y), ss.numero_ponta_a or "", fontsize=10)

            # Serviços (marca X no checkbox à esquerda)
            if ss.svc_instalacao:      mark_X_left_of(page1, "Instalação", dx=-16, dy=0)
            if ss.svc_retirada:        mark_X_left_of(page1, "Retirada", dx=-16, dy=0)
            if ss.svc_vistoria:        mark_X_left_of(page1, "Vistoria Técnica", dx=-16, dy=0) or mark_X_left_of(page1, "Vistoria Tecnica", dx=-16, dy=0)
            if ss.svc_alteracao:       mark_X_left_of(page1, "Alteração Técnica", dx=-16, dy=0) or mark_X_left_of(page1, "Alteração Tecnica", dx=-16, dy=0)
            if ss.svc_mudanca:         mark_X_left_of(page1, "Mudança de Endereço", dx=-16, dy=0) or mark_X_left_of(page1, "Mudanca de Endereco", dx=-16, dy=0)
            if ss.svc_teste_conjunto:  mark_X_left_of(page1, "Teste em conjunto", dx=-16, dy=0)
            if ss.svc_servico_interno: mark_X_left_of(page1, "Serviço interno", dx=-16, dy=0) or mark_X_left_of(page1, "Servico interno", dx=-16, dy=0)

            # ---- Identificação – Aceite (pág.1) ----
            # Checkbox S/N/N-A por âncora (X cai no quadrinho)
            if ss.teste_wan == "S":
                mark_X_left_of(page1, "S", dx=-10, dy=-2)
            elif ss.teste_wan == "N":
                mark_X_left_of(page1, "N", dx=-10, dy=-2)
            else:
                if not mark_X_left_of(page1, "N/A", dx=-10, dy=-2):
                    mark_X_left_of(page1, "N / A", dx=-10, dy=-2)

            # Nomes e contato
            insert_right_of(page1, ["Técnico","Tecnico"], ss.tecnico_nome, dx=8, dy=1)
            insert_right_of(page1, ["Cliente Ciente","Cliente  Ciente"], ss.cliente_ciente_nome, dx=8, dy=1)
            insert_right_of(page1, ["Contato"], ss.contato, dx=8, dy=1)

            # Assinaturas ancoradas pelos rótulos “Técnico” e “Cliente Ciente”
            def _rect_for_signature_from_anchor(page, anchor_labels, dx_left=70, up_px=8, width=210, height=42):
                anchor = None
                for lbl in anchor_labels:
                    hits = page.search_for(lbl)
                    if hits:
                        anchor = hits[0]
                        break
                if not anchor:
                    return None
                y_top = anchor.y0 + 24 - up_px  # linha de assinatura ~24pt abaixo do rótulo
                x_left = anchor.x0 + dx_left
                return fitz.Rect(x_left, y_top, x_left + width, y_top + height)

            tech_rect = _rect_for_signature_from_anchor(page1, ["Técnico","Tecnico"], dx_left=70, up_px=8, width=210, height=42)
            if tech_rect and ss.sig_tec_png:
                page1.insert_image(tech_rect, stream=ss.sig_tec_png, keep_proportion=True)

            cli_anchor = None
            for lbl in ["Cliente Ciente","Cliente  Ciente"]:
                hits = page1.search_for(lbl)
                if hits:
                    cli_anchor = hits[0]; break
            if cli_anchor and ss.sig_cli_png:
                base_x = tech_rect.x0 if tech_rect else (cli_anchor.x0 + 70)
                y_top = cli_anchor.y0 + 24 - 36  # sobe ~0,5"
                cli_rect = fitz.Rect(base_x, y_top, base_x + 210, y_top + 42)
                page1.insert_image(cli_rect, stream=ss.sig_cli_png, keep_proportion=True)

            # Data/Horário auto (browser TZ -> fallback São Paulo)
            now = _now_auto_tz()
            insert_right_of(page1, ["Data"], now.strftime("%d/%m/%Y"), dx=8, dy=1)
            insert_right_of(page1, ["Horario","Horário"], now.strftime("%H:%M"), dx=8, dy=1)

            insert_right_of(page1, ["Aceitação do serviço pelo responsável","Aceitacao do servico pelo responsavel"],
                            ss.aceitacao_resp, dx=8, dy=1)

            # ===== PÁGINA 2 =====
            page2 = doc[1] if doc.page_count >= 2 else doc.new_page()

            # Equipamentos (1 linha por item, com espaçamento maior)
            eq_anchor = _first_hit(page2, ["EQUIPAMENTOS NO CLIENTE","Equipamentos no Cliente"])
            if eq_anchor:
                X_OFFSET = 0; Y_START=36; LINE_W=520; LINE_H=28; FONT_SZ=10
                def txt(it):
                    parts=[]
                    if it.get("tipo"): parts.append(f"Tipo: {it['tipo']}")
                    if it.get("numero_serie"): parts.append(f"S/N: {it['numero_serie']}")
                    if it.get("modelo"): parts.append(f"Mod: {it['modelo']}")
                    if it.get("status"): parts.append(f"Status: {it['status']}")
                    return " | ".join(parts)
                row_idx=0
                for it in ss.equip_cli:
                    t = txt(it).strip()
                    if not t: continue
                    y_rel = Y_START + row_idx*LINE_H
                    rect = fitz.Rect(eq_anchor.x0 + X_OFFSET, eq_anchor.y1 + y_rel,
                                     eq_anchor.x0 + X_OFFSET + LINE_W, eq_anchor.y1 + y_rel + LINE_H)
                    page2.insert_textbox(rect, t, fontsize=FONT_SZ, align=0)
                    row_idx += 1

            # Produtivo -> Observações / Problema / Ação Corretiva
            obs_lines=[]
            if ss.produtivo:
                linha = f"Produtivo: {ss.produtivo}"
                if (ss.suporte_mam or "").strip():
                    linha += f" – acompanhado pelo analista {ss.suporte_mam}"
                else:
                    linha += " – acompanhado pelo analista"
                obs_lines.append(linha)

            problema_extra=""; acao_extra=""
            if ss.produtivo=="sim-com BA":
                acao_extra = f"BA: {ss.ba_num.strip() or '(não informado)'}"
            elif ss.produtivo=="não-improdutivo":
                problema_extra = f"Motivo: {ss.motivo_improdutivo.strip() or '(não informado)'}"

            problema_final = "\n".join([t for t in [problema_extra, (ss.problema_encontrado or '').strip()] if t])
            if problema_final:
                insert_textbox(page2, ["PROBLEMA ENCONTRADO","Problema Encontrado"], problema_final,
                               width=540, y_offset=20, height=160, fontsize=10)

            if acao_extra:
                insert_textbox(page2, ["AÇÃO CORRETIVA","Acao Corretiva","Ação Corretiva"], acao_extra,
                               width=540, y_offset=20, height=120, fontsize=10)

            obs_final = "\n".join([t for t in [("\n".join(obs_lines)).strip(), (ss.observacoes or "").strip()] if t])
            if obs_final:
                insert_textbox(page2, ["OBSERVAÇÕES","Observacoes","Observações"], obs_final,
                               width=540, y_offset=20, height=160, fontsize=10)

            # Fotos do gateway
            for b in ss.fotos_gateway:
                if b: add_image_page(doc, b)

            out = BytesIO(); doc.save(out); doc.close()
            st.success("PDF (OI CPE) gerado!")
            st.download_button("⬇️ Baixar RAT OI CPE",
                               data=out.getvalue(),
                               file_name=f"RAT_OI_CPE_{(ss.numero_chamado or 'sem_num')}.pdf",
                               mime="application/pdf")
        except Exception as e:
            st.error("Falha ao gerar PDF OI CPE.")
            st.exception(e)
