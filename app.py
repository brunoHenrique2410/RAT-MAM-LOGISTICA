import base64
import io
from datetime import date, time

from PIL import Image
import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from pypdf import PdfReader, PdfWriter

PDF_BASE = "RAT MAM.pdf"

st.set_page_config(page_title="Formulário RAT MAM", layout="centered")
st.title("📄 Preenchimento de RAT MAM")

# ---------- CSS: esconde campo técnico (assinatura) ----------
st.markdown("""
<style>
/* Esconde o text_input onde guardamos o dataURL da assinatura */
div:has(> input[aria-label="Assinatura (dataurl)"]) { display:none !important; }
</style>
""", unsafe_allow_html=True)

# ---------- Componentes HTML/JS ----------
def barcode_scanner_live_component():
    # ZXing ao vivo — insere no textarea alvo via aria-label.
    html = """
    <div style="max-width:420px">
      <h4 style="margin:4px 0">Scanner ao vivo (ZXing)</h4>
      <video id="preview" playsinline autoplay muted style="width:100%;border:1px solid #999;"></video>
      <canvas id="overlay" style="position:absolute; left:-9999px; top:-9999px;"></canvas>
      <div style="margin-top:6px; display:flex; gap:8px; flex-wrap:wrap">
        <button id="start">Iniciar</button>
        <button id="stop">Parar</button>
        <button id="insert">Inserir no formulário</button>
      </div>
      <pre id="out" style="background:#111;color:#0f0;padding:6px;min-height:60px;white-space:pre-wrap;margin-top:8px"></pre>
      <small>Dica: toque no vídeo para focar (quando suportado).</small>
    </div>

    <script type="module">
      import { BrowserMultiFormatReader, NotFoundException } from "https://cdn.jsdelivr.net/npm/@zxing/library@0.21.2/esm/index.min.js";
      const TARGET_LABEL = 'Números de Série (digite manualmente, um por linha)';

      const codeReader = new BrowserMultiFormatReader();
      const video = document.getElementById('preview');
      const overlay = document.getElementById('overlay');
      const ctx = overlay.getContext('2d');
      const out = document.getElementById('out');
      const found = new Set();
      let running = false;
      let currentDeviceId = null;

      function drawGuide() {
        const w = overlay.width, h = overlay.height;
        ctx.clearRect(0,0,w,h);
        ctx.beginPath();
        ctx.moveTo(0, h/2);
        ctx.lineTo(w, h/2);
        ctx.lineWidth = 2;
        ctx.strokeStyle = "red";
        ctx.stroke();
      }

      async function start() {
        if (running) return;
        running = true;

        try {
          const devices = await BrowserMultiFormatReader.listVideoInputDevices();
          if (devices && devices.length) {
            const back = devices.find(d => /back|traseira|rear/i.test(d.label)) || devices[devices.length - 1];
            currentDeviceId = back.deviceId;
          }

          const stream = await navigator.mediaDevices.getUserMedia({
            video: currentDeviceId ? { deviceId: { exact: currentDeviceId } } : { facingMode: { exact: "environment" } },
            audio: false
          });
          video.srcObject = stream;
          await video.play();

          const updateSize = () => {
            overlay.width = video.videoWidth || 640;
            overlay.height = video.videoHeight || 360;
            drawGuide();
          };
          video.onloadedmetadata = updateSize;
          window.addEventListener('resize', updateSize);
          updateSize();

          loopDecode();
        } catch (e) {
          console.log("Erro ao iniciar câmera:", e);
          alert("Não foi possível iniciar a câmera. Verifique permissões/HTTPS.");
          running = false;
        }
      }

      async function loopDecode() {
        if (!running) return;
        try {
          const result = await codeReader.decodeOnceFromVideoElement(video);
          if (result && result.text) {
            if (!found.has(result.text)) {
              found.add(result.text);
              out.textContent = Array.from(found).join("\\n");
            }
          }
        } catch (e) {
          if (!(e instanceof NotFoundException)) {
            console.log("ZXing error:", e);
          }
        } finally {
          if (running) requestAnimationFrame(loopDecode);
        }
      }

      function stop() {
        running = false;
        try {
          const stream = video.srcObject;
          if (stream) stream.getTracks().forEach(t => t.stop());
        } catch(e) {}
        video.srcObject = null;
      }

      video.addEventListener('click', async () => {
        const stream = video.srcObject;
        if (!stream) return;
        const track = stream.getVideoTracks()[0];
        const caps = track.getCapabilities ? track.getCapabilities() : null;
        if (caps && caps.focusMode && caps.focusMode.length) {
          try { await track.applyConstraints({ advanced: [{ focusMode: "continuous" }] }); } catch(e) {}
        }
      });

      document.getElementById('start').onclick = start;
      document.getElementById('stop').onclick  = stop;

      document.getElementById('insert').onclick = () => {
        const ta = window.parent.document.querySelector('textarea[aria-label="'+TARGET_LABEL+'"]');
        if (!ta) { alert("Campo de destino não encontrado."); return; }
        const text = out.textContent.trim();
        if (!text) { alert("Nenhum código lido ainda."); return; }
        if (ta.value && !ta.value.endsWith("\\n")) ta.value += "\\n";
        ta.value += text;
        ta.dispatchEvent(new Event('input', { bubbles: true }));
        alert("Códigos inseridos no formulário.");
      };

      // tenta iniciar automaticamente
      start().catch(()=>{});
    </script>
    """
    st.components.v1.html(html, height=560)

