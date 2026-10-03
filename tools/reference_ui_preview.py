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
st.session_state.setdefault("atlasquant_experience_mode", "Avançado")
# Optional visual QA of the actual login shell; never authenticate test inputs.
if st.query_params.get("review") == "login":
    from atlasquant_access_panel import render_login_reference_shell
    column = render_login_reference_shell()
    with column:
        st.markdown('<div class="aq-login-eyebrow">PRÉVIA LOCAL · LOGIN</div><div class="aq-login-panel-title">Bem-vindo ao AtlasQuant</div><div class="aq-login-panel-copy">Entre com sua conta autorizada para abrir sua central.</div>',unsafe_allow_html=True)
        with st.form("atlasquant_login_form", clear_on_submit=False):
            st.text_input("Usuário", key="preview_login_username")
            st.text_input("Senha", type="password", key="preview_login_password")
            submitted = st.form_submit_button("Entrar", width="stretch")
        if submitted:
            st.info("Prévia visual: autenticação real permanece no app oficial.")
    st.stop()
# Backtest is an existing offline panel: CSV import/replay, not a fabricated engine.
if st.query_params.get("review") == "backtest":
    from atlasquant_backtest_panel import render_operational_backtest_panel
    st.caption("Revisão local do laboratório existente · sem providers ou ordens reais")
    render_operational_backtest_panel()
    st.stop()
area=st.session_state.get("atlasquant_central_choice","central_root")
area="central" if area=="central_root" else area
render_reference_workspace(st,access,area,mode=st.session_state.get("atlasquant_experience_mode") or "Avançado")
