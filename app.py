# app.py — RAT MAM (página única, ordem solicitada)
# 1) Dados do RAT
# 2) Seriais & Descrição (com Scanner)
# 3) Assinaturas (SEM fundo preto: JPEG com fundo branco)
#
# Requisitos:
#   streamlit
#   pillow
#   pytesseract  + binário tesseract-ocr no sistema
#   PyMuPDF (fitz)
#   streamlit-drawable-canvas
#   (opcionais p/ códigos de barras) pyzbar, zxing-cpp

from io import BytesIO
from datetime import date, time
from typing import Optional, Tuple, Dict
import os, re, hashlib

import streamlit as st
from PIL import Image, ImageOps, ImageFilter
import numpy as np
import fitz  # PyMuPDF

# --- dependências obrigatórias/opcionais ---
try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    from streamlit_drawable_canvas import st_canvas
    CANVAS_AVAILABLE = True
except Exception:
    CANVAS_AVAILABLE = False

# leitores de código de barras (opcionais)
try:
    from pyzbar.pyzbar import decode as zbar_decode
except Exception:
    zbar_decode = None

try:
    import zxingcpp
except Exception:
    zxingcpp = None

# --- config ---
PDF_BASE_PATH = "RAT MAM.pdf"
APP_TITLE = "RAT MAM – Fechamento (Dados • Seriais • Assinaturas)"
CM = 28.3465  # pontos por cm

st.set_page_config(page_title=APP_TITLE, layout="centered")
st.title("📄 " + APP_TITLE)
st.caption("Ordem: 1) Dados  2) Seriais & Descrição (com Scanner)  3) Assinaturas. Assinatura no PDF com FUNDO BRANCO (JPEG).")

# --- checagens ---
def ensure_tesseract():
    if pytesseract is None:
        st.error("Instale `pytesseract` no requirements.")
        st.stop()
    if os.environ.get("TESSERACT_CMD"):
        pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]
    try:
        _ = pytesseract.get_tesseract_version()
    except Exception:
        st.error(
            "Tesseract não encontrado.\n"
            "Ubuntu/Debian: sudo apt-get update && sudo apt-get install -y tesseract-ocr\n"
            "Windows: instale o Tesseract (UB Mannheim) e defina TESSERACT_CMD se necessário."
        )
        st.stop()

ensure_tesseract()
if not CANVAS_AVAILABLE:
    st.error("Instale `streamlit-drawable-canvas` no requirements.")
    st.stop()

# --- estado ---
ss = st.session_state
def _def(k, v):
    if k not in ss: ss[k] = v

# dados
_def("data_atend", date.today())
_def("hora_ini", time(8, 0))
_def("hora_fim", time(10, 0))
_def("num_chamado", "")
_def("distancia_km", "")
_def("cliente_nome", ""); _def("endereco", ""); _def("bairro", ""); _def("cidade", "")
_def("contato_nome", ""); _def("contato_rg", ""); _def("contato_tel", "")
_def("tec_nome", ""); _def("tec_rg", "")
_def("atividade_txt", ""); _def("info_txt", "")
_def("seriais_texto", "")

# scanner / fotos
_def("scanned_items", [])       # [{modelo,sn,mac,fonte}]
_def("photos_to_append", [])    # [jpg bytes]
_def("seen_hashes", set())
_def("anexar_fotos", True)

# assinaturas (JPEG com fundo branco)
_def("sig_tec_jpg", None)       # bytes JPEG (RGB branco)
_def("sig_cli_jpg", None)       # bytes JPEG (RGB branco)

# --- regex/util ---
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
    "ER605": re.compile(r"^[0-9A-Z\-]{10,16}$", re.I),
    "ER7206": re.compile(r"^[0-9A-Z\-]{10,16}$", re.I),
    "OC200": re.compile(r"^[0-9A-Z]{12,14}$", re.I),
    "EAP610": re.compile(r"^[0-9A-Z]{12,16}$", re.I),
    "SG3428MP": re.compile(r"^[0-9]{12,14}$"),
    "SG2210MP-8P": re.compile(r"^[0-9]{12,14}$"),
    "NHS COMPACT PLUS": re.compile(r"^[0-9]{4,10}$"),
}
FALLBACK_SN = re.compile(r"^[0-9A-Z\-]{6,}$", re.I)

