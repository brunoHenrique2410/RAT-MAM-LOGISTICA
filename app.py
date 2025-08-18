# app.py — RAT MAM (âncoras automáticas + assinatura digital) — corrigido
# - Corrige search_for() para versões antigas do PyMuPDF
# - Assinatura com fundo branco (visível no PDF)
#
# requirements.txt:
#   streamlit==1.37.1
#   Pillow==10.4.0
#   PyMuPDF>=1.24.12
#
# runtime.txt:
#   3.12

import base64
from io import BytesIO
from datetime import date, time

import streamlit as st
from PIL import Image
import fitz  # PyMuPDF

PDF_BASE_PATH = "RAT MAM.pdf"
APP_TITLE = "RAT MAM - Âncoras + Assinatura Digital"

st.set_page_config(page_title=APP_TITLE, layout="centered")
st.title("📄 " + APP_TITLE)
st.caption("Posições por âncoras (rótulos do PDF). Assinatura digital na tela (fundo branco).")

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

def b64_to_image(data_url: str):
    if not data_url:
        return None
    if "," in data_url:
        _, b64 = data_url.split(",", 1)
    else:
        b64 = data_url
    raw = base64.b64decode(b64)
    return Image.open(BytesIO(raw)).convert("RGBA")

def signature_canvas(label: str, height: int = 200):
    st.markdown(f"**{label}**")
    html = f"""
    <div style="border:1px solid #ccc;border-radius:8px;padding:6px;">
      <canvas id="sigCanvas" width="800" height="{height}" style="width:100%;touch-action:none;background:#fff;"></canvas>
      <div style="display:flex;gap:8px;margin-top:8px;">
        <button id="clearBtn" type="button" style="flex:1;padding:10px;">Limpar</button>
        <button id="saveBtn" type="button" style="flex:1;padding:10px;">Salvar assinatura</button>
      </div>
    </div>
    <script>
      const canvas = document.getElementById('sigCanvas');
      const ctx = canvas.getContext('2d');
      // fundo branco desde o início
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0,0,canvas.width,canvas.height);

      let drawing = false;

      function getPos(e) {{
        const r = canvas.getBoundingClientRect();
        const sx = canvas.width / r.width;
        const sy = canvas.height / r.height;
        if (e.touches && e.touches[0]) {{
          return {{ x: (e.touches[0].clientX - r.left) * sx, y: (e.touches[0].clientY - r.top) * sy }};
        }} else {{
          return {{ x: (e.clientX - r.left) * sx, y: (e.clientY - r.top) * sy }};
        }}
      }}

      function start(e) {{
        drawing = true;
        const p = getPos(e);
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
      }}
      function move(e) {{
        if (!drawing) return;
        const p = getPos(e);
        ctx.lineTo(p.x, p.y);
        ctx.lineWidth = 3;        // traço mais visível
        ctx.lineCap = 'round';
        ctx.strokeStyle = '#000000';
        ctx.stroke();
      }}
      function end(e) {{ drawing = false; }}

      canvas.addEventListener('mousedown', start);
      canvas.addEventListener('mousemove', move);
      canvas.addEventListener('mouseup', end);
      canvas.addEventListener('mouseleave', end);

      canvas.addEventListener('touchstart', (e) => {{ e.preventDefault(); start(e); }}, {{passive:false}});
      canvas.addEventListener('touchmove',  (e) => {{ e.preventDefault(); move(e); }}, {{passive:false}});
      canvas.addEventListener('touchend',   (e) => {{ e.preventDefault(); end(e); }}, {{passive:false}});

      document.getElementById('clearBtn').onclick = () => {{
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0,0,canvas.width,canvas.height);
      }};
      document.getElementById('saveBtn').onclick = () => {{
        const dataURL = canvas.toDataURL('image/png');
        window.parent.postMessage({{sigData: dataURL}}, "*");
      }};
    </script>
    """
    st.components.v1.html(html, height=height + 90)
    return st.file_uploader("Ou envie uma imagem da assinatura (PNG/JPG)", type=["png","jpg","jpeg"], key=f"up_{label}")

