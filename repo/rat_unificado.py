# repo/rat_mam_unificada.py
# Tela principal da RAT MAM UNIFICADA
# - usa o layout dark do ui_rat_unificada
# - prepara session_state
# - botão para gerar o PDF unificado

import os
from io import BytesIO
from datetime import date, time, datetime
from zoneinfo import ZoneInfo

import streamlit as st

from common.state import init_defaults
from common.pdf import open_pdf_template, add_image_page  # add_image_page p/ fotos depois
from ui_unificado import render_layout

# Paths do projeto
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
PDF_DIR = os.path.join(PROJECT_ROOT, "pdf_templates")
PDF_BASE_PATH = os.path.join(PDF_DIR, "RAT_MAM_UNIFICADA_VF.pdf")

DEFAULT_TZ = "America/Sao_Paulo"


def _now_tz(tz_name: str | None = None) -> datetime:
    tzname = tz_name or DEFAULT_TZ
    try:
        tz = ZoneInfo(tzname)
    except Exception:
        tz = ZoneInfo(DEFAULT_TZ)
    return datetime.now(tz=tz)


def render():
    st.header("")

    # ==== Defaults para os campos usados no layout ====
    init_defaults(
        {
            # Identificação
            "data_atendimento": date.today(),
            "hora_inicio": time(8, 0),
            "hora_termino": time(10, 0),
            "numero_chamado": "",
            "analista_mam": "",
            "tipo_atendimento": "",
            "cliente": "",
            "cnpj": "",
            "endereco": "",
            "cidade_uf": "",
            "contato_local": "",
            "telefone_local": "",
            "email_local": "",

            # Dados operacionais
            "site_id": "",
            "operadora": "",
            "tipo_link": "",
            "endereco_ip": "",
            "vlan": "",
            "gw": "",
            "eq_tipo": "",
            "eq_fabricante": "",
            "eq_modelo": "",
            "eq_serial": "",

            # Execução
            "servicos_realizados": "",
            "testes_executados": "",
            "obs_gerais": "",

            # Produtividade / aceite
            "produtivo": "sim-totalmente produtivo",
            "teste_final_wan": "NA",
            "resumo_resultado": "",
            "tecnico_nome": "",
            "cliente_validador_nome": "",
            "validador_tel": "",

            # Fotos (você pluga seu uploader aqui depois)
            "fotos_gateway": [],
        }
    )

    # ==== Layout da tela (abas, cards, etc.) ====
    render_layout()

    ss = st.session_state

    st.divider()

    col_a, col_b = st.columns([1, 3])
    with col_a:
        gerar = st.button("🧾 Gerar RAT Unificada (PDF)")
    with col_b:
        st.caption(
            "O PDF usa o template **RAT_MAM_UNIFICADA_VF.pdf** na pasta `pdf_templates`. "
            "Depois fazemos o preenchimento campo a campo."
        )

    if not gerar:
        return

    # ========== GERAÇÃO SIMPLES DE PDF ==========
    try:
        if not os.path.exists(PDF_BASE_PATH):
            st.error(f"Template não encontrado em: {PDF_BASE_PATH}")
            return

        doc, page1 = open_pdf_template(PDF_BASE_PATH, hint="RAT_MAM_UNIFICADA_VF")

        # Aqui poderíamos já começar a preencher algo simples, ex:
        # escrever um selo discreto de geração automática no rodapé da página 1
        agora = _now_tz()
        txt = f"Gerado automaticamente em {agora.strftime('%d/%m/%Y %H:%M')} - Chamado {ss.numero_chamado or '-'}"

        # Retângulo no rodapé da página 1
        r = page1.rect
        footer_rect = (r.width - 320, r.height - 28)
        page1.insert_text(
            footer_rect,
            txt,
            fontsize=7.5,
        )

        # Se já tiver fotos no ss.fotos_gateway, opcionalmente adiciona como páginas
        fotos = ss.get("fotos_gateway", []) or []
        if isinstance(fotos, list) and len(fotos) > 0:
            for b in fotos:
                if not b:
                    continue
                try:
                    add_image_page(doc, b)
                except Exception:
                    # se der ruim numa imagem, segue o baile nas outras
                    continue

        # Salva em memória
        out = BytesIO()
        doc.save(out)
        doc.close()

        st.success("PDF da RAT MAM Unificada gerado!")
        st.download_button(
            "⬇️ Baixar RAT MAM Unificada",
            data=out.getvalue(),
            file_name=f"RAT_MAM_UNIFICADA_{(ss.numero_chamado or 'sem_chamado')}.pdf",
            mime="application/pdf",
        )

    except Exception as e:
        st.error("Falha ao gerar o PDF da RAT Unificada.")
        st.exception(e)
