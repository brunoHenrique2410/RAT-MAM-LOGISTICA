# app.py — RAT MAM (scanner + regex por modelo + âncoras + assinatura sem fundo)
# Requisitos em requirements.txt ao final desta resposta.

from io import BytesIO
from datetime import date, time
from typing import List, Dict, Optional
import re

import streamlit as st
from PIL import Image, ImageOps, ImageFilter
import numpy as np
import fitz  # PyMuPDF
from streamlit_drawable_canvas import st_canvas

# --- libs opcionais para scanner ---
try:
    from pyzbar.pyzbar import decode as zbar_decode  # códigos 1D/2D
except Exception:
    zbar_decode = None

try:
    import zxingcpp  # leitura robusta de códigos
except Exception:
    zxingcpp = None

try:
    import pytesseract  # OCR
except Exception:
    pytesseract = None

PDF_BASE_PATH = "RAT MAM.pdf"
APP_TITLE = "RAT MAM – Assinatura + Âncoras + Scanner de Seriais"
CM = 28.3465  # pontos por cm (A4 ~595x842 pt)

# ---------------- UI base ----------------
st.set_page_config(page_title=APP_TITLE, layout="centered")
st.title("📄 " + APP_TITLE)
st.caption("Scanner adiciona seriais automaticamente (câmera, fotos ou PDF). Assinaturas com fundo removido no PDF.")

# ---------------- Estado ----------------
if "scanned_items" not in st.session_state:
    st.session_state.scanned_items = []  # {modelo, sn, mac, fonte}
if "seriais_texto" not in st.session_state:
    st.session_state.seriais_texto = ""
if "atividade_txt" not in st.session_state:
    st.session_state.atividade_txt = ""
if "info_txt" not in st.session_state:
    st.session_state.info_txt = ""

# ---------------- Utilidades ----------------
REGEX_SN = re.compile(r'(?:S/?N[:\s\-]*)([A-Z0-9\-]{4,})', re.I)
REGEX_MAC = re.compile(r'\b([0-9A-F]{2}[:-]){5}[0-9A-F]{2}\b', re.I)

EQUIP_KEYWORDS = {
    "ER605": re.compile(r"\bER605\b", re.I),
    "ER7206": re.compile(r"\bER7206\b", re.I),
    "OC200": re.compile(r"\bOC200\b", re.I),
    "EAP610": re.compile(r"\bEAP610\b", re.I),
    "SG3428MP": re.compile(r"\bSG3428\b|\b28-PORT\b", re.I),
    "SG2210MP-8P": re.compile(r"\bSG2210\b|\b8-PORT\b", re.I),
    "NHS COMPACT PLUS": re.compile(r"\bNHS\b", re.I),
    "TP-LINK": re.compile(r"TP-?LINK", re.I),
    "OMADA": re.compile(r"\bOMADA\b", re.I),
}

# --- Regex de serial por modelo (ajuste conforme seu parque) ---
SERIAL_REGEX = {
    "ER605":             re.compile(r"^[0-9A-Z\-]{10,16}$", re.I),
    "ER7206":            re.compile(r"^[0-9A-Z\-]{10,16}$", re.I),
    "OC200":             re.compile(r"^[0-9A-Z]{12,14}$", re.I),
    "EAP610":            re.compile(r"^[0-9A-Z]{12,14}$", re.I),
    "SG3428MP":          re.compile(r"^[0-9]{12,14}$"),
    "SG2210MP-8P":       re.compile(r"^[0-9]{12,14}$"),
    "NHS COMPACT PLUS":  re.compile(r"^[0-9]{4,10}$"),
}
FALLBACK_SN = re.compile(r"^[0-9A-Z\-]{6,}$", re.I)

def is_valid_sn(modelo: Optional[str], sn: Optional[str]) -> bool:
    if not sn:
        return False
    if modelo and modelo in SERIAL_REGEX:
        return bool(SERIAL_REGEX[modelo].match(sn))
    return bool(FALLBACK_SN.match(sn))

