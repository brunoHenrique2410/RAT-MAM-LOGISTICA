# common/ui.py — componentes UI: assinaturas, scanner mínimo, fotos

from io import BytesIO
import hashlib

import numpy as np
import streamlit as st
from streamlit_drawable_canvas import st_canvas


def _signature_from_canvas_as_png(
    arr,
    white_threshold: int = 245,
    min_ink_px: int = 10,
):
    if arr is None or getattr(arr, "ndim", 0) != 3 or arr.shape[2] < 4:
        return None

    rgba = arr.astype("uint8")
    red = rgba[..., 0]
    green = rgba[..., 1]
    blue = rgba[..., 2]

    near_white = (
        (red >= white_threshold)
        & (green >= white_threshold)
        & (blue >= white_threshold)
    )
    stroke_mask = ~near_white

    if int(stroke_mask.sum()) < min_ink_px:
        return None

    height, width = red.shape
    out = np.zeros((height, width, 4), dtype=np.uint8)
    out[..., 0:3] = 255
    out[stroke_mask, 0:3] = [0, 0, 0]
    out[..., 3] = 0
    out[stroke_mask, 3] = 255

    from PIL import Image as PILImage

    buffer = BytesIO()
    PILImage.fromarray(out, "RGBA").save(buffer, format="PNG")
    return buffer.getvalue()


def assinatura_tecnico_png() -> None:
    """Exibe e salva somente a assinatura do técnico."""
    ss = st.session_state

    tecnico = st_canvas(
        fill_color="rgba(0,0,0,0)",
        stroke_width=3,
        stroke_color="#000000",
        background_color="#FFFFFF",
        width=800,
        height=180,
        drawing_mode="freedraw",
        key="sig_tec_canvas",
        update_streamlit=True,
        display_toolbar=True,
    )

    col_salvar, col_limpar = st.columns(2)

    with col_salvar:
        if st.button(
            "💾 Salvar assinatura do TÉCNICO",
            key="salvar_sig_tecnico",
            use_container_width=True,
        ):
            ss.sig_tec_png = _signature_from_canvas_as_png(
                getattr(tecnico, "image_data", None)
            )

            if ss.sig_tec_png:
                st.success("Assinatura do técnico salva.")
            else:
                st.warning("Não foi identificada nenhuma assinatura.")

    with col_limpar:
        if st.button(
            "🧹 Limpar assinatura do TÉCNICO",
            key="limpar_sig_tecnico",
            use_container_width=True,
        ):
            ss.sig_tec_png = None
            st.info("Assinatura do técnico removida.")


def assinatura_cliente_png() -> None:
    """Exibe e salva somente a assinatura do cliente."""
    ss = st.session_state

    cliente = st_canvas(
        fill_color="rgba(0,0,0,0)",
        stroke_width=3,
        stroke_color="#000000",
        background_color="#FFFFFF",
        width=800,
        height=180,
        drawing_mode="freedraw",
        key="sig_cli_canvas",
        update_streamlit=True,
        display_toolbar=True,
    )

    col_salvar, col_limpar = st.columns(2)

    with col_salvar:
        if st.button(
            "💾 Salvar assinatura do CLIENTE",
            key="salvar_sig_cliente",
            use_container_width=True,
        ):
            ss.sig_cli_png = _signature_from_canvas_as_png(
                getattr(cliente, "image_data", None)
            )

            if ss.sig_cli_png:
                st.success("Assinatura do cliente salva.")
            else:
                st.warning("Não foi identificada nenhuma assinatura.")

    with col_limpar:
        if st.button(
            "🧹 Limpar assinatura do CLIENTE",
            key="limpar_sig_cliente",
            use_container_width=True,
        ):
            ss.sig_cli_png = None
            st.info("Assinatura do cliente removida.")


def assinatura_dupla_png() -> None:
    """
    Mantida por compatibilidade com outras telas que ainda chamem
    assinatura_dupla_png().
    """
    st.markdown("**Assinatura do TÉCNICO**")
    assinatura_tecnico_png()

    st.divider()

    st.markdown("**Assinatura do CLIENTE**")
    assinatura_cliente_png()


def scanner_minimo() -> None:
    """Uploader simples que anexa fotos sem executar OCR."""
    ss = st.session_state

    with st.form("scanner_mam"):
        fotos = st.file_uploader(
            "📎 Fotos das etiquetas (opcional)",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            key="mam_fotos",
        )

        left, right = st.columns(2)

        with left:
            adicionar = st.form_submit_button("➕ Anexar fotos")

        with right:
            limpar = st.form_submit_button("🧹 Limpar anexos")

    if adicionar and fotos:
        if "photos_to_append" not in ss:
            ss["photos_to_append"] = []

        if "seen_hashes" not in ss:
            ss["seen_hashes"] = set()

        adicionadas = 0

        for arquivo in fotos:
            raw = arquivo.getvalue()
            fingerprint = hashlib.sha256(raw).hexdigest()

            if fingerprint in ss.seen_hashes:
                continue

            ss.photos_to_append.append(raw)
            ss.seen_hashes.add(fingerprint)
            adicionadas += 1

        st.success(f"{adicionadas} foto(s) anexada(s).")

    if limpar:
        ss.photos_to_append = []
        ss.seen_hashes = set()
        st.info("Anexos limpos.")


def foto_gateway_uploader() -> None:
    ss = st.session_state

    with st.form("gateway_fotos"):
        fotos = st.file_uploader(
            "📎 Foto(s) do gateway (obrigatória ao menos 1)",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            key="gw_fotos",
        )

        adicionar = st.form_submit_button("➕ Adicionar")

    if adicionar and fotos:
        if "fotos_gateway" not in ss:
            ss["fotos_gateway"] = []

        for arquivo in fotos:
            ss.fotos_gateway.append(arquivo.getvalue())

        st.success(f"{len(fotos)} foto(s) adicionada(s).")
