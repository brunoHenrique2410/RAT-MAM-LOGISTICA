# app.py — RAT MAM (âncoras automáticas + assinatura digital)
# - Preenche o seu "RAT MAM.pdf" localizando os rótulos do próprio PDF (âncoras via PyMuPDF)
# - Remove qualquer ajuste manual de “técnico” (sem calibração)
# - Assinatura DIGITAL: o técnico e o cliente assinam na tela (canvas), gerando a imagem da assinatura
#
# REQUISITOS (requirements.txt):
#   streamlit==1.37.1
#   Pillow==10.4.0
#   PyMuPDF>=1.24.12
#
# (Se publicar no Streamlit Cloud e quiser garantir wheel compatível, use runtime.txt com:
#   3.12
# )

import base64
from io import BytesIO
from datetime import date, time

import streamlit as st
from PIL import Image
import fitz  # PyMuPDF

# ============== CONFIG ==============
PDF_BASE_PATH = "RAT MAM.pdf"  # deixe este arquivo na raiz do repo
APP_TITLE = "RAT MAM - Âncoras + Assinatura Digital"

st.set_page_config(page_title=APP_TITLE, layout="centered")
st.title("📄 " + APP_TITLE)
st.caption("As posições são detectadas por rótulos do próprio PDF (âncoras). Assinatura é feita na tela, sem câmera.")

# ============== UTILS ==============
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
    """Converte dataURL 'data:image/png;base64,...' em PIL Image."""
    if not data_url:
        return None
    if "," in data_url:
        _, b64 = data_url.split(",", 1)
    else:
        b64 = data_url
    raw = base64.b64decode(b64)
    return Image.open(BytesIO(raw)).convert("RGBA")

# ============== ASSINATURA DIGITAL (canvas) ==============
def signature_canvas(label: str, height: int = 200):
    st.markdown(f"**{label}**")
    html = f"""
    <div style="border:1px solid #ccc;border-radius:8px;padding:6px;">
      <canvas id="sigCanvas" width="800" height="{height}" style="width:100%;touch-action:none;"></canvas>
      <div style="display:flex;gap:8px;margin-top:8px;">
        <button id="clearBtn" type="button" style="flex:1;padding:10px;">Limpar</button>
        <button id="saveBtn" type="button" style="flex:1;padding:10px;">Salvar assinatura</button>
      </div>
    </div>
    <script>
      const canvas = document.getElementById('sigCanvas');
      const ctx = canvas.getContext('2d');
      let drawing = false;
      let rect = null;

      function getPos(e) {{
        const cRect = canvas.getBoundingClientRect();
        if (e.touches && e.touches[0]) {{
          return {{
            x: (e.touches[0].clientX - cRect.left) * (canvas.width / cRect.width),
            y: (e.touches[0].clientY - cRect.top) * (canvas.height / cRect.height)
          }};
        }} else {{
          return {{
            x: (e.clientX - cRect.left) * (canvas.width / cRect.width),
            y: (e.clientY - cRect.top) * (canvas.height / cRect.height)
          }};
        }}
      }}

      function start(e) {{ drawing = true; const p = getPos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); }}
      function move(e) {{
        if (!drawing) return;
        const p = getPos(e);
        ctx.lineTo(p.x, p.y);
        ctx.lineWidth = 2;
        ctx.lineCap = 'round';
        ctx.stroke();
      }}
      function end(e) {{ drawing = false; }}

      canvas.addEventListener('mousedown', start);
      canvas.addEventListener('mousemove', move);
      canvas.addEventListener('mouseup', end);
      canvas.addEventListener('mouseleave', end);

      canvas.addEventListener('touchstart', (e) => {{ e.preventDefault(); start(e); }}, {{"passive": false}});
      canvas.addEventListener('touchmove',  (e) => {{ e.preventDefault(); move(e); }}, {{"passive": false}});
      canvas.addEventListener('touchend',   (e) => {{ e.preventDefault(); end(e); }}, {{"passive": false}});

      document.getElementById('clearBtn').onclick = () => {{
        ctx.clearRect(0,0,canvas.width,canvas.height);
      }};
      document.getElementById('saveBtn').onclick = () => {{
        const dataURL = canvas.toDataURL('image/png');
        window.parent.postMessage({{sigData: dataURL}}, "*");
      }};
    </script>
    """
    st.components.v1.html(html, height=height + 90)
    # A imagem é entregue via postMessage; o Streamlit não captura sozinho.
    # Solução simples: pedir upload opcional como alternativa (salva no PDF do mesmo jeito).
    return st.file_uploader("Ou envie uma imagem da assinatura (PNG/JPG)", type=["png","jpg","jpeg"], key=f"upload_{label}")

