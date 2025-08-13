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

# ---------- CSS p/ esconder campo técnico de assinatura ----------
st.markdown("""
<style>
/* Esconde o text_input técnico onde guardamos o dataURL da assinatura */
div:has(> input[aria-label="Assinatura (dataurl)"]) { display:none !important; }
</style>
""", unsafe_allow_html=True)

# ---------- Componentes HTML: Scanner e Assinatura (sem f-strings) ----------
def barcode_scanner_component():
    # Usa Quagga2 (1D) + html5-qrcode (QR). Insere no textarea alvo via aria-label fixo.
    html = """
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
      const TARGET_LABEL = 'Números de Série (digite manualmente, um por linha)';
      const vals = new Set();

      function addVal(v, box) {
        if (!v) return;
        vals.add(v);
        document.getElementById(box).textContent = Array.from(vals).join("\\n");
      }

      // ---- 1D BARCODE (Quagga) ----
      let running1d = false;
      function start1D(){
        if (running1d) return;
        running1d = true;
        Quagga.init({
          inputStream: {
            type: "LiveStream",
            target: document.querySelector('#video'),
            constraints: { facingMode: "environment" }
          },
          locator: { patchSize: "medium", halfSample: true },
          numOfWorkers: 0,
          decoder: {
            readers: ["code_128_reader","ean_reader","ean_8_reader","code_39_reader","upc_reader","upc_e_reader"]
          }
        }, function(err){
          if (err) { console.log(err); running1d=false; return; }
          Quagga.start();
        });
        Quagga.onDetected(function(result){
          const code = result && result.codeResult && result.codeResult.code;
          if (code) addVal(code, "out1d");
        });
      }
      function stop1D(){ if (running1d){ Quagga.stop(); running1d=false; } }
      document.getElementById("start1d").onclick = start1D;
      document.getElementById("stop1d").onclick  = stop1D;

      // ---- QR (html5-qrcode) ----
      let qrScanner = null;
      function startQR(){
        if (qrScanner) return;
        qrScanner = new Html5Qrcode("reader");
        Html5Qrcode.getCameras().then(cams => {
          const id = cams && cams.length ? cams[cams.length-1].id : undefined;
          qrScanner.start(
            id || { facingMode: "environment" },
            { fps: 10, qrbox: 200 },
            txt => addVal(txt, "outqr"),
            _ => {}
          );
        }).catch(_=>{});
      }
      function stopQR(){ if (qrScanner){ qrScanner.stop().then(()=>{qrScanner.clear(); qrScanner=null;}); } }
      startQR();
      document.getElementById("stopqr").onclick = stopQR;

      // ---- Enviar p/ textarea alvo ----
      document.getElementById("send").onclick = function(){
        const s = Array.from(vals).join("\\n");
        const ta = window.parent.document.querySelector('textarea[aria-label="'+TARGET_LABEL+'"]');
        if (ta) {
          if (ta.value && !ta.value.endsWith("\\n")) ta.value += "\\n";
          ta.value += s;
          ta.dispatchEvent(new Event('input', { bubbles: true }));
          alert("Códigos inseridos no formulário.");
        } else {
          alert("Campo de destino não encontrado.");
        }
      };
    </script>
    """
    st.components.v1.html(html, height=520)

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

# ------------------------------ Formulário ------------------------------
numero_chamado = st.text_input("Número do chamado")
data_atendimento = st.date_input("Data do atendimento", value=date.today())
hora_inicio = st.time_input("Hora início", value=time(8, 0))
hora_termino = st.time_input("Hora término", value=time(17, 0))
distancia_km = st.number_input("Distância (KM)", min_value=0.0, step=0.1)

st.subheader("Descrição de atendimento")
modelo = st.text_input("Modelo do equipamento")

SERIAIS_LABEL = "Números de Série (digite manualmente, um por linha)"
seriais_text = st.text_area(SERIAIS_LABEL, placeholder="Ex.: ABC12345\nDEF67890")

if st.checkbox("📷 Usar scanner de código de barras/QR"):
    barcode_scanner_component()

descricao = st.text_area("Descrição da atividade")
info_adicional = st.text_area("Informações adicionais")

st.subheader("Informações do Cliente")
cliente_nome = st.text_input("Nome")
cliente_doc = st.text_input("Documento (CPF/RG)")
cliente_tel = st.text_input("Telefone")

# Campo hidden para armazenar a assinatura (DataURL)
sig_dataurl = st.text_input("Assinatura (dataurl)", value="", key="sig_dataurl_key")
st.subheader("Assinatura do Cliente")
signature_pad_component()

# ------------------------------ Geração do PDF ------------------------------
if st.button("Gerar PDF Preenchido"):
    # 1) Criar overlay com ReportLab
    packet = io.BytesIO()
    can = Canvas(packet, pagesize=A4)
    can.setFont("Helvetica", 10)

    # A4 aprox. 595 x 842 pt — ajuste fino conforme seu template
    can.drawString(400, 775, (numero_chamado or ""))
    can.drawString(130, 755, data_atendimento.strftime("%d/%m/%Y"))
    can.drawString(350, 755, hora_inicio.strftime("%H:%M"))
    can.drawString(450, 755, hora_termino.strftime("%H:%M"))
    can.drawString(530, 755, f"{distancia_km:.1f}")

    can.drawString(80, 720, f"Modelo: {modelo or ''}")
    y = 700
    for line in (seriais_text or "").splitlines():
        can.drawString(80, y, line[:100])
        y -= 14
        if y < 620:  # evita invadir campos seguintes
            break

    can.drawString(80, 610, (descricao or "")[:300])
    can.drawString(80, 590, (info_adicional or "")[:300])

    can.drawString(100, 120, cliente_nome or "")
    can.drawString(300, 120, cliente_doc or "")
    can.drawString(450, 120, cliente_tel or "")

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

    # 2) Mesclar overlay com PDF base usando pypdf (sem libs nativas)
    base_reader = PdfReader(PDF_BASE)
    writer = PdfWriter()

    # carrega a página do overlay
    overlay_reader = PdfReader(io.BytesIO(overlay_bytes))
    overlay_page = overlay_reader.pages[0]

    # pega a primeira página do PDF base e funde
    base_page = base_reader.pages[0]
    try:
        base_page.merge_page(overlay_page)  # pypdf >=3
    except Exception:
        # fallback para versões antigas (nome era mergePage)
        base_page.mergePage(overlay_page)

    writer.add_page(base_page)

    # se o PDF base tiver mais páginas, mantém
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
