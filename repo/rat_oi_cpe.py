# repo/rat_oi_cpe.py — RAT OI CPE NOVO
# ✅ Ajustes:
# - Horário Início: UI + PDF
# - Horário Término: deslocado ~1,5cm para direita
# - Última linha "Data ... Horario: ...": fonte menor e data espaçada

import os, sys
from io import BytesIO
from datetime import time, datetime
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components
import fitz  # PyMuPDF

# ---------- PATHS ----------
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common.state import init_defaults
from common.ui import assinatura_dupla_png, foto_gateway_uploader
from common.pdf import (
    open_pdf_template, insert_right_of, insert_textbox, mark_X_left_of,
    add_image_page,
)

PDF_DIR = os.path.join(PROJECT_ROOT, "pdf_templates")
PDF_BASE_PATH = os.path.join(PDF_DIR, "RAT_OI_CPE_NOVO.pdf")
DEFAULT_TZ = "America/Sao_Paulo"


# ---------- helpers ----------
def _cm_to_pt(cm: float) -> float:
    return cm * 28.3464567


def _all_hits(page, labels):
    if isinstance(labels, str):
        labels = [labels]
    out = []
    for t in labels:
        try:
            out.extend(page.search_for(t))
        except Exception:
            pass
    return out


def _first_hit(page, labels):
    r = _all_hits(page, labels)
    return r[0] if r else None


def _pick_hit_top(page, labels):
    hits = _all_hits(page, labels)
    return sorted(hits, key=lambda rr: rr.y0)[0] if hits else None


def _pick_hit_bottom(page, labels):
    hits = _all_hits(page, labels)
    return sorted(hits, key=lambda rr: rr.y0)[-1] if hits else None


def _write_right_of_rect(page, rect, text, dx=6, dy=1, fontsize=10):
    if rect is None:
        return False
    x = rect.x1 + dx
    y = rect.y0 + rect.height / 1.5 + dy
    page.insert_text((x, y), text or "", fontsize=fontsize)
    return True


def _as_bytes(x):
    """Converte UploadedFile/stream/bytearray -> bytes (robusto)."""
    if x is None:
        return None
    if isinstance(x, (bytes, bytearray)):
        return bytes(x)
    if hasattr(x, "getvalue"):
        try:
            return x.getvalue()
        except Exception:
            return None
    if hasattr(x, "read"):
        try:
            return x.read()
        except Exception:
            return None
    return None


# ---------- equipamentos (vertical) ----------
def _normalize_equip_rows(rows):
    out = []
    for r in rows or []:
        out.append({
            "tipo": r.get("tipo", ""),
            "numero_serie": r.get("numero_serie", ""),
            "modelo": r.get("modelo", ""),
            "status": r.get("status", ""),
        })
    if not out:
        out = [{"tipo": "", "numero_serie": "", "modelo": "", "status": ""}]
    return out


def equipamentos_editor_vertical():
    ss = st.session_state
    ss.equip_cli = _normalize_equip_rows(ss.equip_cli)

    # ✅ SEM LISTA: status também pode ficar como lista (se quiser tirar tbm, vira text_input)
    status_opts = [
        "", "equipamento no local", "instalado pelo técnico", "retirado pelo técnico",
        "spare técnico", "técnico não levou equipamento"
    ]

    cA, cB = st.columns(2)
    with cA:
        if st.button("➕ Adicionar item"):
            ss.equip_cli.append({"tipo": "", "numero_serie": "", "modelo": "", "status": ""})
    with cB:
        if st.button("➖ Remover último") and len(ss.equip_cli) > 1:
            ss.equip_cli.pop()

    for i, it in enumerate(ss.equip_cli):
        st.markdown(f"**Item {i+1}**")
        it["tipo"] = st.text_input("Tipo", value=it.get("tipo", ""), key=f"equip_{i}_tipo")
        it["numero_serie"] = st.text_input("Nº de Série", value=it.get("numero_serie", ""), key=f"equip_{i}_sn")

        # ✅ MODELO AGORA É TEXTO LIVRE
        it["modelo"] = st.text_input("Modelo", value=it.get("modelo", ""), key=f"equip_{i}_modelo_txt")

        # status mantém selectbox (se quiser tirar também, te mando)
        it["status"] = st.selectbox(
            "Status", status_opts,
            index=(status_opts.index(it.get("status", "")) if it.get("status", "") in status_opts else 0),
            key=f"equip_{i}_status"
        )
        st.divider()

    ss.equip_cli = _normalize_equip_rows(ss.equip_cli)


