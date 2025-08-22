# app.py — RAT MAM (st.camera_input + scanner + regex por modelo + âncoras + assinatura sem fundo)
# Requisitos no final (requirements.txt).

from io import BytesIO
from datetime import date, time
from typing import List, Dict, Optional
import re

import streamlit as st
from PIL import Image, ImageOps, ImageFilter
import numpy as np
import fitz  # PyMuPDF
from streamlit_drawable_canvas import st_canvas

# -------- libs opcionais para scanner (o app funciona mesmo sem todas) --------
try:
    from pyzbar.pyzbar import decode as zbar_decode  # códigos 1D/2D
except Exception:
    zbar_decode = None

try:
    import zxingcpp  # leitura robusta de códigos (1D/2D)
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

# ---------------- Estado não atrelado a widgets ----------------
if "scanned_items" not in st.session_state:
    st.session_state.scanned_items = []  # cada item: {modelo, sn, mac, fonte}
if "photos_to_append" not in st.session_state:
    st.session_state.photos_to_append = []  # bytes das fotos com S/N válido
if "seriais_texto" not in st.session_state:
    st.session_state.seriais_texto = ""

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

# --- Regex de serial por modelo (calibráveis) ---
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
    bw = gray.point(lambda x: 255 if x > 165 else 0, mode="1").convert("L")
    try:
        # psm 6: bloco de texto; whitelist evita ruído de símbolos
        return pytesseract.image_to_string(
            bw, lang="eng",
            config="--psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-/:"
        )
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

    # 1) códigos de barras/QR
    bar_vals = read_barcodes(pil)

    # 2) OCR (imagem inteira + quadrantes, se necessário)
    text = ocr_image(pil)
    if (not text) and (pil.width > 800 and pil.height > 800):
        W, H = pil.size
        for box in [(0,0,W//2,H//2), (W//2,0,W,H//2), (0,H//2,W//2,H), (W//2,H//2,W,H)]:
            text += "\n" + ocr_image(pil.crop(box))

    up = (text or "").upper()

    # modelo por keywords
    model = None
    for name, rx in EQUIP_KEYWORDS.items():
        if name in ("TP-LINK", "OMADA"):
            continue
        if rx.search(up):
            model = name
            break

    # coletores
    sns = [clean_sn(m.group(0)) for m in REGEX_SN.finditer(text or "")]
    macs = [m.group(0) for m in REGEX_MAC.finditer(text or "")]

    # não confundir MAC com SN
    def looks_like_mac(s: str) -> bool:
        return bool(re.fullmatch(r"(?:[0-9A-F]{2}[:-]){5}[0-9A-F]{2}", s, re.I))
    sns = [s for s in sns if not looks_like_mac(s)]

    # barcode que parece serial
    for b in bar_vals:
        if re.fullmatch(r"[A-Z0-9\-]{6,}", b, re.I) and not looks_like_mac(b):
            sns.append(b)

    # se não achou SN por S/N, tente tokens longos como fallback
    if not sns and text:
        long_tokens = [t for t in re.findall(r"[A-Z0-9\-]{8,}", up) if not looks_like_mac(t)]
        sns.extend(long_tokens)

    # validação por modelo
    sn_valido = best_sn_for_model(model, sns)
    mac = macs[0] if macs else None

    if model or sn_valido or mac:
        found.append({
            "modelo": model or "(desconhecido)",
            "sn": sn_valido,   # pode ficar None se nenhum candidato passou na regex
            "mac": mac,
            "fonte": fonte
        })
        # anexa foto ao PDF só se houver SN válido
        if sn_valido:
            buf = BytesIO(); pil.save(buf, format="PNG")
            st.session_state.photos_to_append.append(buf.getvalue())
    return found

def add_scanned(items: List[Dict]):
    keyset = {(e["modelo"], e.get("sn") or "", e.get("mac") or "") for e in st.session_state.scanned_items}
    for it in items:
        k = (it["modelo"], it.get("sn") or "", it.get("mac") or "")
        if k not in keyset:
            st.session_state.scanned_items.append(it)
            keyset.add(k)

def push_scanned_to_textarea():
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
    st.markdown("Use a **câmera** ou **envie fotos/PDF**; os S/N válidos (regex por modelo) serão adicionados abaixo.")

    # câmera (abre a câmera do dispositivo no mobile/desktop suportado)
    cam_img = st.camera_input("📸 Tirar foto agora (abre a câmera)")
    if cam_img is not None:
        try:
            pil = Image.open(cam_img).convert("RGB")
            items = detect_from_pil(pil, fonte="camera")
            add_scanned(items)
            st.success(f"Detectado(s): {items}")
        except Exception as e:
            st.warning(f"Falha ao processar imagem da câmera: {e}")

    # upload de múltiplas fotos
    up_imgs = st.file_uploader("📎 Enviar foto(s) de etiqueta(s)", type=["jpg","jpeg","png","webp"], accept_multiple_files=True)
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
    seriais_texto_area = st.text_area(
        "Seriais (um por linha) — o scanner adiciona aqui automaticamente",
        value=st.session_state.seriais_texto,
        height=200,
        key="seriais_texto_area"
    )

    c3, c4 = st.columns(2)
    with c3:
        add_btn = st.form_submit_button("➕ Adicionar detecções ao campo de seriais", use_container_width=True)
    with c4:
        clear_btn = st.form_submit_button("🗑️ Limpar detecções (scanner)", use_container_width=True)

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

    anexar_fotos = st.checkbox("Anexar as fotos onde o S/N foi reconhecido ao final do PDF", value=True)

    submit_btn = st.form_submit_button("🧾 Gerar PDF preenchido", use_container_width=True)

# ---------------- campos de descrição (fora do form para não sumirem no submit) ----------------
st.subheader("5) Descrição de Atendimento")

atividade_txt = st.text_area(
    "Atividade (texto livre do técnico)", height=80, key="atividade_txt"
)
info_txt = st.text_area(
    "Informações adicionais (opcional)", height=60, key="info_txt"
)

# preview das fotos que irão para o PDF
if st.session_state.photos_to_append:
    st.write("**Fotos que serão anexadas ao PDF:**")
    cols = st.columns(3)
    for i, b in enumerate(st.session_state.photos_to_append):
        with cols[i % 3]:
            st.image(b, caption=f"Foto {i+1}", use_container_width=True)

# ---------------- pós-clique dos botões do form ----------------
if 'add_btn' in locals() and add_btn:
    # atualiza textarea com as detecções válidas, preservando conteúdo
    st.session_state.seriais_texto = st.session_state.get("seriais_texto_area", st.session_state.seriais_texto)
    push_scanned_to_textarea()
    st.success("Detecções adicionadas ao campo de seriais.")

if 'clear_btn' in locals() and clear_btn:
    st.session_state.scanned_items = []
    st.info("Lista de detecções limpa.")

# ---------------- Helpers PDF ----------------
def build_descricao_block(seriais_raw: str, atividade_txt: str, info_txt: str) -> str:
    partes = []
    if seriais_raw and seriais_raw.strip():
        seriais = [ln.strip() for ln in seriais_raw.splitlines() if ln.strip()]
        if seriais:
            partes.append("SERIAIS:\n" + "\n".join(f"- {s}" for s in seriais))
    if atividade_txt and atividade_txt.strip():
        partes.append("ATIVIDADE:\n" + atividade_txt.strip())
    if info_txt and info_txt.strip():
        partes.append("INFORMAÇÕES ADICIONAIS:\n" + info_txt.strip())
    return "\n\n".join(partes) if partes else ""

def insert_descricao_autofit(page, label, text):
    """Insere a descrição com auto-ajuste: fonte e altura crescem/reduzem conforme nº de linhas."""
    if not text:
        return
    r = search_once(page, label)
    if not r:
        return
    linhas = [ln for ln in text.splitlines()]
    n = len(linhas)

    if n <= 15:
        fontsize = 10; height = 240
    elif n <= 22:
        fontsize = 9;  height = 300
    elif n <= 30:
        fontsize = 8;  height = 360
    else:
        fontsize = 7;  height = 420

    rect = fitz.Rect(r.x0 + 0, r.y1 + 20, r.x0 + 540, r.y1 + 20 + height)
    page.insert_textbox(rect, text, fontsize=fontsize, align=0)

# ---------------- Geração PDF ----------------
if 'submit_btn' in locals() and submit_btn:
    try:
        base_bytes = load_pdf_bytes(PDF_BASE_PATH)
    except FileNotFoundError:
        st.error(f"Arquivo base '{PDF_BASE_PATH}' não encontrado. Faça upload como 'RAT MAM.pdf' ao lado do app.")
        st.stop()

    try:
        doc = fitz.open(stream=base_bytes, filetype="pdf")
        page = doc[0]

        # Topo
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

        # Datas/Horas/KM
        insert_right_of(page, ["Data do atendimento:", "Data do Atendimento:"],
                        data_atend.strftime("%d/%m/%Y"), dx=-90, dy=10)
        insert_right_of(page, ["Hora Inicio:", "Hora Início:", "Hora inicio:"],
                        hora_ini.strftime("%H:%M"), dx=0, dy=3)
        insert_right_of(page, ["Hora Termino:", "Hora Término:", "Hora termino:"],
                        hora_fim.strftime("%H:%M"), dx=0, dy=3)
        insert_right_of(page, ["Distancia (KM) :", "Distância (KM) :"],
                        str(distancia_km), dx=0, dy=3)

        # Descrição + seriais
        seriais_raw = st.session_state.get("seriais_texto_area", st.session_state.seriais_texto)
        st.session_state.seriais_texto = seriais_raw  # sincroniza
        bloco_desc = build_descricao_block(seriais_raw, atividade_txt=st.session_state.get("atividade_txt",""), info_txt=st.session_state.get("info_txt",""))
        insert_descricao_autofit(page, ["DESCRIÇÃO DE ATENDIMENTO","DESCRICAO DE ATENDIMENTO"], bloco_desc)

        # Técnico (RG / Nome)
        rg_lbl = find_tecnico_rg_label_rect(page)
        if rg_lbl and tec_rg:
            x_rg = rg_lbl.x1 + (4 * CM)
            y_rg = rg_lbl.y0 + rg_lbl.height/1.5 + 6
            page.insert_text((x_rg, y_rg), str(tec_rg), fontsize=10)
        if rg_lbl and tec_nome:
            x_nome = rg_lbl.x1 - (1 * CM)
            y_nome = rg_lbl.y0 + rg_lbl.height/1.5 + 12
            page.insert_text((x_nome, y_nome), str(tec_nome), fontsize=10)

        # Assinaturas (sem fundo no PDF)
        sigtec_img = np_to_rgba_pil(tec_canvas.image_data if tec_canvas else None)
        sigcli_img = np_to_rgba_pil(cli_canvas.image_data if cli_canvas else None)

        rect_tecnico = (110 - 2*CM, 0 - 1*CM, 330 - 2*CM, 54 - 1*CM)
        insert_signature(page, ["ASSINATURA:", "Assinatura:"], sigtec_img, rect_tecnico)

        rect_cliente = (110, 12 - 3.5*CM, 430, 94 - 3.5*CM)
        insert_signature(page, ["DATA CARIMBO / ASSINATURA", "ASSINATURA CLIENTE", "CLIENTE"],
                         sigcli_img, rect_cliente)

        # Nº CHAMADO — 2 cm mais à esquerda
        insert_right_of(page, [" Nº CHAMADO ", "Nº CHAMADO", "No CHAMADO"],
                        num_chamado, dx=-(2*CM), dy=10)

        # Anexar fotos no final (uma por página)
        if st.session_state.photos_to_append and anexar_fotos:
            for img_bytes in st.session_state.photos_to_append:
                try:
                    page_img = doc.new_page()
                    pil = Image.open(BytesIO(img_bytes)).convert("RGB")
                    W, H = pil.size
                    page_w, page_h = page_img.rect.width, page_img.rect.height
                    margin = 36  # ~0.5"
                    max_w, max_h = page_w - 2*margin, page_h - 2*margin
                    scale = min(max_w / W, max_h / H)
                    new_w, new_h = int(W*scale), int(H*scale)
                    x0 = (page_w - new_w) / 2
                    y0 = (page_h - new_h) / 2
                    rect = fitz.Rect(x0, y0, x0 + new_w, y0 + new_h)
                    b = BytesIO(); pil.save(b, format="JPEG", quality=92)
                    page_img.insert_image(rect, stream=b.getvalue())
                except Exception as e:
                    st.warning(f"Falha ao anexar uma foto: {e}")

        out = BytesIO()
        doc.save(out)
        doc.close()

        st.success("PDF gerado com sucesso!")
        st.download_button(
            "⬇️ Baixar RAT preenchido",
            data=out.getvalue(),
            file_name=f"RAT_MAM_preenchido_{(num_chamado or 'sem_num')}.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.error(f"Falha ao gerar PDF: {e}")
        st.exception(e)
