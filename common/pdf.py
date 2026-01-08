# common/pdf.py — utilitários PyMuPDF (fitz) para preencher PDFs
from io import BytesIO
import os, glob
import fitz
import streamlit as st
from PIL import Image

CM = 28.3465  # pontos por cm


def insert_stamp_image(
    page: fitz.Page,
    image_path: str,
    where: str = "bottom_right",
    width_cm: float = 4.2,
    margin_x: float = 18,
    margin_y: float = 16,
    opacity: float = 0.95,
):
    """
    Insere um PNG como imagem normal (via stream bytes) com tamanho controlado.
    Retorna True se inseriu, False se não encontrou a imagem.
    """
    if not image_path or not os.path.exists(image_path):
        return False

    with open(image_path, "rb") as f:
        img_bytes = f.read()

    # pega tamanho original via PIL (mantém proporção)
    im = Image.open(BytesIO(img_bytes))
    W, H = im.size

    # largura desejada em pontos
    w = width_cm * 28.3464567
    h = w * (H / W)

    r = page.rect
    if where == "bottom_right":
        rect = fitz.Rect(r.width - w - margin_x, r.height - h - margin_y, r.width - margin_x, r.height - margin_y)
    elif where == "bottom_left":
        rect = fitz.Rect(margin_x, r.height - h - margin_y, margin_x + w, r.height - margin_y)
    elif where == "top_right":
        rect = fitz.Rect(r.width - w - margin_x, margin_y, r.width - margin_x, margin_y + h)
    else:  # top_left
        rect = fitz.Rect(margin_x, margin_y, margin_x + w, margin_y + h)

    page.insert_image(rect, stream=img_bytes, keep_proportion=True, overlay=True, opacity=opacity)
    return True


def _find_template_by_hint(hint: str, base_dir: str) -> str | None:
    pat = os.path.join(base_dir, "*.pdf")
    for path in glob.glob(pat):
        name = os.path.basename(path)
        if name.lower().startswith(hint.lower()):
            return path
    return None


def open_pdf_template(path: str, hint: str | None = None):
    try:
        with open(path, "rb") as f:
            base = f.read()
        doc = fitz.open(stream=base, filetype="pdf")
        return doc, doc[0]
    except FileNotFoundError:
        base_dir = os.path.dirname(path)
        if hint:
            alt = _find_template_by_hint(hint, base_dir)
            if alt:
                with open(alt, "rb") as f:
                    base = f.read()
                doc = fitz.open(stream=base, filetype="pdf")
                st.warning(f"Template não achado em '{path}', mas encontrei '{os.path.basename(alt)}'.")
                return doc, doc[0]
        st.error(f"Template PDF não encontrado: {path}")
        up = st.file_uploader("📎 Envie o template PDF desta RAT", type=["pdf"], key=f"upl_{os.path.basename(path)}")
        if up is not None:
            doc = fitz.open(stream=up.read(), filetype="pdf")
            st.info("Usando template enviado pelo usuário (sessão atual).")
            return doc, doc[0]
        raise


def search_once(page, texts, occurrence=1):
    if isinstance(texts, str):
        texts = [texts]
    occ = 0
    for t in texts:
        rects = page.search_for(t)
        if rects:
            for r in rects:
                occ += 1
                if occ == occurrence:
                    return r
    return None


def insert_right_of(page, labels, content, dx=0, dy=0, fontsize=10):
    if not content:
        return
    r = search_once(page, labels)
    if not r:
        return
    x = r.x1 + dx
    y = r.y0 + r.height / 1.5 + dy
    page.insert_text((x, y), str(content), fontsize=fontsize)


def insert_textbox(page, label, text, width=540, y_offset=20, fontsize=10, align=0, occurrence=1, height=280):
    if not text:
        return
    r = search_once(page, label, occurrence=occurrence)
    if not r:
        return
    rect = fitz.Rect(r.x0, r.y1 + y_offset, r.x0 + width, r.y1 + y_offset + height)
    page.insert_textbox(rect, str(text), fontsize=fontsize, align=align)


def mark_X_left_of(page, label_text, dx=-14, dy=0, occurrence=1, near_text=None, fontsize=12):
    r = search_once(page, label_text, occurrence=occurrence)
    if not r:
        return
    x = r.x0 + dx
    y = r.y0 + r.height / 1.2 + dy
    page.insert_text((x, y), "X", fontsize=fontsize)


def insert_signature_png(page, labels, sig_png_bytes, rel_rect, occurrence=1):
    if not sig_png_bytes:
        return
    r = search_once(page, labels, occurrence=occurrence)
    if not r:
        return
    rect = fitz.Rect(
        r.x0 + rel_rect[0], r.y1 + rel_rect[1],
        r.x0 + rel_rect[2], r.y1 + rel_rect[3]
    )
    page.insert_image(rect, stream=sig_png_bytes, keep_proportion=True)


def add_image_page(doc, img_bytes, margin=36):
    if not img_bytes:
        return

    try:
        pil = Image.open(BytesIO(img_bytes))
        if pil.mode not in ("RGB", "L"):
            pil = pil.convert("RGB")
        W, H = pil.size
    except Exception:
        page = doc.new_page()
        page.insert_image(page.rect, stream=img_bytes, keep_proportion=True)
        return

    page = doc.new_page()
    w, h = page.rect.width, page.rect.height

    max_w, max_h = w - 2 * margin, h - 2 * margin
    if max_w <= 0 or max_h <= 0:
        max_w, max_h = w, h

    scale = min(max_w / W, max_h / H)
    new_w, new_h = int(W * scale), int(H * scale)

    x0 = (w - new_w) / 2
    y0 = (h - new_h) / 2
    rect = fitz.Rect(x0, y0, x0 + new_w, y0 + new_h)

    page.insert_image(rect, stream=img_bytes, keep_proportion=True)

def insert_stamp_image(
    page: fitz.Page,
    image_path: str,
    where: str = "bottom_right",
    width_cm: float = 4.2,
    margin_x: float = 18,
    margin_y: float = 16,
    opacity: float = 0.95,
):
    """
    Insere um PNG como imagem normal (via stream bytes) com tamanho controlado.
    Retorna True se inseriu, False se não encontrou a imagem.
    """
    if not image_path or not os.path.exists(image_path):
        return False

    with open(image_path, "rb") as f:
        img_bytes = f.read()

    im = Image.open(BytesIO(img_bytes))
    W, H = im.size

    w = width_cm * 28.3464567
    h = w * (H / W)

    r = page.rect
    if where == "bottom_right":
        rect = fitz.Rect(r.width - w - margin_x, r.height - h - margin_y, r.width - margin_x, r.height - margin_y)
    elif where == "bottom_left":
        rect = fitz.Rect(margin_x, r.height - h - margin_y, margin_x + w, r.height - margin_y)
    elif where == "top_right":
        rect = fitz.Rect(r.width - w - margin_x, margin_y, r.width - margin_x, margin_y + h)
    else:  # top_left
        rect = fitz.Rect(margin_x, margin_y, margin_x + w, margin_y + h)

    page.insert_image(rect, stream=img_bytes, keep_proportion=True, overlay=True, opacity=opacity)
    return True

