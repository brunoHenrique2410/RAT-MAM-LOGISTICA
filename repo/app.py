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

# Adiciona os caminhos do projeto ao Python
for path in [APP_DIR, PROJECT_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)


try:
    import rat_unificado
except Exception as erro:
    st.error("Erro ao importar rat_unificado")
    st.exception(erro)
    st.stop()


def main():
    # Diagnóstico temporário
    st.info(f"app.py carregado de: {__file__}")
    st.info(
        f"rat_unificado carregado de: "
        f"{getattr(rat_unificado, '__file__', 'arquivo não identificado')}"
    )

    try:
        rat_unificado.render()
    except Exception as erro:
        st.error("O formulário apresentou um erro durante a renderização.")
        st.exception(erro)


if __name__ == "__main__":
    main()