# ---------- fuso auto ----------
def _inject_browser_tz_input():
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


# ---------- blindagem (última página) ----------
def _insert_blind_fields_and_cover_with_gateway(doc: fitz.Document, ss):
    page = doc.new_page()
    fields = {}

    fields["numero_chamado"] = (ss.numero_chamado or "").strip()
    fields["cliente"] = (ss.cliente or "").strip()
    fields["responsavel_local"] = (ss.responsavel_local or "").strip()
    fields["responsavel_tel"] = (ss.responsavel_tel or "").strip()
    fields["endereco_ponta_a"] = (ss.endereco_ponta_a or "").strip()
    fields["numero_ponta_a"] = (ss.numero_ponta_a or "").strip()

    fields["tecnico"] = (ss.tecnico_nome or "").strip()
    fields["cliente_validador"] = (ss.cliente_validador_nome or "").strip()
    fields["validador_tel"] = (ss.validador_tel or "").strip()
    fields["teste_final"] = (ss.teste_wan or "NA").upper().strip()
    fields["aceitacao_resp"] = (ss.aceitacao_resp or "").strip()

    # Produtividade
    prod = (ss.produtivo or "").strip()
    fields["produtivo"] = prod
    fields["produtivo_parcial_tipo"] = (ss.prod_parcial_tipo or "").strip() if prod == "produtivo parcial" else ""
    fields["ba_num"] = (ss.ba_num or "").strip() if (prod == "produtivo parcial" and ss.prod_parcial_tipo == "com BA") else ""
    fields["motivo_improdutivo"] = (ss.motivo_improdutivo or "").strip() if prod == "não-improdutivo" else ""
    fields["suporte_mam"] = (ss.suporte_mam or "").strip()

    eq0 = (ss.equip_cli or [{}])[0]
    fields["equip_tipo"] = (eq0.get("tipo") or "").strip()
    fields["equip_sn"] = (eq0.get("numero_serie") or "").strip()
    fields["equip_modelo"] = (eq0.get("modelo") or "").strip()
    fields["equip_status"] = (eq0.get("status") or "").strip()

    fields["observacoes"] = (ss.observacoes or "").strip()

    x0, y0 = 36, 36
    line_h, fsize = 10, 6
    white = (1, 1, 1)

    def put_line(txt):
        nonlocal y0
        page.insert_text((x0, y0), txt or " ", fontsize=fsize, color=white)
        y0 += line_h

    for k in [
        "numero_chamado", "cliente", "responsavel_local", "responsavel_tel",
        "endereco_ponta_a", "numero_ponta_a",
        "tecnico", "cliente_validador", "validador_tel", "teste_final", "aceitacao_resp",
        "produtivo", "produtivo_parcial_tipo", "ba_num", "motivo_improdutivo", "suporte_mam",
        "equip_modelo", "equip_sn", "equip_status", "observacoes"
    ]:
        put_line(f"[[FIELD:{k}={fields.get(k, '')}]]")

    # cobre com a 1ª foto do gateway
    if ss.fotos_gateway:
        try:
            img_bytes = _as_bytes(ss.fotos_gateway[0])
            if img_bytes:
                rect = fitz.Rect(18, 18, page.rect.width - 18, page.rect.height - 18)
                page.insert_image(rect, stream=img_bytes, keep_proportion=True)
        except Exception:
            pass


