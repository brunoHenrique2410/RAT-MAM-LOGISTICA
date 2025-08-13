
import streamlit as st
from datetime import datetime, date, time
from io import BytesIO
import fitz  # PyMuPDF
from PIL import Image, ImageOps
import numpy as np

# ---- CONFIG ----
PDF_BASE_PATH = "RAT MAM.pdf"  # deixe este arquivo na mesma pasta no deploy
APP_TITLE = "RAT MAM - Preenchimento Automático"

st.set_page_config(page_title=APP_TITLE, layout="centered")
st.title("📄 " + APP_TITLE)

st.caption("Preencha os campos abaixo. No final, clique em **Gerar PDF** para baixar o RAT preenchido.")

# ---- Helpers ----
@st.cache_data
def load_pdf_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()

def search_once(page, text):
    res = page.search_for(text, hit_max=1)
    if res:
        return res[0]  # fitz.Rect
    return None

def put_right_of_label(page, label_text, content, dx=8, dy=0, fontsize=10):
    """Escreve o 'content' à direita do rótulo 'label_text' na mesma linha."""
    r = search_once(page, label_text)
    if not r or not content:
        return
    x = r.x1 + dx
    y = r.y0 + r.height/1.5 + dy  # alinhar com baseline aproximado
    page.insert_text((x, y), str(content), fontsize=fontsize)

def put_at(page, anchor_text, content, rel_rect=(0, 14, 400, 120), fontsize=10, align=0):
    """Insere um bloco de texto em uma caixa relativa ao 'anchor_text'."""
    r = search_once(page, anchor_text)
    if not r or not content:
        return
    rect = fitz.Rect(r.x0 + rel_rect[0], r.y1 + rel_rect[1], r.x0 + rel_rect[2], r.y1 + rel_rect[3])
    page.insert_textbox(rect, str(content), fontsize=fontsize, align=align)

def place_signature(page, anchor_text, image_bytes, rel_rect=(0, 10, 240, 90)):
    """Coloca uma assinatura (PNG/JPG) abaixo/ao lado do anchor_text."""
    if not image_bytes:
        return
    r = search_once(page, anchor_text)
    if not r:
        return
    rect = fitz.Rect(r.x0 + rel_rect[0], r.y1 + rel_rect[1], r.x0 + rel_rect[2], r.y1 + rel_rect[3])
    try:
        page.insert_image(rect, stream=image_bytes)
    except Exception:
        # Tenta converter para RGB e comprimir
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        out = BytesIO()
        img.save(out, format="PNG")
        page.insert_image(rect, stream=out.getvalue())

def normalize_phone(s: str) -> str:
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return s

def summarize_text(t: str, max_chars: int = 400) -> str:
    t = " ".join(t.split())
    if len(t) <= max_chars:
        return t
    # Corte elegante por sentença
    cut = t[:max_chars]
    last_dot = cut.rfind(". ")
    if last_dot > 120:
        return cut[: last_dot + 1] + " (resumo)"
    return cut.strip() + "… (resumo)"

def decode_barcodes_from_pil(img: Image.Image):
    """Decode 1D/QR usando pyzbar se disponível (opcional)."""
    try:
        from pyzbar.pyzbar import decode
    except Exception:
        return []
    # Converter para cinza melhora a leitura
    gray = ImageOps.grayscale(img)
    arr = np.array(gray)
    try:
        decoded = decode(arr)
        values = []
        for obj in decoded:
            try:
                values.append(obj.data.decode("utf-8"))
            except Exception:
                values.append(str(obj.data))
        return list(dict.fromkeys(values))  # únicos, preservando ordem
    except Exception:
        return []

# ---- Sidebar: Deploy Info ----
with st.sidebar:
    st.subheader("👥 Uso por vários técnicos (remoto)")
    st.markdown(
        "- Publique no **Streamlit Community Cloud** ou **Hugging Face Spaces**.\n"
        "- Inclua o **RAT MAM.pdf** no repositório/app.\n"
        "- Dependências em `requirements.txt`.\n"
        "- A webcam funciona pelo navegador: use **Capturar Código/Assinatura**.\n"
    )
    st.caption("Dica: ative HTTPS no deploy para permitir câmera em celulares.")

