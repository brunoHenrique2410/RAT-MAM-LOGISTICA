# app.py — RAT MAM (âncoras + assinatura via drawable-canvas)
# Ajustes solicitados:
# - Nº do chamado: -2 cm à esquerda (dx = -2*CM) e mais baixo (mantido dy)
# - Nome do técnico: ~3 cm para baixo (limite prático; 30 cm excede A4) e -1 cm à esquerda
# - RG do técnico: +6 pt para baixo e +5 cm à direita
# - Data do atendimento: um pouco para baixo (+6 pt) e mais à esquerda (~ -70 pt ≈ -2.5 cm)
# - Assinaturas: quadro com fundo branco; técnico (-2 cm X, -1 cm Y), cliente (-2 cm Y)
#
# Requisitos:
#   streamlit==1.37.1
#   Pillow==10.4.0
#   PyMuPDF>=1.24.12
#   streamlit-drawable-canvas==0.9.3
#   numpy==2.3.2
# runtime.txt: 3.12

from io import BytesIO
from datetime import date, time

import streamlit as st
from PIL import Image
import numpy as np
import fitz  # PyMuPDF
from streamlit_drawable_canvas import st_canvas

PDF_BASE_PATH = "RAT MAM.pdf"
APP_TITLE = "RAT MAM – Assinatura Digital + Âncoras"
CM = 28.3465  # pontos por centímetro (A4: 595x842 pt)

st.set_page_config(page_title=APP_TITLE, layout="centered")
st.title("📄 " + APP_TITLE)
st.caption("Assine direto no celular (fundo branco no quadro). Campos posicionados por âncoras do PDF.")

@st.cache_data
def load_pdf_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()

def normalize_phone(s: str) -> str:
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return s

def np_to_rgba_pil(arr) -> Image.Image | None:
    if arr is None or arr.ndim != 3 or arr.shape[2] < 4:
        return None
    if np.max(arr[:, :, 3]) == 0:  # nada desenhado
        return None
    return Image.fromarray(arr.astype("uint8"), mode="RGBA")

# ---------- Form ----------
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

    st.subheader("3) Descrição de Atendimento (inclua TODOS os seriais aqui)")
    seriais_texto = st.text_area("Seriais (um por linha)", placeholder="SN0012345\nSN00ABC678\n...")
    atividade     = st.text_area("Atividade (palavras do técnico)", height=120)
    info_extra    = st.text_area("Informações adicionais (opcional)", height=80)

    st.subheader("4) Técnico")
    tec_nome = st.text_input("Nome do técnico")
    tec_rg   = st.text_input("RG/Documento do técnico")

    st.write("**Assinatura do TÉCNICO**")
    tec_canvas = st_canvas(
        fill_color="rgba(0,0,0,0)",      # sem preenchimento (traço apenas)
        stroke_width=3,
        stroke_color="#000000",
        background_color="#FFFFFF",      # fundo BRANCO no quadro (pedido)
        width=800,
        height=180,
        drawing_mode="freedraw",
        key="sig_tec_canvas",
        update_streamlit=True,
        display_toolbar=False,
    )

    st.write("---")
    st.write("**Assinatura do CLIENTE**")
    cli_canvas = st_canvas(
        fill_color="rgba(0,0,0,0)",
        stroke_width=3,
        stroke_color="#000000",
        background_color="#FFFFFF",      # fundo BRANCO
        width=800,
        height=180,
        drawing_mode="freedraw",
        key="sig_cli_canvas",
        update_streamlit=True,
        display_toolbar=False,
    )

    submitted = st.form_submit_button("🧾 Gerar PDF preenchido")

# ---------- Âncoras e helpers ----------
def search_once(page, texts):
    if isinstance(texts, (str,)):
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

def place_signature_near(page, label, pil_rgba: Image.Image, rel_rect):
    if pil_rgba is None:
        return
    r = search_once(page, label)
    if not r:
        return
    rect = fitz.Rect(r.x0 + rel_rect[0], r.y1 + rel_rect[1], r.x0 + rel_rect[2], r.y1 + rel_rect[3])
    buf = BytesIO()
    pil_rgba.save(buf, format="PNG")   # preserva alfa; como o fundo do quadro é branco, o PNG vai com retângulo branco (pedido)
    page.insert_image(rect, stream=buf.getvalue())

def find_tecnico_rg_label_rect(page):
    for lbl in ["TÉCNICO RG:", "TÉCNICO  RG:", "TECNICO RG:"]:
        rect = search_once(page, [lbl])
        if rect:
            return rect
    return None

