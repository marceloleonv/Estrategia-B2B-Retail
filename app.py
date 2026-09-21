import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(layout="wide", page_title="Executive Command Center", initial_sidebar_state="collapsed")

# Ocultar menú y footer por defecto de Streamlit para que parezca una app nativa
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .block-container {
                padding-top: 0rem;
                padding-bottom: 0rem;
                padding-left: 0rem;
                padding-right: 0rem;
            }
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

with open("dashboard_final.html", "r", encoding="utf-8") as f:
    html_content = f.read()

# Render HTML (ajustamos el height para que no haya doble scroll en lo posible)
components.html(html_content, height=1300, scrolling=True)
