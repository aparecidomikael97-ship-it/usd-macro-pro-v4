"""Loopback-only visual review harness. Fake preview identity, no production login.

streamlit run tools/reference_ui_preview.py --server.address 127.0.0.1
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import streamlit as st
from atlasquant_reference_ui import render_reference_workspace
st.set_page_config(page_title="AtlasQuant · revisão visual local",layout="wide")
st.markdown("<style>[data-testid='stHeader']{display:none}.stApp{background:#020813}</style>",unsafe_allow_html=True)
access={"allowed":True,"role":"ADMIN","mode":"PREVIEW","session":{"username":"Mikael · revisão local"}}
area=st.session_state.get("atlasquant_central_choice","central_root")
area="central" if area=="central_root" else area
render_reference_workspace(st,access,area,mode=st.session_state.get("atlasquant_experience_mode") or "Avançado")
