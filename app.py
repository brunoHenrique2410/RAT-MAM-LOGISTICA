# app.py — RAT MAM (âncoras automáticas + assinatura digital sem fundo)
# - Preenche campos posicionando pelo texto do próprio PDF (PyMuPDF/fitz)
# - Assinaturas desenhadas na tela (canvas), exportadas em PNG com transparência (sem fundo)
# - Sem calibração manual; posições fixas relativas aos rótulos
# Requisitos: streamlit==1.37.1, Pillow==10.4.0, PyMuPDF>=1.24.12 | runtime.txt: 3.12

import base64
from io import BytesIO
from datetime import date, time

import streamlit as st
from PIL import Image
import fitz  # PyMuPDF

PDF_BASE_PATH = "RAT MAM.pdf"
APP_TITLE = "RAT MAM – Âncoras + Assinatura Digital (sem fundo)"

st.set_page_config(page_title=APP_TITLE, layout="centered")
st.title("📄 " + APP_TITLE)
st.caption("O app detecta os rótulos do PDF e posiciona os dados. Assinaturas são digitais (canvas) e entram sem fundo.")

# ---------------- Utils ----------------
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

def dataurl_to_image(data_url: str):
    """Converte dataURL (image/png;base64,...) -> PIL RGBA."""
    if not data_url:
        return None
    if "," in data_url:
        _, b64 = data_url.split(",", 1)
    else:
        b64 = data_url
    raw = base64.b64decode(b64)
    return Image.open(BytesIO(raw)).convert("RGBA")

# -------------- Canvas de assinatura (fundo transparente) --------------
def signature_canvas(label: str, key_prefix: str, height: int = 200):
    st.markdown(f"**{label}**")
    # Canvas com fundo transparente (não pintamos o fundo); stroke preto visível
    html = f"""
    <div style="border:1px solid #ccc;border-radius:8px;padding:6px;">
      <canvas id="sigCanvas_{key_prefix}" width="900" height="{height}" style="width:100%;touch-action:none;background:transparent;"></canvas>
      <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap;">
        <button id="clearBtn_{key_prefix}" type="button" style="flex:1;min-width:120px;padding:10px;">Limpar</button>
        <button id="copyBtn_{key_prefix}" type="button" style="flex:1;min-width:160px;padding:10px;">Copiar p/ área de transferência</button>
        <a id="dl_{key_prefix}" download="assinatura.png" style="flex:1;min-width:140px;padding:10px;text-align:center;border:1px solid #ccc;border-radius:6px;text-decoration:none;color:#000;">Baixar PNG</a>
      </div>
      <small style="color:#666;">Se “Baixar PNG” não anexar automaticamente, use o botão de upload logo abaixo.</small>
    </div>
    <script>
      const canvas = document.getElementById('sigCanvas_{key_prefix}');
      const ctx = canvas.getContext('2d');

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
        ctx.lineWidth = 3;
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

      document.getElementById('clearBtn_{key_prefix}').onclick = () => {{
        // limpa mantendo transparência
        ctx.clearRect(0,0,canvas.width,canvas.height);
      }};

      function getPNG() {{
        return canvas.toDataURL('image/png'); // mantém transparência
      }}

      // Copiar dataURL p/ clipboard (alguns navegadores pedem permissão)
      document.getElementById('copyBtn_{key_prefix}').onclick = async () => {{
        try {{
          const png = getPNG();
          await navigator.clipboard.writeText(png);
          alert('Assinatura copiada! Cole no campo de texto abaixo ou baixe o PNG.');
        }} catch (e) {{
          alert('Não foi possível copiar automaticamente. Use o botão "Baixar PNG".');
        }}
      }};

      // Botão de download
      const dl = document.getElementById('dl_{key_prefix}');
      function refreshDL() {{
        dl.href = getPNG();
      }}
      dl.addEventListener('mouseover', refreshDL);
      dl.addEventListener('touchstart', refreshDL, {{passive:true}});
    </script>
    """
    st.components.v1.html(html, height=height + 120)
    # Campo opcional para colar a dataURL (se o usuário usou "Copiar")
    pasted = st.text_area("Ou cole aqui a assinatura (data URL)", key=f"paste_{key_prefix}", height=80, placeholder="data:image/png;base64,...")
    # Upload (fallback garantido)
    uploaded = st.file_uploader("Ou envie a assinatura (PNG/JPG)", type=["png", "jpg", "jpeg"], key=f"upload_{key_prefix}")
    # Retorna PIL (RGBA) se conseguir converter
    if pasted and pasted.strip().startswith("data:image"):
        try:
            return dataurl_to_image(pasted.strip())
        except Exception:
            pass
    if uploaded is not None:
        try:
            return Image.open(uploaded).convert("RGBA")
        except Exception:
            pass
    return None

