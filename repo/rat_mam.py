# --- PATH FIX: permitir imports a partir da raiz (common/, pdf_templates/) ---
import os, sys
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
# ------------------------------------------------------------------------------

from io import BytesIO
from datetime import date, time
import streamlit as st
from PIL import Image
import fitz

from common.state import init_defaults          # ← este import faltava
from common.ui import assinatura_dupla_png, scanner_minimo
from common.pdf import (
    open_pdf_template, search_once, insert_right_of, insert_textbox,
    insert_signature_png, add_image_page, CM
)

# Caminho do template PDF partindo da raiz do repo
PDF_DIR = os.path.join(PROJECT_ROOT, "pdf_templates")
PDF_BASE_PATH = os.path.join(PDF_DIR, "RAT MAM")

def render():
    st.header("🧾 RAT MAM")

    # Estado inicial
    init_defaults({
        "data_atend": date.today(),
        "hora_ini": time(8,0),
        "hora_fim": time(10,0),
        "num_chamado": "",
        "cliente_nome": "", "endereco": "", "bairro": "", "cidade": "",
        "contato_nome": "", "contato_rg": "", "contato_tel": "",
        "distancia_km": "",
        "seriais_texto": "", "atividade_txt": "", "info_txt": "",
        "photos_to_append": [], "seen_hashes": set(),
        "sig_tec_png": None, "sig_cli_png": None,
        "anexar_fotos": True,
    })

    ss = st.session_state

    # 1) Dados
    with st.expander("1) Dados do RAT (MAM)", expanded=True):
        c1,c2 = st.columns(2)
        with c1:
            ss.data_atend = st.date_input("Data do atendimento", value=ss.data_atend)
            ss.hora_ini   = st.time_input("Hora início", value=ss.hora_ini)
            ss.num_chamado= st.text_input("Nº do chamado", value=ss.num_chamado)
            ss.cliente_nome = st.text_input("Cliente / Razão Social", value=ss.cliente_nome)
            ss.contato_tel  = st.text_input("Telefone (contato)", value=ss.contato_tel)
        with c2:
            ss.hora_fim    = st.time_input("Hora término", value=ss.hora_fim)
            ss.distancia_km= st.text_input("Distância (KM)", value=ss.distancia_km)
            ss.contato_nome= st.text_input("Contato (nome)", value=ss.contato_nome)
            ss.contato_rg  = st.text_input("Contato (RG/Doc)", value=ss.contato_rg)

        ss.endereco = st.text_input("Endereço", value=ss.endereco)
        ss.bairro   = st.text_input("Bairro", value=ss.bairro)
        ss.cidade   = st.text_input("Cidade", value=ss.cidade)

    # 2) Seriais & Descrição + Scanner mínimo (somente anexa fotos válidas)
    with st.expander("2) Seriais & Descrição", expanded=True):
        scanner_minimo()  # preenche ss.photos_to_append; mostra limpar itens/fotos
        ss.seriais_texto = st.text_area("Seriais (um por linha)", value=ss.seriais_texto, height=140)
        ss.atividade_txt = st.text_area("Atividade", value=ss.atividade_txt, height=100)
        ss.info_txt      = st.text_area("Informações adicionais (opcional)", value=ss.info_txt, height=80)

    # 3) Assinaturas (PNG transparente)
    with st.expander("3) Assinaturas", expanded=True):
        assinatura_dupla_png()  # preenche ss.sig_tec_png / ss.sig_cli_png

    st.checkbox("Anexar fotos ao PDF", key="anexar_fotos", value=ss.anexar_fotos)

    if st.button("🧾 Gerar PDF (MAM)"):
        try:
            doc, page = open_pdf_template(PDF_BASE_PATH)

            # Topo
            insert_right_of(page, ["Cliente:", "CLIENTE:"], ss.cliente_nome, dx=6, dy=1)
            insert_right_of(page, ["Endereço:", "ENDEREÇO:"], ss.endereco, dx=6, dy=1)
            insert_right_of(page, ["Bairro:", "BAIRRO:"], ss.bairro, dx=6, dy=1)
            insert_right_of(page, ["Cidade:", "CIDADE:"], ss.cidade, dx=6, dy=1)
            insert_right_of(page, ["Contato:"], ss.contato_nome, dx=6, dy=1)

            insert_right_of(page, ["Telefone:", "TELEFONE:"], ss.contato_tel, dx=6, dy=1)
            insert_right_of(page, ["Data do atendimento:", "Data do Atendimento:"],
                            ss.data_atend.strftime("%d/%m/%Y"), dx=-90, dy=10)
            insert_right_of(page, ["Hora Inicio:", "Hora Início:", "Hora inicio:"],
                            ss.hora_ini.strftime("%H:%M"), dx=0, dy=3)
            insert_right_of(page, ["Hora Termino:", "Hora Término:", "Hora termino:"],
                            ss.hora_fim.strftime("%H:%M"), dx=0, dy=3)
            insert_right_of(page, ["Distancia (KM) :", "Distância (KM) :"], ss.distancia_km, dx=0, dy=3)

            # Descrição
            bloco = ""
            if ss.seriais_texto.strip():
                linhas = [f"- {ln.strip()}" for ln in ss.seriais_texto.splitlines() if ln.strip()]
                bloco += "SERIAIS:\n" + "\n".join(linhas) + "\n\n"
            if ss.atividade_txt.strip():
                bloco += "ATIVIDADE:\n" + ss.atividade_txt.strip() + "\n\n"
            if ss.info_txt.strip():
                bloco += "INFORMAÇÕES ADICIONAIS:\n" + ss.info_txt.strip()
            insert_textbox(page, ["DESCRIÇÃO DE ATENDIMENTO","DESCRICAO DE ATENDIMENTO"],
                           bloco, width=540, y_offset=20)

            # Assinaturas (PNG transparente)
            insert_signature_png(page, ["ASSINATURA:", "Assinatura:"], ss.sig_tec_png,
                                 (110 - 2*CM, 0 - 1*CM, 330 - 2*CM, 54 - 1*CM))
            insert_signature_png(page, ["DATA CARIMBO / ASSINATURA", "ASSINATURA CLIENTE", "CLIENTE"],
                                 ss.sig_cli_png, (110, 12 - 3.5*CM, 430, 94 - 3.5*CM))

            # Nº chamado
            insert_right_of(page, [" Nº CHAMADO ", "Nº CHAMADO", "No CHAMADO"], ss.num_chamado,
                            dx=-(2*CM), dy=10)

            # Fotos anexas
            if st.session_state.get("anexar_fotos", True):
                for img_bytes in ss.photos_to_append:
                    add_image_page(doc, img_bytes)

            out = BytesIO(); doc.save(out); doc.close()
            st.success("PDF (MAM) gerado!")
            st.download_button("⬇️ Baixar RAT MAM", data=out.getvalue(),
                               file_name=f"RAT_MAM_{(ss.num_chamado or 'sem_num')}.pdf",
                               mime="application/pdf")
        except Exception as e:
            st.error("Falha ao gerar PDF MAM.")
            st.exception(e)