# --------- Form ---------
with st.form("rat_mam"):
    st.subheader("1) Chamado e Agenda")
    col_a, col_b = st.columns(2)
    with col_a:
        num_chamado = st.text_input("Nº do chamado")
        data_atend = st.date_input("Data do atendimento", value=date.today())
        hora_ini   = st.time_input("Hora início", value=time(8, 0))
    with col_b:
        hora_fim   = st.time_input("Hora término", value=time(10, 0))
        distancia_km = st.text_input("Distância (KM)")

    st.subheader("2) Cliente (topo do PDF)")
    cliente_nome = st.text_input("Cliente / Razão Social")
    endereco     = st.text_input("Endereço")
    bairro       = st.text_input("Bairro")
    cidade       = st.text_input("Cidade")
    contato_nome = st.text_input("Contato (nome)")
    contato_rg   = st.text_input("Contato (RG/Doc)")
    contato_tel  = st.text_input("Contato (Telefone)")

    st.subheader("3) Descrição de Atendimento")
    seriais_texto = st.text_area("Seriais (um por linha)", placeholder="SN0012345\nSN00ABC678\n...")
    atividade     = st.text_area("Atividade (palavras do técnico)", height=120)
    info_extra    = st.text_area("Informações adicionais (opcional)", height=80)

    st.subheader("4) Linha: Equipamento / Modelo / Nº de Série (PDF)")
    equipamento     = st.text_input("Equipamento", placeholder="ex.: Access Point / Switch / Nobreak")
    modelo          = st.text_input("Modelo", placeholder="ex.: EAP-225 / SG3428MP / SMS XYZ")
    serie_principal = st.text_input("Nº de Série (principal)", placeholder="ex.: SN12345678")

    st.subheader("5) Técnico")
    tec_nome = st.text_input("Nome do técnico")
    tec_rg   = st.text_input("RG/Documento do técnico")

    sigtec_upload = signature_canvas("Assinatura digital do TÉCNICO")
    st.write("---")
    sigcli_upload = signature_canvas("Assinatura digital do CLIENTE")

    submitted = st.form_submit_button("🧾 Gerar PDF preenchido")

# --------- Âncoras / escrita ---------
def search_once(page, texts):
    """Versão compatível com PyMuPDF antigos: sem kwargs extras."""
    if isinstance(texts, (str,)):
        texts = [texts]
    for t in texts:
        try:
            rects = page.search_for(t)  # sem hit_max/quads (compat)
        except TypeError:
            rects = page.search_for(t)
        if rects:
            return rects[0]
    return None

def insert_right_of(page, labels, content, dx=8, fontsize=10):
    if not content:
        return
    r = search_once(page, labels)
    if not r:
        return
    x = r.x1 + dx
    y = r.y0 + r.height/1.5
    page.insert_text((x, y), str(content), fontsize=fontsize)

def insert_textbox_below(page, label, content, box=(0, 18, 540, 230), fontsize=10, align=0):
    if not content:
        return
    r = search_once(page, label)
    if not r:
        return
    rect = fitz.Rect(r.x0 + box[0], r.y1 + box[1], r.x0 + box[2], r.y1 + box[3])
    page.insert_textbox(rect, str(content), fontsize=fontsize, align=align)

def place_signature_near(page, label, pil_img, rel_rect=(0, 10, 240, 90)):
    if pil_img is None:
        return
    r = search_once(page, label)
    if not r:
        return
    # Achatar assinatura sobre fundo branco para evitar fundo escuro
    if pil_img.mode != "RGBA":
        pil_img = pil_img.convert("RGBA")
    white_bg = Image.new("RGB", pil_img.size, "white")
    white_bg.paste(pil_img, mask=pil_img.split()[3])  # usa alfa como máscara

    buf = BytesIO()
    white_bg.save(buf, format="PNG")
    rect = fitz.Rect(r.x0 + rel_rect[0], r.y1 + rel_rect[1], r.x0 + rel_rect[2], r.y1 + rel_rect[3])
    page.insert_image(rect, stream=buf.getvalue())

