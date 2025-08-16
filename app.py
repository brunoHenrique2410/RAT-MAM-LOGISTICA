import streamlit as st
from datetime import date, time
from io import BytesIO
from PIL import Image, ImageOps
import numpy as np

# -----------------------------------------------------------
# APP: RAT MAM - Preenchimento automático (sem dependências nativas)
# - Gera um overlay com ReportLab + mescla com pypdf
# - Scanner de código via câmera é opcional (pyzbar se existir)
# - Pronto para deploy remoto (Streamlit Cloud) no Python 3.13
# -----------------------------------------------------------

# Dependências puras (sem binários nativos)
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from pypdf import PdfReader, PdfWriter

# pyzbar é opcional: só ativa scanner se estiver disponível
try:
    from pyzbar.pyzbar import decode as zbar_decode
    HAS_ZBAR = True
except Exception:
    HAS_ZBAR = False

# -----------------------
# CONFIGURAÇÕES DO APP
# -----------------------
PDF_BASE_PATH = "RAT MAM.pdf"  # coloque o PDF base na mesma pasta do app
APP_TITLE = "RAT MAM - Preenchimento Automático (overlay pypdf+reportlab)"

st.set_page_config(page_title=APP_TITLE, layout="centered")
st.title("📄 " + APP_TITLE)
st.caption("Se o servidor não suportar bibliotecas nativas, este app funciona 100% com pypdf + reportlab. Scanner é opcional.")

# -----------------------
# HELPERS / UTILIDADES
# -----------------------
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

def summarize_text(t: str, max_chars: int = 400) -> str:
    t = " ".join(t.split())
    if len(t) <= max_chars:
        return t
    cut = t[:max_chars]
    last_dot = cut.rfind(". ")
    if last_dot > 120:
        return cut[: last_dot + 1] + " (resumo)"
    return cut.strip() + "… (resumo)"

def decode_barcodes_from_pil(img: Image.Image):
    """Decodifica 1D/QR com pyzbar, se existir; caso contrário, retorna []."""
    if not HAS_ZBAR:
        return []
    gray = ImageOps.grayscale(img)
    arr = np.array(gray)
    try:
        decoded = zbar_decode(arr)
        values = []
        for obj in decoded:
            try:
                values.append(obj.data.decode("utf-8"))
            except Exception:
                values.append(str(obj.data))
        # únicos preservando ordem
        return list(dict.fromkeys(values))
    except Exception:
        return []

def unique_merge(base_list, extra_list):
    """Une duas listas de strings, mantendo ordem e removendo duplicatas."""
    seen = set(base_list)
    out = list(base_list)
    for x in extra_list:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out

# -----------------------
# ESTADO DE SESSÃO
# -----------------------
if "serials" not in st.session_state:
    st.session_state.serials = []

# -----------------------
# FORMULÁRIO
# -----------------------
st.header("1) Dados do Chamado")
col1, col2 = st.columns(2)
with col1:
    num_chamado = st.text_input("Nº do chamado", placeholder="ex.: 123456")
    data_atend = st.date_input("Data do atendimento", value=date.today())
    hora_ini = st.time_input("Hora início", value=time(8, 0))
with col2:
    hora_fim = st.time_input("Hora término", value=time(10, 0))
    distancia_km = st.text_input("Distância (KM)", placeholder="ex.: 12,3")

st.header("2) Dados do Cliente (topo do PDF)")
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

# Seriais (manuais)
seriais_man = st.text_area("Seriais (um por linha)", placeholder="SN0012345\nSN00ABC678\n...")
if st.button("Aplicar seriais manuais"):
    parsed = [ln.strip() for ln in seriais_man.splitlines() if ln.strip()]
    st.session_state.serials = unique_merge([], parsed)
    st.success(f"{len(st.session_state.serials)} serial(is) aplicado(s).")

