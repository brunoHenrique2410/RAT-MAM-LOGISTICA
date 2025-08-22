# app.py — RAT MAM (câmera + scanner com âncora S/N + edição + fotos no PDF)
from io import BytesIO
from datetime import date, time
from typing import List, Dict, Optional, Tuple
import re

import streamlit as st
from PIL import Image, ImageOps, ImageFilter
import numpy as np
import fitz  # PyMuPDF
from streamlit_drawable_canvas import st_canvas

# ------- leitores opcionais -------
try:
    from pyzbar.pyzbar import decode as zbar_decode  # devolve bounding boxes
except Exception:
    zbar_decode = None
try:
    import zxingcpp  # rápido; sem bbox estável em todos formatos
except Exception:
    zxingcpp = None
try:
    import pytesseract  # OCR com bbox (image_to_data)
except Exception:
    pytesseract = None

PDF_BASE_PATH = "RAT MAM.pdf"
APP_TITLE = "RAT MAM – Assinatura + Scanner com Âncora S/N"
CM = 28.3465

st.set_page_config(page_title=APP_TITLE, layout="centered")
st.title("📄 " + APP_TITLE)
st.caption("Scanner prioriza o S/N (âncora), permite editar resultados e anexa fotos ao PDF.")

# --------- estado ---------
if "scanned_items" not in st.session_state:
    st.session_state.scanned_items: List[Dict] = []   # {modelo, sn, mac, fonte}
if "photos_to_append" not in st.session_state:
    st.session_state.photos_to_append: List[bytes] = []
if "seriais_texto" not in st.session_state:
    st.session_state.seriais_texto = ""

# --------- utilidades ---------
REGEX_SN_ANC = re.compile(r'\bS/?N\b[:\-]?', re.I)
REGEX_SN_FROM_TEXT = re.compile(r'\bS/?N[:\s\-]*([A-Z0-9\-]{6,})', re.I)
REGEX_MAC = re.compile(r'(?:[0-9A-F]{2}[:-]){5}[0-9A-F]{2}', re.I)

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
    "ER605":             re.compile(r"^[0-9A-Z\-]{10,16}$", re.I),
    "ER7206":            re.compile(r"^[0-9A-Z\-]{10,16}$", re.I),
    "OC200":             re.compile(r"^[0-9A-Z]{12,14}$", re.I),
    "EAP610":            re.compile(r"^[0-9A-Z]{12,16}$", re.I),
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
    d = "".join(ch for ch in s if ch.isdigit())
    if len(d) == 11: return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10: return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return s

def np_to_rgba_pil(arr) -> Optional[Image.Image]:
    if arr is None or not isinstance(arr, np.ndarray) or arr.ndim != 3 or arr.shape[2] < 4: return None
    if np.max(arr[:, :, 3]) == 0: return None
    return Image.fromarray(arr.astype("uint8"), mode="RGBA")

def remove_white_to_transparent(img: Image.Image, thresh=245) -> Image.Image:
    arr = np.array(img.convert("RGBA"))
    rgb = arr[:, :, :3]
    mask_white = (rgb[:, :, 0] >= thresh) & (rgb[:, :, 1] >= thresh) & (rgb[:, :, 2] >= thresh)
    arr[mask_white, 3] = 0
    return Image.fromarray(arr, mode="RGBA")

@st.cache_data
def load_pdf_bytes(path: str) -> bytes:
    with open(path, "rb") as f: return f.read()

# ---------- OCR helpers ----------
def ocr_text(pil: Image.Image) -> str:
    if pytesseract is None: return ""
    img = ImageOps.grayscale(pil).filter(ImageFilter.SHARPEN)
    img = img.point(lambda x: 255 if x > 165 else 0, mode="1").convert("L")
    return pytesseract.image_to_string(
        img, lang="eng",
        config="--psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-/:"
    )

