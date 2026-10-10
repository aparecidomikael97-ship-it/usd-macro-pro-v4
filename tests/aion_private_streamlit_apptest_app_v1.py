"""Synthetic in-process Streamlit AppTest fixture; not an application entrypoint.

Exercises the real access gate, private-read gate and Research capture code.
All user records and row values come exclusively from offline test fixtures.
"""
from __future__ import annotations

import streamlit as st

from atlasquant_access_panel import render_access_gate
from atlasquant_private_read_gate_v1 import private_read_allowed

gate = render_access_gate()
if not gate.get("allowed"):
    st.stop()

allowed = private_read_allowed()
st.text("PRIVATE_READ=" + ("ALLOWED" if allowed else "DENIED"))

if allowed and st.button("Seed private sample", key="fixture_private_seed"):
    st.session_state["atlasquant_shadow_samples"] = [
        {"private": "A_PRIVATE_SAMPLE_DO_NOT_SHOW_TO_B"}
    ]
    st.session_state["atlasquant_shadow_hydrated"] = True

# Display state only after the real guard authorizes it. The test explicitly
# checks that stale A data does not survive a legitimate B login or policy bump.
st.text(
    "PRIVATE_SHADOW="
    + (repr(st.session_state.get("atlasquant_shadow_samples", [])) if allowed else "[]")
)

if st.button("Attempt Research session capture", key="fixture_local_capture"):
    from atlasquant_research_evidence_capture import capture_research_evidence

    result = capture_research_evidence(
        strategy="synthetic-research", source="offline-apptest",
        passport={"synthetic": True}, evidence={"row": "test"},
        pair="AUDIT", persist=False,
    )
    st.session_state["_apptest_local_capture_reason"] = result.get("reason", "MISSING")
st.text("LOCAL_CAPTURE=" + str(st.session_state.get("_apptest_local_capture_reason", "NOT_RUN")))