def best_sn_for_model(modelo: Optional[str], candidatos: List[str]) -> Optional[str]:
    for s in candidatos:
        if is_valid_sn(modelo, s):
            return s
    return None

def normalize_phone(s: str) -> str:
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return s

def np_to_rgba_pil(arr) -> Optional[Image.Image]:
    if arr is None or not isinstance(arr, np.ndarray) or arr.ndim != 3 or arr.shape[2] < 4:
        return None
    if np.max(arr[:, :, 3]) == 0:
        return None
    return Image.fromarray(arr.astype("uint8"), mode="RGBA")

def remove_white_to_transparent(img: Image.Image, thresh: int = 245) -> Image.Image:
    arr = np.array(img.convert("RGBA"))
    rgb = arr[:, :, :3]
    mask_white = (rgb[:, :, 0] >= thresh) & (rgb[:, :, 1] >= thresh) & (rgb[:, :, 2] >= thresh)
    arr[mask_white, 3] = 0
    return Image.fromarray(arr, mode="RGBA")

@st.cache_data
def load_pdf_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()

def search_once(page, texts):
    if isinstance(texts, str):
        texts = [texts]
    for t in texts:
        rects = page.search_for(t)
        if rects:
            return rects[0]
    return None

def search_all(page, text):
    return page.search_for(text)

def insert_right_of(page, labels, content, dx=0, dy=0, fontsize=10):
    if not content:
        return
    r = search_once(page, labels)
    if not r:
        return
    x = r.x1 + dx
    y = r.y0 + r.height/1.5 + dy
    page.insert_text((x, y), str(content), fontsize=fontsize)

def insert_textbox_below(page, label, content, box=(0, 20, 540, 240), fontsize=10, align=0):
    if not content:
        return
    r = search_once(page, label)
    if not r:
        return
    rect = fitz.Rect(r.x0 + box[0], r.y1 + box[1], r.x0 + box[2], r.y1 + box[3])
    page.insert_textbox(rect, str(content), fontsize=fontsize, align=align)

def insert_signature(page, label, img_rgba: Image.Image, rel_rect):
    if img_rgba is None:
        return
    r = search_once(page, label)
    if not r:
        return
    rect = fitz.Rect(r.x0 + rel_rect[0], r.y1 + rel_rect[1], r.x0 + rel_rect[2], r.y1 + rel_rect[3])
    img_clean = remove_white_to_transparent(img_rgba, thresh=245)
    buf = BytesIO(); img_clean.save(buf, format="PNG")
    page.insert_image(rect, stream=buf.getvalue())

def find_tecnico_rg_label_rect(page):
    for lbl in ["TÉCNICO RG:", "TÉCNICO  RG:", "TECNICO RG:"]:
        rect = search_once(page, [lbl])
        if rect:
            return rect
    return None

# ---------------- Scanner (modelo + S/N + MAC) ----------------
def clean_sn(sn: str) -> str:
    return re.sub(r'(?i)^S/?N[:\s\-]*', '', sn).strip()

def ocr_image(pil: Image.Image) -> str:
    if pytesseract is None:
        return ""
    w, h = pil.size
    if max(w, h) < 1600:
        pil = pil.resize((w * 2, h * 2))
    gray = ImageOps.grayscale(pil)
    gray = gray.filter(ImageFilter.SHARPEN)
    bw = gray.point(lambda x: 255 if x > 160 else 0, mode="1").convert("L")
    try:
        return pytesseract.image_to_string(bw, lang="eng")
    except Exception:
        return ""

def read_barcodes(pil: Image.Image) -> List[str]:
    vals = []
    if zxingcpp:
        try:
            for r in zxingcpp.read_barcodes(pil):
                if r.text:
                    vals.append(r.text.strip())
        except Exception:
            pass
    if zbar_decode:
        try:
            for obj in zbar_decode(pil):
                if obj.data:
                    vals.append(obj.data.decode("utf-8", errors="ignore").strip())
        except Exception:
            pass
    # únicos
    seen = set(); out = []
    for v in vals:
        if v not in seen:
            out.append(v); seen.add(v)
    return out

