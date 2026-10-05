"""Loopback-only visual review harness. Fake preview identity, no production login.

streamlit run tools/reference_ui_preview.py --server.address 127.0.0.1
"""
from pathlib import Path
import sys
import os
import json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import streamlit as st
from atlasquant_reference_ui import render_reference_workspace
st.set_page_config(page_title="AtlasQuant · revisão visual local",layout="wide")
st.markdown("<style>[data-testid='stHeader']{display:none}.stApp{background:#020813}</style>",unsafe_allow_html=True)
access={"allowed":True,"role":"ADMIN","mode":"PREVIEW","session":{"username":"Mikael · revisão local"}}
st.session_state.setdefault("atlasquant_experience_mode", "Avançado")
if st.query_params.get('review') in {'runtime','legacy'}:
    from atlasquant_trader_resident import hydrate_trader_resident_state
    review_path=os.getenv('ATLASQUANT_REVIEW_SNAPSHOT','')
    if not review_path: raise RuntimeError('Runtime review requires an explicit local fixture file.')
    bundle=json.loads(Path(review_path).read_text(encoding='utf-8'))
    hydrate_trader_resident_state(st.session_state,bundle['snapshot'],bundle.get('status'))
    st.caption(bundle.get('label','QA LOCAL · FIXTURE SINTÉTICA · SEM COTAÇÃO VIVA'))
    st.session_state.setdefault('atlasquant_central_choice','trader')
    if st.query_params.get('review')=='legacy':
        import pandas as pd
        from unittest.mock import patch
        from master_panel_v102 import render_master_panel
        matrix=pd.DataFrame([{'Par':pack['pair'],'Direção':pack['direction']+' '+pack['pair'],'Score final':pack.get('priority',0),'Qualidade':pack.get('quality',0)} for pack in bundle['snapshot']['packs']])
        if st.button('Voltar à home Trader',key='review_legacy_home'):
            st.query_params['review']='runtime';st.rerun()
        with patch('master_panel_v102._load_state',return_value=bundle.get('master_state',{'contexts':{}})),patch('master_panel_v102._td_series',side_effect=AssertionError('provider forbidden in offline QA')),patch('requests.get',side_effect=AssertionError('network forbidden in offline QA')):
            render_master_panel(matrix,pd.DataFrame(bundle['snapshot']['inputs']['fast_boot']['ranking']),'',scanner_state=bundle.get('scanner_state'))
        st.caption('REVISÃO LEGADA CONCLUÍDA · ZERO CHAMADAS PROVIDER')
        st.stop()
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
if st.query_params.get("review") == "chat-history":
    # Explicit local QA fixture only: seed via the same session presentation adapter.
    from atlasquant_aion_chat_workspace_ui import session_chat, trusted_context, submit_turn
    context = trusted_context(access, "Avançado")
    chat = session_chat(st.session_state, context)
    if not chat["entries"]:
        for index in range(120):
            submit_turn(chat, {"conversation_id": chat["conversation_id"], "request_id": f"qa-{index}",
                               "message": f"Como está o sistema? Histórico QA {index}", "attachments": []}, context)
    st.session_state["atlasquant_central_choice"] = "aion"
    area = "aion"
render_reference_workspace(st,access,area,mode=st.session_state.get("atlasquant_experience_mode") or "Avançado")
