import os
import sys
import streamlit as st

st.set_page_config(
    page_title="RAT MAM Unificada",
    layout="wide",
    page_icon="🧾",
)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(APP_DIR)

for path in [APP_DIR, PROJECT_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

import rat_unificado


def main():
    rat_unificado.render()


if __name__ == "__main__":
    main()
