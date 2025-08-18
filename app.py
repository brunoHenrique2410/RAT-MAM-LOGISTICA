# app.py — RAT MAM (âncoras + assinatura digital transparente + ajustes finos)
# Requisitos:
#   requirements.txt
#     streamlit==1.37.1
#     Pillow==10.4.0
#     PyMuPDF>=1.24.12
#   runtime.txt
#     3.12

import base64
from io import BytesIO
from datetime import date, time
from urllib.parse import urlencode

import streamlit as st
from PIL import Image
import fitz  # PyMuPDF

PDF_BASE_PATH = "RAT MAM.pdf"
APP_TITLE = "RAT MAM – Assinatura Digital + Âncoras"

st.set_page_config(page_title=APP_TITLE, layout="centered")
st.title("📄 " + APP_TITLE)
st.caption("Campos posicionados por âncoras do PDF. Assinaturas digitais (sem fundo) e salvas automaticamente.")

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
    if not data_url:
        return None
    if "," in data_url:
        _, b64 = data_url.split(",", 1)
    else:
        b64 = data_url
    raw = base64.b64decode(b64)
    return Image.open(BytesIO(raw)).convert("RGBA")

# ---------------- Canvas com salvamento AUTO + transparência ----------------
def signature_canvas_auto(label: str, key_prefix: str, height: int = 180):
    st.markdown(f"**{label}**")
    # UX: fundo visual branco para enxergar; ao salvar converto branco -> transparente
    html = f"""
    <div style="border:1px solid #ccc;border-radius:8px;padding:6px;">
      <canvas id="sig_{key_prefix}" width="800" height="{height}"
              style="width:100%;touch-action:none;background:#fff;border-radius:6px;"></canvas>
      <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap;">
        <button id="clear_{key_prefix}" type="button" style="flex:1;min-width:120px;padding:10px;">Limpar</button>
        <button id="save_{key_prefix}"  type="button" style="flex:2;min-width:160px;padding:10px;">Salvar assinatura</button>
      </div>
    </div>
    <script>
      const cv = document.getElementById('sig_{key_prefix}');
      const ctx = cv.getContext('2d');
      // pinta fundo branco para visibilidade
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0,0,cv.width,cv.height);

      let drawing = false;
      function getPos(e) {{
        const r = cv.getBoundingClientRect();
        const sx = cv.width / r.width, sy = cv.height / r.height;
        if (e.touches && e.touches[0]) {{
          return {{ x:(e.touches[0].clientX - r.left)*sx, y:(e.touches[0].clientY - r.top)*sy }};
        }} else {{
          return {{ x:(e.clientX - r.left)*sx, y:(e.clientY - r.top)*sy }};
        }}
      }}
      function start(e) {{ drawing=true; const p=getPos(e); ctx.beginPath(); ctx.moveTo(p.x,p.y); }}
      function move(e) {{
        if(!drawing) return;
        const p=getPos(e);
        ctx.lineTo(p.x,p.y);
        ctx.lineWidth = 3; ctx.lineCap = 'round'; ctx.strokeStyle = '#000';
        ctx.stroke();
      }}
      function end(e) {{ drawing=false; }}

      cv.addEventListener('mousedown', start);
      cv.addEventListener('mousemove', move);
      cv.addEventListener('mouseup',   end);
      cv.addEventListener('mouseleave',end);
      cv.addEventListener('touchstart',(e)=>{{e.preventDefault();start(e)}},{{passive:false}});
      cv.addEventListener('touchmove', (e)=>{{e.preventDefault();move(e)}}, {{passive:false}});
      cv.addEventListener('touchend',  (e)=>{{e.preventDefault();end(e)}},  {{passive:false}});

      document.getElementById('clear_{key_prefix}').onclick = () => {{
        ctx.fillStyle = '#ffffff'; ctx.fillRect(0,0,cv.width,cv.height);
      }};

      function toTransparentPNG() {{
        // cria canvas RGBA transparente e converte branco (~fundo) para alpha=0
        const off = document.createElement('canvas');
        off.width = cv.width; off.height = cv.height;
        const octx = off.getContext('2d');
        octx.drawImage(cv,0,0);
        const img = octx.getImageData(0,0,off.width,off.height);
        const d = img.data;
        for (let i=0;i<d.length;i+=4) {{
          const r=d[i], g=d[i+1], b=d[i+2];
          // limiar de "quase branco"
          if (r>240 && g>240 && b>240) {{
            d[i+3]=0; // transparente
          }}
        }}
        octx.putImageData(img,0,0);
        return off.toDataURL('image/png');
      }}

      document.getElementById('save_{key_prefix}').onclick = () => {{
        try {{
          const png = toTransparentPNG(); // já vem com fundo removido
          const url = new URL(window.location.href);
          url.searchParams.set('{ 'sig_tec' if key_prefix=='tec' else 'sig_cli' }', png);
          window.location.replace(url.toString()); // evita criar novo histórico
        }} catch(e) {{
          alert('Não consegui salvar automaticamente. Tente novamente.');
        }}
      }};
    </script>
    """
    st.components.v1.html(html, height=height + 110)

