"""Loopback-only staged durable AION Chat browser harness.

Uses the same staged host composer as the real Streamlit shell, with an explicit
QA identity and explicit local SQLite directory. Never deployed as an app entry.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from atlasquant_aion_chat_host_staging import (
    build_streamlit_staged_binding,
    close_staged_host_store,
)
from atlasquant_central_hub_ui import (
    CENTRAL_CHOICE_KEY,
    CENTRAL_ROOT,
    render_central_hub,
)


st.set_page_config(
    page_title="AtlasQuant · staged durable AION chat QA",
    layout="wide",
)
st.markdown(
    "<style>[data-testid='stHeader']{display:none}.stApp{background:#020813}</style>",
    unsafe_allow_html=True,
)

ACCESS = {
    "allowed": True,
    "mode": "AUTHENTICATED",
    "reason": "QA_LOCAL_ONLY",
    "role": "ADMIN",
    "session": {
        "username": "mikael",
        "role": "ADMIN",
        "permissions": [
            "app:read",
            "aion:admin",
            "aion:checkpoint",
        ],
        "credential_fingerprint": "staged-browser-qa-fingerprint",
        "authenticated_at": 1.0,
        "last_seen": 1.0,
    },
}

binding = build_streamlit_staged_binding(
    st,
    ACCESS,
    environment="STAGING",
)
if binding is None:
    raise RuntimeError("staged durable chat QA flag is not enabled")

st.session_state.setdefault("atlasquant_experience_mode", "Avançado")
st.session_state.setdefault(CENTRAL_CHOICE_KEY, "aion")

st.markdown(
    '<span id="aq-staged-host-marker" '
    'data-state="STAGED_BOUND" data-production="false" '
    'data-provider="false" data-network="false" aria-hidden="true"></span>',
    unsafe_allow_html=True,
)

if st.button(
    "QA · remontar store durável",
    key="qa_remount_staged_chat_store",
):
    close_staged_host_store(st.session_state, binding["scope"])
    st.session_state["qa_staged_store_remounts"] = int(
        st.session_state.get("qa_staged_store_remounts", 0)
    ) + 1
    st.rerun()

st.caption(
    "QA LOCAL · SQLite staged · provider desligado · produção desligada · "
    f"remounts={int(st.session_state.get('qa_staged_store_remounts', 0))}"
)

requested = st.session_state.get(CENTRAL_CHOICE_KEY, "aion")
if requested == CENTRAL_ROOT:
    requested = "central"

render_central_hub(
    ACCESS,
    requested,
    aion_chat_binding=binding,
)