def detect_from_pil(pil: Image.Image, fonte: str) -> List[Dict]:
    found = []
    # 1) códigos
    bar_vals = read_barcodes(pil)

    # 2) OCR imagem inteira + quadrantes (fallback)
    text = ocr_image(pil)
    if (not text) and (pil.width > 800 and pil.height > 800):
        W, H = pil.size
        for box in [(0,0,W//2,H//2), (W//2,0,W,H//2), (0,H//2,W//2,H), (W//2,H//2,W,H)]:
            text += "\n" + ocr_image(pil.crop(box))

    up = (text or "").upper()

    # modelo (heurística por palavras‑chave)
    model = None
    for name, rx in EQUIP_KEYWORDS.items():
        if name in ("TP-LINK", "OMADA"):
            continue
        if rx.search(up):
            model = name
            break

    # seriais & macs
    sns = [clean_sn(m.group(0)) for m in REGEX_SN.finditer(text or "")]
    macs = [m.group(0) for m in REGEX_MAC.finditer(text or "")]

    # barcode que parece serial
    for b in bar_vals:
        if re.fullmatch(r"[A-Z0-9\-]{6,}", b, re.I):
            sns.append(b)

    # commit com validação
    sn_valido = best_sn_for_model(model, sns)
    mac = macs[0] if macs else None

    if model or sn_valido or mac:
        found.append({
            "modelo": model or "(desconhecido)",
            "sn": sn_valido,   # pode ficar None se nenhum candidato passou na regex
            "mac": mac,
            "fonte": fonte
        })
    return found

def add_scanned(items: List[Dict]):
    # evita dup: chave por (modelo, sn, mac)
    keyset = {(e["modelo"], e.get("sn") or "", e.get("mac") or "") for e in st.session_state.scanned_items}
    for it in items:
        k = (it["modelo"], it.get("sn") or "", it.get("mac") or "")
        if k not in keyset:
            st.session_state.scanned_items.append(it)
            keyset.add(k)

def push_scanned_to_textarea():
    # gera linhas no padrão "Modelo – S/N XXXXX" (só se passar na regex)
    linhas = []
    for it in st.session_state.scanned_items:
        sn = it.get("sn")
        modelo = it.get("modelo")
        if not is_valid_sn(modelo, sn):
            continue
        if sn:
            if modelo and modelo != "(desconhecido)":
                linhas.append(f"{modelo}  S/N {sn}")
            else:
                linhas.append(f"{sn}")
    # mantém o que já havia + adiciona novos, sem duplicar
    exist = [ln.strip() for ln in (st.session_state.seriais_texto or "").splitlines() if ln.strip()]
    all_lines, seen = [], set()
    for ln in exist + linhas:
        if ln not in seen:
            all_lines.append(ln); seen.add(ln)
    st.session_state.seriais_texto = "\n".join(all_lines)

# ---------------- Form principal ----------------
with st.form("rat_mam"):
    st.subheader("1) Chamado e Agenda")
    c1, c2 = st.columns(2)
    with c1:
        num_chamado = st.text_input("Nº do chamado")
        data_atend  = st.date_input("Data do atendimento", value=date.today())
        hora_ini    = st.time_input("Hora início", value=time(8, 0))
    with c2:
        hora_fim    = st.time_input("Hora término", value=time(10, 0))
        distancia_km = st.text_input("Distância (KM)")

    st.subheader("2) Cliente (topo do PDF)")
    cliente_nome = st.text_input("Cliente / Razão Social")
    endereco     = st.text_input("Endereço")
    bairro       = st.text_input("Bairro")
    cidade       = st.text_input("Cidade")
    contato_nome = st.text_input("Contato (nome)")
    contato_rg   = st.text_input("Contato (RG/Doc)")
    contato_tel  = st.text_input("Contato (Telefone)")

    st.subheader("3) Seriais (Scanner + Texto)")
    st.markdown("**Scanner** – use a câmera ou envie fotos/PDF; os seriais válidos (regex por modelo) serão adicionados abaixo.")

    # câmera (mobile/desktop)
    cam_img = st.camera_input("📷 Tirar foto da etiqueta (opcional)")
    if cam_img is not None:
        try:
            pil = Image.open(cam_img).convert("RGB")
            items = detect_from_pil(pil, fonte="camera")
            add_scanned(items)
            st.success(f"Detectado(s): {items}")
        except Exception as e:
            st.warning(f"Falha ao processar imagem da câmera: {e}")

    # upload de múltiplas fotos
    up_imgs = st.file_uploader("📎 Enviar foto(s) de etiqueta(s)", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True)
    if up_imgs:
        for f in up_imgs:
            try:
                pil = Image.open(f).convert("RGB")
                items = detect_from_pil(pil, fonte=f.name)
                add_scanned(items)
            except Exception as e:
                st.warning(f"{f.name}: erro ao processar — {e}")

    # upload de PDF para varrer imagens embutidas
    up_pdf = st.file_uploader("📎 Enviar RAT (PDF) para extrair fotos de etiquetas", type=["pdf"])
    if up_pdf is not None:
        try:
            doc_tmp = fitz.open(stream=up_pdf.read(), filetype="pdf")
            hits = 0
            for pno, page in enumerate(doc_tmp):
                for idx, info in enumerate(page.get_images(full=True)):
                    base = doc_tmp.extract_image(info[0])
                    pil = Image.open(BytesIO(base["image"])).convert("RGB")
                    items = detect_from_pil(pil, fonte=f"pdf:p{pno}_img{idx}")
                    add_scanned(items); hits += len(items)
            st.success(f"PDF analisado: {hits} possível(is) etiqueta(s) reconhecida(s).")
        except Exception as e:
            st.warning(f"Erro ao varrer PDF: {e}")

    # prévia dos detectados (com flag sn_valido)
    if st.session_state.scanned_items:
        enriched = []
        for it in st.session_state.scanned_items:
            enriched.append({**it, "sn_valido": is_valid_sn(it.get("modelo"), it.get("sn"))})
        st.write("**Detectados (prévia):**")
        st.dataframe(enriched, use_container_width=True, height=240)

    # área de seriais (editável)
    seriais_texto = st.text_area(
        "Seriais (um por linha) — o scanner adiciona aqui automaticamente",
        value=st.session_state.seriais_texto,
        height=200,
        key="seriais_texto_area"
    )

    c3, c4 = st.columns(2)
    with c3:
        if st.form_submit_button("➕ Adicionar detecções ao campo de seriais", use_container_width=True):
            st.session_state.seriais_texto = st.session_state.get("seriais_texto_area", st.session_state.seriais_texto)
            push_scanned_to_textarea()
            st.session_state.seriais_texto = st.session_state.seriais_texto  # garante persistência
            st.success("Detecções adicionadas ao campo de seriais.")
    with c4:
        if st.form_submit_button("🗑️ Limpar detecções (scanner)", use_container_width=True):
            st.session_state.scanned_items = []
            st.info("Lista de detecções limpa.")

    st.subheader("4) Técnico")
    tec_nome = st.text_input("Nome do técnico")
    tec_rg   = st.text_input("RG/Documento do técnico")

    st.write("**Assinatura do TÉCNICO**")
    tec_canvas = st_canvas(
        fill_color="rgba(0,0,0,0)",
        stroke_width=3,
        stroke_color="#000000",
        background_color="#FFFFFF",
        width=800, height=180,
        drawing_mode="freedraw",
        key="sig_tec_canvas",
        update_streamlit=True,
        display_toolbar=True,
    )

    st.write("---")
    st.write("**Assinatura do CLIENTE**")
    cli_canvas = st_canvas(
        fill_color="rgba(0,0,0,0)",
        stroke_width=3,
        stroke_color="#000000",
        background_color="#FFFFFF",
        width=800, height=180,
        drawing_mode="freedraw",
        key="sig_cli_canvas",
        update_streamlit=True,
        display_toolbar=True,
    )

    submitted = st.form_submit_button("🧾 Gerar PDF preenchido", use_container_width=True)

# campos de descrição (fora do form para não sumirem no submit)
st.subheader("5) Descrição de Atendimento")
st.session_state.atividade_txt = st.text_area("Atividade (texto livre do técnico)", height=80, key="atividade_txt")
st.session_state.info_txt = st.text_area("Informações adicionais (opcional)", height=60, key="info_txt")

# ---------------- Helpers PDF ----------------
def build_descricao_block() -> str:
    partes = []
    seriais_raw = st.session_state.get("seriais_texto_area", st.session_state.seriais_texto)
    if seriais_raw and seriais_raw.strip():
        seriais = [ln.strip() for ln in seriais_raw.splitlines() if ln.strip()]
        if seriais:
            partes.append("SERIAIS:\n" + "\n".join(f"- {s}" for s in seriais))
    if st.session_state.atividade_txt and st.session_state.atividade_txt.strip():
        partes.append("ATIVIDADE:\n" + st.session_state.atividade_txt.strip())
    if st.session_state.info_txt and st.session_state.info_txt.strip():
        partes.append("INFORMAÇÕES ADICIONAIS:\n" + st.session_state.info_txt.strip())
    return "\n\n".join(partes) if partes else ""

def insert_descricao_autofit(page, label, text):
    """Insere a descrição com auto-ajuste:
       - fonte 10 para até ~15 linhas; depois reduz para 9/8/7
       - aumenta a altura da caixa se necessário
    """
    if not text:
        return
    r = search_once(page, label)
    if not r:
        return
    linhas = [ln for ln in text.splitlines()]
    n = len(linhas)

    # heurística de fonte/altura
    if n <= 15:
        fontsize = 10; height = 240
    elif n <= 22:
        fontsize = 9; height = 300
    elif n <= 30:
        fontsize = 8; height = 360
    else:
        fontsize = 7; height = 420  # muitos seriais

    rect = fitz.Rect(r.x0 + 0, r.y1 + 20, r.x0 + 540, r.y1 + 20 + height)
    page.insert_textbox(rect, text, fontsize=fontsize, align=0)

# ---------------- Geração PDF ----------------
if submitted:
    # sincroniza seriais
    st.session_state.seriais_texto = st.session_state.get("seriais_texto_area", st.session_state.seriais_texto)

    # assinaturas do canvas
    sigtec_img = np_to_rgba_pil(tec_canvas.image_data if tec_canvas else None)
    sigcli_img = np_to_rgba_pil(cli_canvas.image_data if cli_canvas else None)

    # pedir base se não existir localmente
    base_bytes = None
    try:
        base_bytes = load_pdf_bytes(PDF_BASE_PATH)
    except FileNotFoundError:
        st.warning(f"Arquivo base '{PDF_BASE_PATH}' não encontrado. Envie abaixo.")
        up = st.file_uploader("📎 Envie o RAT MAM.pdf", type=["pdf"], key="base_pdf_on_submit")
        if up is not None:
            base_bytes = up.read()
    if base_bytes is None:
        st.stop()

    try:
        doc = fitz.open(stream=base_bytes, filetype="pdf")
        page = doc[0]

        # Topo
        # (Você pode mover estes campos para dentro do form, se preferir)
        # Para exemplo, estou deixando como placeholders vazios; ajuste conforme sua coleta real
        cliente_nome = st.session_state.get("cliente_nome", "")
        endereco = st.session_state.get("endereco", "")
        bairro = st.session_state.get("bairro", "")
        cidade = st.session_state.get("cidade", "")
        contato_nome = st.session_state.get("contato_nome", "")
        contato_rg = st.session_state.get("contato_rg", "")
        contato_tel = st.session_state.get("contato_tel", "")

        insert_right_of(page, ["Cliente:", "CLIENTE:"], cliente_nome, dx=6, dy=1)
        insert_right_of(page, ["Endereço:", "ENDEREÇO:"], endereco, dx=6, dy=1)
        insert_right_of(page, ["Bairro:", "BAIRRO:"],     bairro,     dx=6, dy=1)
        insert_right_of(page, ["Cidade:", "CIDADE:"],     cidade,     dx=6, dy=1)
        insert_right_of(page, ["Contato:"], contato_nome, dx=6, dy=1)

        r_cont = search_once(page, ["Contato:"])
        if r_cont and contato_rg:
            rg_rects = search_all(page, "RG:")
            if rg_rects:
                cy = r_cont.y0 + r_cont.height/2
                rg_best = min(rg_rects, key=lambda rr: abs((rr.y0+rr.height/2)-cy))
                x = rg_best.x1 + 6
                y = rg_best.y0 + rg_best.height/1.5 + 6
                page.insert_text((x, y), str(contato_rg), fontsize=10)

        insert_right_of(page, ["Telefone:", "TELEFONE:"], normalize_phone(contato_tel), dx=6, dy=1)

        # Datas/Horas/KM — como exemplo, valores default:
        insert_right_of(page, ["Data do atendimento:", "Data do Atendimento:"],
                        date.today().strftime("%d/%m/%Y"), dx=-90, dy=10)
        insert_right_of(page, ["Hora Inicio:", "Hora Início:", "Hora inicio:"],
                        time(8,0).strftime("%H:%M"), dx=0, dy=3)
        insert_right_of(page, ["Hora Termino:", "Hora Término:", "Hora termino:"],
                        time(10,0).strftime("%H:%M"), dx=0, dy=3)
        insert_right_of(page, ["Distancia (KM) :", "Distância (KM) :"],
                        "", dx=0, dy=3)

        # Descrição com SERIAIS (auto-fit)
        bloco_desc = build_descricao_block()
        insert_descricao_autofit(page, ["DESCRIÇÃO DE ATENDIMENTO","DESCRICAO DE ATENDIMENTO"], bloco_desc)

        # Técnico (RG / Nome)
        rg_lbl = find_tecnico_rg_label_rect(page)
        tec_nome = st.session_state.get("tec_nome", "")
        tec_rg   = st.session_state.get("tec_rg", "")
        if rg_lbl and tec_rg:
            x_rg = rg_lbl.x1 + (4 * CM)
            y_rg = rg_lbl.y0 + rg_lbl.height/1.5 + 6
            page.insert_text((x_rg, y_rg), str(tec_rg), fontsize=10)
        if rg_lbl and tec_nome:
            x_nome = rg_lbl.x1 - (1 * CM)
            y_nome = rg_lbl.y0 + rg_lbl.height/1.5 + 12
            page.insert_text((x_nome, y_nome), str(tec_nome), fontsize=10)

        # Assinaturas (sem fundo no PDF)
        rect_tecnico = (110 - 2*CM, 0 - 1*CM, 330 - 2*CM, 54 - 1*CM)
        insert_signature(page, ["ASSINATURA:", "Assinatura:"], sigtec_img, rect_tecnico)

        rect_cliente = (110, 12 - 3.5*CM, 430, 94 - 3.5*CM)
        insert_signature(page, ["DATA CARIMBO / ASSINATURA", "ASSINATURA CLIENTE", "CLIENTE"],
                         sigcli_img, rect_cliente)

        # Nº CHAMADO — 2 cm mais à esquerda (exemplo: vazio)
        insert_right_of(page, [" Nº CHAMADO ", "Nº CHAMADO", "No CHAMADO"], "", dx=-(2*CM), dy=10)

        out = BytesIO()
        doc.save(out)
        doc.close()

        st.success("PDF gerado com sucesso!")
        st.download_button(
            "⬇️ Baixar RAT preenchido",
            data=out.getvalue(),
            file_name=f"RAT_MAM_preenchido.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.error(f"Falha ao gerar PDF: {e}")
        st.exception(e)