def barcode_scanner_photo_component():
    # Quagga2 por FOTO (upload) — robusto em Cloud/iframe
    html = """
    <div style="max-width:420px">
      <h4 style="margin:4px 0">Ler código por foto</h4>
      <p style="margin:6px 0 8px 0">Tire uma foto nítida, com boa luz, preferencialmente usando a câmera traseira.</p>
      <input id="file" type="file" accept="image/*" capture="environment" style="margin-bottom:8px" />
      <div>
        <button id="decode">Ler código</button>
      </div>
      <pre id="out" style="background:#111;color:#0f0;padding:6px;min-height:60px;white-space:pre-wrap;margin-top:8px"></pre>
    </div>

    <script src="https://unpkg.com/@ericblade/quagga2/dist/quagga.js"></script>
    <script>
      const TARGET_LABEL = 'Números de Série (digite manualmente, um por linha)';

      function appendToTextarea(val){
        const ta = window.parent.document.querySelector('textarea[aria-label="'+TARGET_LABEL+'"]');
        if (!ta) { alert("Campo de destino não encontrado."); return; }
        if (ta.value && !ta.value.endsWith("\\n")) ta.value += "\\n";
        ta.value += val;
        ta.dispatchEvent(new Event('input', { bubbles: true }));
      }

      document.getElementById('decode').onclick = () => {
        const f = document.getElementById('file').files[0];
        if (!f) { alert("Selecione ou fotografe um código primeiro."); return; }

        const reader = new FileReader();
        reader.onload = () => {
          const dataUrl = reader.result;

          Quagga.decodeSingle({
            src: dataUrl,
            numOfWorkers: 0,
            inputStream: { size: 1024 },
            locator: { patchSize: "medium", halfSample: true },
            decoder: {
              readers: [
                "code_128_reader",
                "ean_reader",
                "ean_8_reader",
                "code_39_reader",
                "upc_reader",
                "upc_e_reader"
              ]
            }
          }, (result) => {
            const out = document.getElementById('out');
            if (result && result.codeResult && result.codeResult.code) {
              const code = result.codeResult.code;
              out.textContent = code;
              appendToTextarea(code);
              alert("Código inserido no formulário.");
            } else {
              out.textContent = "Não foi possível ler. Tente outra foto (mais perto, melhor luz/contraste).";
            }
          });
        };
        reader.readAsDataURL(f);
      };
    </script>
    """
    st.components.v1.html(html, height=320)

def signature_pad_component():
    html = """
    <style>
      #sig-wrap {border:1px dashed #999; width:400px; height:160px; background:#fff;}
      #sig {width:100%; height:100%;}
      .sig-btns {margin-top:6px; display:flex; gap:6px;}
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
      function resize(){
        const ratio = Math.max(window.devicePixelRatio || 1, 1);
        canvas.width = wrapper.clientWidth * ratio;
        canvas.height = wrapper.clientHeight * ratio;
        canvas.getContext("2d").scale(ratio, ratio);
      }
      window.addEventListener("resize", resize);
      resize();
      const pad = new SignaturePad(canvas, {backgroundColor: 'rgba(255,255,255,1)'});
      document.getElementById('clear').onclick = () => pad.clear();
      document.getElementById('use').onclick = () => {
        if (pad.isEmpty()) { alert("Faça a assinatura."); return; }
        const dataUrl = pad.toDataURL("image/png");
        const input = window.parent.document.querySelector('input[aria-label="Assinatura (dataurl)"]');
        if (input) {
          input.value = dataUrl;
          input.dispatchEvent(new Event('input', { bubbles: true }));
          alert("Assinatura anexada.");
        } else {
          alert("Campo hidden de assinatura não encontrado.");
        }
      };
    </script>
    """
    st.components.v1.html(html, height=230)

