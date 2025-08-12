import streamlit as st
from datetime import date, time
from PIL import Image
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from streamlit_drawable_canvas import st_canvas
import numpy as np

PDF_BASE = "RAT MAM.pdf"

st.set_page_config(page_title="Formulário RAT MAM", layout="centered")
st.title("📄 Preenchimento de RAT MAM")

# ---- Função para scanner via navegador ----
def barcode_scanner():
    scanner_code = """
    <script src="https://unpkg.com/html5-qrcode"></script>
    <div id="reader" width="300px"></div>
    <script>
        function onScanSuccess(decodedText, decodedResult) {
            const streamlitInput = window.parent.document.querySelector('textarea[aria-label="Números de Série"]');
            if (streamlitInput) {
                streamlitInput.value += "\\n" + decodedText;
                streamlitInput.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }
        function onScanFailure(error) {}
        let html5QrcodeScanner = new Html5QrcodeScanner(
            "reader", { fps: 10, qrbox: 250 });
        html5QrcodeScanner.render(onScanSuccess, onScanFailure);
    </script>
    """
    st.components.v1.html(scanner_code, height=400)

# ---- Campos do formulário ----
numero_chamado = st.text_input("Número do chamado")
data_atendimento = st.date_input("Data do atendimento", value=date.today())
hora_inicio = st.time_input("Hora início", value=time(8, 0))
hora_termino = st.time_input("Hora término", value=time(17, 0))
distancia_km = st.number_input("Distância (KM)", min_value=0.0, step=0.1)

st.subheader("Descrição de atendimento")

modelo = st.text_input("Modelo do equipamento")
seriais = st.text_area("Números de Série (digite ou escaneie)")

if st.button("📷 Escanear código de barras/QR Code"):
    barcode_scanner()

descricao = st.text_area("Descrição da atividade")
info_adicional = st.text_area("Informações adicionais")

st.subheader("Informações do Cliente")
cliente_nome = st.text_input("Nome")
cliente_doc = st.text_input("Documento (CPF/RG)")
cliente_tel = st.text_input("Telefone")

# ---- Assinatura direto na tela ----
st.subheader("Assinatura do Cliente (use o dedo no celular)")
canvas_result = st_canvas(
    fill_color="rgba(0, 0, 0, 0)",
    stroke_width=2,
    stroke_color="#000000",
    background_color="#FFFFFF",
    height=150,
    width=400,
    drawing_mode="freedraw",
    key="canvas",
)

# ---- Botão gerar PDF ----
if st.button("Gerar PDF Preenchido"):
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)
    can.setFont("Helvetica", 10)

    # Posicionamento aproximado (ajuste conforme PDF)
    can.drawString(400, 775, numero_chamado)
    can.drawString(130, 755, data_atendimento.strftime("%d/%m/%Y"))
    can.drawString(350, 755, hora_inicio.strftime("%H:%M"))
    can.drawString(450, 755, hora_termino.strftime("%H:%M"))
    can.drawString(530, 755, f"{distancia_km:.1f}")

    can.drawString(80, 720, f"Modelo: {modelo}")
    can.drawString(80, 700, seriais)
    can.drawString(80, 680, descricao)
    can.drawString(80, 660, info_adicional)

    can.drawString(100, 120, cliente_nome)
    can.drawString(300, 120, cliente_doc)
    can.drawString(450, 120, cliente_tel)

    # Adiciona assinatura desenhada
    if canvas_result.image_data is not None:
        img = Image.fromarray((canvas_result.image_data).astype(np.uint8))
        img = img.convert("RGB")
        img = img.resize((100, 50))
        can.drawImage(ImageReader(img), 450, 90)

    can.save()

    packet.seek(0)
    new_pdf = fitz.open(stream=packet.getvalue(), filetype="pdf")
    base_pdf = fitz.open(PDF_BASE)
    page = base_pdf[0]
    page.show_pdf_page(page.rect, new_pdf, 0)

    output_bytes = base_pdf.write()

    st.download_button(
        label="📥 Baixar PDF Preenchido",
        data=output_bytes,
        file_name=f"RAT_{numero_chamado}.pdf",
        mime="application/pdf"
    )

    st.success("✅ PDF gerado com sucesso!")





