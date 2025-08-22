# app.py — RAT MAM (abas isoladas: Scanner | Assinaturas | Dados & PDF)
# - OCR Tesseract obrigatório (erro amigável se ausente)
# - Assinaturas isoladas e salvas como PNG (transparente ou fundo branco)
# - Scanner com botões: CÂMERA / FOTOS / PDF; sem pré-visualização; com deduplicação
# - Âncora "S/N" para priorizar serial (evita confundir com MAC)
# - Editor de itens scaneados + "Jogar S/N" para textarea
# - Anexar fotos ao PDF (páginas novas)
from io import BytesIO
from datetime import date, time
from typing import List, Dict, Optional, Tuple
import os, re, hashlib

import streamlit as st
from PIL import Image, ImageOps, ImageFilter
import numpy as np
import fitz  # PyMuPDF
from streamlit_drawable_canvas import st_canvas

# ---- Leitores (tolerante: zbar/zxing são opcionais; Tesseract é obrigatório) ----
try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    from pyzbar.pyzbar import decode as zbar_decode
except Exception:
    zbar_decode = None

try:
    import zxingcpp
except Exception:
    zxingcpp = None


# -------------------- CONFIG --------------------
PDF_BASE_PATH = "RAT MAM.pdf"
APP_TITLE = "RAT MAM – Scanner + Assinaturas isoladas (OCR obrigatório)"
CM = 28.3465  # pontos por cm

st.set_page_config(page_title=APP_TITLE, layout="centered")
st.title("📄 " + APP_TITLE)
st.caption("Abas isoladas: Scanner / Assinaturas / Dados & PDF. OCR obrigatório; sem pré‑visualização de fotos.")

# -------------------- OCR obrigatório --------------------
def ensure_tesseract_available():
    if pytesseract is None:
        st.error("`pytesseract` não está instalado. Adicione `pytesseract` no requirements e reinicie.")
        st.stop()
    if os.environ.get("TESSERACT_CMD"):
        pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]
    try:
        _ = pytesseract.get_tesseract_version()
    except Exception:
        st.error(
            "Tesseract OCR não encontrado no sistema.\n\n"
            "Instale o binário do Tesseract:\n"
            "• Ubuntu/Debian: `sudo apt-get update && sudo apt-get install -y tesseract-ocr`\n"
            "• Windows: instale o Tesseract (UB Mannheim) e defina TESSERACT_CMD se necessário."
        )
        st.stop()

ensure_tesseract_available()

# -------------------- ESTADO --------------------
ss = st.session_state

# Scanner / fotos / dedup
ss.setdefault("scanned_items", [])            # [{modelo,sn,mac,fonte}]
ss.setdefault("photos_to_append", [])         # [bytes JPEG]
ss.setdefault("seen_hashes", set())           # para deduplicar imagens processadas
ss.setdefault("seriais_texto", "")
ss.setdefault("anexar_fotos", True)

# Assinaturas salvas (PNG) e modo de fundo
ss.setdefault("sig_tec_png", None)            # bytes (PNG)
ss.setdefault("sig_cli_png", None)            # bytes (PNG)
ss.setdefault("assinatura_transparente", True)

# Dados do RAT (defaults)
defaults = {
    "data_atend": date.today(),
    "hora_ini": time(8,0),
    "hora_fim": time(10,0),
    "num_chamado": "",
    "distancia_km": "",
    "cliente_nome": "", "endereco": "", "bairro": "", "cidade": "",
    "contato_nome": "", "contato_rg": "", "contato_tel": "",
    "tec_nome": "", "tec_rg": "",
    "atividade_txt": "", "info_txt": "",
}
for k, v in defaults.items():
    ss.setdefault(k, v)

# -------------------- REGEX / UTILS --------------------
REGEX_SN_ANC        = re.compile(r'\bS/?N\b[:\-]?', re.I)
REGEX_SN_FROM_TEXT  = re.compile(r'\bS/?N[:\s\-]*([A-Z0-9\-]{6,})', re.I)
REGEX_MAC           = re.compile(r'(?:[0-9A-F]{2}[:-]){5}[0-9A-F]{2}', re.I)