# ---------- Formulário ----------
numero_chamado = st.text_input("Número do chamado")
data_atendimento = st.date_input("Data do atendimento", value=date.today())
hora_inicio = st.time_input("Hora início", value=time(8, 0))
hora_termino = st.time_input("Hora término", value=time(17, 0))
distancia_km = st.number_input("Distância (KM)", min_value=0.0, step=0.1)

st.subheader("Descrição de atendimento")
modelo = st.text_input("Modelo do equipamento")

SERIAIS_LABEL = "Números de Série (digite manualmente, um por linha)"
seriais_text = st.text_area(SERIAIS_LABEL, placeholder="Ex.: ABC12345\nDEF67890")

# Scanner: ao vivo + foto (as duas opções)
with st.expander("📷 Ler serial por câmera (ao vivo)"):
    barcode_scanner_live_component()
with st.expander("🖼️ Ler serial por foto (fallback)"):
    barcode_scanner_photo_component()

descricao = st.text_area("Descrição da atividade")
info_adicional = st.text_area("Informações adicionais")

st.subheader("Informações do Cliente")
cliente_nome = st.text_input("Nome")
cliente_doc = st.text_input("Documento (CPF/RG)")
cliente_tel = st.text_input("Telefone")

# Campo hidden para assinatura (dataURL)
sig_dataurl = st.text_input("Assinatura (dataurl)", value="", key="sig_dataurl_key")
st.subheader("Assinatura do Cliente")
signature_pad_component()

# ---------- Gerar PDF ----------
if st.button("Gerar PDF Preenchido"):
    # 1) Cria overlay com ReportLab
    packet = io.BytesIO()
    can = Canvas(packet, pagesize=A4)
    can.setFont("Helvetica", 10)

    # A4 ~ 595 x 842 pt — ajuste fino conforme seu template
    can.drawString(400, 775, (numero_chamado or ""))
    can.drawString(130, 755, data_atendimento.strftime("%d/%m/%Y"))
    can.drawString(350, 755, hora_inicio.strftime("%H:%M"))
    can.drawString(450, 755, hora_termino.strftime("%H:%M"))
    can.drawString(530, 755, f"{distancia_km:.1f}")

    # Modelo + seriais (multi-linha)
    can.drawString(80, 720, f"Modelo: {modelo or ''}")
    y = 700
    for line in (seriais_text or "").splitlines():
        can.drawString(80, y, line[:100])
        y -= 14
        if y < 620:
            break

    can.drawString(80, 610, (descricao or "")[:300])
    can.drawString(80, 590, (info_adicional or "")[:300])

    can.drawString(100, 120, cliente_nome or "")
    can.drawString(300, 120, cliente_doc or "")
    can.drawString(450, 120, cliente_tel or "")

    # Assinatura (dataURL -> imagem)
    if isinstance(sig_dataurl, str) and sig_dataurl.startswith("data:image"):
        try:
            b64 = sig_dataurl.split(",")[1]
            sig_bytes = base64.b64decode(b64)
            sig_img = Image.open(io.BytesIO(sig_bytes)).convert("RGB")
            sig_img = sig_img.resize((120, 60))
            can.drawImage(ImageReader(sig_img), 450, 90)
        except Exception as e:
            st.warning(f"Assinatura não aplicada (erro ao processar): {e}")

    can.save()
    packet.seek(0)
    overlay_bytes = packet.getvalue()

    # 2) Mescla overlay com PDF base (pypdf)
    base_reader = PdfReader(PDF_BASE)
    writer = PdfWriter()

    overlay_reader = PdfReader(io.BytesIO(overlay_bytes))
    overlay_page = overlay_reader.pages[0]

    base_page = base_reader.pages[0]
    try:
        base_page.merge_page(overlay_page)   # pypdf >= 3
    except Exception:
        base_page.mergePage(overlay_page)    # fallback p/ versões antigas

    writer.add_page(base_page)
    for i in range(1, len(base_reader.pages)):
        writer.add_page(base_reader.pages[i])

    out_buf = io.BytesIO()
    writer.write(out_buf)
    out_buf.seek(0)

    st.download_button(
        "📥 Baixar PDF Preenchido",
        data=out_buf.getvalue(),
        file_name=f"RAT_{(numero_chamado or 'sem_numero')}.pdf",
        mime="application/pdf",
    )
    st.success("✅ PDF gerado com sucesso!")