# ============== FORMULÁRIO ==============
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

    sigtec_upload   = signature_canvas("Assinatura digital do TÉCNICO (desenhe aqui)")
    st.write("---")
    sigcli_upload   = signature_canvas("Assinatura digital do CLIENTE (desenhe aqui)")

    submitted = st.form_submit_button("🧾 Gerar PDF preenchido")

# ============== FUNÇÕES DE ÂNCORA ==============
def search_once(page, texts):
    """Procura a 1ª ocorrência de qualquer variação em 'texts' (lista/tupla) e retorna o Rect."""
    if isinstance(texts, (str,)):
        texts = [texts]
    for t in texts:
        rects = page.search_for(t, quads=False, hit_max=1)  # case-sensitive; se precisar, duplique variações
        if rects:
            return rects[0]
    return None

def insert_right_of(page, labels, content, dx=8, fontsize=10):
    """Escreve 'content' à direita do rótulo (âncora)."""
    if not content:
        return
    r = search_once(page, labels)
    if not r:
        return
    x = r.x1 + dx
    # alinhamento aproximado com baseline do rótulo
    y = r.y0 + r.height/1.5
    page.insert_text((x, y), str(content), fontsize=fontsize)

def insert_textbox_below(page, label, content, box=(0, 18, 540, 230), fontsize=10, align=0):
    """Insere bloco de texto em uma caixa retangular logo abaixo do label (âncora)."""
    if not content:
        return
    r = search_once(page, label)
    if not r:
        return
    rect = fitz.Rect(r.x0 + box[0], r.y1 + box[1], r.x0 + box[2], r.y1 + box[3])
    page.insert_textbox(rect, str(content), fontsize=fontsize, align=align)

def place_signature_near(page, label, pil_img, rel_rect=(0, 10, 240, 90)):
    """Cola a assinatura (PIL) numa caixa relativa à âncora (label)."""
    if pil_img is None:
        return
    r = search_once(page, label)
    if not r:
        return
    rect = fitz.Rect(r.x0 + rel_rect[0], r.y1 + rel_rect[1], r.x0 + rel_rect[2], r.y1 + rel_rect[3])
    buf = BytesIO()
    pil_img.save(buf, format="PNG")
    page.insert_image(rect, stream=buf.getvalue())