# Scanner de seriais por câmera (opcional)
if HAS_ZBAR:
    cam_barcode = st.camera_input("Capturar código de barras / QR (opcional)")
    if cam_barcode is not None:
        img = Image.open(cam_barcode)
        decoded = decode_barcodes_from_pil(img)
        if decoded:
            st.session_state.serials = unique_merge(st.session_state.serials, decoded)
            st.success(f"Detectados: {', '.join(decoded)}")
        else:
            st.info("Nenhum código detectado na imagem. Tente aproximar/centralizar.")
else:
    st.caption("Scanner desabilitado (pyzbar não instalado). Os seriais podem ser inseridos manualmente.")

# Mostra a lista atual de seriais
if st.session_state.serials:
    st.markdown("**Seriais atuais:**")
    for s in st.session_state.serials:
        st.write(f"• {s}")

atividade = st.text_area(
    "Descrição da atividade (palavras do técnico)",
    placeholder="Descreva o que foi feito: troca/configuração de equipamentos, testes, resultados etc.",
    height=120,
)
resumir = st.checkbox("Resumir automaticamente a descrição", value=True)
info_extra = st.text_area("Informações adicionais (opcional)", height=80)

st.header("4) Equipamento / Modelo / Nº de Série (linha dedicada no PDF)")
equipamento = st.text_input("Equipamento", placeholder="ex.: Access Point / Switch / Nobreak")
modelo = st.text_input("Modelo", placeholder="ex.: EAP-225 / SG3428MP / SMS XYZ")
serie_principal = st.text_input("Nº de Série (principal)", placeholder="ex.: SN12345678")

st.header("5) Dados do Técnico")
tec_nome = st.text_input("Técnico - Nome", placeholder="Seu nome")
tec_rg = st.text_input("Técnico - RG", placeholder="Documento do técnico")

st.header("6) Assinaturas")
st.markdown("**Assinatura do TÉCNICO** (upload ou foto)")
sig_tec_up = st.file_uploader("Upload assinatura do técnico (PNG/JPG)", type=["png", "jpg", "jpeg"], key="sigtec_up")
sig_tec_cam = st.camera_input("Fotografar assinatura do técnico (opcional)", key="sigtec_cam")

st.markdown("---")
st.markdown("**CLIENTE** — Nome legível, Documento, Telefone e Assinatura")
cli_nome_legivel = st.text_input("Cliente - Nome legível", value=cliente_nome)
cli_rg = st.text_input("Cliente - Documento (RG/CPF)")
cli_tel = st.text_input("Cliente - Telefone", value=contato_tel, placeholder="(xx) xxxxx-xxxx")
sig_cli_up = st.file_uploader("Upload assinatura do cliente (PNG/JPG)", type=["png", "jpg", "jpeg"], key="sigcli_up")
sig_cli_cam = st.camera_input("Fotografar assinatura do cliente (opcional)", key="sigcli_cam")

# Montagem do bloco de descrição
serials_text = ", ".join(st.session_state.serials) if st.session_state.serials else ""
atividade_text = summarize_text(atividade) if resumir else atividade
desc_bloc = ""
if serials_text:
    desc_bloc += f"SERIAIS: {serials_text}\n"
if (atividade_text or "").strip():
    desc_bloc += f"ATIVIDADE: {atividade_text.strip()}\n"
if (info_extra or "").strip():
    desc_bloc += f"INFO ADICIONAIS: {info_extra.strip()}\n"

