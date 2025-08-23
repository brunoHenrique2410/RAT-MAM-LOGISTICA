# common/pdf.py
import os, fitz, streamlit as st
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))  # isto aponta para common/
PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)               # sobe p/ raiz
# ... (o restante igual)

# common/pdf.py — utilitários PyMuPDF (fitz) para preencher PDFs
from io import BytesIO
import fitz
import streamlit as st

CM = 28.3465  # pontos por cm

def open_pdf_template(path: str):
    try:
        with open(path, "rb") as f:
            base = f.read()
    except FileNotFoundError:
        st.error(f"Template PDF não encontrado: {path}")
        raise
    doc = fitz.open(stream=base, filetype="pdf")
    return doc, doc[0]

def search_once(page, texts, occurrence=1):
    """Retorna o Retângulo da 'occurrence'-ésima ocorrência da string."""
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
    x = r.x1 + dx; y = r.y0 + r.height/1.5 + dy
    page.insert_text((x, y), str(content), fontsize=fontsize)

def insert_textbox(page, label, text, width=540, y_offset=20, fontsize=10, align=0, occurrence=1):
    if not text:
        return
    r = search_once(page, label, occurrence=occurrence)
    if not r:
        return
    rect = fitz.Rect(r.x0, r.y1 + y_offset, r.x0 + width, r.y1 + y_offset + 280)
    page.insert_textbox(rect, str(text), fontsize=fontsize, align=align)

def mark_X_left_of(page, label_text, dx=-14, dy=0, occurrence=1, near_text=None, fontsize=12):
    """
    Marca 'X' à esquerda do texto (em checkboxes).
    Se 'near_text' for passado, busca primeiro esse texto de referência (linha/área).
    """
    tgt = None
    if near_text:
        tgt = search_once(page, near_text)
    base = search_once(page, label_text, occurrence=occurrence)
    r = base
    if not r:
        return
    x = r.x0 + dx; y = r.y0 + r.height/1.2 + dy
    page.insert_text((x, y), "X", fontsize=fontsize)

def insert_signature_png(page, labels, sig_png_bytes, rel_rect, occurrence=1):
    """
    Insere assinatura PNG **com transparência**.
    rel_rect = (dx0, dy0, dx1, dy1) relativo à âncora (parte superior do texto da âncora).
    """
    if not sig_png_bytes:
        return
    r = search_once(page, labels, occurrence=occurrence)
    if not r:
        return
    rect = fitz.Rect(r.x0 + rel_rect[0], r.y1 + rel_rect[1],
                     r.x0 + rel_rect[2], r.y1 + rel_rect[3])
    page.insert_image(rect, stream=sig_png_bytes, keep_proportion=True)

# common/pdf.py

from io import BytesIO
from PIL import Image

def add_image_page(doc, img_bytes, margin=36):
    """
    Cria uma página no PDF e insere a imagem centralizada com margens.
    Usa PIL para ler a imagem (mais robusto do que abrir via fitz.open(filetype="image")).
    """
    if not img_bytes:
        return

    # Abre com PIL para obter dimensões e garantir compatibilidade com formatos (jpg/png/webp)
    try:
        pil = Image.open(BytesIO(img_bytes)).convert("RGB")
    except Exception:
        # fallback: não conseguiu abrir; tenta inserir sem redimensionar
        page = doc.new_page()
        page.insert_image(page.rect, stream=img_bytes, keep_proportion=True)
        return

    W, H = pil.size

    # Nova página A4 (ou tamanho padrão do doc)
    page = doc.new_page()
    w, h = page.rect.width, page.rect.height

    # Caixa útil com margens
    max_w, max_h = w - 2 * margin, h - 2 * margin
    if max_w <= 0 or max_h <= 0:
        max_w, max_h = w, h

    # Escala mantendo proporção
    scale = min(max_w / W, max_h / H)
    new_w, new_h = int(W * scale), int(H * scale)

    x0 = (w - new_w) / 2
    y0 = (h - new_h) / 2
    rect = fitz.Rect(x0, y0, x0 + new_w, y0 + new_h)

    # Reusa os bytes originais (PyMuPDF redimensiona internamente pela box)
    page.insert_image(rect, stream=img_bytes, keep_proportion=True)
