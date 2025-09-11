# repo/rat_oi_cpe.py — RAT OI CPE com BLINDAGEM na última página
# - Preenche a RAT como antes (pág.1/2)
# - Cria uma PÁGINA FINAL com todos os [[FIELD:...]] invisíveis (fonte 0.1pt branca)
# - Sobre a página final, aplica a FOTO DE COBERTURA enviada pelo técnico
#
# Requer: common.state, common.ui (assinatura_dupla_png, foto_gateway_uploader),
#         common.pdf (open_pdf_template, insert_right_of, insert_textbox, mark_X_left_of, add_image_page)
#         pdf_templates/RAT_OI_CPE_NOVO.pdf

import os, sys
from io import BytesIO
from datetime import date, time, datetime
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components
import fitz  # PyMuPDF
from PIL import Image

# --- paths / imports comuns ---
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common.state import init_defaults
from common.ui import assinatura_dupla_png, foto_gateway_uploader
from common.pdf import (
    open_pdf_template, insert_right_of, insert_textbox, mark_X_left_of, add_image_page
)

PDF_DIR = os.path.join(PROJECT_ROOT, "pdf_templates")
PDF_BASE_PATH = os.path.join(PDF_DIR, "RAT_OI_CPE_NOVO.pdf")
DEFAULT_TZ = "America/Sao_Paulo"

# ---------- utils de busca ----------
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

# ---------- editor de equipamentos (vertical) ----------
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

# ---------- captura do fuso do navegador (automático) ----------
def _try_detect_browser_tz():
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

# ---------- blindagem: escreve [[FIELD:key=value]] invisível ----------
def _write_blind_field(page, x, y, key, value):
    """Escreve um FIELD invisível (branco, 0.1pt) em (x,y)."""
    if value is None: value = ""
    hidden = f"[[FIELD:{key}={value}]]"
    # color=(1,1,1) é branco em PyMuPDF (RGB de 0..1)
    page.insert_text((x, y), hidden, fontsize=0.1, color=(1,1,1))

def _add_blindage_page(doc, fields: dict, cover_image_bytes: bytes|None):
    """
    Cria uma nova página ao final do documento, grava todos os [[FIELD:...]]
    invisíveis (fonte 0.1 branca) e depois insere a foto de cobertura ocupando a página.
    """
    p = doc.new_page()  # última página
    w, h = p.rect.width, p.rect.height
    # layout simples: uma coluna de linhas
    margin = 36
    cursor_y = margin + 12  # começa um pouco abaixo
    line_h = 12             # espaçamento entre linhas

    # 1) escreve todos os fields invisíveis
    # para estabilidade, escreve também um cabeçalho invisível
    _write_blind_field(p, margin, cursor_y, "document", "RAT_OI_CPE")
    cursor_y += line_h
    for k, v in fields.items():
        # fragmenta valores muito longos em múltiplas linhas invisíveis
        sval = "" if v is None else str(v)
        if len(sval) <= 180:
            _write_blind_field(p, margin, cursor_y, k, sval)
            cursor_y += line_h
        else:
            # quebra a cada ~150-180 chars para manter próximo
            chunk = 170
            for i in range(0, len(sval), chunk):
                _write_blind_field(p, margin, cursor_y, k, sval[i:i+chunk])
                cursor_y += line_h

        # se encostar no rodapé, pula mais um pouco
        if cursor_y > (h - margin - 24):
            cursor_y = margin + 12

    # 2) cobre com a foto (se enviada)
    if cover_image_bytes:
        try:
            pil = Image.open(BytesIO(cover_image_bytes)).convert("RGB")
            W,H = pil.size
            # centraliza com margens
            max_w, max_h = w - 2*margin, h - 2*margin
            scale = min(max_w/W, max_h/H)
            new_w, new_h = int(W*scale), int(H*scale)
            x0 = (w - new_w) / 2
            y0 = (h - new_h) / 2
            rect = fitz.Rect(x0, y0, x0 + new_w, y0 + new_h)
            buf = BytesIO(); pil.save(buf, format="JPEG", quality=92)
            p.insert_image(rect, stream=buf.getvalue())
        except Exception:
            # se der erro na imagem, mantemos a página com fields invisíveis mesmo assim
            pass

