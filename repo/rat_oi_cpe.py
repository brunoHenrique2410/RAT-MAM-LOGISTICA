# repo/rat_oi_cpe.py — RAT OI CPE
# Ajustes:
# - Assinatura TÉCNICO: mais à direita (+60 pt) e um pouco acima (-8 pt)
# - Assinatura CLIENTE: sobe ~0,5" (-36 pt vs baseline da âncora) e usa o MESMO X da assinatura do técnico
# - Fuso horário "automático" via navegador (experimental) com fallback para seletor
# - Equipamentos: insere item-a-item, cada um numa linha/posição própria (fácil de calibrar)
#
# Requer: common/pdf.py, common/ui.py, common/state.py e PDF "RAT OI CPE NOVO.pdf" em pdf_templates/

import os, sys
from io import BytesIO
from datetime import date, time, datetime
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components
import fitz  # PyMuPDF

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common.state import init_defaults
from common.ui import assinatura_dupla_png, foto_gateway_uploader
from common.pdf import (
    open_pdf_template, insert_right_of, insert_textbox, mark_X_left_of,
    add_image_page
)

PDF_DIR = os.path.join(PROJECT_ROOT, "pdf_templates")
PDF_BASE_PATH = os.path.join(PDF_DIR, "RAT_OI_CPE_NOVO.pdf")

DEFAULT_TZ = "America/Sao_Paulo"

# ================= helpers de âncora =================

def _all_hits(page, labels):
    if isinstance(labels, str):
        labels = [labels]
    rects = []
    for lbl in labels:
        try:
            rects.extend(page.search_for(lbl))
        except Exception:
            pass
    return rects

def _first_hit(page, labels):
    hits = _all_hits(page, labels)
    return hits[0] if hits else None

def _nearest_to(page, label, near_rect, max_dy=30):
    if near_rect is None:
        return None
    cands = _all_hits(page, label)
    if not cands:
        return None
    cy = near_rect.y0 + near_rect.height/2
    cands.sort(key=lambda r: abs((r.y0 + r.height/2) - cy))
    best = cands[0]
    if abs((best.y0 + best.height/2) - cy) <= max_dy:
        return best
    return best

def _assinatura_anchor_near_label(page, label_rect):
    if label_rect is None:
        return None
    anchors = _all_hits(page, ["Assinatura", "ASSINATURA"])
    if not anchors:
        return None
    below = [r for r in anchors if r.y0 >= label_rect.y0 - 2]
    if not below:
        below = anchors
    below.sort(key=lambda r: (abs(r.y0 - label_rect.y0), r.x0))
    return below[0]

# ================= equipamentos: item-a-item =================

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

    st.caption("Preencha os itens (inputs verticais). Cada item será posicionado em uma linha própria no PDF.")
    modelo_opts  = ["", "aligera", "SynWay"]
    status_opts  = ["", "equipamento no local", "instalado pelo técnico", "retirado pelo técnico",
                    "spare técnico", "técnico não levou equipamento"]

    col_add, col_del = st.columns(2)
    with col_add:
        if st.button("➕ Adicionar item"):
            ss.equip_cli.append({"tipo":"","numero_serie":"","modelo":"","status":""})
    with col_del:
        if st.button("➖ Remover último") and len(ss.equip_cli) > 1:
            ss.equip_cli.pop()

    for i, it in enumerate(ss.equip_cli):
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

# ================ fuso auto (experimental) ================