# ---------------- Form (sem Equip/Modelo/Série) ----------------
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

    st.subheader("3) Descrição de Atendimento (inclua TODOS os seriais aqui)")
    seriais_texto = st.text_area("Seriais (um por linha)", placeholder="SN0012345\nSN00ABC678\n...")
    atividade     = st.text_area("Atividade (palavras do técnico)", height=120)
    info_extra    = st.text_area("Informações adicionais (opcional)", height=80)

    st.subheader("4) Técnico")
    tec_nome = st.text_input("Nome do técnico")
    tec_rg   = st.text_input("RG/Documento do técnico")

    signature_canvas_auto("Assinatura DIGITAL do TÉCNICO (sem fundo)", key_prefix="tec")
    st.write("---")
    signature_canvas_auto("Assinatura DIGITAL do CLIENTE (sem fundo)", key_prefix="cli")

    submitted = st.form_submit_button("🧾 Gerar PDF preenchido")

# ---------------- Âncoras e escrita ----------------
def search_once(page, texts):
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

def search_all(page, text):
    try:
        return page.search_for(text)
    except TypeError:
        return page.search_for(text)

def insert_right_of(page, labels, content, dx=6, dy=1, fontsize=10):
    """Escreve à direita da âncora com ajuste fino X/Y (negativo p/ esquerda, positivo p/ baixo)."""
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

def place_signature_near(page, label, pil_rgba, rel_rect):
    if pil_rgba is None:
        return
    r = search_once(page, label)
    if not r:
        return
    rect = fitz.Rect(r.x0 + rel_rect[0], r.y1 + rel_rect[1], r.x0 + rel_rect[2], r.y1 + rel_rect[3])
    buf = BytesIO()
    pil_rgba.save(buf, format="PNG")  # mantém transparência
    page.insert_image(rect, stream=buf.getvalue())

def find_tecnico_rg_label_rect(page):
    """Encontra especificamente o label 'TÉCNICO RG:' (evita pegar o RG do contato)."""
    for lbl in ["TÉCNICO RG:", "TÉCNICO  RG:", "TECNICO RG:"]:
        rect = search_once(page, [lbl])
        if rect:
            return rect
    return None

# ---------------- Pega assinaturas da URL (auto) ----------------
params = st.experimental_get_query_params()
sig_tec_data = params.get("sig_tec", [None])[0]
sig_cli_data = params.get("sig_cli", [None])[0]
sigtec_img = dataurl_to_image(sig_tec_data) if sig_tec_data else None
sigcli_img = dataurl_to_image(sig_cli_data) if sig_cli_data else None