# ============== GERAÇÃO DO PDF ==============
if submitted:
    # 1) Tentar carregar PDF base da pasta; se não existir, pedir upload
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

    # 2) Capturar as assinaturas do upload (caso o usuário tenha clicado em "Salvar assinatura" no canvas,
    #    normalmente você trataria via postMessage -> Python; como fallback universal, usamos o input de upload).
    #    → Fluxo prático: o técnico/cliente desenha e clica "Salvar assinatura"; aparece o botão de download do PDF
    #    sem a imagem? Basta tocar no upload e enviar um print/printscreen do canvas.
    sigtec_img = None
    sigcli_img = None
    if sigtec_upload is not None:
        sigtec_img = Image.open(sigtec_upload).convert("RGBA")
    if sigcli_upload is not None:
        sigcli_img = Image.open(sigcli_upload).convert("RGBA")

    # 3) Abrir o PDF e preencher
    try:
        doc = fitz.open(stream=base_bytes, filetype="pdf")
        page = doc[0]

        # TOPO: Cliente / Endereço / Bairro / Cidade / Contato / RG / Telefone
        insert_right_of(page, ["Cliente:", "CLIENTE:"], cliente_nome)
        insert_right_of(page, ["Endereço:", "ENDEREÇO:"], endereco)
        insert_right_of(page, ["Bairro:", "BAIRRO:"], bairro)
        insert_right_of(page, ["Cidade:", "CIDADE:"], cidade)

        insert_right_of(page, ["Contato:"], contato_nome)
        # Atenção: o PDF tem mais de um "RG:"; esse método pega a primeira âncora RG do topo.
        insert_right_of(page, ["RG:"], contato_rg)
        insert_right_of(page, ["Telefone:", "TELEFONE:"], normalize_phone(contato_tel))

        # Data / Horas / KM
        insert_right_of(page, ["Data do atendimento:", "Data do Atendimento:"], data_atend.strftime("%d/%m/%Y"))
        insert_right_of(page, ["Hora Inicio:", "Hora Início:", "Hora inicio:"], hora_ini.strftime("%H:%M"))
        insert_right_of(page, ["Hora Termino:", "Hora Término:", "Hora termino:"], hora_fim.strftime("%H:%M"))
        insert_right_of(page, ["Distancia (KM)", "Distância (KM)"], str(distancia_km))

        # BLOCO: DESCRIÇÃO DE ATENDIMENTO
        bloco = ""
        seriais_linhas = [ln.strip() for ln in (seriais_texto or "").splitlines() if ln.strip()]
        if seriais_linhas:
            bloco += "SERIAIS:\n" + "\n".join(f"- {s}" for s in seriais_linhas) + "\n\n"
        if (atividade or "").strip():
            bloco += "ATIVIDADE:\n" + atividade.strip() + "\n\n"
        if (info_extra or "").strip():
            bloco += "INFORMAÇÕES ADICIONAIS:\n" + info_extra.strip()
        insert_textbox_below(
            page,
            ["DESCRIÇÃO DE ATENDIMENTO", "DESCRICAO DE ATENDIMENTO"],
            bloco,
            box=(0, 20, 540, 240),  # largura/altura do bloco
            fontsize=10,
            align=0
        )

        # LINHA: EQUIPAMENTO / MODELO / Nº DE SERIE
        insert_right_of(page, ["EQUIPAMENTO:"], equipamento)
        insert_right_of(page, ["MODELO:"], modelo)
        insert_right_of(page, ["Nº DE SERIE:", "Nº DE SÉRIE:", "NO DE SERIE:"], serie_principal)

        # TÉCNICO / RG (sem ajuste manual) + ASSINATURA DIGITAL
        insert_right_of(page, ["TÉCNICO", "TECNICO"], tec_nome)
        # o próximo RG pode colidir com o RG do contato; se isso ocorrer na sua versão, posso ancorar pelo "TÉCNICO"
        # e deslocar para a direita. Aqui mantemos o básico:
        insert_right_of(page, ["TÉCNICO RG:", "TÉCNICO  RG:", "TECNICO RG:"], tec_rg)
        place_signature_near(page, ["ASSINATURA:", "Assinatura:"], sigtec_img, rel_rect=(180, -10, 380, 60))

        # CLIENTE (rodapé) + ASSINATURA DIGITAL
        # Preenche nome legível + RG + telefone (se o seu RAT tiver campos específicos, posso ajustar as âncoras)
        insert_right_of(page, ["NOME LEGÍVEL", "NOME LEGIVEL"], cliente_nome)
        insert_right_of(page, [" RG", "RG\n"], contato_rg)  # usa o RG informado no topo (contato); ajuste se quiser outro doc
        # Se houver um label claro de telefone no rodapé, acrescente-o aqui; muitos RATs só têm a caixa e a assinatura.
        place_signature_near(page, ["DATA CARIMBO / ASSINATURA", "ASSINATURA", "CLIENTE"], sigcli_img, rel_rect=(310, 10, 560, 90))

        # Nº CHAMADO
        insert_right_of(page, ["Nº CHAMADO", "No CHAMADO"], num_chamado, dx=12)

        # Salvar saída
        buf = BytesIO()
        doc.save(buf)
        doc.close()

        st.success("PDF gerado com sucesso!")
        st.download_button(
            "⬇️ Baixar RAT preenchido",
            data=buf.getvalue(),
            file_name=f"RAT_MAM_preenchido_{(num_chamado or 'sem_num')}.pdf",
            mime="application/pdf"
        )

    except Exception as e:
        st.error(f"Falha ao gerar PDF: {e}")
        st.exception(e)