def is_valid_sn(modelo: Optional[str], sn: Optional[str]) -> bool:
    if not sn: return False
    if modelo in SERIAL_REGEX and SERIAL_REGEX[modelo].match(sn): return True
    return bool(FALLBACK_SN.match(sn))

def normalize_phone(s: str) -> str:
    d = "".join(ch for ch in (s or "") if ch.isdigit())
    if len(d)==11: return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d)==10: return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return s or ""

@st.cache_data
def load_pdf_bytes(path: str) -> bytes:
    with open(path, "rb") as f: return f.read()

# --- assinatura: canvas -> JPEG RGB (fundo branco) ---
def signature_from_canvas_as_jpeg(arr: np.ndarray, jpeg_quality: int = 92) -> Optional[bytes]:
    """
    Converte o canvas RGBA em imagem RGB com FUNDO BRANCO (sem alpha) e exporta como JPEG.
    Isso elimina de vez o “fundo preto” em qualquer viewer de PDF.
    """
    if arr is None or arr.ndim != 3 or arr.shape[2] < 4:
        return None
    rgba = arr.astype("uint8")
    mask = (rgba[:, :, 3] > 0)  # onde foi desenhado

    # Fundo branco RGB
    out = np.full((rgba.shape[0], rgba.shape[1], 3), 255, dtype=np.uint8)
    out[mask] = [0, 0, 0]  # traço preto

    img = Image.fromarray(out, "RGB")
    b = BytesIO()
    img.save(b, format="JPEG", quality=jpeg_quality)
    return b.getvalue()

