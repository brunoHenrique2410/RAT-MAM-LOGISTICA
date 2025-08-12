import base64
import io
from datetime import date, time

import fitz  # PyMuPDF
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas  # <<-- IMPORT CORRIGIDO
import streamlit as st

PDF_BASE = "RAT MAM.pdf"

st.set_page_config(page_title="Formulário RAT MAM", layout="centered")
st.title("📄 Preenchimento de RAT MAM")

# ------------------------ Estilos p/ esconder campos técnicos ------------------------
st.markdown("""
<style>
/* esconde os campos auxiliares */
[data-testid="stTextInput"] label:has(+ div input[aria-label="Assinatura (dataurl)"]),
div:has(> input[aria-label="Assinatura (dataurl)"]) { display:none !important; }
</style>
""", unsafe_allow_html=True)

# ------------------------ Componentes HTML (Scanner e Assinatura) ------------------------
def barcode_scanner_component(target_aria_label: str):
    """
    Abre scanner 1D (QuaggaJS) e QR (html5-qrcode).
    Ao clicar "Inserir no formulário", escreve nos 'textarea' com aria-label = target_aria_label.
    """
    html = f"""
    <div style="display:flex; gap:16px; flex-wrap:wrap">
      <div style="min-width:320px">
        <h4 style="margin:4px 0">Scanner Código de Barras (1D)</h4>
        <video id="video" width="320" height="200" style="border:1px solid #999"></video>
        <div style="margin-top:6px">
          <button id="start1d">Iniciar</button>
          <button id="stop1d">Parar</button>
        </div>
        <pre id="out1d" style="background:#111;color:#0f0;padding:6px;min-height:60px;white-space:pre-wrap"></pre>
      </div>

      <div style="min-width:320px">
        <h4 style="margin:4px 0">Scanner QR (opcional)</h4>
        <div id="reader" style="width:320px"></div>
        <div style="margin-top:6px">
          <button id="stopqr">Parar QR</button>
        </div>
        <pre id="outqr" style="background:#111;color:#0f0;padding:6px;min-height:60px;white-space:pre-wrap"></pre>
      </div>
    </div>

    <div style="margin-top:10px">
      <button id="send">Inserir no formulário</button>
    </div>

    <script src="https://unpkg.com/@ericblade/quagga2/dist/quagga.js"></script>
    <script src="https://unpkg.com/html5-qrcode"></script>
    <script>
      const vals = new Set();
      function addVal(v, box) {{
        if (!v) return;
        if (!vals.has(v)) {{ vals.add(v); }}
        document.getElementById(box).textContent = Array.from(vals).join("\\n");
      }}

      // ---- 1D BARCODE (Quagga) ----
      let running1d = false;
      function start1D(){{
        if (running1d) return;
        running1d = true;
        Quagga.init({{
          inputStream: {{
            type: "LiveStream",
            target: document.querySelector('#video'),
            constraints: {{ facingMode: "environment" }}
          }},
          locator: {{ patchSize: "medium", halfSample: true }},
          numOfWorkers: 0,
          decoder: {{
            readers: ["code_128_reader","ean_reader","ean_8_reader","code_39_reader","upc_reader","upc_e_reader"]
          }}
        }}, function(err){{
          if (err) {{ console.log(err); running1d=false; return; }}
          Quagga.start();
        }});
        Quagga.onDetected(function(result){{
          const code = result?.codeResult?.code;
          if (code) addVal(code, "out1d");
        }});
      }}
      function stop1D(){{ if (running1d){{ Quagga.stop(); running1d=false; }} }}
      document.getElementById("start1d").onclick = start1D;
      document.getElementById("stop1d").onclick  = stop1D;

      // ---- QR (html5-qrcode) ----
      let qrScanner = null;
      function startQR(){{
        if (qrScanner) return;
        qrScanner = new Html5Qrcode("reader");
        Html5Qrcode.getCameras().then(cams => {{
          const id = cams && cams.length ? cams[cams.length-1].id : undefined;
          qrScanner.start(
            id || {{ facingMode: "environment" }},
            {{ fps: 10, qrbox: 200 }},
            txt => addVal(txt, "outqr"),
            _ => {{}}
          );
        }}).catch(_=>{});
      }}
      function stopQR(){{ if (qrScanner){{ qrScanner.stop().then(()=>{{qrScanner.clear(); qrScanner=null;}}); }} }}
      startQR();
      document.getElementById("stopqr").onclick = stopQR;

      // ---- Enviar p/ textarea alvo ----
      document.getElementById("send").onclick = function(){{
        const s = Array.from(vals).join("\\n");
        const ta = window.parent.document.querySelector('textarea[aria-label="{target_aria_label}"]');
        if (ta) {{
          if (ta.value && !ta.value.endsWith("\\n")) ta.value += "\\n";
          ta.value += s;
          ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
          alert("Códigos inseridos no formulário.");
        }} else {{
          alert("Campo de destino não encontrado.");
        }}
      }};
    </script>
    """
    st.components.v1.html(html, height=520)


