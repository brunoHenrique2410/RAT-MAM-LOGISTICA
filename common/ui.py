# common/ui.py — componentes UI: assinaturas, scanner mínimo, fotos
from io import BytesIO
import hashlib
import streamlit as st
from PIL import Image
import numpy as np
from streamlit_drawable_canvas import st_canvas

def _signature_from_canvas_as_png(arr, white_threshold: int = 245, min_ink_px: int = 10):
    if arr is None or getattr(arr, "ndim", 0) != 3 or arr.shape[2] < 4:
        return None
    rgba = arr.astype("uint8")
    R, G, B, _ = rgba[...,0], rgba[...,1], rgba[...,2], rgba[...,3]
    near_white = (R >= white_threshold) & (G >= white_threshold) & (B >= white_threshold)
    stroke_mask = ~near_white
    if int(stroke_mask.sum()) < min_ink_px:
        return None
    H, W = R.shape
    out = np.zeros((H,W,4), dtype=np.uint8)
    out[...,0:3] = 255
    out[stroke_mask,0:3] = [0,0,0]
    out[...,3] = 0
    out[stroke_mask,3] = 255
    from PIL import Image as PILImage
    b = BytesIO(); PILImage.fromarray(out, "RGBA").save(b, format="PNG")
    return b.getvalue()

def assinatura_dupla_png():
    ss = st.session_state
    st.markdown("**Assinatura do TÉCNICO**")
    tec = st_canvas(
        fill_color="rgba(0,0,0,0)", stroke_width=3, stroke_color="#000000",
        background_color="#FFFFFF", width=800, height=180,
        drawing_mode="freedraw", key="sig_tec_canvas", update_streamlit=True, display_toolbar=True,
    )
    if st.button("💾 Salvar assinatura do TÉCNICO"):
        ss.sig_tec_png = _signature_from_canvas_as_png(getattr(tec, "image_data", None))
        st.success("Assinatura do técnico salva." if ss.sig_tec_png else "Nada para salvar.")

    st.divider()
    st.markdown("**Assinatura do CLIENTE**")
    cli = st_canvas(
        fill_color="rgba(0,0,0,0)", stroke_width=3, stroke_color="#000000",
        background_color="#FFFFFF", width=800, height=180,
        drawing_mode="freedraw", key="sig_cli_canvas", update_streamlit=True, display_toolbar=True,
    )
    if st.button("💾 Salvar assinatura do CLIENTE"):
        ss.sig_cli_png = _signature_from_canvas_as_png(getattr(cli, "image_data", None))
        st.success("Assinatura do cliente salva." if ss.sig_cli_png else "Nada para salvar.")

    if st.button("🧹 Limpar assinaturas salvas"):
        ss.sig_tec_png = None; ss.sig_cli_png = None
        st.info("Assinaturas removidas.")

def scanner_minimo():
    """Uploader simples que só anexa fotos; OCR deixamos para o MAM completo se quiser."""
    ss = st.session_state
    with st.form("scanner_mam"):
        fotos = st.file_uploader("📎 Fotos das etiquetas (opcional)", type=["jpg","jpeg","png","webp"],
                                 accept_multiple_files=True, key="mam_fotos")
        l, r = st.columns(2)
        with l: ok = st.form_submit_button("➕ Anexar fotos")
        with r: clr = st.form_submit_button("🧹 Limpar anexos")
    if ok and fotos:
        if "photos_to_append" not in ss: ss["photos_to_append"] = []
        if "seen_hashes" not in ss: ss["seen_hashes"] = set()
        for f in fotos:
            raw = f.getvalue()
            fp = hashlib.sha256(raw).hexdigest()
            if fp in ss.seen_hashes: continue
            ss.photos_to_append.append(raw)
            ss.seen_hashes.add(fp)
        st.success(f"{len(fotos)} foto(s) anexada(s).")
    if clr:
        ss.photos_to_append = []
        ss.seen_hashes = set()
        st.info("Anexos limpos.")

def foto_gateway_uploader():
    ss = st.session_state
    with st.form("gateway_fotos"):
        fotos = st.file_uploader("📎 Foto(s) do gateway (obrigatória ao menos 1)", type=["jpg","jpeg","png","webp"],
                                 accept_multiple_files=True, key="gw_fotos")
        ok = st.form_submit_button("➕ Adicionar")
    if ok and fotos:
        if "fotos_gateway" not in ss: ss["fotos_gateway"] = []
        for f in fotos:
            ss.fotos_gateway.append(f.getvalue())
        st.success(f"{len(fotos)} foto(s) adicionada(s).")
