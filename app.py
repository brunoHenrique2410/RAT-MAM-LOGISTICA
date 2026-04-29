# repo/app.py
import streamlit as st
import repo.rat_unificado.py

def main():
    st.set_page_config(
        page_title="RAT MAM Unificada",
        layout="wide",
        page_icon="🧾",
    )
    rat_unificado.render()

if __name__ == "__main__":
    main()