def _try_detect_browser_tz():
    """
    Tenta detectar o TZ do navegador via JS e joga no session_state['browser_tz'].
    Nem todo ambiente do Streamlit permite; se não funcionar, ignora silenciosamente.
    """
    components.html(
        """
        <script>
        (function(){
          try {
            const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
            const streamlitDoc = window.parent.document;
            const el = streamlitDoc.querySelector('input[data-testid="__tz_input"]');
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

# ===================== UI principal + geração =====================

def render():
    st.header("🔌 RAT OI CPE NOVO")

    init_defaults({
        # Cabeçalho
        "cliente": "",
        "numero_chamado": "",
        "hora_inicio": time(8,0),
        "hora_termino": time(10,0),

        # Endereço Ponta A
        "endereco_ponta_a": "",
        "numero_ponta_a": "",

        # Serviços
        "svc_instalacao": False, "svc_retirada": False, "svc_vistoria": False,
        "svc_alteracao": False, "svc_mudanca": False, "svc_teste_conjunto": False,
        "svc_servico_interno": False,

        # Aceite
        "teste_wan": "NA",
        "tecnico_nome": "", "cliente_ciente_nome": "",
        "contato": "", "data_aceite": date.today(),
        "horario_aceite": time(10,0), "aceitacao_resp": "",
        "sig_tec_png": None, "sig_cli_png": None,

        # Data/hora automáticas
        "usar_agora": True,
        "tz_name": DEFAULT_TZ,
        "tz_custom": "",
        "browser_tz": "",

        # Equipamentos
        "equip_cli": [{"tipo":"","numero_serie":"","modelo":"","status":""}],

        # Textos
        "problema_encontrado": "",
        "observacoes": "",

        # Produtividade / suporte
        "suporte_mam": "",
        "produtivo": "sim-totalmente produtivo",
        "ba_num": "",
        "motivo_improdutivo": "",

        # Fotos
        "fotos_gateway": [],
    })

    ss = st.session_state

    # Tentativa de auto-TZ via navegador
    _try_detect_browser_tz()
    # campo oculto que o JS tenta preencher
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

        st.markdown("**Endereço Ponta A (linha do PDF ‘Endereço ponta A… N° …’):**")
        c3,c4 = st.columns([4,1])
        with c3:
            ss.endereco_ponta_a = st.text_input("Endereço Ponta A", value=ss.endereco_ponta_a)
        with c4:
            ss.numero_ponta_a = st.text_input("Nº (Ponta A)", value=ss.numero_ponta_a)

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

        st.checkbox("Usar data/hora atuais na geração do PDF", value=ss.usar_agora, key="usar_agora")

        tz_opts = ["America/Sao_Paulo","America/Manaus","America/Bahia","America/Fortaleza","UTC"]
        # se o browser forneceu TZ, usar como sugestão
        prefill_tz = (ss.browser_tz or ss.tz_name or DEFAULT_TZ)
        if prefill_tz not in tz_opts:
            tz_opts = [prefill_tz] + tz_opts
        ss.tz_name = st.selectbox("Fuso horário (auto se detectado)", tz_opts,
                                  index=0, help="Se seu aparelho informar o fuso, ele aparece aqui em primeiro.")
        ss.tz_custom = st.text_input("Fuso (avançado, opcional)", value=ss.tz_custom)

        assinatura_dupla_png()  # preenche ss.sig_tec_png / ss.sig_cli_png

    # 4) Equipamentos (verticais)
    with st.expander("4) Equipamentos no Cliente", expanded=True):
        equipamentos_editor_vertical()

    # 5) Produtividade & Textos
    with st.expander("5) Produtividade & Textos", expanded=True):
        ss.produtivo = st.selectbox(
            "Produtivo?",
            ["sim-totalmente produtivo", "sim-com BA", "não-improdutivo"],
            index=["sim-totalmente produtivo","sim-com BA","não-improdutivo"].index(ss.produtivo)
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

    # 6) Foto do Gateway
    with st.expander("6) Foto do Gateway", expanded=True):
        foto_gateway_uploader()

    # --------- GERAÇÃO DO PDF ---------
    if st.button("🧾 Gerar PDF (OI CPE)"):
        try:
            doc, page1 = open_pdf_template(PDF_BASE_PATH, hint="RAT OI CPE NOVO")

            # ===== PÁGINA 1: Cabeçalho + Serviços =====
            insert_right_of(page1, ["Cliente"], ss.cliente, dx=8, dy=1)

            insert_right_of(page1, ["Número do Bilhete", "Numero do Bilhete"], ss.numero_chamado, dx=8, dy=1)
            insert_right_of(page1, ["Designação do Circuito", "Designacao do Circuito"], ss.numero_chamado, dx=8, dy=1)

            # Horários (de atendimento, topo)
            insert_right_of(page1, ["Horário Início", "Horario Inicio", "Horario Início"],
                            ss.hora_inicio.strftime("%H:%M"), dx=8, dy=1)
            insert_right_of(page1, ["Horário Término", "Horario Termino", "Horário termino"],
                            ss.hora_termino.strftime("%H:%M"), dx=8, dy=1)

            # Endereço Ponta A + N°
            insert_right_of(page1, ["Endereço ponta A", "Endereço Ponta A"], ss.endereco_ponta_a, dx=8, dy=1)
            no_rects = _all_hits(page1, ["N°", "Nº", "N °", "N o"])
            base_rect = _first_hit(page1, ["Endereço ponta A", "Endereço Ponta A"])
            if no_rects and base_rect:
                same_line = [r for r in no_rects if abs((r.y0 + r.height/2) - (base_rect.y0 + base_rect.height/2)) < 12]
                target_no = same_line[0] if same_line else no_rects[0]
                x = target_no.x1 + 6
                y = target_no.y0 + target_no.height/1.5 + 1
                page1.insert_text((x, y), ss.numero_ponta_a or "", fontsize=10)

            # Serviços – marcar X
            if ss.svc_instalacao:      mark_X_left_of(page1, "Instalação", dx=-16, dy=0)
            if ss.svc_retirada:        mark_X_left_of(page1, "Retirada", dx=-16, dy=0)
            if ss.svc_vistoria:        mark_X_left_of(page1, "Vistoria Tecnica", dx=-16, dy=0); mark_X_left_of(page1, "Vistoria Técnica", dx=-16, dy=0)
            if ss.svc_alteracao:       mark_X_left_of(page1, "Alteração Tecnica", dx=-16, dy=0); mark_X_left_of(page1, "Alteração Técnica", dx=-16, dy=0)
            if ss.svc_mudanca:         mark_X_left_of(page1, "Mudança de Endereço", dx=-16, dy=0); mark_X_left_of(page1, "Mudanca de Endereco", dx=-16, dy=0)
            if ss.svc_teste_conjunto:  mark_X_left_of(page1, "Teste em conjunto", dx=-16, dy=0)
            if ss.svc_servico_interno: mark_X_left_of(page1, "Serviço interno", dx=-16, dy=0); mark_X_left_of(page1, "Servico interno", dx=-16, dy=0)

            # ===== IDENTIFICAÇÃO – ACEITE (página 1, rodapé) =====

            # Teste WAN — offsets pedidos
            wan_label = _first_hit(page1, ["Teste de conectividade WAN", "Teste final com equipamento do cliente"])
            if wan_label:
                pos_S  = wan_label.x1 + 140
                pos_N  = wan_label.x1 + 165
                pos_NA = wan_label.x1 + 210
                ymark  = wan_label.y0
                if ss.teste_wan == "S":
                    page1.insert_text((pos_S, ymark), "X", fontsize=12)
                elif ss.teste_wan == "N":
                    page1.insert_text((pos_N, ymark), "X", fontsize=12)
                else:
                    page1.insert_text((pos_NA, ymark), "X", fontsize=12)

            # Técnico — nome + assinatura (mais à direita e um pouco acima)
            insert_right_of(page1, ["Técnico","Tecnico"], ss.tecnico_nome, dx=8, dy=1)
            tec_label = _first_hit(page1, ["Técnico","Tecnico"])
            x_tec_sig0 = None
            if tec_label and ss.sig_tec_png:
                anchor_tec = _assinatura_anchor_near_label(page1, tec_label)
                if anchor_tec:
                    # >>> ajuste solicitado: +60 pt à direita, -8 pt para cima
                    rect = fitz.Rect(anchor_tec.x0 + 60, anchor_tec.y0 - 8,
                                     anchor_tec.x0 + 60 + 200, anchor_tec.y0 + 42)
                    x_tec_sig0 = rect.x0
                    page1.insert_image(rect, stream=ss.sig_tec_png, keep_proportion=True)

            # Cliente — nome + assinatura (meia polegada pra cima e alinhado no X do técnico)
            insert_right_of(page1, ["Cliente Ciente","Cliente  Ciente"], ss.cliente_ciente_nome, dx=8, dy=1)
            cli_label = _first_hit(page1, ["Cliente Ciente","Cliente  Ciente"])
            if cli_label and ss.sig_cli_png:
                anchor_cli = _assinatura_anchor_near_label(page1, cli_label)
                if anchor_cli:
                    # >>> ajuste solicitado: mesma coluna X do técnico; subir ~0,5" (36 pt)
                    base_x = x_tec_sig0 if x_tec_sig0 is not None else anchor_cli.x0 + 60
                    rect = fitz.Rect(base_x, anchor_cli.y0 - 36,
                                     base_x + 200, anchor_cli.y0 + 14)
                    page1.insert_image(rect, stream=ss.sig_cli_png, keep_proportion=True)

            # Contato (âncora na mesma linha do cliente, se possível)
            contato_anchor = _nearest_to(page1, ["Contato"], cli_label, max_dy=40)
            if contato_anchor and (ss.contato or "").strip():
                x = contato_anchor.x1 + 8
                y = contato_anchor.y0 + contato_anchor.height/1.5 + 1
                page1.insert_text((x, y), ss.contato, fontsize=10)
            else:
                insert_right_of(page1, ["Contato"], ss.contato, dx=8, dy=1)

            # Data / Horário (com TZ: browser > custom > seletor > default)
            if ss.usar_agora:
                tzname = (ss.browser_tz.strip() or ss.tz_custom.strip() or ss.tz_name or DEFAULT_TZ)
                try:
                    tz = ZoneInfo(tzname)
                except Exception:
                    tz = ZoneInfo(DEFAULT_TZ)
                now = datetime.now(tz=tz)
                insert_right_of(page1, ["Data"], now.strftime("%d/%m/%Y"), dx=8, dy=1)
                insert_right_of(page1, ["Horario","Horário"], now.strftime("%H:%M"), dx=8, dy=1)
            else:
                insert_right_of(page1, ["Data"], ss.data_aceite.strftime("%d/%m/%Y"), dx=8, dy=1)
                insert_right_of(page1, ["Horario","Horário"], ss.horario_aceite.strftime("%H:%M"), dx=8, dy=1)

            # Aceitação do responsável
            insert_right_of(page1, ["Aceitação do serviço pelo responsável","Aceitacao do servico pelo responsavel",
                                    "Aceitação do serviço","Aceitacao do servico"],
                            ss.aceitacao_resp, dx=8, dy=1)

            # ===== PÁGINA 2: Blocos técnicos =====
            page2 = doc[1] if doc.page_count >= 2 else doc.new_page()

            # ---- Equipamentos: item-a-item em posições próprias ----
            # Âncora de referência:
            eq_anchor = _first_hit(page2, ["EQUIPAMENTOS NO CLIENTE","Equipamentos no Cliente"])
            if eq_anchor:
                # Configurável: deslocamentos
                X_OFFSET = 0            # ajuste fino horizontal a partir do x0 da âncora
                Y_START  = 36           # distância inicial abaixo da âncora
                LINE_W   = 520          # largura útil de linha
                LINE_H   = 26           # altura entre linhas
                FONT_SZ  = 10
                # Campo de texto de cada item (apenas a resposta)
                # Montagem do texto de cada item (pode alterar a ordem/labels aqui se quiser)
                def _txt(it):
                    parts=[]
                    if it.get("tipo"): parts.append(f"Tipo: {it['tipo']}")
                    if it.get("numero_serie"): parts.append(f"S/N: {it['numero_serie']}")
                    if it.get("modelo"): parts.append(f"Mod: {it['modelo']}")
                    if it.get("status"): parts.append(f"Status: {it['status']}")
                    return " | ".join(parts)
                # Caso precise calibrar linha a linha, altere Y_START / LINE_H ou crie uma lista de Ys.
                EQUIP_Y_STEPS = []  # se quiser posições 100% custom, preencha manualmente (ex.: [36, 68, 100, ...])
                for idx, it in enumerate(ss.equip_cli):
                    txt = _txt(it).strip()
                    if not txt: 
                        continue
                    if EQUIP_Y_STEPS:
                        y_rel = EQUIP_Y_STEPS[min(idx, len(EQUIP_Y_STEPS)-1)]
                    else:
                        y_rel = Y_START + idx * LINE_H
                    rect = fitz.Rect(eq_anchor.x0 + X_OFFSET, eq_anchor.y1 + y_rel,
                                     eq_anchor.x0 + X_OFFSET + LINE_W, eq_anchor.y1 + y_rel + LINE_H)
                    page2.insert_textbox(rect, txt, fontsize=FONT_SZ, align=0)

            # Regras de Produtividade → Problema/Ação/Obs
            obs_lines=[]
            if ss.produtivo:
                linha = f"Produtivo: {ss.produtivo}"
                if (ss.suporte_mam or "").strip():
                    linha += f" – acompanhado pelo analista {ss.suporte_mam}"
                else:
                    linha += " – acompanhado pelo analista"
                obs_lines.append(linha)

            problema_extra=""; acao_extra=""
            if ss.produtivo == "sim-com BA":
                acao_extra = f"BA: {ss.ba_num.strip() or '(não informado)'}"
            elif ss.produtivo == "não-improdutivo":
                problema_extra = f"Motivo: {ss.motivo_improdutivo.strip() or '(não informado)'}"

            problema_final = "\n".join([t for t in [problema_extra, (ss.problema_encontrado or '').strip()] if t])
            if problema_final:
                insert_textbox(page2, ["PROBLEMA ENCONTRADO","Problema Encontrado"],
                               problema_final, width=540, y_offset=20, height=160, fontsize=10)

            if acao_extra:
                insert_textbox(page2, ["AÇÃO CORRETIVA","Acao Corretiva","Ação Corretiva"],
                               acao_extra, width=540, y_offset=20, height=120, fontsize=10)

            obs_final = "\n".join([t for t in [("\n".join(obs_lines)).strip(), (ss.observacoes or "").strip()] if t])
            if obs_final:
                insert_textbox(page2, ["OBSERVAÇÕES","Observacoes","Observações"],
                               obs_final, width=540, y_offset=20, height=160, fontsize=10)

            # Fotos do gateway: 1 página por foto
            for b in ss.fotos_gateway:
                if b:
                    add_image_page(doc, b)

            out = BytesIO(); doc.save(out); doc.close()
            st.success("PDF (OI CPE) gerado!")
            st.download_button(
                "⬇️ Baixar RAT OI CPE",
                data=out.getvalue(),
                file_name=f"RAT_OI_CPE_{(ss.numero_chamado or 'sem_num')}.pdf",
                mime="application/pdf"
            )
        except Exception as e:
            st.error("Falha ao gerar PDF OI CPE.")
            st.exception(e)