def ocr_data(pil: Image.Image):
    """Retorna dataframe-like list do image_to_data para bounding boxes por palavra."""
    if pytesseract is None: return None
    img = ImageOps.grayscale(pil)
    try:
        raw = pytesseract.image_to_data(img, lang="eng", output_type=pytesseract.Output.DICT)
        return raw
    except Exception:
        return None

def find_sn_anchor_bbox(pil: Image.Image) -> Optional[Tuple[int,int,int,int]]:
    """Procura 'S/N' e devolve um retângulo expandido ao redor para leitura dirigida."""
    data = ocr_data(pil)
    if not data: return None
    n = len(data["text"])
    cand = []
    for i in range(n):
        t = (data["text"][i] or "").strip()
        if REGEX_SN_ANC.fullmatch(t):
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            cand.append((x, y, w, h))
    if not cand: return None
    # pega o maior (ou o primeiro) e expande retângulo para a direita
    x, y, w, h = sorted(cand, key=lambda r: r[2]*r[3], reverse=True)[0]
    W, H = pil.size
    expand_x = int(W*0.45)  # varre boa faixa à direita
    expand_y = int(H*0.20)  # e um pouco vertical
    x0 = max(0, x - 10)
    y0 = max(0, y - expand_y//2)
    x1 = min(W, x + w + expand_x)
    y1 = min(H, y + h + expand_y)
    return (x0, y0, x1, y1)

# ---------- leitura de códigos ----------
def read_barcodes_with_bbox(pil: Image.Image):
    """Retorna lista de (valor, (cx,cy)) se possível."""
    out = []
    if zbar_decode:
        try:
            for obj in zbar_decode(pil):
                v = obj.data.decode("utf-8", errors="ignore").strip()
                x, y, w, h = obj.rect.left, obj.rect.top, obj.rect.width, obj.rect.height
                out.append((v, (x + w/2.0, y + h/2.0)))
        except Exception:
            pass
    # zxingcpp pode não trazer bbox estável – se trouxer, ótimo
    if zxingcpp:
        try:
            for r in zxingcpp.read_barcodes(pil):
                if r.text:
                    # tenta centro geométrico dos pontos, se existir
                    try:
                        pts = r.position  # list[Point]
                        cx = sum(p.x for p in pts)/len(pts); cy = sum(p.y for p in pts)/len(pts)
                        out.append((r.text.strip(), (cx, cy)))
                    except Exception:
                        out.append((r.text.strip(), None))
        except Exception:
            pass
    # dedup
    seen, res = set(), []
    for v, c in out:
        if v not in seen:
            res.append((v, c)); seen.add(v)
    return res

def pick_sn_from_barcodes_near_roi(pil: Image.Image, roi: Tuple[int,int,int,int]) -> Optional[str]:
    """Escolhe o barcode mais próximo do centro do ROI (âncora S/N) e valida como serial."""
    x0,y0,x1,y1 = roi
    cx_roi, cy_roi = (x0+x1)/2.0, (y0+y1)/2.0
    candidates = []
    for val, center in read_barcodes_with_bbox(pil):
        if REGEX_MAC.fullmatch(val):  # nunca usar MAC
            continue
        if not re.fullmatch(r"[A-Z0-9\-]{6,}", val, re.I):
            continue
        # distância ao ROI (se não tiver centro, dá prioridade menor)
        if center:
            dist = (center[0]-cx_roi)**2 + (center[1]-cy_roi)**2
        else:
            dist = 1e18
        candidates.append((dist, val))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    # devolve o mais próximo
    return candidates[0][1]

def detect_model(text_upper: str) -> Optional[str]:
    for name, rx in EQUIP_KEYWORDS.items():
        if rx.search(text_upper):
            return name
    return None

# ---------- scanner principal ----------
def scan_one_image(pil: Image.Image, fonte: str) -> Dict:
    """Retorna {modelo, sn, mac} (sn pode ser None), e salva foto se sn válido."""
    text = ocr_text(pil)
    up = (text or "").upper()
    modelo = detect_model(up)

    # 1) tentar ROI ao redor do "S/N"
    roi = find_sn_anchor_bbox(pil)
    sn = None
    if roi:
        crop = pil.crop(roi)
        # tenta barcode dentro/ao redor
        sn = pick_sn_from_barcodes_near_roi(pil, roi)
        if not sn:
            # OCR direto no recorte
            local_txt = ocr_text(crop)
            m = REGEX_SN_FROM_TEXT.search(local_txt or "")
            if m: sn = m.group(1).strip()

    # 2) se ainda não, tenta pegar por OCR global "S/N: XXXXX"
    if not sn:
        m = REGEX_SN_FROM_TEXT.search(text or "")
        if m: sn = m.group(1).strip()

    # 3) como último recurso, tokens longos (sem padrão de MAC)
    if not sn:
        tokens = [t for t in re.findall(r"[A-Z0-9\-]{8,}", up) if not REGEX_MAC.fullmatch(t)]
        sn = next((t for t in tokens if is_valid_sn(modelo, t)), (tokens[0] if tokens else None))

    # MAC (apenas metadado)
    macs = REGEX_MAC.findall(text or "")
    mac = macs[0] if macs else None

    # guarda foto se SN passou na regex
    if is_valid_sn(modelo, sn):
        buf = BytesIO(); pil.save(buf, format="PNG")
        st.session_state.photos_to_append.append(buf.getvalue())

    return {"modelo": (modelo or ""), "sn": (sn or ""), "mac": (mac or ""), "fonte": fonte}

def add_scanned_item(item: Dict):
    # permitir editar depois -> não deduplico por vazio
    k = (item.get("modelo",""), item.get("sn",""), item.get("mac",""))
    keyset = {(e.get("modelo",""), e.get("sn",""), e.get("mac","")) for e in st.session_state.scanned_items}
    if k not in keyset:
        st.session_state.scanned_items.append(item)

def push_to_textarea_from_items():
    linhas, seen = [], set()
    # apenas linhas com SN preenchido
    for it in st.session_state.scanned_items:
        sn = (it.get("sn") or "").strip()
        if not sn: continue
        model = (it.get("modelo") or "").strip()
        line = f"{model}  S/N {sn}" if model else f"{sn}"
        if line not in seen:
            linhas.append(line); seen.add(line)
    # preserva o que já estava
    exist = [ln.strip() for ln in (st.session_state.seriais_texto or "").splitlines() if ln.strip()]
    all_lines = []
    seen2 = set()
    for ln in exist + linhas:
        if ln not in seen2:
            all_lines.append(ln); seen2.add(ln)
    st.session_state.seriais_texto = "\n".join(all_lines)

# ---------- UI principal ----------
with st.form("topo"):
    c1, c2 = st.columns(2)
    with c1:
        num_chamado = st.text_input("Nº do chamado")
        data_atend = st.date_input("Data do atendimento", value=date.today())
        hora_ini = st.time_input("Hora início", value=time(8,0))
    with c2:
        hora_fim = st.time_input("Hora término", value=time(10,0))
        distancia_km = st.text_input("Distância (KM)")

    st.subheader("Cliente")
    cliente_nome = st.text_input("Cliente / Razão Social")
    endereco = st.text_input("Endereço")
    bairro = st.text_input("Bairro")
    cidade = st.text_input("Cidade")
    contato_nome = st.text_input("Contato (nome)")
    contato_rg = st.text_input("Contato (RG/Doc)")
    contato_tel = st.text_input("Telefone (contato)")

    st.subheader("Scanner de etiquetas (S/N)")
    cam = st.camera_input("📸 Tirar foto (abre câmera)")
    if cam:
        pil = Image.open(cam).convert("RGB")
        item = scan_one_image(pil, "camera")
        add_scanned_item(item)
        st.success(f"Detectado: {item}")

    imgs = st.file_uploader("📎 Enviar foto(s) de etiquetas", type=["jpg","jpeg","png","webp"], accept_multiple_files=True)
    if imgs:
        for f in imgs:
            pil = Image.open(f).convert("RGB")
            item = scan_one_image(pil, f.name)
            add_scanned_item(item)

    pdf = st.file_uploader("📎 Enviar RAT (PDF) para extrair fotos de etiquetas", type=["pdf"])
    if pdf:
        doc = fitz.open(stream=pdf.read(), filetype="pdf")
        for pno, page in enumerate(doc):
            for idx, info in enumerate(page.get_images(full=True)):
                base = doc.extract_image(info[0])
                pil = Image.open(BytesIO(base["image"])).convert("RGB")
                item = scan_one_image(pil, f"pdf:p{pno}_img{idx}")
                add_scanned_item(item)
        st.success("PDF analisado.")

    st.write("—")
    add_btn = st.form_submit_button("➕ Jogar os S/N para o campo de seriais")

# tabela EDITÁVEL dos itens
st.subheader("Itens scaneados (edite se necessário)")
if st.session_state.scanned_items:
    # usa st.data_editor para permitir edição
    edited = st.data_editor(
        st.session_state.scanned_items,
        num_rows="dynamic",
        use_container_width=True,
        key="editor_scans",
        column_config={
            "modelo": st.column_config.TextColumn("Modelo", width="medium"),
            "sn": st.column_config.TextColumn("S/N", width="large"),
            "mac": st.column_config.TextColumn("MAC", width="large"),
            "fonte": st.column_config.TextColumn("Fonte", disabled=True),
        },
    )
    # aplicar edições
    st.session_state.scanned_items = edited

    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        if st.button("🧹 Limpar ITENS (scanner)"):
            st.session_state.scanned_items = []
            st.info("Itens limpos.")
    with cc2:
        if st.button("🧹 Limpar FOTOS anexas"):
            st.session_state.photos_to_append = []
            st.info("Fotos limpas.")
    with cc3:
        anexar_fotos = st.checkbox("Anexar fotos com S/N ao PDF", value=True)

# pré‑visualização das fotos
if st.session_state.photos_to_append:
    st.write("**Pré‑visualização das fotos que irão para o PDF:**")
    cols = st.columns(3)
    for i, b in enumerate(st.session_state.photos_to_append):
        with cols[i % 3]:
            st.image(b, caption=f"Foto {i+1}", use_container_width=True)

# campo de seriais
if add_btn:
    push_to_textarea_from_items()
seriais_text = st.text_area(
    "Seriais (um por linha) — você pode editar livremente",
    value=st.session_state.seriais_texto,
    height=200,
    key="seriais_texto_area"
)

# assinaturas e técnico
st.subheader("Técnico e Assinaturas")
tec_nome = st.text_input("Nome do técnico")
tec_rg = st.text_input("RG/Documento do técnico")

st.write("Assinatura do TÉCNICO")
tec_canvas = st_canvas(
    fill_color="rgba(0,0,0,0)", stroke_width=3, stroke_color="#000000",
    background_color="#FFFFFF", width=800, height=180,
    drawing_mode="freedraw", key="sig_tec", update_streamlit=True, display_toolbar=True,
)

st.write("—")
st.write("Assinatura do CLIENTE")
cli_canvas = st_canvas(
    fill_color="rgba(0,0,0,0)", stroke_width=3, stroke_color="#000000",
    background_color="#FFFFFF", width=800, height=180,
    drawing_mode="freedraw", key="sig_cli", update_streamlit=True, display_toolbar=True,
)

# descrição livre
st.subheader("Descrição de Atendimento")
atividade_txt = st.text_area("Atividade (texto do técnico)", height=80, key="atividade_txt")
info_txt = st.text_area("Informações adicionais (opcional)", height=60, key="info_txt")

# ---------- helpers PDF ----------
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

def insert_signature(page, label, img_rgba: Image.Image, rel_rect):
    if img_rgba is None: return
    r = search_once(page, label)
    if not r: return
    rect = fitz.Rect(r.x0 + rel_rect[0], r.y1 + rel_rect[1], r.x0 + rel_rect[2], r.y1 + rel_rect[3])
    img_clean = remove_white_to_transparent(img_rgba, 245)
    buf = BytesIO(); img_clean.save(buf, format="PNG")
    page.insert_image(rect, stream=buf.getvalue())

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

# ---------- gerar PDF ----------
if st.button("🧾 Gerar PDF preenchido"):
    base = None
    try:
        base = load_pdf_bytes(PDF_BASE_PATH)
    except FileNotFoundError:
        st.error(f"Arquivo '{PDF_BASE_PATH}' não encontrado.")
        st.stop()
    try:
        doc = fitz.open(stream=base, filetype="pdf")
        page = doc[0]
        insert_right_of(page, ["Cliente:", "CLIENTE:"], cliente_nome, 6, 1)
        insert_right_of(page, ["Endereço:", "ENDEREÇO:"], endereco, 6, 1)
        insert_right_of(page, ["Bairro:", "BAIRRO:"], bairro, 6, 1)
        insert_right_of(page, ["Cidade:", "CIDADE:"], cidade, 6, 1)
        insert_right_of(page, ["Contato:"], contato_nome, 6, 1)

        r_cont = search_once(page, ["Contato:"])
        if r_cont and contato_rg:
            rg_rects = search_all(page, "RG:")
            if rg_rects:
                cy = r_cont.y0 + r_cont.height/2
                rg_best = min(rg_rects, key=lambda rr: abs((rr.y0+rr.height/2)-cy))
                x = rg_best.x1 + 6; y = rg_best.y0 + rg_best.height/1.5 + 6
                page.insert_text((x, y), str(contato_rg), fontsize=10)

        insert_right_of(page, ["Telefone:", "TELEFONE:"], normalize_phone(contato_tel), 6, 1)
        insert_right_of(page, ["Data do atendimento:", "Data do Atendimento:"], data_atend.strftime("%d/%m/%Y"), -90, 10)
        insert_right_of(page, ["Hora Inicio:", "Hora Início:", "Hora inicio:"], hora_ini.strftime("%H:%M"), 0, 3)
        insert_right_of(page, ["Hora Termino:", "Hora Término:", "Hora termino:"], hora_fim.strftime("%H:%M"), 0, 3)
        insert_right_of(page, ["Distancia (KM) :", "Distância (KM) :"], str(distancia_km), 0, 3)

        # descrição
        st.session_state.seriais_texto = st.session_state.get("seriais_texto_area", st.session_state.seriais_texto)
        bloco = descricao_block(st.session_state.seriais_texto, st.session_state.get("atividade_txt",""), st.session_state.get("info_txt",""))
        insert_descricao_autofit(page, ["DESCRIÇÃO DE ATENDIMENTO","DESCRICAO DE ATENDIMENTO"], bloco)

        # assinaturas
        sigtec = np_to_rgba_pil(tec_canvas.image_data if tec_canvas else None)
        sigcli = np_to_rgba_pil(cli_canvas.image_data if cli_canvas else None)
        insert_signature(page, ["ASSINATURA:", "Assinatura:"], sigtec, (110 - 2*CM, 0 - 1*CM, 330 - 2*CM, 54 - 1*CM))
        insert_signature(page, ["DATA CARIMBO / ASSINATURA", "ASSINATURA CLIENTE", "CLIENTE"], sigcli, (110, 12 - 3.5*CM, 430, 94 - 3.5*CM))

        insert_right_of(page, [" Nº CHAMADO ", "Nº CHAMADO", "No CHAMADO"], num_chamado, dx=-(2*CM), dy=10)

        # fotos no final (apenas com S/N válido já salvas)
        if st.session_state.photos_to_append:
            for img_bytes in st.session_state.photos_to_append:
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
        st.download_button("⬇️ Baixar RAT preenchido", data=out.getvalue(),
                           file_name=f"RAT_MAM_preenchido_{(num_chamado or 'sem_num')}.pdf",
                           mime="application/pdf")
    except Exception as e:
        st.error(f"Falha ao gerar PDF: {e}")
        st.exception(e)