EQUIP_KEYWORDS = {
    "ER605": re.compile(r"\bER605\b", re.I),
    "ER7206": re.compile(r"\bER7206\b", re.I),
    "OC200": re.compile(r"\bOC200\b", re.I),
    "EAP610": re.compile(r"\bEAP610\b", re.I),
    "SG3428MP": re.compile(r"\bSG3428\b", re.I),
    "SG2210MP-8P": re.compile(r"\bSG2210\b", re.I),
    "NHS COMPACT PLUS": re.compile(r"\bNHS\b", re.I),
}
SERIAL_REGEX = {
    "ER605":             re.compile(r"^[0-9A-Z\-]{10,16}$", reI:=re.I),
    "ER7206":            re.compile(r"^[0-9A-Z\-]{10,16}$", reI),
    "OC200":             re.compile(r"^[0-9A-Z]{12,14}$",  reI),
    "EAP610":            re.compile(r"^[0-9A-Z]{12,16}$",  reI),
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

def normalize_phone(s: str) -> str:
    d = "".join(ch for ch in s if s and ch.isdigit())
    if len(d) == 11: return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10: return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return s or ""

@st.cache_data
def load_pdf_bytes(path: str) -> bytes:
    with open(path, "rb") as f: return f.read()

# -------------------- Assinatura (canvas -> PNG) --------------------
def signature_rgba_from_canvas(arr: np.ndarray, transparente: bool = True) -> Optional[Image.Image]:
    if arr is None or arr.ndim != 3 or arr.shape[2] < 4:
        return None
    rgba = arr.astype("uint8").copy()
    mask = (rgba[:, :, 3] > 0)
    if transparente:
        # fundo 100% transparente; traço preto opaco
        out = np.zeros_like(rgba, dtype=np.uint8)
        out[mask, 0] = 0; out[mask, 1] = 0; out[mask, 2] = 0; out[mask, 3] = 255
        return Image.fromarray(out, mode="RGBA")
    else:
        # chapado em branco (sem alpha)
        out = np.full_like(rgba, 255, dtype=np.uint8)
        out[mask, 0] = 0; out[mask, 1] = 0; out[mask, 2] = 0
        return Image.fromarray(out[:, :, :3], mode="RGB")

def to_png_bytes(img: Image.Image, transparente: bool = True) -> Optional[bytes]:
    if img is None:
        return None
    buf = BytesIO()
    if transparente and img.mode != "RGBA":
        img = img.convert("RGBA")
    if not transparente and img.mode != "RGB":
        img = img.convert("RGB")
    img.save(buf, format="PNG")
    return buf.getvalue()

# -------------------- OCR helpers --------------------
def ocr_text(pil: Image.Image) -> str:
    img = ImageOps.grayscale(pil).filter(ImageFilter.SHARPEN)
    img = img.point(lambda x: 255 if x > 165 else 0, mode="1").convert("L")
    return pytesseract.image_to_string(
        img, lang="eng",
        config="--psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-/:"
    )

def ocr_data(pil: Image.Image):
    try:
        img = ImageOps.grayscale(pil)
        return pytesseract.image_to_data(img, lang="eng", output_type=pytesseract.Output.DICT)
    except Exception:
        return None

def find_sn_anchor_bbox(pil: Image.Image) -> Optional[Tuple[int,int,int,int]]:
    data = ocr_data(pil)
    if not data: return None
    cand = []
    for i, t in enumerate(data["text"]):
        t = (t or "").strip()
        if REGEX_SN_ANC.fullmatch(t):
            x, y = data["left"][i], data["top"][i]
            w, h = data["width"][i], data["height"][i]
            cand.append((x, y, w, h))
    if not cand: return None
    x, y, w, h = sorted(cand, key=lambda r: r[2]*r[3], reverse=True)[0]
    W, H = pil.size
    ex, ey = int(W*0.45), int(H*0.20)
    return (max(0, x-10), max(0, y-ey//2), min(W, x+w+ex), min(H, y+h+ey))

# -------------------- códigos de barras --------------------
def read_barcodes_with_bbox(pil: Image.Image):
    out = []
    # Pyzbar
    if zbar_decode:
        try:
            for obj in zbar_decode(pil):
                val = obj.data.decode("utf-8", errors="ignore").strip()
                cx = obj.rect.left + obj.rect.width/2.0
                cy = obj.rect.top  + obj.rect.height/2.0
                out.append((val, (cx, cy)))
        except Exception:
            pass
    # ZXingCPP
    if zxingcpp:
        try:
            for r in zxingcpp.read_barcodes(pil):
                if r.text:
                    try:
                        pts = r.position
                        cx = sum(p.x for p in pts)/len(pts)
                        cy = sum(p.y for p in pts)/len(pts)
                        out.append((r.text.strip(), (cx, cy)))
                    except Exception:
                        out.append((r.text.strip(), None))
        except Exception:
            pass
    # dedup por valor
    seen, res = set(), []
    for v, c in out:
        if v not in seen:
            res.append((v, c)); seen.add(v)
    return res

def pick_sn_from_barcodes_near_roi(pil: Image.Image, roi: Tuple[int,int,int,int]) -> Optional[str]:
    x0,y0,x1,y1 = roi
    cx, cy = (x0+x1)/2.0, (y0+y1)/2.0
    cand = []
    for val, center in read_barcodes_with_bbox(pil):
        if REGEX_MAC.fullmatch(val):          # ignora MAC
            continue
        if not re.fullmatch(r"[A-Z0-9\-]{6,}", val, re.I):
            continue
        dist = (center[0]-cx)**2 + (center[1]-cy)**2 if center else 1e18
        cand.append((dist, val))
    if not cand: return None
    cand.sort(key=lambda x: x[0])
    return cand[0][1]

def detect_model(text_upper: str) -> Optional[str]:
    for name, rx in EQUIP_KEYWORDS.items():
        if rx.search(text_upper):
            return name
    return None

# -------------------- scanner principal --------------------
def _jpg_bytes(pil: Image.Image, quality=92) -> Optional[bytes]:
    try:
        b = BytesIO()
        pil.convert("RGB").save(b, format="JPEG", quality=quality)
        return b.getvalue()
    except Exception:
        return None

def _fingerprint_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def scan_one_image(pil: Image.Image, fonte: str) -> Dict:
    text = ocr_text(pil)
    up = (text or "").upper()
    modelo = detect_model(up)

    # 1) ROI perto do "S/N"
    roi = find_sn_anchor_bbox(pil)
    sn = None
    if roi:
        sn = pick_sn_from_barcodes_near_roi(pil, roi)
        if not sn:
            local_txt = ocr_text(pil.crop(roi))
            m = REGEX_SN_FROM_TEXT.search(local_txt or "")
            if m: sn = m.group(1).strip()

    # 2) Texto geral "S/N ..."
    if not sn:
        m = REGEX_SN_FROM_TEXT.search(text or "")
        if m: sn = m.group(1).strip()

    # 3) Fallback por tokens (evita MAC)
    if not sn:
        tokens = [t for t in re.findall(r"[A-Z0-9\-]{8,}", up) if not REGEX_MAC.fullmatch(t)]
        sn = next((t for t in tokens if is_valid_sn(modelo, t)), (tokens[0] if tokens else None))

    # MAC (apenas para exibir no grid; não prioriza)
    macs = REGEX_MAC.findall(text or "")
    mac = macs[0] if macs else ""

    # salvar foto apenas se houver S/N válido
    if is_valid_sn(modelo, sn):
        jpg = _jpg_bytes(pil, 92)
        if jpg:
            fp = _fingerprint_bytes(jpg)
            if fp not in ss.seen_hashes:
                ss.photos_to_append.append(jpg)
                ss.seen_hashes.add(fp)

    return {"modelo": (modelo or ""), "sn": (sn or ""), "mac": (mac or ""), "fonte": fonte}

def add_scanned_item(item: Dict):
    k = (item.get("modelo",""), item.get("sn",""), item.get("mac",""))
    current = {(e.get("modelo",""), e.get("sn",""), e.get("mac","")) for e in ss.scanned_items}
    if k not in current:
        ss.scanned_items.append(item)

def push_to_textarea_from_items():
    linhas, seen = [], set()
    for it in ss.scanned_items:
        sn = (it.get("sn") or "").strip()
        if not sn: continue
        model = (it.get("modelo") or "").strip()
        line = f"{model}  S/N {sn}" if model else f"{sn}"
        if line not in seen:
            linhas.append(line); seen.add(line)
    # merge com o que já tem
    exist = [ln.strip() for ln in (ss.seriais_texto or "").splitlines() if ln.strip()]
    all_lines, seen2 = [], set()
    for ln in exist + linhas:
        if ln not in seen2:
            all_lines.append(ln); seen2.add(ln)
    ss.seriais_texto = "\n".join(all_lines)

# -------------------- PDF helpers --------------------
def search_once(page, texts):
    if isinstance(texts, str): texts = [texts]
    for t in texts:
        rects = page.search_for(t)
        if rects: return rects[0]
    return None
def search_all(page, text): return page.search_for(text)

def insert_right_of(page, labels, content, dx=0, dy=0, fontsize=10):
    if not content: return
    r = search_once(page, labels)
    if not r: return
    x = r.x1 + dx; y = r.y0 + r.height/1.5 + dy
    page.insert_text((x, y), str(content), fontsize=fontsize)

def insert_signature(page, label, png_bytes: Optional[bytes], rel_rect):
    if not png_bytes: return
    r = search_once(page, label)
    if not r: return
    rect = fitz.Rect(r.x0 + rel_rect[0], r.y1 + rel_rect[1], r.x0 + rel_rect[2], r.y1 + rel_rect[3])
    page.insert_image(rect, stream=png_bytes)  # PNG mantém alpha (ou branco)

def descricao_block(seriais: str, atividade: str, info: str) -> str:
    partes = []
    if seriais and seriais.strip():
        linhas = [ln.strip() for ln in seriais.splitlines() if ln.strip()]
        partes.append("SERIAIS:\n" + "\n".join(f"- {ln}" for ln in linhas))
    if atividade and atividade.strip(): partes.append("ATIVIDADE:\n" + atividade.strip())
    if info and info.strip(): partes.append("INFORMAÇÕES ADICIONAIS:\n" + info.strip())
    return "\n\n".join(partes) if partes else ""

def insert_descricao_autofit(page, label, text):
    if not text: return
    r = search_once(page, label)
    if not r: return
    n = len(text.splitlines())
    if n <= 15: fontsize, height = 10, 240
    elif n <= 22: fontsize, height = 9, 300
    elif n <= 30: fontsize, height = 8, 360
    else: fontsize, height = 7, 420
    rect = fitz.Rect(r.x0, r.y1 + 20, r.x0 + 540, r.y1 + 20 + height)
    page.insert_textbox(rect, text, fontsize=fontsize, align=0)

# ==========================
#          ABAS
# ==========================
tab1, tab2, tab3 = st.tabs(["🧪 Scanner", "✍️ Assinaturas", "🧾 Dados & PDF"])

# -------- Aba 1: Scanner --------
with tab1:
    st.subheader("Scanner de etiquetas (S/N)")
    with st.form("scanner_form"):
        cam = st.camera_input("📸 Tirar foto (abre câmera)", key="cam_in")
        imgs = st.file_uploader("📎 Enviar foto(s) de etiquetas", type=["jpg","jpeg","png","webp"],
                                accept_multiple_files=True, key="imgs_in")
        pdf  = st.file_uploader("📎 Enviar RAT (PDF) para extrair fotos de etiquetas", type=["pdf"], key="pdf_in")

        cbtn1, cbtn2, cbtn3, cbtn4 = st.columns([1,1,1,2])
        with cbtn1: btn_cam  = st.form_submit_button("➕ Ler CÂMERA")
        with cbtn2: btn_imgs = st.form_submit_button("➕ Ler FOTOS")
        with cbtn3: btn_pdf  = st.form_submit_button("➕ Ler PDF")
        with cbtn4: btn_push = st.form_submit_button("🡓 Jogar S/N no campo de seriais")

    if btn_cam and ss.get("cam_in") is not None:
        try:
            pil = Image.open(ss.cam_in).convert("RGB")
            add_scanned_item(scan_one_image(pil, "camera"))
            st.success("Foto da CÂMERA lida.")
        except Exception as e:
            st.warning(f"Não consegui ler a foto da câmera: {e}")

    if btn_imgs and ss.get("imgs_in"):
        for f in ss.imgs_in:
            try:
                raw = f.getvalue()
                fp = _fingerprint_bytes(raw)
                if fp in ss.seen_hashes:
                    continue
                pil = Image.open(BytesIO(raw)).convert("RGB")
                add_scanned_item(scan_one_image(pil, f.name))
                ss.seen_hashes.add(fp)
            except Exception as e:
                st.warning(f"Não consegui ler uma foto: {e}")
        st.success("FOTOS lidas.")

    if btn_pdf and ss.get("pdf_in") is not None:
        try:
            doc = fitz.open(stream=ss.pdf_in.read(), filetype="pdf")
            for pno, page in enumerate(doc):
                for idx, info in enumerate(page.get_images(full=True)):
                    base = doc.extract_image(info[0])
                    raw = base["image"]
                    fp = _fingerprint_bytes(raw)
                    if fp in ss.seen_hashes:
                        continue
                    pil = Image.open(BytesIO(raw)).convert("RGB")
                    add_scanned_item(scan_one_image(pil, f"pdf:p{pno}_img{idx}"))
                    ss.seen_hashes.add(fp)
            st.success("PDF lido.")
        except Exception as e:
            st.warning(f"Falha ao analisar PDF: {e}")

    if btn_push:
        push_to_textarea_from_items()
        st.success("Seriais enviados para o campo.")

    st.subheader("Itens scaneados (edite se necessário)")
    if ss.scanned_items:
        edited = st.data_editor(
            ss.scanned_items,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_scans",
            column_config={
                "modelo": st.column_config.TextColumn("Modelo", width="medium"),
                "sn":     st.column_config.TextColumn("S/N", width="large"),
                "mac":    st.column_config.TextColumn("MAC", width="large"),
                "fonte":  st.column_config.TextColumn("Fonte", disabled=True),
            },
        )
        ss.scanned_items = edited

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🧹 Limpar ITENS (scanner)"):
            ss.scanned_items = []
            st.info("Itens limpos.")
    with c2:
        if st.button("🧹 Limpar FOTOS anexas"):
            ss.photos_to_append = []
            ss.seen_hashes = set()
            st.info("Fotos limpas.")

# -------- Aba 2: Assinaturas --------
with tab2:
    st.checkbox("Salvar assinatura com fundo transparente (recomendado)", key="assinatura_transparente",
                value=ss.assinatura_transparente)
    st.caption("Se o visualizador de PDF escurecer o fundo, desmarque para salvar com fundo branco chapado.")

    st.write("Assinatura do TÉCNICO")
    tec_canvas = st_canvas(
        fill_color="rgba(0,0,0,0)", stroke_width=3, stroke_color="#000000",
        background_color="rgba(0,0,0,0)", width=800, height=180,
        drawing_mode="freedraw", key="sig_tec_canvas", update_streamlit=True, display_toolbar=True,
    )
    if st.button("💾 Salvar assinatura do TÉCNICO"):
        arr = getattr(tec_canvas, "image_data", None)
        img = signature_rgba_from_canvas(arr, transparente=ss.assinatura_transparente) if arr is not None else None
        ss.sig_tec_png = to_png_bytes(img, transparente=ss.assinatura_transparente)
        st.success("Assinatura do técnico salva." if ss.sig_tec_png else "Nada para salvar (assine no quadro).")

    st.write("---")
    st.write("Assinatura do CLIENTE")
    cli_canvas = st_canvas(
        fill_color="rgba(0,0,0,0)", stroke_width=3, stroke_color="#000000",
        background_color="rgba(0,0,0,0)", width=800, height=180,
        drawing_mode="freedraw", key="sig_cli_canvas", update_streamlit=True, display_toolbar=True,
    )
    if st.button("💾 Salvar assinatura do CLIENTE"):
        arr = getattr(cli_canvas, "image_data", None)
        img = signature_rgba_from_canvas(arr, transparente=ss.assinatura_transparente) if arr is not None else None
        ss.sig_cli_png = to_png_bytes(img, transparente=ss.assinatura_transparente)
        st.success("Assinatura do cliente salva." if ss.sig_cli_png else "Nada para salvar (assine no quadro).")

    if st.button("🧹 Limpar assinaturas salvas"):
        ss.sig_tec_png = None
        ss.sig_cli_png = None
        st.info("Assinaturas salvas removidas.")

# -------- Aba 3: Dados & PDF --------
with tab3:
    st.subheader("1) Chamado e Agenda")
    c1, c2 = st.columns(2)
    with c1:
        st.date_input("Data do atendimento", value=ss.data_atend, key="data_atend")
        st.time_input("Hora início", value=ss.hora_ini, key="hora_ini")
        st.text_input("Nº do chamado", value=ss.num_chamado, key="num_chamado")
        st.text_input("Nome do técnico", value=ss.tec_nome, key="tec_nome")
        st.text_input("RG/Documento do técnico", value=ss.tec_rg, key="tec_rg")
    with c2:
        st.time_input("Hora término", value=ss.hora_fim, key="hora_fim")
        st.text_input("Distância (KM)", value=ss.distancia_km, key="distancia_km")
        st.text_input("Cliente / Razão Social", value=ss.cliente_nome, key="cliente_nome")
        st.text_input("Telefone (contato)", value=ss.contato_tel, key="contato_tel")

    st.text_input("Endereço", value=ss.endereco, key="endereco")
    st.text_input("Bairro", value=ss.bairro, key="bairro")
    st.text_input("Cidade", value=ss.cidade, key="cidade")
    st.text_input("Contato (nome)", value=ss.contato_nome, key="contato_nome")
    st.text_input("Contato (RG/Doc)", value=ss.contato_rg, key="contato_rg")

    st.subheader("2) Seriais")
    ss.seriais_texto = st.text_area(
        "Seriais (um por linha) — use a aba Scanner e clique “Jogar S/N” para preencher aqui",
        value=ss.seriais_texto, height=200, key="seriais_texto_area"
    )

    st.subheader("3) Descrição de Atendimento")
    st.text_area("Atividade (texto do técnico)", height=80, key="atividade_txt", value=ss.atividade_txt)
    st.text_area("Informações adicionais (opcional)", height=60, key="info_txt", value=ss.info_txt)

    st.checkbox("Anexar fotos com S/N ao PDF", key="anexar_fotos", value=ss.anexar_fotos)

    if st.button("🧾 Gerar PDF preenchido"):
        try:
            base = load_pdf_bytes(PDF_BASE_PATH)
        except FileNotFoundError:
            st.error(f"Arquivo '{PDF_BASE_PATH}' não encontrado.")
            st.stop()

        try:
            doc = fitz.open(stream=base, filetype="pdf")
            page = doc[0]

            insert_right_of(page, ["Cliente:", "CLIENTE:"], ss.get("cliente_nome",""), 6, 1)
            insert_right_of(page, ["Endereço:", "ENDEREÇO:"], ss.get("endereco",""), 6, 1)
            insert_right_of(page, ["Bairro:", "BAIRRO:"],     ss.get("bairro",""), 6, 1)
            insert_right_of(page, ["Cidade:", "CIDADE:"],     ss.get("cidade",""), 6, 1)
            insert_right_of(page, ["Contato:"],               ss.get("contato_nome",""), 6, 1)

            r_cont = search_once(page, ["Contato:"])
            if r_cont and ss.get("contato_rg",""):
                for rr in search_all(page, "RG:") or []:
                    pass
                x = r_cont.x1 + 40; y = r_cont.y0 + r_cont.height/1.5 + 6
                page.insert_text((x, y), str(ss["contato_rg"]), fontsize=10)

            insert_right_of(page, ["Telefone:", "TELEFONE:"], normalize_phone(ss.get("contato_tel","")), 6, 1)

            insert_right_of(page, ["Data do atendimento:", "Data do Atendimento:"],
                            ss["data_atend"].strftime("%d/%m/%Y"), -90, 10)
            insert_right_of(page, ["Hora Inicio:", "Hora Início:", "Hora inicio:"],
                            ss["hora_ini"].strftime("%H:%M"), 0, 3)
            insert_right_of(page, ["Hora Termino:", "Hora Término:", "Hora termino:"],
                            ss["hora_fim"].strftime("%H:%M"), 0, 3)
            insert_right_of(page, ["Distancia (KM) :", "Distância (KM) :"],
                            str(ss.get("distancia_km","")), 0, 3)

            bloco = descricao_block(
                ss.get("seriais_texto_area",""),
                ss.get("atividade_txt",""),
                ss.get("info_txt","")
            )
            insert_descricao_autofit(page, ["DESCRIÇÃO DE ATENDIMENTO","DESCRICAO DE ATENDIMENTO"], bloco)

            # assinaturas — usam os PNG salvos na aba Assinaturas
            insert_signature(page, ["ASSINATURA:", "Assinatura:"], ss.get("sig_tec_png"),
                             (110 - 2*CM, 0 - 1*CM, 330 - 2*CM, 54 - 1*CM))
            insert_signature(page, ["DATA CARIMBO / ASSINATURA", "ASSINATURA CLIENTE", "CLIENTE"],
                             ss.get("sig_cli_png"), (110, 12 - 3.5*CM, 430, 94 - 3.5*CM))

            insert_right_of(page, [" Nº CHAMADO ", "Nº CHAMADO", "No CHAMADO"], ss.get("num_chamado",""),
                            dx=-(2*CM), dy=10)

            # anexar fotos (se marcado)
            if ss.get("anexar_fotos", True) and ss.photos_to_append:
                for img_bytes in ss.photos_to_append:
                    p = doc.new_page()
                    pil = Image.open(BytesIO(img_bytes)).convert("RGB")
                    W,H = pil.size; w,h = p.rect.width, p.rect.height
                    margin = 36; max_w, max_h = w-2*margin, h-2*margin
                    scale = min(max_w/W, max_h/H); new_w, new_h = int(W*scale), int(H*scale)
                    x0 = (w-new_w)/2; y0 = (h-new_h)/2
                    rect = fitz.Rect(x0, y0, x0+new_w, y0+new_h)
                    b = BytesIO(); pil.save(b, format="JPEG", quality=92)
                    p.insert_image(rect, stream=b.getvalue())

            out = BytesIO(); doc.save(out); doc.close()
            st.success("PDF gerado!")
            st.download_button(
                "⬇️ Baixar RAT preenchido",
                data=out.getvalue(),
                file_name=f"RAT_MAM_preenchido_{(ss.get('num_chamado') or 'sem_num')}.pdf",
                mime="application/pdf"
            )
        except Exception as e:
            st.error(f"Falha ao gerar PDF: {e}")
            st.exception(e)
