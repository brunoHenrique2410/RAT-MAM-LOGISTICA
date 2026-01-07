# common/pdf.py — utilitários PyMuPDF (fitz) para preencher PDFs

from io import BytesIO
import os
import glob
import fitz
import streamlit as st

# Pillow é opcional, mas suportado
try:
    from PIL import Image
except Exception:
    Image = None


# =========================================================
# 🔖 SELO DE GERAÇÃO (imagem + texto)
# =========================================================
def add_generation_stamp(
    page: fitz.Page,
    image_path: str,
    text: str,
    where: str = "bottom_right",
    scale: float = 0.55,
    opacity: float = 0.85,
):
    """
    Adiciona um selo de geração automática no PDF (imagem + texto).

    text exemplo:
    "Gerado automaticamente\n07/01/2026 14:32 • Chamado 123456789"
    """

    r = page.rect
    margin_x, margin_y = 18, 16

    # ---------- fallback: só texto ----------
    if not image_path or not os.path.exists(image_path):
        rect_txt = fitz.Rect(
            r.width - 240,
            r.height - 70,
            r.width - 18,
            r.height - 18,
        )
        page.insert_textbox(
            rect_txt,
            text,
            fontsize=7.2,
            fontname="helv",
            align=fitz.TEXT_ALIGN_LEFT,
            color=(0.45, 0.45, 0.45),
        )
        return

    # ---------- imagem ----------
    pix = fitz.Pixmap(image_path)
    img_w, img_h = pix.width * scale, pix.height * scale

    if where == "bottom_right":
        rect_img = fitz.Rect(
            r.width - img_w - margin_x,
            r.height - img_h - margin_y,
            r.width - margin_x,
            r.height - margin_y,
        )
    elif where == "bottom_left":
        rect_img = fitz.Rect(
            margin_x,
            r.height - img_h - margin_y,
            margin_x + img_w,
            r.height - margin_y,
        )
    elif where == "top_right":
        rect_img = fitz.Rect(
            r.width - img_w - margin_x,
            margin_y,
            r.width - margin_x,
            margin_y + img_h,
        )
    else:  # top_left
        rect_img = fitz.Rect(
            margin_x,
            margin_y,
            margin_x + img_w,
            margin_y + img_h,
        )

    page.insert_image(
        rect_img,
        filename=image_path,
        keep_proportion=True,
        overlay=True,
        opacity=opacity,
    )

    # ---------- texto ----------
    gap = 6
    txt_height = 34

    rect_txt = fitz.Rect(
        rect_img.x0,
        rect_img.y1 + gap,
        rect_img.x1,
        rect_img.y1 + gap + txt_height,
    )

    # se estourar o rodapé, joga o texto para cima da imagem
    if rect_txt.y1 > r.height - 6:
        rect_txt = fitz.Rect(
            rect_img.x0,
            rect_img.y0 - gap - txt_height,
            rect_img.x1,
            rect_img.y0 - gap,
        )

    page.insert_textbox(
        rect_txt,
        text,
        fontsize=7.2,
        fontname="helv",
        align=fitz.TEXT_ALIGN_LEFT,
        color=(0.45, 0.45, 0.45),
    )


# =========================================================
# 📄 TEMPLATE PDF
# =========================================================
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
                st.warning(f"Template não achado, usando '{os.path.basename(alt)}'.")
                return doc, doc[0]
        st.error(f"Template PDF não encontrado: {path}")
        up = st.file_uploader("📎 Envie o template PDF", type=["pdf"])
        if up:
            doc = fitz.open(stream=up.read(), filetype="pdf")
            return doc, doc[0]
        raise


# =========================================================
# 🔎 BUSCAS E INSERÇÕES
# =========================================================
def search_once(page, texts, occurrence=1):
    if isinstance(texts, str):
        texts = [texts]
    occ = 0
    for t in texts:
        for r in page.search_for(t):
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
    r = search_once(page, label, occurrence)
    if not r:
        return
    rect = fitz.Rect(r.x0, r.y1 + y_offset, r.x0 + width, r.y1 + y_offset + height)
    page.insert_textbox(rect, str(text), fontsize=fontsize, align=align)


def mark_X_left_of(page, label_text, dx=-14, dy=0, occurrence=1, fontsize=12):
    r = search_once(page, label_text, occurrence)
    if not r:
        return
    x = r.x0 + dx
    y = r.y0 + r.height / 1.2 + dy
    page.insert_text((x, y), "X", fontsize=fontsize)


# =========================================================
# ✍️ ASSINATURA
# =========================================================
def insert_signature_png(page, labels, sig_png_bytes, rel_rect, occurrence=1):
    if not sig_png_bytes:
        return
    r = search_once(page, labels, occurrence)
    if not r:
        return
    rect = fitz.Rect(
        r.x0 + rel_rect[0], r.y1 + rel_rect[1],
        r.x0 + rel_rect[2], r.y1 + rel_rect[3],
    )
    page.insert_image(rect, stream=sig_png_bytes, keep_proportion=True)


# =========================================================
# 🖼️ IMAGEM EM NOVA PÁGINA
# =========================================================
def add_image_page(doc, img_bytes, margin=36):
    if not img_bytes:
        return

    # fallback sem Pillow
    if Image is None:
        page = doc.new_page()
        page.insert_image(page.rect, stream=img_bytes, keep_proportion=True)
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
    scale = min(max_w / W, max_h / H)

    new_w, new_h = int(W * scale), int(H * scale)
    x0 = (w - new_w) / 2
    y0 = (h - new_h) / 2

    rect = fitz.Rect(x0, y0, x0 + new_w, y0 + new_h)
    page.insert_image(rect, stream=img_bytes, keep_proportion=True)
