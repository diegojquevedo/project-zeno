import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="Zeno", page_icon="🦣")

API_BASE_URL = os.environ.get(
    "API_BASE_URL", os.environ.get("LOCAL_API_BASE_URL", "http://localhost:8000")
)

STREAMLIT_URL = os.environ.get(
    "STREAMLIT_URL", "http://localhost:8501"
)  # URL where the Streamlit app is hosted

# Handle token from URL callback (OAuth redirect)
token = st.query_params.get("token")
if token:
    st.session_state["token"] = token
    st.query_params.clear()

# Auto-login: use token from .env if no token in session
if not st.session_state.get("token"):
    auto_token = os.environ.get("AUTO_LOGIN_TOKEN")
    if auto_token and auto_token != "<your-gfw-jwt-token>":
        st.session_state["token"] = auto_token

# Redirect directly to Map Chat
st.switch_page("pages/4_🌎_Map_Chat.py")