# ---- Form Inputs ----
st.header("1) Dados do Chamado")
col1, col2 = st.columns(2)
with col1:
    num_chamado = st.text_input("Nº do chamado", placeholder="ex.: 123456")
    data_atend = st.date_input("Data do atendimento", value=date.today())
    hora_ini = st.time_input("Hora início", value=time(8, 0))
with col2:
    hora_fim = st.time_input("Hora término", value=time(10, 0))
    distancia_km = st.text_input("Distância (KM)", placeholder="ex.: 12,3")

st.header("2) Dados do Cliente (topo)")
c1, c2 = st.columns(2)
with c1:
    cliente_nome = st.text_input("Cliente (Razão/Nome)", placeholder="ex.: Escola Municipal ABC")
    endereco = st.text_input("Endereço", placeholder="Rua X, nº Y")
    bairro = st.text_input("Bairro", placeholder="Centro")
with c2:
    cidade = st.text_input("Cidade", placeholder="Fortaleza - CE")
    contato_nome = st.text_input("Contato", placeholder="Responsável no local")
    contato_rg = st.text_input("RG do Contato", placeholder="RG/Documento")
    contato_tel = st.text_input("Telefone do Contato", placeholder="(xx) xxxxx-xxxx")

st.header("3) Descrição de Atendimento")
# Scanner de seriais
st.markdown("**Seriais** (adicione manualmente ou use câmera)")
serials = st.tags_input("Seriais (enter para adicionar)", suggestions=[])

cam_barcode = st.camera_input("Capturar código de barras / QR (opcional)")
if cam_barcode is not None:
    img = Image.open(cam_barcode)
    decoded = decode_barcodes_from_pil(img)
    if decoded:
        st.success(f"Códigos detectados: {', '.join(decoded)}")
        serials = list(dict.fromkeys(serials + decoded))
    else:
        st.warning("Nenhum código detectado na imagem. Tente aproximar/centralizar.")

atividade = st.text_area("Descrição da atividade (palavras do técnico)",
                         placeholder="Descreva o que foi feito, troca de equipamentos, configurações, testes, etc.",
                         height=120)
resumir = st.checkbox("Resumir automaticamente a descrição", value=True)
info_extra = st.text_area("Informações adicionais (opcional)", height=80)

st.header("4) Equipamento / Modelo / Nº de Série (linha dedicada)")
equipamento = st.text_input("Equipamento", placeholder="ex.: Access Point / Switch / Nobreak")
modelo = st.text_input("Modelo", placeholder="ex.: EAP-225 / SG3428MP / SMS XYZ")
serie_principal = st.text_input("Nº de Série (principal)", placeholder="ex.: SN12345678")

st.header("5) Dados do Técnico")
tec_nome = st.text_input("Técnico - Nome", placeholder="Seu nome")
tec_rg = st.text_input("Técnico - RG", placeholder="Documento do técnico")

st.header("6) Assinaturas")
st.markdown("**Assinatura do TÉCNICO** (faça upload de uma imagem com a assinatura ou fotografe no papel)")
sig_tec_up = st.file_uploader("Upload assinatura do técnico (PNG/JPG)", type=["png", "jpg", "jpeg"], key="sigtec_up")
sig_tec_cam = st.camera_input("Fotografar assinatura do técnico (opcional)", key="sigtec_cam")

st.markdown("---")
st.markdown("**CLIENTE** — Nome, Documento, Telefone e Assinatura")
cli_nome_legivel = st.text_input("Cliente - Nome legível", value=cliente_nome)
cli_rg = st.text_input("Cliente - Documento (RG/CPF)")
cli_tel = st.text_input("Cliente - Telefone", value=contato_tel, placeholder="(xx) xxxxx-xxxx")
sig_cli_up = st.file_uploader("Upload assinatura do cliente (PNG/JPG)", type=["png", "jpg", "jpeg"], key="sigcli_up")
sig_cli_cam = st.camera_input("Fotografar assinatura do cliente (opcional)", key="sigcli_cam")

st.markdown("---")

# ---- Montagem do texto da descrição ----
serials_text = ", ".join(serials) if serials else ""
atividade_text = summarize_text(atividade) if resumir else atividade
desc_bloc = ""
if serials_text:
    desc_bloc += f"SERIAIS: {serials_text}\n"
if atividade_text.strip():
    desc_bloc += f"ATIVIDADE: {atividade_text.strip()}\n"
if info_extra.strip():
    desc_bloc += f"INFO ADICIONAIS: {info_extra.strip()}\n"