# --- OCR helpers ---
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
    cand=[]
    for i,t in enumerate(data["text"]):
        t=(t or "").strip()
        if REGEX_SN_ANC.fullmatch(t):
            x,y = data["left"][i], data["top"][i]
            w,h = data["width"][i], data["height"][i]
            cand.append((x,y,w,h))
    if not cand: return None
    x,y,w,h = sorted(cand, key=lambda r:r[2]*r[3], reverse=True)[0]
    W,H = pil.size
    ex,ey = int(W*0.45), int(H*0.20)
    return (max(0,x-10), max(0,y-ey//2), min(W,x+w+ex), min(H,y+h+ey))

# --- códigos de barras (opcional) ---
def read_barcodes_with_bbox(pil: Image.Image):
    out=[]
    if zbar_decode:
        try:
            for obj in zbar_decode(pil):
                val = obj.data.decode("utf-8", errors="ignore").strip()
                cx = obj.rect.left + obj.rect.width/2
                cy = obj.rect.top  + obj.rect.height/2
                out.append((val,(cx,cy)))
        except Exception: pass
    if zxingcpp:
        try:
            for r in zxingcpp.read_barcodes(pil):
                if r.text:
                    try:
                        pts=r.position; cx=sum(p.x for p in pts)/len(pts); cy=sum(p.y for p in pts)/len(pts)
                        out.append((r.text.strip(),(cx,cy)))
                    except Exception:
                        out.append((r.text.strip(),None))
        except Exception: pass
    # dedup por valor
    seen=set(); res=[]
    for v,c in out:
        if v not in seen: res.append((v,c)); seen.add(v)
    return res

def pick_sn_from_barcodes_near_roi(pil: Image.Image, roi) -> Optional[str]:
    x0,y0,x1,y1 = roi
    cx,cy=(x0+x1)/2,(y0+y1)/2
    cand=[]
    for val,center in read_barcodes_with_bbox(pil):
        if REGEX_MAC.fullmatch(val): continue
        if not re.fullmatch(r"[A-Z0-9\-]{6,}", val, re.I): continue
        dist = (center[0]-cx)**2 + (center[1]-cy)**2 if center else 1e18
        cand.append((dist,val))
    if not cand: return None
    cand.sort(key=lambda x:x[0])
    return cand[0][1]

def detect_model(text_upper: str) -> Optional[str]:
    for name,rx in EQUIP_KEYWORDS.items():
        if rx.search(text_upper): return name
    return None

# --- scanner principal ---
def _jpg_bytes(pil: Image.Image, q=92) -> Optional[bytes]:
    try:
        b=BytesIO(); pil.convert("RGB").save(b, format="JPEG", quality=q); return b.getvalue()
    except Exception: return None

def _fingerprint(b: bytes) -> str: return hashlib.sha256(b).hexdigest()

def scan_one_image(pil: Image.Image, fonte: str) -> Dict:
    text = ocr_text(pil)
    up = (text or "").upper()
    modelo = detect_model(up)

    sn=None
    roi = find_sn_anchor_bbox(pil)
    if roi:
        sn = pick_sn_from_barcodes_near_roi(pil, roi)
        if not sn:
            local = ocr_text(pil.crop(roi))
            m = REGEX_SN_FROM_TEXT.search(local or "")
            if m: sn=m.group(1).strip()

    if not sn:
        m = REGEX_SN_FROM_TEXT.search(text or "")
        if m: sn=m.group(1).strip()

    if not sn:
        tokens=[t for t in re.findall(r"[A-Z0-9\-]{8,}", up) if not REGEX_MAC.fullmatch(t)]
        sn = next((t for t in tokens if is_valid_sn(modelo, t)), (tokens[0] if tokens else None))

    macs = REGEX_MAC.findall(text or "")
    mac = macs[0] if macs else ""

    if is_valid_sn(modelo, sn):
        jpg=_jpg_bytes(pil,92)
        if jpg:
            fp=_fingerprint(jpg)
            if fp not in ss.seen_hashes:
                ss.photos_to_append.append(jpg)
                ss.seen_hashes.add(fp)

    return {"modelo": (modelo or ""), "sn": (sn or ""), "mac": (mac or ""), "fonte": fonte}

def add_scanned_item(item: Dict):
    k=(item.get("modelo",""), item.get("sn",""), item.get("mac",""))
    current={(e.get("modelo",""), e.get("sn",""), e.get("mac","")) for e in ss.scanned_items}
    if k not in current: ss.scanned_items.append(item)

def push_to_textarea_from_items():
    linhas, seen = [], set()
    for it in ss.scanned_items:
        sn=(it.get("sn") or "").strip()
        if not sn: continue
        model=(it.get("modelo") or "").strip()
        line=f"{model}  S/N {sn}" if model else f"{sn}"
        if line not in seen: linhas.append(line); seen.add(line)
    exist=[ln.strip() for ln in (ss.seriais_texto or "").splitlines() if ln.strip()]
    all_lines, seen2=[], set()
    for ln in exist + linhas:
        if ln not in seen2: all_lines.append(ln); seen2.add(ln)
    ss.seriais_texto="\n".join(all_lines)

# --- PDF helpers ---
def search_once(page, texts):
    if isinstance(texts,str): texts=[texts]
    for t in texts:
        r=page.search_for(t)
        if r: return r[0]
    return None

def insert_right_of(page, labels, content, dx=0, dy=0, fontsize=10):
    if not content: return
    r=search_once(page, labels)
    if not r: return
    x=r.x1+dx; y=r.y0+r.height/1.5+dy
    page.insert_text((x,y), str(content), fontsize=fontsize)

def descricao_block(seriais: str, atividade: str, info: str) -> str:
    parts=[]
    if seriais and seriais.strip():
        linhas=[ln.strip() for ln in seriais.splitlines() if ln.strip()]
        parts.append("SERIAIS:\n" + "\n".join(f"- {ln}" for ln in linhas))
    if atividade and atividade.strip(): parts.append("ATIVIDADE:\n"+atividade.strip())
    if info and info.strip(): parts.append("INFORMAÇÕES ADICIONAIS:\n"+info.strip())
    return "\n\n".join(parts) if parts else ""

def insert_descricao_autofit(page, label, text):
    if not text: return
    r=search_once(page, label)
    if not r: return
    n=len(text.splitlines())
    if n<=15: fs,h=10,240
    elif n<=22: fs,h=9,300
    elif n<=30: fs,h=8,360
    else: fs,h=7,420
    rect=fitz.Rect(r.x0, r.y1+20, r.x0+540, r.y1+20+h)
    page.insert_textbox(rect, text, fontsize=fs, align=0)

def insert_signature_jpeg(page, label, sig_jpg_bytes: Optional[bytes], rel_rect):
    """
    Insere a assinatura no PDF como JPEG (RGB, fundo branco).
    Não existe alpha em nenhum momento → não há fundo preto.
    """
    if not sig_jpg_bytes: return
    r=search_once(page, label)
    if not r: return
    rect = fitz.Rect(r.x0+rel_rect[0], r.y1+rel_rect[1], r.x0+rel_rect[2], r.y1+rel_rect[3])
    page.insert_image(rect, stream=sig_jpg_bytes, keep_proportion=True)

# ===================== UI (1 página) =====================

# 1) DADOS DO RAT
with st.expander("1) 🧾 Dados do RAT (preencha aqui primeiro)", expanded=True):
    c1,c2 = st.columns(2)
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

# 2) SERIAIS & DESCRIÇÃO (com Scanner)
with st.expander("2) 🔎 Seriais & Descrição (inclui Scanner)", expanded=True):
    # Scanner embutido nesta seção
    with st.form("scanner_form"):
        cam_in = st.camera_input("📸 Tirar foto (abre câmera)", key="cam_in")
        imgs_in = st.file_uploader("📎 Enviar foto(s) de etiquetas", type=["jpg","jpeg","png","webp"],
                                   accept_multiple_files=True, key="imgs_in")
        pdf_in = st.file_uploader("📎 Enviar RAT (PDF) para extrair fotos de etiquetas", type=["pdf"], key="pdf_in")
        c1,c2,c3,c4 = st.columns([1,1,1,2])
        with c1: btn_cam = st.form_submit_button("➕ Ler CÂMERA")
        with c2: btn_imgs= st.form_submit_button("➕ Ler FOTOS")
        with c3: btn_pdf = st.form_submit_button("➕ Ler PDF")
        with c4: btn_push= st.form_submit_button("🡓 Jogar S/N no campo")

    if btn_cam and ss.get("cam_in") is not None:
        try:
            pil = Image.open(ss.cam_in).convert("RGB")
            add_scanned_item(scan_one_image(pil, "camera"))
            st.success("Foto da CÂMERA lida.")
        except Exception as e:
            st.warning(f"Falha câmera: {e}")

    if btn_imgs and ss.get("imgs_in"):
        for f in ss.imgs_in:
            try:
                raw=f.getvalue(); fp=hashlib.sha256(raw).hexdigest()
                if fp in ss.seen_hashes: continue
                pil=Image.open(BytesIO(raw)).convert("RGB")
                add_scanned_item(scan_one_image(pil, f.name))
                ss.seen_hashes.add(fp)
            except Exception as e:
                st.warning(f"Falha foto: {e}")
        st.success("FOTOS lidas.")

    if btn_pdf and ss.get("pdf_in") is not None:
        try:
            doc=fitz.open(stream=ss.pdf_in.read(), filetype="pdf")
            for pno,page in enumerate(doc):
                for idx,info in enumerate(page.get_images(full=True)):
                    base=doc.extract_image(info[0]); raw=base["image"]; fp=hashlib.sha256(raw).hexdigest()
                    if fp in ss.seen_hashes: continue
                    pil=Image.open(BytesIO(raw)).convert("RGB")
                    add_scanned_item(scan_one_image(pil, f"pdf:p{pno}_img{idx}"))
                    ss.seen_hashes.add(fp)
            st.success("PDF lido.")
        except Exception as e:
            st.warning(f"Falha PDF: {e}")

    if btn_push:
        push_to_textarea_from_items()
        st.success("Seriais jogados para o campo.")

    st.subheader("Itens scaneados (edite se necessário)")
    if ss.scanned_items:
        edited = st.data_editor(
            ss.scanned_items, num_rows="dynamic", use_container_width=True, key="editor_scans",
            column_config={
                "modelo": st.column_config.TextColumn("Modelo", width="medium"),
                "sn":     st.column_config.TextColumn("S/N", width="large"),
                "mac":    st.column_config.TextColumn("MAC", width="large"),
                "fonte":  st.column_config.TextColumn("Fonte", disabled=True),
            },
        )
        ss.scanned_items = edited

    cA,cB = st.columns(2)
    with cA:
        if st.button("🧹 Limpar ITENS (scanner)"):
            ss.scanned_items=[]; st.info("Itens limpos.")
    with cB:
        if st.button("🧹 Limpar FOTOS anexas"):
            ss.photos_to_append=[]; ss.seen_hashes=set(); st.info("Fotos limpas.")

    st.subheader("Campos do relatório")
    ss.seriais_texto = st.text_area(
        "Seriais (um por linha)",
        value=ss.seriais_texto, height=160, key="seriais_texto_area"
    )
    st.text_area("Atividade (texto do técnico)", height=80, key="atividade_txt", value=ss.atividade_txt)
    st.text_area("Informações adicionais (opcional)", height=60, key="info_txt", value=ss.info_txt)

# 3) ASSINATURAS (por último)
with st.expander("3) ✍️ Assinaturas (Técnico e Cliente) — fundo BRANCO garantido", expanded=True):
    st.caption("O PDF recebe a assinatura como JPEG (RGB, fundo branco). Isso elimina o fundo preto.")
    st.write("Assinatura do TÉCNICO")
    tec_canvas = st_canvas(
        fill_color="rgba(0,0,0,0)",
        stroke_width=3,
        stroke_color="#000000",
        background_color="#FFFFFF",   # fundo do quadro BRANCO para melhor visualização
        width=800, height=180,
        drawing_mode="freedraw",
        key="sig_tec_canvas",
        update_streamlit=True,
        display_toolbar=True,
    )
    if st.button("💾 Salvar assinatura do TÉCNICO (fundo branco)"):
        arr = getattr(tec_canvas, "image_data", None)
        ss.sig_tec_jpg = signature_from_canvas_as_jpeg(arr)
        st.success("Assinatura do técnico salva." if ss.sig_tec_jpg else "Nada para salvar.")

    st.write("---")
    st.write("Assinatura do CLIENTE")
    cli_canvas = st_canvas(
        fill_color="rgba(0,0,0,0)",
        stroke_width=3,
        stroke_color="#000000",
        background_color="#FFFFFF",   # fundo do quadro BRANCO
        width=800, height=180,
        drawing_mode="freedraw",
        key="sig_cli_canvas",
        update_streamlit=True,
        display_toolbar=True,
    )
    if st.button("💾 Salvar assinatura do CLIENTE (fundo branco)"):
        arr = getattr(cli_canvas, "image_data", None)
        ss.sig_cli_jpg = signature_from_canvas_as_jpeg(arr)
        st.success("Assinatura do cliente salva." if ss.sig_cli_jpg else "Nada para salvar.")

    if st.button("🧹 Limpar assinaturas salvas"):
        ss.sig_tec_jpg=None; ss.sig_cli_jpg=None; st.info("Assinaturas removidas.")

# ====== GERAÇÃO DO PDF ======
st.write("---")
if st.checkbox("Anexar fotos com S/N ao PDF", key="anexar_fotos", value=ss.anexar_fotos):
    ss.anexar_fotos = True
else:
    ss.anexar_fotos = False

if st.button("🧾 Gerar PDF preenchido"):
    try:
        base = load_pdf_bytes(PDF_BASE_PATH)
    except FileNotFoundError:
        st.error(f"Arquivo '{PDF_BASE_PATH}' não encontrado.")
        st.stop()

    try:
        doc = fitz.open(stream=base, filetype="pdf")
        page = doc[0]

        # Topo
        insert_right_of(page, ["Cliente:", "CLIENTE:"], ss.get("cliente_nome",""), 6, 1)
        insert_right_of(page, ["Endereço:", "ENDEREÇO:"], ss.get("endereco",""), 6, 1)
        insert_right_of(page, ["Bairro:", "BAIRRO:"],     ss.get("bairro",""), 6, 1)
        insert_right_of(page, ["Cidade:", "CIDADE:"],     ss.get("cidade",""), 6, 1)
        insert_right_of(page, ["Contato:"],               ss.get("contato_nome",""), 6, 1)
        # RG do contato (à direita de "Contato")
        r_cont = page.search_for("Contato:")
        if r_cont and ss.get("contato_rg",""):
            r = r_cont[0]; x = r.x1 + 40; y = r.y0 + r.height/1.5 + 6
            page.insert_text((x,y), str(ss["contato_rg"]), fontsize=10)
        insert_right_of(page, ["Telefone:", "TELEFONE:"], normalize_phone(ss.get("contato_tel","")), 6, 1)

        # Datas/Horas/KM
        insert_right_of(page, ["Data do atendimento:", "Data do Atendimento:"],
                        ss["data_atend"].strftime("%d/%m/%Y"), -90, 10)
        insert_right_of(page, ["Hora Inicio:", "Hora Início:", "Hora inicio:"],
                        ss["hora_ini"].strftime("%H:%M"), 0, 3)
        insert_right_of(page, ["Hora Termino:", "Hora Término:", "Hora termino:"],
                        ss["hora_fim"].strftime("%H:%M"), 0, 3)
        insert_right_of(page, ["Distancia (KM) :", "Distância (KM) :"],
                        str(ss.get("distancia_km","")), 0, 3)

        # Descrição (inclui seriais)
        block = descricao_block(ss.get("seriais_texto_area",""), ss.get("atividade_txt",""), ss.get("info_txt",""))
        insert_descricao_autofit(page, ["DESCRIÇÃO DE ATENDIMENTO","DESCRICAO DE ATENDIMENTO"], block)

        # Assinaturas — JPEG (RGB BRANCO)
        insert_signature_jpeg(page, ["ASSINATURA:", "Assinatura:"], ss.get("sig_tec_jpg"),
                              (110 - 2*CM, 0 - 1*CM, 330 - 2*CM, 54 - 1*CM))
        insert_signature_jpeg(page, ["DATA CARIMBO / ASSINATURA", "ASSINATURA CLIENTE", "CLIENTE"],
                              ss.get("sig_cli_jpg"), (110, 12 - 3.5*CM, 430, 94 - 3.5*CM))

        # Nº chamado
        insert_right_of(page, [" Nº CHAMADO ", "Nº CHAMADO", "No CHAMADO"], ss.get("num_chamado",""),
                        dx=-(2*CM), dy=10)

        # Fotos anexas
        if ss.get("anexar_fotos", True) and ss.photos_to_append:
            for img_bytes in ss.photos_to_append:
                p = doc.new_page()
                pil = Image.open(BytesIO(img_bytes)).convert("RGB")
                W,H = pil.size; w,h = p.rect.width, p.rect.height
                margin=36; max_w, max_h = w-2*margin, h-2*margin
                scale=min(max_w/W, max_h/H); new_w, new_h = int(W*scale), int(H*scale)
                x0=(w-new_w)/2; y0=(h-new_h)/2
                rect=fitz.Rect(x0,y0,x0+new_w,y0+new_h)
                b=BytesIO(); pil.save(b, format="JPEG", quality=92)
                p.insert_image(rect, stream=b.getvalue())

        out=BytesIO(); doc.save(out); doc.close()
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
