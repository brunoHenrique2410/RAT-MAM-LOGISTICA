# repo/app.py
import os
import sys
import streamlit as st

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import rat_unificado  # este arquivo que te mandei

def main():
    st.set_page_config(
        page_title="RAT – MAM Unificada",
        layout="wide",
        page_icon="🧾",
    )
    rat_unificado.render()

if __name__ == "__main__":
    main()
