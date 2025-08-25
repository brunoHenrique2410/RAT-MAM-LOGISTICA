# repo/rat_oi_cpe.py — RAT OI CPE (preenchimento ancorado, assinaturas +3cm)

# --- PATH FIX: permite importar common/ e pdf_templates/ a partir da raiz ---
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
# ---------------------------------------------------------------------------

from io import BytesIO
from datetime import date, time
import streamlit as st
from PIL import Image
import fitz

from common.state import init_defaults
from common.ui import assinatura_dupla_png, foto_gateway_uploader
from common.pdf import (
    open_pdf_template, search_once, insert_right_of, insert_textbox, mark_X_left_of,
    insert_signature_png, add_image_page, CM
)

PDF_DIR = os.path.join(PROJECT_ROOT, "pdf_templates")
PDF_BASE_PATH = os.path.join(PDF_DIR, "RAT_OI_CPE_NOVO.pdf")


# ===================== Helpers locais =====================

def _find_any(page, labels, occurrence=1):
    """
    Busca a 'occurrence'-ésima ocorrência de qualquer label na lista.
    Retorna o primeiro Rect correspondente ou None.
    """
    if isinstance(labels, str):
        labels = [labels]
    occ = 0
    for txt in labels:
        try:
            rs = page.search_for(txt)
        except Exception:
            rs = []
        for r in rs:
            occ += 1
            if occ == occurrence:
                return r
    return None


def insert_equip_table(page, rows, row_height=18, dy_header=42, fontsize=10):
    """
    Preenche a grade 'EQUIPAMENTOS NO CLIENTE' célula a célula.
    Usa as âncoras dos títulos de coluna e escreve as linhas para baixo.
    Evita sobrepor o cabeçalho da tabela.
    """
    if not rows:
        return

    # âncora do bloco para referência
    blk_anchor = _find_any(page, ["EQUIPAMENTOS NO CLIENTE", "Equipamentos no Cliente"])
    if not blk_anchor:
        return

    # cabeçalhos das 4 colunas
    tipo_r = _find_any(page, ["Tipo"])
    ns_r   = _find_any(page, ["Nº de Série", "No de Serie", "Nº de Serie", "N° de Série"])
    fab_r  = _find_any(page, ["Fabricante"])
    st_r   = _find_any(page, ["Status"])

    # fallback se não achar algum cabeçalho
    if not (tipo_r and ns_r and fab_r and st_r):
        base_x = blk_anchor.x0 + 12
        y0 = blk_anchor.y1 + dy_header
        xs = [base_x, base_x + 160, base_x + 320, base_x + 460]
    else:
        # inicie um pouco abaixo da linha dos cabeçalhos
        y0 = max(tipo_r.y1, ns_r.y1, fab_r.y1, st_r.y1) + (dy_header - 20)
        xs = [tipo_r.x0, ns_r.x0, fab_r.x0, st_r.x0]

    for i, r in enumerate(rows):
        y = y0 + i * row_height
        vals = [
            r.get("tipo", ""),
            r.get("numero_serie", ""),
            r.get("fabricante", ""),
            r.get("status", ""),
        ]
        for x, val in zip(xs, vals):
            if val:
                page.insert_text((x + 4, y), str(val), fontsize=fontsize)


def _normalize_equip_rows(rows):
    """
    Garante que toda linha tenha as 4 chaves, evitando apagar colunas ao editar.
    """
    out = []
    for r in rows or []:
        out.append({
            "tipo": r.get("tipo", ""),
            "numero_serie": r.get("numero_serie", ""),
            "fabricante": r.get("fabricante", ""),
            "status": r.get("status", ""),
        })
    if not out:
        out = [{"tipo": "", "numero_serie": "", "fabricante": "", "status": ""}]
    return out


# ===================== UI + Geração =====================