# ---------------- Geração ----------------
if submitted:
    # Descrição (seriais + atividade + extra)
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

        # ===== TOPO (posições finas) =====
        insert_right_of(page, ["Cliente:", "CLIENTE:"], cliente_nome, dx=6, dy=1)
        insert_right_of(page, ["Endereço:", "ENDEREÇO:"], endereco, dx=6, dy=1)
        insert_right_of(page, ["Bairro:", "BAIRRO:"],     bairro,     dx=6, dy=1)
        insert_right_of(page, ["Cidade:", "CIDADE:"],     cidade,     dx=6, dy=1)

        insert_right_of(page, ["Contato:"], contato_nome, dx=6, dy=1)
        # RG do contato: usa o rótulo 'Contato:' como referência vertical
        r_cont = search_once(page, ["Contato:"])
        if r_cont and contato_rg:
            # acha todos "RG:" e usa o que está mais perto em Y do 'Contato:'
            rg_rects = search_all(page, "RG:")
            if rg_rects:
                cy = r_cont.y0 + r_cont.height/2
                rg_best = min(rg_rects, key=lambda rr: abs((rr.y0+rr.height/2)-cy))
                x = rg_best.x1 + 6
                y = rg_best.y0 + rg_best.height/1.5 + 3   # ↓ desce um pouco
                page.insert_text((x, y), str(contato_rg), fontsize=10)

        insert_right_of(page, ["Telefone:", "TELEFONE:"], normalize_phone(contato_tel), dx=6, dy=1)

        # ===== Datas/Horas/KM — mais à ESQUERDA e BAIXO (como solicitado) =====
        insert_right_of(page, ["Data do atendimento:", "Data do Atendimento:"], data_atend.strftime("%d/%m/%Y"), dx=2, dy=3)
        insert_right_of(page, ["Hora Inicio:", "Hora Início:", "Hora inicio:"], hora_ini.strftime("%H:%M"), dx=0, dy=3)
        insert_right_of(page, ["Hora Termino:", "Hora Término:", "Hora termino:"], hora_fim.strftime("%H:%M"), dx=0, dy=3)
        insert_right_of(page, ["Distancia (KM) :", "Distância (KM) :"], str(distancia_km), dx=0, dy=3)

        # ===== DESCRIÇÃO =====
        insert_textbox_below(page, ["DESCRIÇÃO DE ATENDIMENTO","DESCRICAO DE ATENDIMENTO"], bloco_desc,
                             box=(0, 20, 540, 240), fontsize=10, align=0)

        # ===== TÉCNICO (nome + RG) =====
        insert_right_of(page, ["TÉCNICO", "TECNICO"], tec_nome, dx=8, dy=0)  # nome do técnico
        rg_lbl = find_tecnico_rg_label_rect(page)  # rótulo "TÉCNICO RG:"
        if rg_lbl and tec_rg:
            x = rg_lbl.x1 + 6
            y = rg_lbl.y0 + rg_lbl.height/1.5 + 1
            page.insert_text((x, y), str(tec_rg), fontsize=10)

        # ===== Assinaturas (retângulos revistos) =====
        # Técnico: âncora "ASSINATURA:" (na mesma linha do técnico)
        place_signature_near(page, ["ASSINATURA:", "Assinatura:"], sigtec_img,
                             rel_rect=(110, 0, 330, 54))  # mais à esquerda e um pouco mais baixo

        # Cliente: âncora "DATA CARIMBO / ASSINATURA"
        place_signature_near(page, ["DATA CARIMBO / ASSINATURA", "ASSINATURA CLIENTE", "CLIENTE"],
                             sigcli_img,
                             rel_rect=(110, 12, 430, 94)) # mais à esquerda e baixo

        # ===== Nº CHAMADO — “literalmente embaixo do campo” (mais à esquerda e para baixo) =====
        insert_right_of(page, [" Nº CHAMADO ", "Nº CHAMADO", "No CHAMADO"], num_chamado, dx=-4, dy=6)

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
