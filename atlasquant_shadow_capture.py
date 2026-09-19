"""AtlasQuant Shadow Mode session + persistent capture."""
from __future__ import annotations

import os
from typing import Any, Mapping, Sequence
import streamlit as st

from atlasquant_challenger_v1 import build_challenger_snapshot, champion_snapshot
from atlasquant_shadow_mode import compare_shadow_sample, append_shadow_sample
from atlasquant_shadow_store import load_shadow_samples, persist_shadow_samples
from atlasquant_runtime_store import resolve_runtime_branch


SESSION_KEY="atlasquant_shadow_samples"
HYDRATED_KEY="atlasquant_shadow_hydrated"
STATUS_KEY="atlasquant_shadow_persistence_status"


def _secret_or_env(key: str, default: str="") -> str:
    try:
        value=st.secrets.get(key,os.getenv(key,default))
    except Exception:
        value=os.getenv(key,default)
    return str(value or "").strip()


def shadow_persistence_config() -> dict[str,str]:
    return {
        "repo":_secret_or_env(
            "GITHUB_REPO_HISTORICO",
            os.getenv("GITHUB_REPOSITORY","aparecidomikael97-ship-it/usd-macro-pro-v4"),
        ),
        "branch":resolve_runtime_branch(
            _secret_or_env("GITHUB_DATA_BRANCH",""),
            _secret_or_env("GITHUB_BRANCH_HISTORICO",""),
        ),
        "token":_secret_or_env("GITHUB_TOKEN_HISTORICO",os.getenv("GITHUB_TOKEN","")),
    }


def hydrate_shadow_samples(
    session_samples: Sequence[Mapping[str,Any]] | None,
    remote_samples: Sequence[Mapping[str,Any]] | None,
) -> list[dict[str,Any]]:
    rows=[dict(x) for x in (remote_samples or [])]
    for raw in (session_samples or []):
        rows,_=append_shadow_sample(rows,raw)
    return rows


def ensure_shadow_hydrated() -> tuple[list[dict[str,Any]],dict[str,Any]]:
    current=list(st.session_state.get(SESSION_KEY,[]) or [])
    if bool(st.session_state.get(HYDRATED_KEY,False)):
        return current,dict(st.session_state.get(STATUS_KEY,{}) or {})

    cfg=shadow_persistence_config()
    if not cfg["repo"] or not cfg["token"]:
        status={"ok":False,"reason":"NOT_CONFIGURED","samples":len(current),"source":"session","branch":cfg["branch"],"error":""}
        st.session_state[HYDRATED_KEY]=True
        st.session_state[STATUS_KEY]=status
        return current,status

    try:
        remote=load_shadow_samples(
            repo=cfg["repo"],branch=cfg["branch"],token=cfg["token"]
        )
        current=hydrate_shadow_samples(current,remote)
        status={"ok":True,"reason":"LOADED","samples":len(remote),"source":"runtime_persistent","branch":cfg["branch"],"error":""}
    except Exception as exc:
        status={"ok":False,"reason":"LOAD_ERROR","samples":len(current),"source":"session_fallback","branch":cfg["branch"],"error":f"{type(exc).__name__}: {exc}"}

    st.session_state[SESSION_KEY]=current
    st.session_state[HYDRATED_KEY]=True
    st.session_state[STATUS_KEY]=status
    return current,status


def build_shadow_batch(
    packs: Sequence[Mapping[str,Any]] | None,
    *,
    champion_version: str,
) -> list[dict[str,Any]]:
    samples=[]
    for pack in (packs or []):
        champ=champion_snapshot(pack,version=champion_version)
        challenger=build_challenger_snapshot(pack)
        samples.append(compare_shadow_sample(champ,challenger))
    return samples


def capture_shadow_batch(
    packs: Sequence[Mapping[str,Any]] | None,
    *,
    champion_version: str,
) -> dict[str,Any]:
    rows,_=ensure_shadow_hydrated()
    batch=build_shadow_batch(packs,champion_version=champion_version)

    new=[]
    for sample in batch:
        rows2,added=append_shadow_sample(rows,sample)
        if added:
            rows=rows2
            new.append(sample)

    st.session_state[SESSION_KEY]=rows
    if not new:
        status={"ok":True,"reason":"ALREADY_PRESENT","added":0,"samples":len(rows),"error":""}
        st.session_state[STATUS_KEY]=status
        return status

    cfg=shadow_persistence_config()
    status=persist_shadow_samples(
        new,repo=cfg["repo"],branch=cfg["branch"],token=cfg["token"]
    )
    status["session_samples"]=len(rows)
    st.session_state[STATUS_KEY]=status
    return status