# ---------- Geração ----------
if submitted:
    # Monta bloco de descrição
    partes = []
    if seriais_texto and seriais_texto.strip():
        seriais = [ln.strip() for ln in seriais_texto.splitlines() if ln.strip()]
        if seriais:
            partes.append("SERIAIS:\n" + "\n".join(f"- {s}" for s in seriais))
    if atividade and atividade.strip():
        partes.append("ATIVIDADE:\n" + atividade.strip())
    if info_extra and info_extra.strip():
        partes.append("INFORMAÇÕES ADICIONAIS:\n" + info_extra.strip())
    bloco_desc = "\n\n".join(partes) if partes else ""

    # Assinaturas do canvas
    sigtec_img = np_to_rgba_pil(tec_canvas.image_data if tec_canvas else None)
    sigcli_img = np_to_rgba_pil(cli_canvas.image_data if cli_canvas else None)

    # PDF base
    base_bytes = None
    try:
        base_bytes = load_pdf_bytes(PDF_BASE_PATH)
    except FileNotFoundError:
        st.warning(f"Arquivo base '{PDF_BASE_PATH}' não encontrado. Envie abaixo.")
        up = st.file_uploader("📎 Envie o RAT MAM.pdf", type=["pdf"], key="base_pdf")
        if up is not None:
            base_bytes = up.read()
    if base_bytes is None:
        st.stop()

    try:
        doc = fitz.open(stream=base_bytes, filetype="pdf")
        page = doc[0]

        # ===== TOPO =====
        insert_right_of(page, ["Cliente:", "CLIENTE:"], cliente_nome, dx=6, dy=1)
        insert_right_of(page, ["Endereço:", "ENDEREÇO:"], endereco, dx=6, dy=1)
        insert_right_of(page, ["Bairro:", "BAIRRO:"],     bairro,     dx=6, dy=1)
        insert_right_of(page, ["Cidade:", "CIDADE:"],     cidade,     dx=6, dy=1)

        insert_right_of(page, ["Contato:"], contato_nome, dx=6, dy=1)
        # RG do contato: "descer um pouco", centralização já estava ok
        r_cont = search_once(page, ["Contato:"])
        if r_cont and contato_rg:
            rg_rects = search_all(page, "RG:")
            if rg_rects:
                cy = r_cont.y0 + r_cont.height/2
                rg_best = min(rg_rects, key=lambda rr: abs((rr.y0+rr.height/2)-cy))
                x = rg_best.x1 + 6
                y = rg_best.y0 + rg_best.height/1.5 + 6  # desce um pouco
                page.insert_text((x, y), str(contato_rg), fontsize=10)
        insert_right_of(page, ["Telefone:", "TELEFONE:"], normalize_phone(contato_tel), dx=6, dy=1)

        # ===== Datas/Horas/KM =====
        # Data: mais à esquerda (~ -70 pt ≈ -2.5 cm) e um pouco abaixo (+6 pt)
        insert_right_of(page, ["Data do atendimento:", "Data do Atendimento:"],
                        data_atend.strftime("%d/%m/%Y"), dx=-70, dy=6)
        insert_right_of(page, ["Hora Inicio:", "Hora Início:", "Hora inicio:"],
                        hora_ini.strftime("%H:%M"), dx=0, dy=3)
        insert_right_of(page, ["Hora Termino:", "Hora Término:", "Hora termino:"],
                        hora_fim.strftime("%H:%M"), dx=0, dy=3)
        insert_right_of(page, ["Distancia (KM) :", "Distância (KM) :"],
                        str(distancia_km), dx=0, dy=3)

        # ===== DESCRIÇÃO =====
        insert_textbox_below(page, ["DESCRIÇÃO DE ATENDIMENTO","DESCRICAO DE ATENDIMENTO"],
                             bloco_desc, box=(0, 20, 540, 240), fontsize=10, align=0)

        # ===== TÉCNICO =====
        # Nome do técnico: MUITO mais para baixo (~3 cm ≈ 85 pt) e 1 cm à esquerda
        # (30 cm excede 842 pt de altura da página; por isso limitei a ~3 cm para não sair do papel.
        #  Se quiser mais, me diga um valor entre 0–10 cm que ajusto aqui.)
        insert_right_of(page, ["TÉCNICO", "TECNICO"], tec_nome, dx=-(1*CM), dy=(3*CM))

        # RG do técnico: +5 cm para a direita e +6 pt para baixo a partir do rótulo "TÉCNICO RG:"
        rg_lbl = None
        for lbl in ["TÉCNICO RG:", "TÉCNICO  RG:", "TECNICO RG:"]:
            rg_lbl = search_once(page, [lbl])
            if rg_lbl:
                break
        if rg_lbl and tec_rg:
            x = rg_lbl.x1 + (5*CM)   # ~5 cm direita
            y = rg_lbl.y0 + rg_lbl.height/1.5 + 6
            page.insert_text((x, y), str(tec_rg), fontsize=10)

        # ===== Assinaturas (com quadro branco) =====
        # Técnico: 2 cm para a ESQUERDA e 1 cm para CIMA do retângulo anterior
        rect_tecnico = (110 - 2*CM, 0 - 1*CM, 330 - 2*CM, 54 - 1*CM)
        if sigtec_img is not None:
            r = search_once(page, ["ASSINATURA:", "Assinatura:"])
            if r:
                rect = fitz.Rect(r.x0 + rect_tecnico[0], r.y1 + rect_tecnico[1],
                                 r.x0 + rect_tecnico[2], r.y1 + rect_tecnico[3])
                buf = BytesIO(); sigtec_img.save(buf, format="PNG")  # terá retângulo branco, como pedido
                page.insert_image(rect, stream=buf.getvalue())

        # Cliente: 2 cm para CIMA do retângulo anterior do cliente
        rect_cliente = (110, 12 - 2*CM, 430, 94 - 2*CM)
        if sigcli_img is not None:
            r = search_once(page, ["DATA CARIMBO / ASSINATURA", "ASSINATURA CLIENTE", "CLIENTE"])
            if r:
                rect = fitz.Rect(r.x0 + rect_cliente[0], r.y1 + rect_cliente[1],
                                 r.x0 + rect_cliente[2], r.y1 + rect_cliente[3])
                buf = BytesIO(); sigcli_img.save(buf, format="PNG")
                page.insert_image(rect, stream=buf.getvalue())

        # ===== Nº CHAMADO — 2 cm mais à esquerda e um pouco mais baixo =====
        insert_right_of(page, [" Nº CHAMADO ", "Nº CHAMADO", "No CHAMADO"],
                        num_chamado, dx=-(2*CM), dy=10)

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