# ===================== UI + geração =====================
def render():
    st.header("🔌 RAT OI CPE NOVO")

    init_defaults({
        "cliente": "", "numero_chamado": "",
        "hora_inicio": time(8, 0),
        "hora_termino": time(10, 0),

        "responsavel_local": "", "responsavel_tel": "",
        "endereco_ponta_a": "", "numero_ponta_a": "",

        "svc_instalacao": False, "svc_retirada": False, "svc_vistoria": False,
        "svc_alteracao": False, "svc_mudanca": False, "svc_teste_conjunto": False,
        "svc_servico_interno": False,

        "teste_wan": "NA",
        "tecnico_nome": "", "cliente_validador_nome": "",
        "validador_tel": "", "aceitacao_resp": "",
        "sig_tec_png": None, "sig_cli_png": None,

        "browser_tz": "", "usar_agora": True,

        "equip_cli": [{"tipo": "", "numero_serie": "", "modelo": "", "status": ""}],
        "observacoes": "",
        "suporte_mam": "",

        # ✅ sem opções: ainda usamos os mesmos campos, mas a UI vira texto livre
        "produtivo": "sim-totalmente produtivo",  # pode deixar vazio se quiser
        "prod_parcial_tipo": "",
        "ba_num": "",
        "motivo_improdutivo": "",

        "fotos_gateway": [],
    })
    ss = st.session_state

    _inject_browser_tz_input()
    st.text_input("browser_tz_hidden", value=ss.browser_tz, key="browser_tz", label_visibility="hidden")

    # 1) Cabeçalho
    with st.expander("1) Cabeçalho", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            ss.cliente = st.text_input("Cliente", value=ss.cliente)
            ss.numero_chamado = st.text_input("Número do Chamado (preenche Bilhete/Designação)", value=ss.numero_chamado)

        with c2:
            ss.hora_inicio = st.time_input("Horário Início", value=ss.hora_inicio)
            ss.hora_termino = st.time_input("Horário Término", value=ss.hora_termino)
            ss.suporte_mam = st.text_input("Nome do suporte MAM", value=ss.suporte_mam)

        st.markdown("**Responsável local**")
        cRL, cRT = st.columns([3, 2])
        with cRL:
            ss.responsavel_local = st.text_input("Responsável local (nome)", value=ss.responsavel_local)
        with cRT:
            ss.responsavel_tel = st.text_input("Telefone do responsável local", value=ss.responsavel_tel)

        st.markdown("**Endereço Ponta A:**")
        c3, c4 = st.columns([4, 1])
        with c3:
            ss.endereco_ponta_a = st.text_input("Endereço Ponta A", value=ss.endereco_ponta_a)
        with c4:
            ss.numero_ponta_a = st.text_input("Nº (Ponta A)", value=ss.numero_ponta_a)

    # 2) Serviços
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

    # 3) Identificação – Aceite
    with st.expander("3) Identificação – Aceite da Atividade", expanded=True):
        ss.teste_wan = st.radio(
            "Teste final com equipamento do cliente?",
            ["S", "N", "NA"],
            index=["S", "N", "NA"].index(ss.teste_wan)
        )
        c1, c2 = st.columns(2)
        with c1:
            ss.tecnico_nome = st.text_input("Técnico (nome)", value=ss.tecnico_nome)
            ss.cliente_validador_nome = st.text_input("Cliente validador (nome)", value=ss.cliente_validador_nome)
            ss.validador_tel = st.text_input("Contato (telefone do validador)", value=ss.validador_tel)
        with c2:
            ss.aceitacao_resp = st.text_input("Aceitação do serviço pelo responsável", value=ss.aceitacao_resp)

        assinatura_dupla_png()

    # 4) Equipamentos
    with st.expander("4) Equipamentos no Cliente", expanded=True):
        equipamentos_editor_vertical()

    # 5) Produtividade & Observações
    with st.expander("5) Produtividade & Observações", expanded=True):
        # ✅ sem opções: texto livre
        ss.produtivo = st.text_input("Produtivo? (texto livre)", value=ss.produtivo)

        # se você usa isso no PDF, mantém como campos livres também
        ss.prod_parcial_tipo = st.text_input("Tipo (se produtivo parcial)", value=ss.prod_parcial_tipo)
        ss.ba_num = st.text_input("BA (se houver)", value=ss.ba_num)

        # ✅ sem opções: improdutividade texto livre
        ss.motivo_improdutivo = st.text_input("Motivo da improdutividade (texto livre)", value=ss.motivo_improdutivo)

        ss.observacoes = st.text_area("Observações (texto adicional)", value=ss.observacoes, height=100)

    # 6) Foto do Gateway
    with st.expander("6) Foto do Gateway", expanded=True):
        foto_gateway_uploader()

    # -------- PDF --------
    if st.button("🧾 Gerar PDF (OI CPE)"):
        try:
            doc, page1 = open_pdf_template(PDF_BASE_PATH, hint="RAT OI CPE NOVO")

            # ===== Timezone/now =====
            tzname = (ss.browser_tz.strip() or DEFAULT_TZ) if ss.usar_agora else DEFAULT_TZ
            try:
                tz = ZoneInfo(tzname)
            except Exception:
                tz = ZoneInfo(DEFAULT_TZ)
            now = datetime.now(tz=tz)

            # ===== CABEÇALHO (pág.1) =====
            insert_right_of(page1, ["Cliente"], ss.cliente, dx=8, dy=1)
            insert_right_of(page1, ["Número do Bilhete", "Numero do Bilhete"], ss.numero_chamado, dx=8, dy=1)
            insert_right_of(page1, ["Designação do Circuito", "Designacao do Circuito"], ss.numero_chamado, dx=8, dy=1)

            # Horário Início
            r_ini = _pick_hit_top(page1, ["Horário Início", "Horario Inicio", "Horário inicio"])
            if r_ini:
                _write_right_of_rect(page1, r_ini, ss.hora_inicio.strftime("%H:%M"), dx=6, dy=1, fontsize=10)
            else:
                insert_right_of(page1, ["Horário Início", "Horario Inicio", "Horário inicio"], ss.hora_inicio.strftime("%H:%M"), dx=8, dy=1)

            # Horário Término + 1,5cm
            r_term = _pick_hit_top(page1, ["Horário Término", "Horario Termino", "Horário termino", "Horário de término", "Horario de termino"])
            if r_term:
                _write_right_of_rect(page1, r_term, ss.hora_termino.strftime("%H:%M"), dx=6 + _cm_to_pt(1.5), dy=1, fontsize=10)
            else:
                insert_right_of(page1, ["Horário Término", "Horario Termino", "Horário termino"], ss.hora_termino.strftime("%H:%M"), dx=8, dy=1)

            # Endereço Ponta A
            insert_right_of(page1, ["Endereço ponta A", "Endereço Ponta A"], ss.endereco_ponta_a, dx=8, dy=1)

            # ===== Nº (Ponta A) na mesma linha do Endereço =====
            num_label_rect = None
            no_rects = _all_hits(page1, ["N°", "Nº", "N o", "N °"])
            base_rect = _first_hit(page1, ["Endereço ponta A", "Endereço Ponta A"])
            if no_rects and base_rect:
                same_line = [
                    r for r in no_rects
                    if abs((r.y0 + r.height/2) - (base_rect.y0 + base_rect.height/2)) < 12
                ]
                target_no = same_line[0] if same_line else no_rects[0]
                num_label_rect = target_no
                x = target_no.x1 + 6
                y = target_no.y0 + target_no.height/1.5 + 1
                page1.insert_text((x, y), ss.numero_ponta_a or "", fontsize=10)

            # ===== Serviços (X) =====
            if ss.svc_instalacao:
                mark_X_left_of(page1, "Instalação", dx=-16, dy=0)
            if ss.svc_retirada:
                mark_X_left_of(page1, "Retirada", dx=-16, dy=0)
            if ss.svc_vistoria:
                mark_X_left_of(page1, "Vistoria Técnica", dx=-16, dy=0) or mark_X_left_of(page1, "Vistoria Tecnica", dx=-16, dy=0)
            if ss.svc_alteracao:
                mark_X_left_of(page1, "Alteração Técnica", dx=-16, dy=0) or mark_X_left_of(page1, "Alteração Tecnica", dx=-16, dy=0)
            if ss.svc_mudanca:
                mark_X_left_of(page1, "Mudança de Endereço", dx=-16, dy=0) or mark_X_left_of(page1, "Mudanca de Endereco", dx=-16, dy=0)
            if ss.svc_teste_conjunto:
                mark_X_left_of(page1, "Teste em conjunto", dx=-16, dy=0)
            if ss.svc_servico_interno:
                mark_X_left_of(page1, "Serviço interno", dx=-16, dy=0) or mark_X_left_of(page1, "Servico interno", dx=-16, dy=0)

            # ===== WAN S / N / NA =====
            wan_label = _first_hit(page1, ["Teste de conectividade WAN", "Teste final com equipamento do cliente"])
            if wan_label:
                pos_S = wan_label.x1 + 138
                pos_N = wan_label.x1 + 165
                pos_NA = wan_label.x1 + 207
                ymark = wan_label.y0 + 11
                page1.insert_text(
                    (pos_S if ss.teste_wan == "S" else pos_N if ss.teste_wan == "N" else pos_NA, ymark),
                    "X",
                    fontsize=12
                )

            # Técnico / Cliente validador
            insert_right_of(page1, ["Técnico", "Tecnico"], ss.tecnico_nome, dx=8, dy=1)
            insert_right_of(page1, ["Cliente Ciente", "Cliente  Ciente", "Cliente Validador"], ss.cliente_validador_nome, dx=8, dy=1)

            # Assinaturas
            sig_slots = _all_hits(page1, ["Assinatura", "ASSINATURA"])
            sig_slots = sorted(sig_slots, key=lambda r: (r.y0, r.x0))
            tech_slot = sig_slots[0] if len(sig_slots) >= 1 else None
            cli_slot = sig_slots[1] if len(sig_slots) >= 2 else None

            tech_x = None
            if tech_slot and ss.sig_tec_png:
                rect = fitz.Rect(tech_slot.x0 + 40, tech_slot.y0 - 15, tech_slot.x0 + 240, tech_slot.y0 + 20)
                tech_x = rect.x0
                page1.insert_image(rect, stream=ss.sig_tec_png, keep_proportion=True)

            if cli_slot and ss.sig_cli_png:
                base_x = tech_x if tech_x is not None else (cli_slot.x0 + 40)
                rect = fitz.Rect(base_x, cli_slot.y0 - 10, base_x + 200, cli_slot.y0 + 145)
                page1.insert_image(rect, stream=ss.sig_cli_png, keep_proportion=True)

            # Contato do validador (telefone)
            if cli_slot and (ss.validador_tel or "").strip() and num_label_rect is not None:
                x = num_label_rect.x0
                y = cli_slot.y0 + cli_slot.height/1.5 + 55
                page1.insert_text((x, y), ss.validador_tel.strip(), fontsize=10)

            # Data / Horário (última linha)
            data_txt = f"{now.strftime('%d')}  {now.strftime('%m')}   {now.strftime('%Y')}"
            hora_txt = now.strftime("%H:%M")
            r_data_bottom = _pick_hit_bottom(page1, ["Data"])
            r_hora_bottom = _pick_hit_bottom(page1, ["Horario", "Horário"])
            _write_right_of_rect(page1, r_data_bottom, data_txt, dx=6, dy=1, fontsize=9)
            _write_right_of_rect(page1, r_hora_bottom, hora_txt, dx=6, dy=1, fontsize=9)

            # Aceitação do serviço
            insert_right_of(
                page1,
                ["Aceitação do serviço pelo responsável", "Aceitacao do servico pelo responsavel"],
                ss.aceitacao_resp,
                dx=8, dy=1
            )

            # ===== Página 2 =====
            page2 = doc[1] if doc.page_count >= 2 else doc.new_page()

            # ✅ SELO: texto no canto inferior direito da página 2
            chamado = (ss.numero_chamado or "").strip() or "-"
            stamp_text = "Gerado automaticamente\n" + f"{now.strftime('%d/%m/%Y %H:%M')} • Chamado {chamado}"
            r = page2.rect
            rect_txt = fitz.Rect(r.width - 210, r.height - 80, r.width - 18, r.height - 18)
            page2.insert_textbox(rect_txt, stamp_text, fontsize=7, fontname="helv", align=0, color=(0.2, 0.2, 0.2), overlay=True)

            # ===== Equipamentos (pág.2) =====
            eq_title = _first_hit(page2, ["EQUIPAMENTOS NO CLIENTE", "Equipamentos no Cliente"])
            if eq_title:
                col_tipo = _first_hit(page2, ["Tipo"])
                col_sn = _first_hit(page2, ["Nº de Serie", "N° de Serie", "Nº de Série", "No de Serie", "N de Serie"])
                col_modelo = _first_hit(page2, ["Modelo", "Fabricante"])
                col_status = _first_hit(page2, ["Status"])

                base_x = eq_title.x0
                col_tipo_x = (col_tipo.x0 if col_tipo else base_x + 10)
                col_sn_x = (col_sn.x0 if col_sn else base_x + 180)
                col_modelo_x = (col_modelo.x0 if col_modelo else base_x + 320)
                col_status_x = (col_status.x0 if col_status else base_x + 470)

                DY, TOP, ROW, FS = 2, 36, 26, 10
                for i, it in enumerate(ss.equip_cli):
                    y = eq_title.y1 + TOP + i * ROW
                    if it.get("tipo"):
                        page2.insert_text((col_tipo_x, y + DY), str(it["tipo"]), fontsize=FS)
                    if it.get("numero_serie"):
                        page2.insert_text((col_sn_x, y + DY), str(it["numero_serie"]), fontsize=FS)
                    if it.get("modelo"):
                        page2.insert_text((col_modelo_x, y + DY), str(it["modelo"]), fontsize=FS)
                    if it.get("status"):
                        page2.insert_text((col_status_x, y + DY), str(it["status"]), fontsize=FS)

            # ===== Produtividade / Observações (pág.2) =====
            # Agora tudo é texto livre, então só joga o que tiver
            obs_lines = []
            if (ss.produtivo or "").strip():
                obs_lines.append(f"Produtivo: {ss.produtivo.strip()}")

            if (ss.prod_parcial_tipo or "").strip():
                obs_lines.append(f"Tipo parcial: {ss.prod_parcial_tipo.strip()}")

            if (ss.ba_num or "").strip():
                obs_lines.append(f"BA: {ss.ba_num.strip()}")

            if (ss.motivo_improdutivo or "").strip():
                insert_textbox(page2, ["PROBLEMA ENCONTRADO", "Problema Encontrado"], ss.motivo_improdutivo.strip(),
                               width=540, y_offset=20, height=120, fontsize=10)

            obs_final = "\n".join([t for t in [("\n".join(obs_lines)).strip(), (ss.observacoes or "").strip()] if t])
            if obs_final:
                insert_textbox(page2, ["OBSERVAÇÕES", "Observacoes", "Observações"], obs_final,
                               width=540, y_offset=20, height=160, fontsize=10)

            # ===== Blindagem + fotos (extras no final) =====
            _insert_blind_fields_and_cover_with_gateway(doc, ss)

            imgs = [_as_bytes(i) for i in (ss.fotos_gateway or [])]
            imgs = [i for i in imgs if i]
            if len(imgs) > 1:
                for b in imgs[1:]:
                    add_image_page(doc, b)

            out = BytesIO()
            doc.save(out)
            doc.close()

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
