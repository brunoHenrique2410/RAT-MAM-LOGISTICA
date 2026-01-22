# repo/app.py
import os
import sys
import streamlit as st

# === Ajuste de PATH para achar "common", "pdf_templates", etc. ===
THIS_DIR = os.path.dirname(os.path.abspath(__file__))   # .../repo
PROJECT_ROOT = os.path.dirname(THIS_DIR)               # raiz do projeto
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import rat_unificado  # depois do PATH estar ajustado


def main():
    st.set_page_config(
        page_title="RAT MAM – Unificada",
        layout="wide",
        page_icon="🧾",
    )
    rat_mam_unificada.render()


if __name__ == "__main__":
    main()