def signature_pad_component(hidden_target_aria_label: str):
    """
    Exibe SignaturePad; ao clicar 'Usar assinatura', grava o dataURL PNG
    em um input hidden do Streamlit (text_input escondido) identificado por aria-label=hidden_target_aria_label.
    """
    html = f"""
    <style>
      #sig-wrap {{border:1px dashed #999; width:400px; height:160px; position:relative; background:#fff;}}
      #sig {{width:100%; height:100%;}}
      .sig-btns {{margin-top:6px; display:flex; gap:6px;}}
    </style>
    <div>
      <div id="sig-wrap"><canvas id="sig"></canvas></div>
      <div class="sig-btns">
        <button id="clear">Limpar</button>
        <button id="use">Usar assinatura</button>
      </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/signature_pad@4.1.7/dist/signature_pad.umd.min.js"></script>
    <script>
      const canvas = document.getElementById('sig');
      const wrapper = document.getElementById('sig-wrap');
      function resize(){{
        const ratio = Math.max(window.devicePixelRatio || 1, 1);
        canvas.width = wrapper.clientWidth * ratio;
        canvas.height = wrapper.clientHeight * ratio;
        canvas.getContext("2d").scale(ratio, ratio);
      }}
      window.addEventListener("resize", resize);
      resize();
      const pad = new SignaturePad(canvas, {{backgroundColor: 'rgba(255,255,255,1)'}});
      document.getElementById('clear').onclick = () => pad.clear();
      document.getElementById('use').onclick = () => {{
        if (pad.isEmpty()) {{ alert("Faça a assinatura."); return; }}
        const dataUrl = pad.toDataURL("image/png");
        const input = window.parent.document.querySelector('input[aria-label="{hidden_target_aria_label}"]');
        if (input) {{
          input.value = dataUrl;
          input.dispatchEvent(new Event('input', {{ bubbles: true }}));
          alert("Assinatura anexada.");
        }} else {{
          alert("Campo hidden de assinatura não encontrado.");
        }}
      }};
    </script>
    """
    st.components.v1.html(html, height=230)

# ------------------------------ Formulário ------------------------------
numero_chamado = st.text_input("Número do chamado")
data_atendimento = st.date_input("Data do atendimento", value=date.today())
hora_inicio = st.time_input("Hora início", value=time(8, 0))
hora_termino = st.time_input("Hora término", value=time(17, 0))
distancia_km = st.number_input("Distância (KM)", min_value=0.0, step=0.1)

st.subheader("Descrição de atendimento")
modelo = st.text_input("Modelo do equipamento")

# Digitando ou escaneando seriais (ambos)
SERIAIS_LABEL = "Números de Série (digite manualmente, um por linha)"
seriais_text = st.text_area(SERIAIS_LABEL, placeholder="Ex.: ABC12345\nDEF67890")
if st.checkbox("📷 Usar scanner de código de barras/QR"):
    barcode_scanner_component(SERIAIS_LABEL)

descricao = st.text_area("Descrição da atividade")
info_adicional = st.text_area("Informações adicionais")

st.subheader("Informações do Cliente")
cliente_nome = st.text_input("Nome")
cliente_doc = st.text_input("Documento (CPF/RG)")
cliente_tel = st.text_input("Telefone")

# Campo hidden onde o JS grava a assinatura (dataURL)
sig_hidden_label = "Assinatura (dataurl)"
sig_dataurl = st.text_input(sig_hidden_label, value="", key="sig_dataurl_key")
st.subheader("Assinatura do Cliente")
signature_pad_component(sig_hidden_label)

# ------------------------------ Geração do PDF ------------------------------
if st.button("Gerar PDF Preenchido"):
    # Overlay PDF com ReportLab
    packet = io.BytesIO()
    can = Canvas(packet, pagesize=A4)  # <<-- agora Canvas está definido
    can.setFont("Helvetica", 10)

    # A4 ~ 595 x 842 pt; ajuste fino conforme seu PDF
    can.drawString(400, 775, (numero_chamado or ""))
    can.drawString(130, 755, data_atendimento.strftime("%d/%m/%Y"))
    can.drawString(350, 755, hora_inicio.strftime("%H:%M"))
    can.drawString(450, 755, hora_termino.strftime("%H:%M"))
    can.drawString(530, 755, f"{distancia_km:.1f}")

    # Modelo e Seriais (multi-linha)
    can.drawString(80, 720, f"Modelo: {modelo or ''}")
    y = 700
    for line in (seriais_text or "").splitlines():
        can.drawString(80, y, line[:100])
        y -= 14
        if y < 620:
            break

    can.drawString(80, 610, (descricao or "")[:300])
    can.drawString(80, 590, (info_adicional or "")[:300])

    # Cliente
    can.drawString(100, 120, cliente_nome or "")
    can.drawString(300, 120, cliente_doc or "")
    can.drawString(450, 120, cliente_tel or "")

    # Assinatura (dataURL -> PNG)
    if isinstance(sig_dataurl, str) and sig_dataurl.startswith("data:image"):
        try:
            b64 = sig_dataurl.split(",")[1]
            sig_bytes = base64.b64decode(b64)
            sig_img = Image.open(io.BytesIO(sig_bytes)).convert("RGB")
            sig_img = sig_img.resize((120, 60))
            can.drawImage(ImageReader(sig_img), 450, 90)
        except Exception as e:
            st.warning(f"Assinatura não aplicada (erro ao processar imagem): {e}")

    can.save()

    # Mesclar com o PDF base
    packet.seek(0)
    overlay_pdf = fitz.open(stream=packet.getvalue(), filetype="pdf")
    base_pdf = fitz.open(PDF_BASE)
    page = base_pdf[0]
    page.show_pdf_page(page.rect, overlay_pdf, 0)

    output_bytes = base_pdf.write()
    st.download_button(
        "📥 Baixar PDF Preenchido",
        data=output_bytes,
        file_name=f"RAT_{(numero_chamado or 'sem_numero')}.pdf",
        mime="application/pdf",
    )
    st.success("✅ PDF gerado com sucesso!")
