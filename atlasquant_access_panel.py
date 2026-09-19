"""AtlasQuant optional Streamlit login gate.

Disabled by default. When ATLASQUANT_AUTH_REQUIRED=true, the app fails closed
unless ATLASQUANT_USERS_JSON contains valid PBKDF2 user records.
"""
from __future__ import annotations

from typing import Any
import os
import streamlit as st

from atlasquant_access_control import authenticate, load_users_config, has_permission, session_is_current

SESSION_KEY="atlasquant_access_session"

def _setting(key:str, default:str="")->str:
    try:
        value=st.secrets.get(key,os.getenv(key,default))
    except Exception:
        value=os.getenv(key,default)
    return str(value or "").strip()

def _bool_setting(value:Any)->bool:
    return str(value or "").strip().lower() in {"1","true","yes","on","sim"}

def access_required()->bool:
    return _bool_setting(_setting("ATLASQUANT_AUTH_REQUIRED","false"))

def configured_users():
    return load_users_config(_setting("ATLASQUANT_USERS_JSON",""))

def current_session()->dict[str,Any]|None:
    raw=st.session_state.get(SESSION_KEY)
    return dict(raw) if isinstance(raw,dict) else None

def clear_session()->None:
    st.session_state.pop(SESSION_KEY,None)

def evaluate_access(
    *,
    required:bool,
    users_count:int,
    session:dict[str,Any]|None,
    users:dict|None=None,
)->dict[str,Any]:
    if not required:
        return {"allowed":True,"mode":"OPEN","reason":"AUTH_DISABLED"}
    if users_count<=0:
        return {"allowed":False,"mode":"LOCKED","reason":"NO_USERS_CONFIGURED"}
    if not isinstance(session,dict) or not has_permission(session,"app:read"):
        return {"allowed":False,"mode":"LOGIN","reason":"AUTH_REQUIRED"}
    if users is not None and not session_is_current(session,users):
        return {"allowed":False,"mode":"LOGIN","reason":"SESSION_REVOKED"}
    return {"allowed":True,"mode":"AUTHENTICATED","reason":"OK"}

def render_access_gate()->dict[str,Any]:
    required=access_required()
    users=configured_users()
    session=current_session()
    decision=evaluate_access(required=required,users_count=len(users),session=session,users=users)
    if not required:
        return {**decision,"session":None,"role":"OPEN"}

    if decision["reason"]=="NO_USERS_CONFIGURED":
        st.error("🔒 Login obrigatório, mas nenhum usuário seguro foi configurado.")
        st.caption("Configure ATLASQUANT_USERS_JSON com hashes PBKDF2; credenciais em texto puro não são aceitas.")
        return {**decision,"session":None,"role":None}

    if decision["allowed"]:
        c1,c2=st.sidebar.columns([3,1])
        c1.caption(f"🔐 {session.get('username','')} · {session.get('role','')}")
        if c2.button("Sair",key="atlasquant_logout"):
            clear_session()
            st.rerun()
        return {**decision,"session":session,"role":session.get("role")}

    if decision["reason"]=="SESSION_REVOKED":
        clear_session()
        st.warning("Sua sessão foi encerrada porque a conta, o perfil ou a credencial mudou.")
    st.markdown("## 🔐 AtlasQuant")
    st.caption("Acesso privado. Use sua conta autorizada.")
    with st.form("atlasquant_login_form",clear_on_submit=False):
        username=st.text_input("Usuário",autocomplete="username")
        password=st.text_input("Senha",type="password",autocomplete="current-password")
        submit=st.form_submit_button("Entrar",type="primary")
    if submit:
        authenticated=authenticate(username,password,users)
        if authenticated is None:
            st.error("Usuário ou senha inválidos.")
        else:
            st.session_state[SESSION_KEY]=authenticated
            st.rerun()
    return {**decision,"session":None,"role":None}
