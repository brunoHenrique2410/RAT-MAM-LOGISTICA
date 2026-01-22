import streamlit as st
from common.state import init_defaults

def page_identificacao(ss):
    st.subheader("1) Identificação do Atendimento")

    c1, c2 = st.columns(2)
    with c1:
        ss.data_atendimento = st.date_input("Data do atendimento", value=ss.data_atendimento)
        ss.cliente = st.text_input("Cliente / Razão Social", ss.cliente)

    with c2:
        ss.numero_chamado = st.text_input("Número do Chamado", ss.numero_chamado)
        ss.analista = st.text_input("Analista MAMINFO", ss.analista)

    st.text_input("CNPJ / Identificação", ss.cnpj)

    st.subheader("Contato / Local")
    c3, c4 = st.columns(2)
    with c3:
        ss.contato_nome = st.text_input("Contato local (nome)", ss.contato_nome)
    with c4:
        ss.contato_tel = st.text_input("Telefone do contato local", ss.contato_tel)

    st.text_input("Endereço", ss.endereco)
    st.text_input("Cidade / UF", ss.cidade_uf)