# ===================== UI + geração =====================
def render():
    st.header("🔌 RAT OI CPE NOVO (com blindagem na última página)")

    init_defaults({
        "cliente": "", "numero_chamado": "",
        "hora_inicio": time(8,0), "hora_termino": time(10,0),

        "endereco_ponta_a": "", "numero_ponta_a": "",

        "svc_instalacao": False, "svc_retirada": False, "svc_vistoria": False,
        "svc_alteracao": False, "svc_mudanca": False, "svc_teste_conjunto": False,
        "svc_servico_interno": False,

        "teste_wan": "NA",
        "tecnico_nome": "", "cliente_ciente_nome": "",
        "contato": "", "aceitacao_resp": "",
        "sig_tec_png": None, "sig_cli_png": None,

        "browser_tz": "", "usar_agora": True,

        "equip_cli": [{"tipo":"","numero_serie":"","modelo":"","status":""}],
        "problema_encontrado": "", "observacoes": "",
        "suporte_mam": "", "produtivo":"sim-totalmente produtivo", "ba_num":"", "motivo_improdutivo":"",

        "fotos_gateway": [],
        "foto_cobertura_blindagem": None,  # NOVO: foto que cobre a página de blindagem
    })
    ss = st.session_state

    # captura fuso do navegador
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

        st.markdown("**Endereço Ponta A (preenche linha ‘Endereço ponta A … N° …’ do PDF):**")
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

    # 5) Observações / Produtivo
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

    # 6) Fotos do gateway
    with st.expander("6) Foto(s) do Gateway", expanded=True):
        foto_gateway_uploader()  # preenche ss.fotos_gateway

    # 7) Foto de COBERTURA (blindagem)
    with st.expander("7) Foto de cobertura da página de BLINDAGEM (opcional, ficará por cima dos FIELDs)", expanded=True):
        up = st.file_uploader("Foto (JPG/PNG)", type=["jpg","jpeg","png"], key="foto_cobertura_up")
        if up is not None:
            ss.foto_cobertura_blindagem = up.read()
            st.success("Foto de cobertura carregada.")
        if st.button("🧹 Limpar foto de cobertura"):
            ss.foto_cobertura_blindagem = None
            st.info("Foto de cobertura removida.")

    # -------- PDF --------
    if st.button("🧾 Gerar PDF (OI CPE)"):
        try:
            doc, page1 = open_pdf_template(PDF_BASE_PATH, hint="RAT OI CPE NOVO")

            # ======= Página 1: Cabeçalho + Serviços + Aceite =======
            # Cabeçalho
            insert_right_of(page1, ["Cliente"], ss.cliente, dx=8, dy=1)
            insert_right_of(page1, ["Número do Bilhete","Numero do Bilhete"], ss.numero_chamado, dx=8, dy=1)
            insert_right_of(page1, ["Designação do Circuito","Designacao do Circuito"], ss.numero_chamado, dx=8, dy=1)
            insert_right_of(page1, ["Horário Início","Horario Inicio","Horario Início"], ss.hora_inicio.strftime("%H:%M"), dx=8, dy=1)
            insert_right_of(page1, ["Horário Término","Horario Termino","Horário termino"], ss.hora_termino.strftime("%H:%M"), dx=8, dy=1)

            insert_right_of(page1, ["Endereço ponta A","Endereço Ponta A"], ss.endereco_ponta_a, dx=8, dy=1)
            # N°
            no_rects = _all_hits(page1, ["N°","Nº","N o","N °"])
            base_rect = _first_hit(page1, ["Endereço ponta A","Endereço Ponta A"])
            if no_rects and base_rect:
                same_line=[r for r in no_rects if abs((r.y0+r.height/2)-(base_rect.y0+base_rect.height/2))<12]
                target_no = same_line[0] if same_line else no_rects[0]
                x=target_no.x1+6; y=target_no.y0+target_no.height/1.5+1
                page1.insert_text((x,y), ss.numero_ponta_a or "", fontsize=10)

            # Serviços (checkbox com "X" à esquerda)
            if ss.svc_instalacao:      mark_X_left_of(page1, "Instalação", dx=-16, dy=0)
            if ss.svc_retirada:        mark_X_left_of(page1, "Retirada", dx=-16, dy=0)
            if ss.svc_vistoria:        mark_X_left_of(page1, "Vistoria Técnica", dx=-16, dy=0) or mark_X_left_of(page1, "Vistoria Tecnica", dx=-16, dy=0)
            if ss.svc_alteracao:       mark_X_left_of(page1, "Alteração Técnica", dx=-16, dy=0) or mark_X_left_of(page1, "Alteração Tecnica", dx=-16, dy=0)
            if ss.svc_mudanca:         mark_X_left_of(page1, "Mudança de Endereço", dx=-16, dy=0) or mark_X_left_of(page1, "Mudanca de Endereco", dx=-16, dy=0)
            if ss.svc_teste_conjunto:  mark_X_left_of(page1, "Teste em conjunto", dx=-16, dy=0)
            if ss.svc_servico_interno: mark_X_left_of(page1, "Serviço interno", dx=-16, dy=0) or mark_X_left_of(page1, "Servico interno", dx=-16, dy=0)

            # Identificação – Aceite (rótulos)
            # Checkbox do "Teste final..." — ajusta offsets conforme seu template
            wan_label = _first_hit(page1, ["Teste de conectividade WAN","Teste final com equipamento do cliente"])
            if wan_label:
                pos_S  = wan_label.x1 + 138
                pos_N  = wan_label.x1 + 165
                pos_NA = wan_label.x1 + 207
                ymark  = wan_label.y0 + 11
                xmark  = pos_S if ss.teste_wan=="S" else pos_N if ss.teste_wan=="N" else pos_NA
                page1.insert_text((xmark, ymark), "X", fontsize=12)

            insert_right_of(page1, ["Técnico","Tecnico"], ss.tecnico_nome, dx=8, dy=1)
            insert_right_of(page1, ["Cliente Ciente","Cliente  Ciente"], ss.cliente_ciente_nome, dx=8, dy=1)
            insert_right_of(page1, ["Contato"], ss.contato, dx=8, dy=1)

            # Data/Hora automáticas (fuso do navegador se disponível)
            if ss.usar_agora:
                tzname = (ss.browser_tz.strip() or DEFAULT_TZ)
                try: tz = ZoneInfo(tzname)
                except: tz = ZoneInfo(DEFAULT_TZ)
                now = datetime.now(tz=tz)
                insert_right_of(page1, ["Data"], now.strftime("%d/%m/%Y"), dx=8, dy=1)
                insert_right_of(page1, ["Horario","Horário"], now.strftime("%H:%M"), dx=8, dy=1)

            insert_right_of(page1, ["Aceitação do serviço pelo responsável","Aceitacao do servico pelo responsavel"], ss.aceitacao_resp, dx=8, dy=1)

            # Assinaturas (usa assinatura_dupla_png para capturar imagens em ss.sig_tec_png / ss.sig_cli_png)
            # Encontrar âncoras "Assinatura"
            sig_slots = _all_hits(page1, ["Assinatura","ASSINATURA"])
            sig_slots = sorted(sig_slots, key=lambda r: (r.y0, r.x0))
            tech_slot = sig_slots[0] if len(sig_slots)>=1 else None
            cli_slot  = sig_slots[1] if len(sig_slots)>=2 else None

            # Técnico: levemente à direita e pouco acima
            if tech_slot and ss.sig_tec_png:
                rect = fitz.Rect(tech_slot.x0 + 40, tech_slot.y0 - 15,
                                 tech_slot.x0 + 40 + 200, tech_slot.y0 + 20)
                page1.insert_image(rect, stream=ss.sig_tec_png, keep_proportion=True)

            # Cliente: mesmo X do técnico, um pouco acima (meia polegada ≈ 36pt)
            if cli_slot and ss.sig_cli_png:
                base_x = (tech_slot.x0 + 40) if tech_slot else (cli_slot.x0 + 10)
                rect = fitz.Rect(base_x, cli_slot.y0 - 10, base_x + 200, cli_slot.y0 + 145)
                page1.insert_image(rect, stream=ss.sig_cli_png, keep_proportion=True)

            # ======= Página 2: Equipamentos / Problema / Observações / Ação =======
            page2 = doc[1] if doc.page_count >= 2 else doc.new_page()

            # Equipamentos: linhas legíveis com espaçamento
            eq_anchor = _first_hit(page2, ["EQUIPAMENTOS NO CLIENTE","Equipamentos no Cliente"])
            if eq_anchor:
                X_OFFSET = 0; Y_START=36; LINE_W=520; LINE_H=26; FONT_SZ=10
                def txt(it):
                    parts=[]
                    if it.get("tipo"): parts.append(f"Tipo: {it['tipo']}")
                    if it.get("numero_serie"): parts.append(f"S/N: {it['numero_serie']}")
                    if it.get("modelo"): parts.append(f"Mod: {it['modelo']}")
                    if it.get("status"): parts.append(f"Status: {it['status']}")
                    return " | ".join(parts)
                for idx,it in enumerate(ss.equip_cli):
                    t = txt(it).strip()
                    if not t: continue
                    y_rel = Y_START + idx*LINE_H
                    rect = fitz.Rect(eq_anchor.x0 + X_OFFSET, eq_anchor.y1 + y_rel,
                                     eq_anchor.x0 + X_OFFSET + LINE_W, eq_anchor.y1 + y_rel + LINE_H)
                    page2.insert_textbox(rect, t, fontsize=FONT_SZ, align=0)

            # Regras de produtividade → Problema / Ação / Observações
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

            # Fotos do gateway (cada uma em página própria)
            for b in ss.fotos_gateway:
                if b: add_image_page(doc, b)

            # ======= PÁGINA FINAL DE BLINDAGEM =======
            # Monta o dicionário de fields que ficarão invisíveis na última página
            # (Pode adicionar/retirar chaves à vontade; o extrator buscará estas primeiro.)
            equip0 = (ss.equip_cli[0] if ss.equip_cli else {"tipo":"","numero_serie":"","modelo":"","status":""})
            fields = {
                "document"          : "RAT_OI_CPE",
                "numero_chamado"    : ss.numero_chamado,
                "cliente"           : ss.cliente,
                "endereco_ponta_a"  : ss.endereco_ponta_a,
                "numero_ponta_a"    : ss.numero_ponta_a,
                "hora_inicio"       : ss.hora_inicio.strftime("%H:%M") if isinstance(ss.hora_inicio, time) else str(ss.hora_inicio),
                "hora_termino"      : ss.hora_termino.strftime("%H:%M") if isinstance(ss.hora_termino, time) else str(ss.hora_termino),
                "teste_final"       : ss.teste_wan,  # S/N/NA
                "tecnico"           : ss.tecnico_nome,
                "cliente_ciente"    : ss.cliente_ciente_nome,
                "contato"           : ss.contato,
                "aceitacao_resp"    : ss.aceitacao_resp,
                "suporte_mam"       : ss.suporte_mam,
                "produtivo"         : ss.produtivo,
                "ba_num"            : ss.ba_num,
                "motivo_improdutivo": ss.motivo_improdutivo,
                # equipamento principal (primeiro item)
                "equip_tipo"        : equip0.get("tipo",""),
                "equip_modelo"      : equip0.get("modelo",""),
                "equip_sn"          : equip0.get("numero_serie",""),
                "equip_status"      : equip0.get("status",""),
                # textos livres
                "problema_encontrado": ss.problema_encontrado,
                "observacoes"        : ss.observacoes,
            }
            _add_blindage_page(doc, fields, ss.foto_cobertura_blindagem)

            # ======= salvar =======
            out = BytesIO(); doc.save(out); doc.close()
            st.success("PDF (OI CPE) gerado com blindagem!")
            st.download_button("⬇️ Baixar RAT OI CPE",
                               data=out.getvalue(),
                               file_name=f"RAT_OI_CPE_{(ss.numero_chamado or 'sem_num')}.pdf",
                               mime="application/pdf")
        except Exception as e:
            st.error("Falha ao gerar PDF OI CPE.")
            st.exception(e)
