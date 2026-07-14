import os
import sys
import streamlit as st


st.set_page_config(
    page_title="RAT MAM Unificada",
    layout="wide",
    page_icon="🧾",
)


repo_dir = os.path.dirname(os.path.abspath(__file__))
common_dir = os.path.join(repo_dir, "common")

# Informações temporárias para diagnóstico
st.write("__file__:", __file__)
st.write("sys.path:", sys.path[:5])
st.write("Arquivos na pasta atual:", os.listdir("."))
st.write("Arquivos na pasta do repositório:", os.listdir(repo_dir))

st.write("Existe common?", os.path.exists(common_dir))

if os.path.exists(common_dir):
    st.write("Arquivos em common:", os.listdir(common_dir))


import rat_unificado


def main():
    rat_unificado.render()


if __name__ == "__main__":
    main()