# -----------------------
# CALIBRAÇÃO (overlay)
# -----------------------
with st.expander("⚙️ Calibração (apenas se o layout sair fora do lugar)", expanded=False):
    st.write("Unidade: pontos (1 pt ≈ 0,35 mm). A4 = 595 x 842 pt.")
    off_top_x = st.number_input("Ajuste X (Topo: Cliente/Endereço/Bairro/Cidade/Contato/RG/Telefone)", -200, 200, 0)
    off_top_y = st.number_input("Ajuste Y (Topo)", -200, 200, 0)
    off_desc_x = st.number_input("Ajuste X (Bloco DESCRIÇÃO)", -200, 200, 0)
    off_desc_y = st.number_input("Ajuste Y (Bloco DESCRIÇÃO)", -200, 200, 0)
    off_eqp_x = st.number_input("Ajuste X (Linha EQUIPAMENTO/MODELO/SÉRIE)", -200, 200, 0)
    off_eqp_y = st.number_input("Ajuste Y (Linha EQUIPAMENTO/MODELO/SÉRIE)", -200, 200, 0)
    off_tec_x = st.number_input("Ajuste X (Técnico/RG/Assinatura)", -200, 200, 0)
    off_tec_y = st.number_input("Ajuste Y (Técnico/RG/Assinatura)", -200, 200, 0)
    off_cli_x = st.number_input("Ajuste X (Cliente rodapé: Nome/RG/Tel/Assinatura)", -200, 200, 0)
    off_cli_y = st.number_input("Ajuste Y (Cliente rodapé)", -200, 200, 0)
    off_chamado_x = st.number_input("Ajuste X (Nº CHAMADO)", -200, 200, 0)
    off_chamado_y = st.number_input("Ajuste Y (Nº CHAMADO)", -200, 200, 0)

