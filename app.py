# app.py — RAT MAM (mobile-first)
# - Foco em celular: UI em uma coluna, botões grandes, câmera para assinaturas
# - Sem dependências nativas (funciona no Streamlit Cloud)
# - Gera PDF usando overlay (pypdf + reportlab)
# - Sem scanner (em cloud é instável); se quiser, dá pra ativar local mais tarde

import streamlit as st
from datetime import date, time
from io import BytesIO
from PIL import Image
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from pypdf import PdfReader, PdfWriter

# ========= CONFIG =========
PDF_BASE_PATH = "RAT MAM.pdf"  # deixe este arquivo na raiz do repo
APP_TITLE = "RAT MAM - Preenchimento (Mobile)"

st.set_page_config(page_title=APP_TITLE, layout="centered")

# CSS simples para melhorar toque/legibilidade no celular
st.markdown("""
<style>
    .stButton>button { padding: 14px 18px; font-size: 18px; width: 100%; }
    textarea, input, .stTextInput>div>div>input { font-size: 18px !important; }
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    .stDownloadButton>button { padding: 14px 18px; font-size: 18px; width: 100%; }
</style>
""", unsafe_allow_html=True)

st.title("📄 " + APP_TITLE)
st.caption("Preencha os campos abaixo. Use a câmera do celular para as assinaturas. (Scanner de código desativado para máxima compatibilidade.)")

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

# --------- FORM ÚNICO (evita recarregamentos no celular) ---------
with st.form("rat_mam_form"):
    st.subheader("1) Chamado e Agenda")
    num_chamado = st.text_input("Nº do chamado")
    col_a, col_b = st.columns(2)
    with col_a:
        data_atend = st.date_input("Data", value=date.today())
        hora_ini = st.time_input("Início", value=time(8, 0))
    with col_b:
        hora_fim = st.time_input("Término", value=time(10, 0))
        distancia_km = st.text_input("Distância (KM)")

    st.subheader("2) Cliente (topo do PDF)")
    cliente_nome = st.text_input("Cliente / Razão Social")
    endereco = st.text_input("Endereço")
    bairro = st.text_input("Bairro")
    cidade = st.text_input("Cidade")
    contato_nome = st.text_input("Contato (nome)")
    contato_rg = st.text_input("Contato (RG/Doc)")
    contato_tel = st.text_input("Contato (Telefone)")

    st.subheader("3) Descrição de Atendimento")
    seriais_texto = st.text_area("Seriais (um por linha)", placeholder="SN0012345\nSN00ABC678\n...")
    atividade = st.text_area("Atividade (palavras do técnico)",
                             placeholder="Descreva o que foi feito: troca/configurações/testes/resultados.",
                             height=120)
    info_extra = st.text_area("Informações adicionais (opcional)", height=80)

    st.subheader("4) Linha: Equipamento / Modelo / Nº de Série (PDF)")
    equipamento = st.text_input("Equipamento", placeholder="ex.: Access Point / Switch / Nobreak")
    modelo = st.text_input("Modelo", placeholder="ex.: EAP-225 / SG3428MP / SMS XYZ")
    serie_principal = st.text_input("Nº de Série (principal)", placeholder="ex.: SN12345678")

    st.subheader("5) Técnico")
    tec_nome = st.text_input("Nome do técnico")
    tec_rg = st.text_input("RG/Documento do técnico")
    st.caption("Assinatura do técnico (use a câmera do celular)")
    sig_tec_cam = st.camera_input("Foto da assinatura do técnico (papel + caneta)")

    st.subheader("6) Cliente (rodapé do PDF)")
    cli_nome_legivel = st.text_input("Nome legível (cliente)", value=cliente_nome)
    cli_rg = st.text_input("Documento (RG/CPF) do cliente")
    cli_tel = st.text_input("Telefone (cliente)")
    st.caption("Assinatura do cliente (use a câmera do celular)")
    sig_cli_cam = st.camera_input("Foto da assinatura do cliente (papel + caneta)")

    with st.expander("⚙️ Calibração (use só se algo sair do lugar)"):
        st.caption("A4 = 595 x 842 pt (1 pt ≈ 0,35 mm).")
        off_top_x = st.number_input("Ajuste X (Topo)", -200, 200, 0)
        off_top_y = st.number_input("Ajuste Y (Topo)", -200, 200, 0)
        off_desc_x = st.number_input("Ajuste X (Descrição)", -200, 200, 0)
        off_desc_y = st.number_input("Ajuste Y (Descrição)", -200, 200, 0)
        off_eqp_x = st.number_input("Ajuste X (Equip/Modelo/Série)", -200, 200, 0)
        off_eqp_y = st.number_input("Ajuste Y (Equip/Modelo/Série)", -200, 200, 0)
        off_tec_x = st.number_input("Ajuste X (Técnico)", -200, 200, 0)
        off_tec_y = st.number_input("Ajuste Y (Técnico)", -200, 200, 0)
        off_cli_x = st.number_input("Ajuste X (Cliente rodapé)", -200, 200, 0)
        off_cli_y = st.number_input("Ajuste Y (Cliente rodapé)", -200, 200, 0)
        off_ch_x  = st.number_input("Ajuste X (Nº CHAMADO)", -200, 200, 0)
        off_ch_y  = st.number_input("Ajuste Y (Nº CHAMADO)", -200, 200, 0)

    submitted = st.form_submit_button("🧾 Gerar PDF preenchido")

