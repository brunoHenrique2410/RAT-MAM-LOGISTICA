# rat_oi_cpe.py — fluxo RAT OI CPE NOVO (com os campos que você pediu)
from io import BytesIO
from datetime import date, time, datetime
import streamlit as st
from PIL import Image
import fitz

from common.ui import assinatura_dupla_png, foto_gateway_uploader
from common.pdf import (
    open_pdf_template, search_once, insert_right_of, insert_textbox,
    mark_X_left_of, insert_signature_png, add_image_page, CM
)
from common.state import init_defaults

PDF_BASE_PATH = "pdf_templates/RAT OI CPE NOVO.pdf"

def render():
    st.header("🔌 RAT OI CPE NOVO")

    # Estado inicial
    init_defaults({
        "cliente": "",
        "numero_chamado": "",
        "hora_inicio": time(8,0),
        "hora_termino": time(10,0),
        # serviços
        "svc_instalacao": False, "svc_retirada": False, "svc_vistoria": False,
        "svc_alteracao": False, "svc_mudanca": False, "svc_teste_conjunto": False,
        "svc_servico_interno": False,
        # aceite
        "teste_wan": "NA",
        "tecnico_nome": "", "cliente_ciente_nome": "",
        "contato": "", "data_aceite": date.today(),
        "horario_aceite": time(10,0), "aceitacao_resp": "",
        "sig_tec_png": None, "sig_cli_png": None,
        # equipamentos cliente (lista simples)
        "equip_cli": [{"tipo":"", "numero_serie":"", "fabricante":"", "status":""}],
        # textos
        "problema_encontrado": "",
        "observacoes": "",
        # fotos
        "fotos_gateway": [],
    })

    ss = st.session_state

    # 1) Cabeçalho
    with st.expander("1) Cabeçalho", expanded=True):
        c1,c2 = st.columns(2)
        with c1:
            ss.cliente = st.text_input("Cliente", value=ss.cliente)
            ss.numero_chamado = st.text_input("Número do Chamado", value=ss.numero_chamado)
            ss.hora_inicio = st.time_input("Horário Início", value=ss.hora_inicio)
        with c2:
            st.markdown("**Número do Bilhete e Designação do Circuito receberão o Nº do Chamado.**")
            ss.hora_termino = st.time_input("Horário Término", value=ss.hora_termino)

    # 2) Serviços e Atividades Solicitadas
    with st.expander("2) Serviços e Atividades Solicitadas", expanded=True):
        c1,c2,c3 = st.columns(3)
        with c1:
            ss.svc_instalacao = st.checkbox("Instalação", value=ss.svc_instalacao)
            ss.svc_retirada   = st.checkbox("Retirada", value=ss.svc_retirada)
            ss.svc_vistoria   = st.checkbox("Vistoria Técnica", value=ss.svc_vistoria)
        with c2:
            ss.svc_alteracao  = st.checkbox("Alteração Técnica", value=ss.svc_alteracao)
            ss.svc_mudanca    = st.checkbox("Mudança de Endereço", value=ss.svc_mudanca)
        with c3:
            ss.svc_teste_conjunto = st.checkbox("Teste em conjunto", value=ss.svc_teste_conjunto)
            ss.svc_servico_interno= st.checkbox("Serviço interno", value=ss.svc_servico_interno)

    # 3) Identificação – Aceite da Atividade
    with st.expander("3) Identificação – Aceite da Atividade", expanded=True):
        ss.teste_wan = st.radio("Teste de conectividade WAN realizado com sucesso?", ["S","N","NA"], index=["S","N","NA"].index(ss.teste_wan))
        c1,c2 = st.columns(2)
        with c1:
            ss.tecnico_nome = st.text_input("Técnico (nome)", value=ss.tecnico_nome)
            ss.cliente_ciente_nome = st.text_input("Cliente ciente (nome)", value=ss.cliente_ciente_nome)
            ss.contato = st.text_input("Contato (telefone)", value=ss.contato)
        with c2:
            ss.data_aceite = st.date_input("Data", value=ss.data_aceite)
            ss.horario_aceite = st.time_input("Horário", value=ss.horario_aceite)
            ss.aceitacao_resp = st.text_input("Aceitação do serviço pelo responsável", value=ss.aceitacao_resp)

        assinatura_dupla_png()  # usa ss.sig_tec_png / ss.sig_cli_png

    # 4) Equipamentos no Cliente (dinâmico)
    with st.expander("4) Equipamentos no Cliente", expanded=True):
        st.caption("Preencha ao menos 1 linha.")
        data = st.data_editor(
            ss.equip_cli, num_rows="dynamic", use_container_width=True, key="equip_cli_editor",
            column_config={
                "tipo":        st.column_config.TextColumn("Tipo"),
                "numero_serie":st.column_config.TextColumn("Nº de Série"),
                "fabricante":  st.column_config.TextColumn("Fabricante"),
                "status":      st.column_config.TextColumn("Status"),
            },
        )
        ss.equip_cli = data

    # 5) Problema / Observações
    with st.expander("5) Problema Encontrado & Observações", expanded=True):
        ss.problema_encontrado = st.text_area("Problema Encontrado", value=ss.problema_encontrado, height=120)
        ss.observacoes         = st.text_area("Observações", value=ss.observacoes, height=120)

    # 6) Foto(s) do Gateway
    with st.expander("6) Foto do Gateway", expanded=True):
        foto_gateway_uploader()  # preenche ss.fotos_gateway

    if st.button("🧾 Gerar PDF (OI CPE)"):
        try:
            doc, page = open_pdf_template(PDF_BASE_PATH)

            # Cabeçalho
            insert_right_of(page, ["Cliente"], ss.cliente, dx=8, dy=1)
            insert_right_of(page, ["Número do Bilhete","Numero do Bilhete"], ss.numero_chamado, dx=8, dy=1)
            insert_right_of(page, ["Designação do Circuito","Designacao do Circuito"], ss.numero_chamado, dx=8, dy=1)

            # Horários (ajuste fino pode ser necessário dependendo do template)
            insert_right_of(page, ["Horario","Horário"], ss.hora_inicio.strftime("%H:%M"), dx=80, dy=0)   # início
            # término costuma ir em outro bloco; se houver âncora específica use-a:
            insert_right_of(page, ["Horário Término","Horario Termino","Horário termino"], ss.hora_termino.strftime("%H:%M"), dx=8, dy=1)

            # Serviços: marcar "X"
            if ss.svc_instalacao:       mark_X_left_of(page, "Instalação", dx=-16, dy=0)
            if ss.svc_retirada:         mark_X_left_of(page, "Retirada", dx=-16, dy=0)
            if ss.svc_vistoria:         mark_X_left_of(page, "Vistoria", dx=-16, dy=0)
            if ss.svc_alteracao:        mark_X_left_of(page, "Alteração", dx=-16, dy=0)
            if ss.svc_mudanca:          mark_X_left_of(page, "Mudança", dx=-16, dy=0)
            if ss.svc_teste_conjunto:   mark_X_left_of(page, "Teste em conjunto", dx=-16, dy=0)
            if ss.svc_servico_interno:  mark_X_left_of(page, "Serviço interno", dx=-16, dy=0)

            # Aceite — textos
            insert_right_of(page, ["Técnico","Tecnico"], ss.tecnico_nome, dx=8, dy=1)
            insert_right_of(page, ["Cliente Ciente"], ss.cliente_ciente_nome, dx=8, dy=1)
            insert_right_of(page, ["Contato"], ss.contato, dx=8, dy=1)
            insert_right_of(page, ["Data"], ss.data_aceite.strftime("%d/%m/%y"), dx=8, dy=1)
            insert_right_of(page, ["Horario","Horário"], ss.horario_aceite.strftime("%H:%M"), dx=8, dy=1)
            insert_right_of(page, ["Aceitação do serviço","Aceitacao do servico"], ss.aceitacao_resp, dx=8, dy=1)

            # Aceite — marcar S/N/NA
            if ss.teste_wan == "S":  mark_X_left_of(page, "S", dx=-12, dy=0, near_text="Teste de conectividade")
            if ss.teste_wan == "N":  mark_X_left_of(page, "N", dx=-12, dy=0, near_text="Teste de conectividade")
            if ss.teste_wan == "NA": mark_X_left_of(page, "N/A", dx=-12, dy=0, near_text="Teste de conectividade")

            # Assinaturas (PNG transparente)
            insert_signature_png(page, ["Assinatura"], ss.sig_tec_png, (80, 20, 280, 90), occurrence=1)
            insert_signature_png(page, ["Assinatura"], ss.sig_cli_png, (80, 20, 280, 90), occurrence=2)

            # Equipamentos no Cliente — tabela simplificada como texto
            if ss.equip_cli:
                linhas = ["Tipo | Nº de Série | Fabricante | Status"]
                for it in ss.equip_cli:
                    if not (it.get("tipo") or it.get("numero_serie")):
                        continue
                    linhas.append(f"{it.get('tipo','')} | {it.get('numero_serie','')} | {it.get('fabricante','')} | {it.get('status','')}")
                bloco_tab = "\n".join(linhas)
                insert_textbox(page, ["EQUIPAMENTOS NO CLIENTE","Equipamentos no Cliente"], bloco_tab, width=540, y_offset=20)

            # Problema / Observações
            if ss.problema_encontrado.strip():
                insert_textbox(page, ["PROBLEMA ENCONTRADO","Problema Encontrado"], ss.problema_encontrado, width=540, y_offset=20)
            if ss.observacoes.strip():
                insert_textbox(page, ["OBSERVAÇÕES","Observacoes","Observações"], ss.observacoes, width=540, y_offset=20)

            # Foto(s) do gateway — cada uma vira uma página
            for b in ss.fotos_gateway:
                add_image_page(doc, b)

            out = BytesIO(); doc.save(out); doc.close()
            st.success("PDF (OI CPE) gerado!")
            st.download_button("⬇️ Baixar RAT OI CPE", data=out.getvalue(),
                               file_name=f"RAT_OI_CPE_{(ss.numero_chamado or 'sem_num')}.pdf",
                               mime="application/pdf")
        except Exception as e:
            st.error("Falha ao gerar PDF OI CPE.")
            st.exception(e)