# ---------------- Formulário (sem repetições) ----------------
with st.form("rat_mam"):
    st.subheader("1) Chamado e Agenda")
    col_a, col_b = st.columns(2)
    with col_a:
        num_chamado = st.text_input("Nº do chamado")
        data_atend  = st.date_input("Data do atendimento", value=date.today())
        hora_ini    = st.time_input("Hora início", value=time(8, 0))
    with col_b:
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

    sigtec_img = signature_canvas("Assinatura DIGITAL do TÉCNICO (fundo transparente)", key_prefix="tec")
    st.write("---")
    sigcli_img = signature_canvas("Assinatura DIGITAL do CLIENTE (fundo transparente)", key_prefix="cli")

    submitted = st.form_submit_button("🧾 Gerar PDF preenchido")

# ---------------- Âncoras e escrita ----------------
def search_once(page, texts):
    """Procura a 1ª ocorrência (compat com versões antigas do fitz)."""
    if isinstance(texts, (str,)):
        texts = [texts]
    for t in texts:
        try:
            rects = page.search_for(t)
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

def insert_textbox_below(page, label, content, box=(0, 20, 540, 240), fontsize=10, align=0):
    if not content:
        return
    r = search_once(page, label)
    if not r:
        return
    rect = fitz.Rect(r.x0 + box[0], r.y1 + box[1], r.x0 + box[2], r.y1 + box[3])
    page.insert_textbox(rect, str(content), fontsize=fontsize, align=align)

def place_signature_near(page, label, pil_rgba, rel_rect):
    """Cola assinatura como PNG RGBA (mantém transparência)."""
    if pil_rgba is None:
        return
    r = search_once(page, label)
    if not r:
        return
    rect = fitz.Rect(r.x0 + rel_rect[0], r.y1 + rel_rect[1], r.x0 + rel_rect[2], r.y1 + rel_rect[3])
    buf = BytesIO()
    pil_rgba.save(buf, format="PNG")  # mantém canal alfa
    page.insert_image(rect, stream=buf.getvalue())

# ---------------- Geração ----------------
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

    # Monta texto da descrição
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

    try:
        doc = fitz.open(stream=base_bytes, filetype="pdf")
        page = doc[0]

        # Topo (âncoras fiéis ao seu RAT)
        insert_right_of(page, ["Cliente:", "CLIENTE:"], cliente_nome)
        insert_right_of(page, ["Endereço:", "ENDEREÇO:"], endereco)
        insert_right_of(page, ["Bairro:", "BAIRRO:"], bairro)
        insert_right_of(page, ["Cidade:", "CIDADE:"], cidade)

        insert_right_of(page, ["Contato:"], contato_nome)
        insert_right_of(page, ["RG:"], contato_rg)  # primeira ocorrência do topo
        insert_right_of(page, ["Telefone:", "TELEFONE:"], normalize_phone(contato_tel))

        insert_right_of(page, ["Data do atendimento:", "Data do Atendimento:"], data_atend.strftime("%d/%m/%Y"))
        insert_right_of(page, ["Hora Inicio:", "Hora Início:", "Hora inicio:"], hora_ini.strftime("%H:%M"))
        insert_right_of(page, ["Hora Termino:", "Hora Término:", "Hora termino:"], hora_fim.strftime("%H:%M"))
        insert_right_of(page, ["Distancia (KM)", "Distância (KM)"], str(distancia_km))

        # Bloco descrição
        insert_textbox_below(page, ["DESCRIÇÃO DE ATENDIMENTO","DESCRICAO DE ATENDIMENTO"], bloco_desc,
                             box=(0, 20, 540, 240), fontsize=10, align=0)

        # Linha equipamento/modelo/série
        insert_right_of(page, ["EQUIPAMENTO:"], equipamento)
        insert_right_of(page, ["MODELO:"], modelo)
        insert_right_of(page, ["Nº DE SERIE:", "Nº DE SÉRIE:", "NO DE SERIE:"], serie_principal)

        # Técnico – nome / RG / Assinatura (ajuste posicional fino via rel_rect)
        insert_right_of(page, ["TÉCNICO", "TECNICO"], tec_nome)
        insert_right_of(page, ["TÉCNICO RG:", "TÉCNICO  RG:", "TECNICO RG:"], tec_rg)

        # Assinatura do técnico: ancorada em "ASSINATURA:" dessa linha
        # rel_rect=(x0, y0, x1, y1) relativo à âncora:
        place_signature_near(page, ["ASSINATURA:", "Assinatura:"], sigtec_img,
                             rel_rect=(160, -12, 370, 58))

        # Assinatura do cliente: ancorada no bloco "DATA CARIMBO / ASSINATURA"
        place_signature_near(page, ["DATA CARIMBO / ASSINATURA", "ASSINATURA CLIENTE", "CLIENTE"],
                             sigcli_img,
                             rel_rect=(280, 8, 560, 90))

        # Nº CHAMADO
        insert_right_of(page, [" Nº CHAMADO ", "Nº CHAMADO", "No CHAMADO"], num_chamado, dx=12)

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