# --------- Geração ---------
if submitted:
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

    # Assinaturas (via upload do canvas)
    sigtec_img = Image.open(sigtec_upload).convert("RGBA") if sigtec_upload else None
    sigcli_img = Image.open(sigcli_upload).convert("RGBA") if sigcli_upload else None

    try:
        doc = fitz.open(stream=base_bytes, filetype="pdf")
        page = doc[0]

        # Topo
        insert_right_of(page, ["Cliente:", "CLIENTE:"], cliente_nome)
        insert_right_of(page, ["Endereço:", "ENDEREÇO:"], endereco)
        insert_right_of(page, ["Bairro:", "BAIRRO:"], bairro)
        insert_right_of(page, ["Cidade:", "CIDADE:"], cidade)

        insert_right_of(page, ["Contato:"], contato_nome)
        insert_right_of(page, ["RG:"], contato_rg)  # pode pegar a primeira ocorrência de RG do topo
        insert_right_of(page, ["Telefone:", "TELEFONE:"], normalize_phone(contato_tel))

        insert_right_of(page, ["Data do atendimento:", "Data do Atendimento:"], data_atend.strftime("%d/%m/%Y"))
        insert_right_of(page, ["Hora Inicio:", "Hora Início:", "Hora inicio:"], hora_ini.strftime("%H:%M"))
        insert_right_of(page, ["Hora Termino:", "Hora Término:", "Hora termino:"], hora_fim.strftime("%H:%M"))
        insert_right_of(page, ["Distancia (KM)", "Distância (KM)"], str(distancia_km))

        # Descrição
        bloco = ""
        seriais_linhas = [ln.strip() for ln in (seriais_texto or "").splitlines() if ln.strip()]
        if seriais_linhas:
            bloco += "SERIAIS:\n" + "\n".join(f"- {s}" for s in seriais_linhas) + "\n\n"
        if (atividade or "").strip():
            bloco += "ATIVIDADE:\n" + atividade.strip() + "\n\n"
        if (info_extra or "").strip():
            bloco += "INFORMAÇÕES ADICIONAIS:\n" + info_extra.strip()
        insert_textbox_below(page, ["DESCRIÇÃO DE ATENDIMENTO", "DESCRICAO DE ATENDIMENTO"],
                             bloco, box=(0, 20, 540, 240), fontsize=10, align=0)

        # Linha equipamento / modelo / série
        insert_right_of(page, ["EQUIPAMENTO:"], equipamento)
        insert_right_of(page, ["MODELO:"], modelo)
        insert_right_of(page, ["Nº DE SERIE:", "Nº DE SÉRIE:", "NO DE SERIE:"], serie_principal)

        # Técnico + assinaturas
        insert_right_of(page, ["TÉCNICO", "TECNICO"], tec_nome)
        insert_right_of(page, ["TÉCNICO RG:", "TÉCNICO  RG:", "TECNICO RG:"], tec_rg)
        place_signature_near(page, ["ASSINATURA:", "Assinatura:"], sigtec_img, rel_rect=(180, -10, 380, 60))

        # Cliente (rodapé) + assinatura
        # Se o seu rodapé tiver labels específicos (ex.: "NOME LEGÍVEL:"), ancore-os aqui.
        place_signature_near(page, ["DATA CARIMBO / ASSINATURA", "ASSINATURA", "CLIENTE"], sigcli_img, rel_rect=(310, 10, 560, 90))

        out = BytesIO()
        doc.save(out)
        doc.close()

        st.success("PDF gerado com sucesso!")
        st.download_button("⬇️ Baixar RAT preenchido",
                           data=out.getvalue(),
                           file_name=f"RAT_MAM_preenchido_{(num_chamado or 'sem_num')}.pdf",
                           mime="application/pdf")
    except Exception as e:
        st.error(f"Falha ao gerar PDF: {e}")
        st.exception(e)