def render():
    st.header("🔌 RAT OI CPE NOVO")

    # ---------- Estado inicial ----------
    init_defaults({
        "cliente": "",
        "numero_chamado": "",
        "hora_inicio": time(8, 0),
        "hora_termino": time(10, 0),

        # Serviços e atividades solicitadas
        "svc_instalacao": False,
        "svc_retirada": False,
        "svc_vistoria": False,
        "svc_alteracao": False,
        "svc_mudanca": False,
        "svc_teste_conjunto": False,
        "svc_servico_interno": False,

        # Identificação – Aceite da Atividade
        "teste_wan": "NA",
        "tecnico_nome": "",
        "cliente_ciente_nome": "",
        "contato": "",
        "data_aceite": date.today(),
        "horario_aceite": time(10, 0),
        "aceitacao_resp": "",
        "sig_tec_png": None,
        "sig_cli_png": None,

        # Tabela Equipamentos no Cliente
        "equip_cli": [{"tipo": "", "numero_serie": "", "fabricante": "", "status": ""}],

        # Blocos de texto
        "problema_encontrado": "",
        "observacoes": "",

        # Fotos (gateway)
        "fotos_gateway": [],
    })

    ss = st.session_state

    # ---------- 1) Cabeçalho ----------
    with st.expander("1) Cabeçalho", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            ss.cliente = st.text_input("Cliente", value=ss.cliente)
            ss.numero_chamado = st.text_input("Número do Chamado", value=ss.numero_chamado)
            ss.hora_inicio = st.time_input("Horário Início", value=ss.hora_inicio)
        with c2:
            st.caption("“Número do Bilhete” e “Designação do Circuito” receberão o Nº do Chamado.")
            ss.hora_termino = st.time_input("Horário Término", value=ss.hora_termino)

    # ---------- 2) Serviços e Atividades ----------
    with st.expander("2) Serviços e Atividades Solicitadas", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            ss.svc_instalacao = st.checkbox("Instalação", value=ss.svc_instalacao)
            ss.svc_retirada = st.checkbox("Retirada", value=ss.svc_retirada)
            ss.svc_vistoria = st.checkbox("Vistoria Técnica", value=ss.svc_vistoria)
        with c2:
            ss.svc_alteracao = st.checkbox("Alteração Técnica", value=ss.svc_alteracao)
            ss.svc_mudanca = st.checkbox("Mudança de Endereço", value=ss.svc_mudanca)
        with c3:
            ss.svc_teste_conjunto = st.checkbox("Teste em conjunto", value=ss.svc_teste_conjunto)
            ss.svc_servico_interno = st.checkbox("Serviço interno", value=ss.svc_servico_interno)

    # ---------- 3) Identificação – Aceite ----------
    with st.expander("3) Identificação – Aceite da Atividade", expanded=True):
        ss.teste_wan = st.radio(
            "Teste de conectividade WAN realizado com sucesso?",
            ["S", "N", "NA"],
            index=["S", "N", "NA"].index(ss.teste_wan)
        )
        c1, c2 = st.columns(2)
        with c1:
            ss.tecnico_nome = st.text_input("Técnico (nome)", value=ss.tecnico_nome)
            ss.cliente_ciente_nome = st.text_input("Cliente ciente (nome)", value=ss.cliente_ciente_nome)
            ss.contato = st.text_input("Contato (telefone)", value=ss.contato)
        with c2:
            ss.data_aceite = st.date_input("Data", value=ss.data_aceite)
            ss.horario_aceite = st.time_input("Horário", value=ss.horario_aceite)
            ss.aceitacao_resp = st.text_input("Aceitação do serviço pelo responsável", value=ss.aceitacao_resp)

        # Captura das assinaturas (PNG com transparência)
        assinatura_dupla_png()  # popula ss.sig_tec_png e ss.sig_cli_png

    # ---------- 4) Equipamentos ----------
    with st.expander("4) Equipamentos no Cliente", expanded=True):
        st.caption("Preencha ao menos 1 linha.")
        ss.equip_cli = _normalize_equip_rows(ss.equip_cli)
        data = st.data_editor(
            ss.equip_cli,
            num_rows="dynamic",
            use_container_width=True,
            key="equip_cli_editor",
            column_config={
                "tipo": st.column_config.TextColumn("Tipo"),
                "numero_serie": st.column_config.TextColumn("Nº de Série"),
                "fabricante": st.column_config.TextColumn("Fabricante"),
                "status": st.column_config.TextColumn("Status"),
            },
        )
        ss.equip_cli = _normalize_equip_rows(data)

    # ---------- 5) Problema / Observações ----------
    with st.expander("5) Problema Encontrado & Observações", expanded=True):
        ss.problema_encontrado = st.text_area("Problema Encontrado", value=ss.problema_encontrado, height=120)
        ss.observacoes = st.text_area("Observações", value=ss.observacoes, height=120)

    # ---------- 6) Foto(s) do Gateway ----------
    with st.expander("6) Foto do Gateway", expanded=True):
        foto_gateway_uploader()  # adiciona bytes das imagens em ss.fotos_gateway

    # ---------- Geração do PDF ----------
    if st.button("🧾 Gerar PDF (OI CPE)"):
        try:
            # Abre o template
            doc, page1 = open_pdf_template(PDF_BASE_PATH, hint="RAT OI CPE NOVO")
            has_p2 = doc.page_count >= 2
            page2 = doc[1] if has_p2 else page1  # alvo dos blocos pós-cabeçalho

            # ====== PÁGINA 1: Cabeçalho + Serviços ======
            insert_right_of(page1, ["Cliente"], ss.cliente, dx=8, dy=1)
            insert_right_of(page1, ["Número do Bilhete", "Numero do Bilhete"], ss.numero_chamado, dx=8, dy=1)
            insert_right_of(page1, ["Designação do Circuito", "Designacao do Circuito"], ss.numero_chamado, dx=8, dy=1)

            insert_right_of(page1, ["Horário Início", "Horario Inicio", "Horario Início"],
                            ss.hora_inicio.strftime("%H:%M"), dx=8, dy=1)
            insert_right_of(page1, ["Horário Término", "Horario Termino", "Horário termino"],
                            ss.hora_termino.strftime("%H:%M"), dx=8, dy=1)

            # Serviços – marcar X na página 1
            if ss.svc_instalacao:
                mark_X_left_of(page1, "Instalação", dx=-16, dy=0)
            if ss.svc_retirada:
                mark_X_left_of(page1, "Retirada", dx=-16, dy=0)
            if ss.svc_vistoria:
                mark_X_left_of(page1, "Vistoria Técnica", dx=-16, dy=0)
                mark_X_left_of(page1, "Vistoria Tecnica", dx=-16, dy=0)
            if ss.svc_alteracao:
                mark_X_left_of(page1, "Alteração Técnica", dx=-16, dy=0)
                mark_X_left_of(page1, "Alteracao Tecnica", dx=-16, dy=0)
            if ss.svc_mudanca:
                mark_X_left_of(page1, "Mudança de Endereço", dx=-16, dy=0)
                mark_X_left_of(page1, "Mudanca de Endereco", dx=-16, dy=0)
            if ss.svc_teste_conjunto:
                mark_X_left_of(page1, "Teste em conjunto", dx=-16, dy=0)
            if ss.svc_servico_interno:
                mark_X_left_of(page1, "Serviço interno", dx=-16, dy=0)
                mark_X_left_of(page1, "Servico interno", dx=-16, dy=0)

            # ====== Alvo dos blocos “parte 2” (page2 se existir) ======
            target = page2

            # Identificação – Aceite (textos)
            insert_right_of(target, ["Técnico:", "Tecnico:", "Técnico", "Tecnico"],
                            ss.tecnico_nome, dx=8, dy=1)
            insert_right_of(target, ["Cliente Ciente:", "Cliente Ciente"],
                            ss.cliente_ciente_nome, dx=8, dy=1)
            insert_right_of(target, ["Contato:", "Contato"],
                            ss.contato, dx=8, dy=1)
            insert_right_of(target, ["Data:", "Data"],
                            ss.data_aceite.strftime("%d/%m/%Y"), dx=8, dy=1)
            insert_right_of(target, ["Horário:", "Horario:", "Horário", "Horario"],
                            ss.horario_aceite.strftime("%H:%M"), dx=8, dy=1)
            insert_right_of(target, ["Aceitação do serviço", "Aceitacao do servico"],
                            ss.aceitacao_resp, dx=8, dy=1)

            # Teste WAN — X em S/N/NA
            if ss.teste_wan == "S":
                mark_X_left_of(target, "S", dx=-12, dy=0, occurrence=1)
            elif ss.teste_wan == "N":
                mark_X_left_of(target, "N", dx=-12, dy=0, occurrence=1)
            else:
                mark_X_left_of(target, "N/A", dx=-12, dy=0, occurrence=1)

            # Assinaturas — subir 3 cm
            up3 = 3 * CM
            insert_signature_png(target, ["Assinatura"], ss.sig_tec_png,
                                 (80, 20 - up3, 280, 90 - up3), occurrence=1)
            insert_signature_png(target, ["Assinatura"], ss.sig_cli_png,
                                 (80, 20 - up3, 280, 90 - up3), occurrence=2)

            # Equipamentos no Cliente (tabela)
            insert_equip_table(target, ss.equip_cli, row_height=18, dy_header=42, fontsize=10)

            # Problema / Observações
            if (ss.problema_encontrado or "").strip():
                insert_textbox(target, ["PROBLEMA ENCONTRADO", "Problema Encontrado"],
                               ss.problema_encontrado, width=540, y_offset=20, height=160, fontsize=10)
            if (ss.observacoes or "").strip():
                insert_textbox(target, ["OBSERVAÇÕES", "Observacoes", "Observações"],
                               ss.observacoes, width=540, y_offset=20, height=160, fontsize=10)

            # Fotos do gateway: 1 página por foto
            for b in ss.fotos_gateway:
                if not b:
                    continue
                add_image_page(doc, b)

            # Exporta
            out = BytesIO()
            doc.save(out)
            doc.close()
            st.success("PDF (OI CPE) gerado!")
            st.download_button(
                "⬇️ Baixar RAT OI CPE",
                data=out.getvalue(),
                file_name=f"RAT_OI_CPE_{(ss.numero_chamado or 'sem_num')}.pdf",
                mime="application/pdf",
            )
        except Exception as e:
            st.error("Falha ao gerar PDF OI CPE.")
            st.exception(e)
