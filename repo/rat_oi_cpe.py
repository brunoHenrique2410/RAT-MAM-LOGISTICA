# repo/rat_oi_cpe.py — RAT OI CPE NOVO
# ✅ Horário início / término
# ✅ Data/Horário do preenchimento usando fuso do browser
# ✅ Selo (imagem + texto) com fallback e blindagem (nunca quebra o PDF)

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

# Import seguro do selo (não derruba o app se algo faltar)
try:
    from common.pdf import add_generation_stamp
except Exception:
    add_generation_stamp = None

PDF_DIR = os.path.join(PROJECT_ROOT, "pdf_templates")
PDF_BASE_PATH = os.path.join(PDF_DIR, "RAT_OI_CPE_NOVO.pdf")
DEFAULT_TZ = "America/Sao_Paulo"

# ✅ resolve do caminho do selo (não quebra no cloud se o arquivo não existir)
def _resolve_stamp_path(project_root: str) -> str:
    candidates = [
        os.path.join(project_root, "assets", "selo_evernex_maminfo.png"),
        os.path.join(project_root, "assets", "selo_evernex_maminfo.PNG"),
        os.path.join(project_root, "assets", "selo.png"),
        os.path.join(project_root, "assets", "stamp.png"),
        os.path.join(project_root, "assets", "carimbo.png"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return ""  # vazio => a função do selo deve cair no fallback (texto)

SELO_IMG = _resolve_stamp_path(PROJECT_ROOT)


# ---------- helpers ----------
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

def _cm_to_pt(cm: float) -> float:
    return cm * 28.3464567


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

    modelo_opts = ["", "aligera", "SynWay"]
    status_opts = ["", "equipamento no local", "instalado pelo técnico", "retirado pelo técnico",
                   "spare técnico", "técnico não levou equipamento"]

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
        it["modelo"] = st.selectbox(
            "Modelo", modelo_opts,
            index=(modelo_opts.index(it.get("modelo", "")) if it.get("modelo", "") in modelo_opts else 0),
            key=f"equip_{i}_modelo"
        )
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
    page = doc.new_page()  # última
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

    if ss.fotos_gateway:
        try:
            img_bytes = ss.fotos_gateway[0]
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
        "produtivo": "sim-totalmente produtivo",
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

        st.markdown("**Responsável local** (antes do endereço)")
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
        ss.produtivo = st.selectbox(
            "Produtivo?",
            ["sim-totalmente produtivo", "produtivo parcial", "não-improdutivo"],
            index=["sim-totalmente produtivo", "produtivo parcial", "não-improdutivo"].index(ss.produtivo)
        )

        if ss.produtivo == "produtivo parcial":
            ss.prod_parcial_tipo = st.radio(
                "Tipo de parcial",
                ["com BA", "problema PABX"],
                index=(["com BA", "problema PABX"].index(ss.prod_parcial_tipo)
                       if ss.prod_parcial_tipo in ["com BA", "problema PABX"] else 0)
            )
            if ss.prod_parcial_tipo == "com BA":
                ss.ba_num = st.text_input("Nº do BA", value=ss.ba_num)
            else:
                ss.ba_num = ""
        else:
            ss.prod_parcial_tipo = ""
            ss.ba_num = ""

        improd_opts = [
            "IMPRODUTIVO - CONECTOR PABX INCOMPATIVEL",
            "IMPRODUTIVO - CLIENTE NÃO LIBEROU ACESSO - CLIENTE NÃO PERMITIU",
            "IMPRODUTIVO - NÃO TEM TOMADA - INTERNET E ETC - FALTA INFRA",
            "IMPRODUTIVO - CABO NÃO COMPATIVEL COM A MIGRAÇÃO",
            "IMPRODUTIVO - FALTA EQUIPAMENTO",
            "IMPRODUTIVO - EQUIPAMENTO COM DEFEITO",
            "IMPRODUTIVO - PLATAFORMA DA OI INDISPONIVEL",
            "IMPRODUTIVO - SEM TI DO CLIENTE NO LOCAL / CHAVE NÃO LOCALIZADA",
            "IMPRODUTIVO - ENDEREÇO INCORRETO/CHAVE NÃO LOCALIZADA",
            "IMPRODUTIVO - CLIENTE CANCELOU A CHAVE - CANCELADO",
            "IMPRODUTIVO - SEM INFORMAÇÕES DOS IPS",
            "IMPRODUTIVO - CLIENTE NÃO LIBEROU PORTA DE SW",
            "IMPRODUTIVO - CLIENTE NÃO LIEBEROU AS REGRAS - REGRAS de FIREWALL",
            "IMPRODUTIVO - CLIENTE SOLICITOU NOVA DATA",
            "IMPRODUTIVO - CHAMADO AGENDADO PARA OUTRA DATA",
            "IMPRODUTIVO - PORTADO PARA OUTRA OPERADORA - PORTABILIDADE",
            "IMPRODUTIVO - TECNICO NÃO COMPARECEU",
        ]
        if ss.produtivo == "não-improdutivo":
            default_idx = improd_opts.index(ss.motivo_improdutivo) if ss.motivo_improdutivo in improd_opts else 0
            ss.motivo_improdutivo = st.selectbox("Motivo da improdutividade", improd_opts, index=default_idx)
        else:
            ss.motivo_improdutivo = ""

        ss.observacoes = st.text_area("Observações (texto adicional)", value=ss.observacoes, height=100)

    # 6) Foto do Gateway
    with st.expander("6) Foto do Gateway", expanded=True):
        foto_gateway_uploader()

    # -------- PDF --------
    if st.button("🧾 Gerar PDF (OI CPE)"):
        try:
            doc, page1 = open_pdf_template(PDF_BASE_PATH, hint="RAT OI CPE NOVO")

            # (… aqui você mantém TODO o seu preenchimento atual …)

            # =========================================================
            # ✅ GARANTIR NOW (se não tiver sido definido antes)
            # =========================================================
            if "now" not in locals() or now is None:
                now = datetime.now(ZoneInfo(DEFAULT_TZ))

            # =========================================================
            # ✅ Blindagem + fotos
            # =========================================================
            _insert_blind_fields_and_cover_with_gateway(doc, ss)
            if len(ss.fotos_gateway) > 1:
                for b in ss.fotos_gateway[1:]:
                    if b:
                        add_image_page(doc, b)

            # =========================================================
            # ✅ SELO (blindado: nunca derruba e sempre tenta aplicar)
            # =========================================================
            try:
                if add_generation_stamp:
                    stamp_text = (
                        "Gerado automaticamente\n"
                        f"{now.strftime('%d/%m/%Y %H:%M')} • Chamado {ss.numero_chamado or '-'}"
                    )
                    add_generation_stamp(
                        page1,
                        SELO_IMG,  # se vazio/inexistente => fallback só texto (na função)
                        stamp_text,
                        where="top_right",  # <- use top_right para garantir visível; depois volta p/ bottom_right se quiser
                        scale=0.55,
                        opacity=0.85
                    )
                else:
                    # fallback mínimo (garante que algo apareça)
                    page1.insert_text((40, 40), "Gerado automaticamente", fontsize=9)
            except Exception:
                # se der qualquer problema no selo, NÃO quebra o PDF
                pass

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
