import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from model.database import init_db

init_db()  # garante que a tabela existe ao subir

# Roteamento simples por session_state
if "pagina" not in st.session_state:
    st.session_state["pagina"] = "login"

if st.session_state["pagina"] == "login":
    from view.login import login_page
    login_page()

elif st.session_state["pagina"] == "cadastro":
    from view.cadastro import cadastro_page
    cadastro_page()