import os
import sys
import streamlit as st

st.write("CWD:", os.getcwd())
st.write("__file__:", __file__)
st.write("sys.path:", sys.path[:5])
st.write("Arquivos na pasta atual:", os.listdir("."))
st.write("Arquivos em /repo:", os.listdir(os.path.dirname(__file__)))

repo_dir = os.path.dirname(__file__)
common_dir = os.path.join(repo_dir, "common")

st.write("Existe common?", os.path.exists(common_dir))
if os.path.exists(common_dir):
    st.write("Arquivos em common:", os.listdir(common_dir))

import rat_unificado
def main():
    st.set_page_config(
        page_title="RAT MAM Unificada",
        layout="wide",
        page_icon="🧾",
    )
    rat_unificado.render()

if __name__ == "__main__":
    main()