# -----------------------
# GERAÇÃO DO PDF
# -----------------------
def build_overlay_pdf(base_bytes: bytes) -> bytes:
    """
    Cria um overlay com reportlab (posições aproximadas) e mescla na 1ª página do PDF base.
    Padrões já estão ajustados para um layout típico do RAT MAM; use a calibração para ajustes finos.
    """
    # Página A4 (595 x 842 pt)
    packet = BytesIO()
    c = rl_canvas.Canvas(packet, pagesize=A4)
    c.setFont("Helvetica", 10)

    # --- Topo (Cliente/Endereço/Bairro/Cidade/Contato/RG/Telefone/Data/Horas/KM)
    x0, y0 = 80 + off_top_x, 780 + off_top_y
    line = 14  # espaçamento vertical entre linhas

    # Cliente / Endereço / Bairro / Cidade
    c.drawString(x0, y0, str(cliente_nome or ""))
    c.drawString(x0, y0 - line, str(endereco or ""))
    c.drawString(x0, y0 - 2*line, str(bairro or ""))
    c.drawString(x0 + 260, y0 - 2*line, str(cidade or ""))

    # Contato / RG / Telefone
    c.drawString(x0, y0 - 3*line, str(contato_nome or ""))
    c.drawString(x0 + 180, y0 - 3*line, str(contato_rg or ""))
    c.drawString(x0 + 330, y0 - 3*line, normalize_phone(contato_tel or ""))

    # Data do atendimento / Hora início / Hora término / Distância (KM)
    c.drawString(x0,       y0 - 4*line, (data_atend.strftime("%d/%m/%Y") if data_atend else ""))
    c.drawString(x0 + 160, y0 - 4*line, (hora_ini.strftime("%H:%M") if hora_ini else ""))
    c.drawString(x0 + 260, y0 - 4*line, (hora_fim.strftime("%H:%M") if hora_fim else ""))
    c.drawString(x0 + 360, y0 - 4*line, str(distancia_km or ""))

    # --- Descrição (caixa grande)
    x_desc, y_desc = 60 + off_desc_x, 610 + off_desc_y
    w_desc, h_desc = 480, 150
    if desc_bloc:
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, Frame
        from reportlab.lib.enums import TA_LEFT
        styles = getSampleStyleSheet()
        styleN = styles["Normal"]
        styleN.fontName = "Helvetica"
        styleN.fontSize = 10
        styleN.leading = 12
        styleN.alignment = TA_LEFT
        frame = Frame(x_desc, y_desc - h_desc + 150, w_desc, h_desc, showBoundary=0)
        story = [Paragraph(desc_bloc.replace("\n", "<br/>"), styleN)]
        frame.addFromList(story, c)

    # --- Linha: EQUIPAMENTO / MODELO / Nº DE SÉRIE
    x_eqp, y_eqp = 70 + off_eqp_x, 560 + off_eqp_y
    c.drawString(x_eqp, y_eqp, str(equipamento or ""))
    c.drawString(x_eqp + 180, y_eqp, str(modelo or ""))
    serie_final = serie_principal or (st.session_state.serials[0] if st.session_state.serials else "")
    c.drawString(x_eqp + 360, y_eqp, str(serie_final))

    # --- Técnico (nome e RG) + assinatura do técnico
    x_tec, y_tec = 70 + off_tec_x, 520 + off_tec_y
    c.drawString(x_tec, y_tec, str(tec_nome or ""))
    c.drawString(x_tec + 180, y_tec, str(tec_rg or ""))

    sigtec_bytes = None
    if sig_tec_up is not None:
        sigtec_bytes = sig_tec_up.read()
    elif sig_tec_cam is not None:
        sigtec_bytes = sig_tec_cam.getvalue()
    if sigtec_bytes:
        try:
            c.drawImage(ImageReader(BytesIO(sigtec_bytes)), x_tec + 310, y_tec - 10,
                        width=160, height=40, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    # --- Cliente (rodapé): Nome legível / RG / Telefone + assinatura do cliente
    x_cli, y_cli = 70 + off_cli_x, 450 + off_cli_y
    c.drawString(x_cli, y_cli, f"NOME LEGÍVEL: {cli_nome_legivel or ''}")
    c.drawString(x_cli, y_cli - line, f"RG/CPF: {cli_rg or ''}")
    c.drawString(x_cli, y_cli - 2*line, f"Telefone: {normalize_phone(cli_tel or '')}")

    sigcli_bytes = None
    if sig_cli_up is not None:
        sigcli_bytes = sig_cli_up.read()
    elif sig_cli_cam is not None:
        sigcli_bytes = sig_cli_cam.getvalue()
    if sigcli_bytes:
        try:
            c.drawImage(ImageReader(BytesIO(sigcli_bytes)), x_cli + 260, y_cli - 10,
                        width=220, height=60, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    # --- Nº CHAMADO (campo inferior direito aproximado)
    x_ch, y_ch = 420 + off_chamado_x, 430 + off_chamado_y
    c.drawString(x_ch, y_ch, str(num_chamado or ""))

    # Finaliza overlay
    c.showPage()
    c.save()
    packet = BytesIO(packet.getvalue())

    # Mescla overlay na página 1 do PDF base
    overlay_pdf = PdfReader(packet)
    base_reader = PdfReader(BytesIO(base_bytes))
    writer = PdfWriter()

    # 1ª página com overlay
    base_page = base_reader.pages[0]
    overlay_page = overlay_pdf.pages[0]
    base_page.merge_page(overlay_page)
    writer.add_page(base_page)

    # Demais páginas (se existirem)
    for i in range(1, len(base_reader.pages)):
        writer.add_page(base_reader.pages[i])

    out = BytesIO()
    writer.write(out)
    return out.getvalue()

# Botão principal
if st.button("🧾 Gerar PDF preenchido", type="primary"):
    # Tenta carregar o PDF base do disco; se não existir, pede upload
    base_bytes = None
    try:
        base_bytes = load_pdf_bytes(PDF_BASE_PATH)
    except FileNotFoundError:
        st.warning(f"Arquivo base '{PDF_BASE_PATH}' não encontrado. Envie abaixo.")
        base_upload = st.file_uploader("📎 Envie o arquivo base RAT MAM.pdf", type=["pdf"], key="base_pdf")
        if base_upload is not None:
            base_bytes = base_upload.read()

    if base_bytes is None:
        st.stop()

    try:
        pdf_out = build_overlay_pdf(base_bytes)
        st.success("PDF gerado com sucesso!")
        st.download_button(
            "⬇️ Baixar RAT preenchido",
            data=pdf_out,
            file_name=f"RAT_MAM_preenchido_{(num_chamado or 'sem_num')}.pdf",
            mime="application/pdf",
        )
    except Exception as e:
        st.error(f"Falha ao gerar PDF: {e}")
        st.exception(e)

st.markdown("---")
st.caption("Se alguma posição sair fora, ajuste a seção ⚙️ Calibração e me diga o deslocamento ideal para eu fixar no código.")