# ---- Botão Gerar PDF ----
if st.button("🧾 Gerar PDF preenchido", type="primary"):
    # Carrega base
    try:
        base_bytes = load_pdf_bytes(PDF_BASE_PATH)
    except FileNotFoundError:
        st.error(f"Arquivo base '{PDF_BASE_PATH}' não encontrado. Faça upload abaixo.")
        base_bytes = None

    if base_bytes is None:
        base_upload = st.file_uploader("📎 Envie o arquivo base RAT MAM.pdf", type=["pdf"], key="base_pdf")
        st.stop()

    doc = fitz.open(stream=base_bytes, filetype="pdf")
    page = doc[0]

    # --- Campos topo
    put_right_of_label(page, "Cliente:", cliente_nome)
    put_right_of_label(page, "Endereço:", endereco)
    put_right_of_label(page, "Bairro:", bairro)
    put_right_of_label(page, "Cidade:", cidade)

    put_right_of_label(page, "Contato:", contato_nome)
    put_right_of_label(page, "RG:", contato_rg)
    put_right_of_label(page, "Telefone:", normalize_phone(contato_tel))

    # --- Data / Horas / Distância
    data_fmt = data_atend.strftime("%d/%m/%Y")
    put_right_of_label(page, "Data do atendimento:", data_fmt)
    put_right_of_label(page, "Hora Inicio:", hora_ini.strftime("%H:%M"))
    put_right_of_label(page, "Hora Termino:", hora_fim.strftime("%H:%M"))
    put_right_of_label(page, "Distancia (KM)", distancia_km)

    # --- Bloco grande: DESCRIÇÃO DE ATENDIMENTO
    if desc_bloc:
        put_at(page, "DESCRIÇÃO DE ATENDIMENTO", desc_bloc, rel_rect=(0, 20, 540, 240), fontsize=10, align=0)

    # --- Linha: EQUIPAMENTO / MODELO / Nº DE SERIE
    put_right_of_label(page, "EQUIPAMENTO:", equipamento)
    put_right_of_label(page, "MODELO:", modelo)
    put_right_of_label(page, "Nº DE SERIE:", serie_principal if serie_principal else (serials[0] if serials else ""))

    # --- Técnico / RG / Assinatura
    put_right_of_label(page, "TÉCNICO", tec_nome)
    put_right_of_label(page, "RG:", tec_rg)  # Nota: há mais de um "RG:" no documento; este colocará à direita do primeiro match após topo
    # Assinatura do técnico (imagem) próxima ao label "ASSINATURA:" (mesma linha do técnico)
    sigtec_bytes = None
    if sig_tec_up is not None:
        sigtec_bytes = sig_tec_up.read()
    elif sig_tec_cam is not None:
        sigtec_bytes = sig_tec_cam.getvalue()
    place_signature(page, "ASSINATURA:", sigtec_bytes, rel_rect=(180, -10, 380, 60))

    # --- CLIENTE (nome legível, RG, telefone, assinatura) próximo ao rótulo "CLIENTE"
    put_at(page, "CLIENTE", f"NOME LEGÍVEL: {cli_nome_legivel}\nRG/CPF: {cli_rg}\nTelefone: {normalize_phone(cli_tel)}",
           rel_rect=(0, 10, 300, 90), fontsize=10, align=0)
    sigcli_bytes = None
    if sig_cli_up is not None:
        sigcli_bytes = sig_cli_up.read()
    elif sig_cli_cam is not None:
        sigcli_bytes = sig_cli_cam.getvalue()
    place_signature(page, "CLIENTE", sigcli_bytes, rel_rect=(310, 10, 560, 90))

    # --- Nº CHAMADO (rodapé/lado direito)
    put_right_of_label(page, "Nº CHAMADO", num_chamado, dx=12)

    # --- Senha Mam / Fornecida Por (opcionais - não coletados aqui; pode-se incluir depois)
    # Exemplo de como preencher se quiser:
    # put_right_of_label(page, "Senha Mam:", "XXXXXX")
    # put_right_of_label(page, "Fornecida Por", "Fulano")

    # --- Exporta
    out = BytesIO()
    doc.save(out)
    doc.close()

    st.success("PDF gerado com sucesso!")
    st.download_button("⬇️ Baixar RAT preenchido", data=out.getvalue(), file_name=f"RAT_MAM_preenchido_{num_chamado or 'sem_num'}.pdf", mime="application/pdf")