# --------- GERAÇÃO DO PDF ---------
def build_overlay_pdf(base_bytes: bytes) -> bytes:
    packet = BytesIO()
    c = rl_canvas.Canvas(packet, pagesize=A4)
    c.setFont("Helvetica", 10)

    # Topo (Cliente/Endereço/Bairro/Cidade/Contato/RG/Telefone/Data/Horas/KM)
    x0, y0 = 80 + off_top_x, 780 + off_top_y
    line = 14
    c.drawString(x0, y0, str(cliente_nome or ""))
    c.drawString(x0, y0 - line, str(endereco or ""))
    c.drawString(x0, y0 - 2*line, str(bairro or ""))
    c.drawString(x0 + 260, y0 - 2*line, str(cidade or ""))

    c.drawString(x0, y0 - 3*line, str(contato_nome or ""))
    c.drawString(x0 + 180, y0 - 3*line, str(contato_rg or ""))
    c.drawString(x0 + 330, y0 - 3*line, normalize_phone(contato_tel or ""))

    c.drawString(x0,       y0 - 4*line, (data_atend.strftime("%d/%m/%Y") if data_atend else ""))
    c.drawString(x0 + 160, y0 - 4*line, (hora_ini.strftime("%H:%M") if hora_ini else ""))
    c.drawString(x0 + 260, y0 - 4*line, (hora_fim.strftime("%H:%M") if hora_fim else ""))
    c.drawString(x0 + 360, y0 - 4*line, str(distancia_km or ""))

    # DESCRIÇÃO — monta bloco (seriais + atividade + info) — não repete em outro lugar
    bloco_desc = ""
    seriais_linhas = [ln.strip() for ln in (seriais_texto or "").splitlines() if ln.strip()]
    if seriais_linhas:
        bloco_desc += "SERIAIS:\n" + "\n".join(f"- {s}" for s in seriais_linhas) + "\n\n"
    if (atividade or "").strip():
        bloco_desc += "ATIVIDADE:\n" + atividade.strip() + "\n\n"
    if (info_extra or "").strip():
        bloco_desc += "INFORMAÇÕES ADICIONAIS:\n" + info_extra.strip()

    if bloco_desc:
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, Frame
        from reportlab.lib.enums import TA_LEFT
        styles = getSampleStyleSheet()
        styleN = styles["Normal"]
        styleN.fontName = "Helvetica"
        styleN.fontSize = 10
        styleN.leading = 12
        styleN.alignment = TA_LEFT
        x_desc, y_desc = 60 + off_desc_x, 610 + off_desc_y
        w_desc, h_desc = 480, 150
        frame = Frame(x_desc, y_desc - h_desc + 150, w_desc, h_desc, showBoundary=0)
        story = [Paragraph(bloco_desc.replace("\n", "<br/>"), styleN)]
        frame.addFromList(story, c)

    # Linha: EQUIPAMENTO / MODELO / Nº DE SÉRIE
    x_eqp, y_eqp = 70 + off_eqp_x, 560 + off_eqp_y
    c.drawString(x_eqp, y_eqp, str(equipamento or ""))
    c.drawString(x_eqp + 180, y_eqp, str(modelo or ""))
    c.drawString(x_eqp + 360, y_eqp, str(serie_principal or ""))

    # TÉCNICO (nome, RG, assinatura)
    x_tec, y_tec = 70 + off_tec_x, 520 + off_tec_y
    c.drawString(x_tec, y_tec, str(tec_nome or ""))
    c.drawString(x_tec + 180, y_tec, str(tec_rg or ""))
    if sig_tec_cam is not None:
        try:
            c.drawImage(ImageReader(sig_tec_cam), x_tec + 310, y_tec - 10,
                        width=160, height=40, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    # CLIENTE (rodapé)
    x_cli, y_cli = 70 + off_cli_x, 450 + off_cli_y
    c.drawString(x_cli, y_cli, f"NOME LEGÍVEL: {cli_nome_legivel or ''}")
    c.drawString(x_cli, y_cli - line, f"RG/CPF: {cli_rg or ''}")
    c.drawString(x_cli, y_cli - 2*line, f"Telefone: {normalize_phone(cli_tel or '')}")
    if sig_cli_cam is not None:
        try:
            c.drawImage(ImageReader(sig_cli_cam), x_cli + 260, y_cli - 10,
                        width=220, height=60, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    # Nº CHAMADO
    x_ch, y_ch = 420 + off_ch_x, 430 + off_ch_y
    c.drawString(x_ch, y_ch, str(num_chamado or ""))

    c.showPage()
    c.save()
    packet = BytesIO(packet.getvalue())

    # Mescla overlay com PDF base
    overlay_pdf = PdfReader(packet)
    base_reader = PdfReader(BytesIO(base_bytes))
    writer = PdfWriter()
    base_page = base_reader.pages[0]
    base_page.merge_page(overlay_pdf.pages[0])
    writer.add_page(base_page)
    for i in range(1, len(base_reader.pages)):
        writer.add_page(base_reader.pages[i])

    out = BytesIO()
    writer.write(out)
    return out.getvalue()

if submitted:
    # Carrega base
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
