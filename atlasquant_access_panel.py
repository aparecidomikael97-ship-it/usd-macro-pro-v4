"""AtlasQuant optional Streamlit login gate.

Disabled by default. When ATLASQUANT_AUTH_REQUIRED=true, the app fails closed
unless ATLASQUANT_USERS_JSON contains valid PBKDF2 user records.
"""
from __future__ import annotations

from typing import Any
import os
import time
import streamlit as st

from atlasquant_access_control import authenticate, load_users_config, has_permission, session_is_current

SESSION_KEY="atlasquant_access_session"
THROTTLE_KEY="atlasquant_login_throttle"
MAX_FAILED_ATTEMPTS=5
LOCK_SECONDS=300
SESSION_MAX_SECONDS=12*60*60
SESSION_IDLE_SECONDS=2*60*60

def session_time_status(session:Any, now:float)->dict[str,Any]:
    if not isinstance(session,dict):
        return {"valid":False,"reason":"NO_SESSION"}
    try:
        issued=float(session.get("authenticated_at"))
        last_seen=float(session.get("last_seen"))
        now_f=float(now)
        if issued<=0 or last_seen<=0 or not (issued<=last_seen<=now_f):
            raise ValueError()
        if now_f-issued>SESSION_MAX_SECONDS:
            return {"valid":False,"reason":"SESSION_MAX_AGE"}
        if now_f-last_seen>SESSION_IDLE_SECONDS:
            return {"valid":False,"reason":"SESSION_IDLE_TIMEOUT"}
        return {"valid":True,"reason":"OK"}
    except Exception:
        return {"valid":False,"reason":"INVALID_SESSION_TIME"}


def throttle_status(state:Any, now:float)->dict[str,Any]:
    try:
        data=dict(state) if isinstance(state,dict) else {}
        attempts=int(data.get("attempts",0))
        lock_until=float(data.get("lock_until",0.0))
        if attempts<0 or lock_until<0:
            raise ValueError()
    except Exception:
        return {"attempts":MAX_FAILED_ATTEMPTS,"lock_until":float(now)+LOCK_SECONDS,"locked":True,"retry_after":LOCK_SECONDS}
    if lock_until and lock_until<=float(now):
        attempts=0
        lock_until=0.0
    locked=bool(lock_until>float(now))
    retry=max(0,int(lock_until-float(now))) if locked else 0
    return {"attempts":attempts,"lock_until":lock_until,"locked":locked,"retry_after":retry}

def record_login_failure(state:Any, now:float)->dict[str,Any]:
    current=throttle_status(state,now)
    if current["locked"]:
        return current
    attempts=int(current["attempts"])+1
    lock_until=float(now)+LOCK_SECONDS if attempts>=MAX_FAILED_ATTEMPTS else 0.0
    return throttle_status({"attempts":attempts,"lock_until":lock_until},now)

def reset_login_throttle()->None:
    st.session_state.pop(THROTTLE_KEY,None)

def _setting(key:str, default:str="")->str:
    try:
        value=st.secrets.get(key,os.getenv(key,default))
    except Exception:
        value=os.getenv(key,default)
    return str(value or "").strip()

def _bool_setting(value:Any)->bool:
    return str(value or "").strip().lower() in {"1","true","yes","on","sim"}

def access_required()->bool:
    environment=_setting("ATLASQUANT_ENV","").upper()
    if environment=="PRODUCTION":
        return True
    return _bool_setting(_setting("ATLASQUANT_AUTH_REQUIRED","false"))

def configured_users():
    return load_users_config(_setting("ATLASQUANT_USERS_JSON",""))

def registry_role_counts(users)->dict[str,int]:
    counts={"USER":0,"SALES":0,"ADMIN":0,"TOTAL":0}
    if not isinstance(users,dict):
        return counts
    for user in users.values():
        role=str(getattr(user,"role","") or "").upper()
        active=bool(getattr(user,"active",False))
        if active and role in ("USER","SALES","ADMIN"):
            counts[role]+=1
            counts["TOTAL"]+=1
    return counts

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
    role_counts=registry_role_counts(users)
    session=current_session()
    decision=evaluate_access(required=required,users_count=len(users),session=session,users=users)
    if required and decision["allowed"]:
        time_check=session_time_status(session,time.time())
        if not time_check["valid"]:
            clear_session()
            session=None
            decision={"allowed":False,"mode":"LOGIN","reason":time_check["reason"]}
        else:
            session["last_seen"]=time.time()
            st.session_state[SESSION_KEY]=session
    if not required:
        return {**decision,"session":None,"role":"OPEN","registry":role_counts}

    if decision["reason"]=="NO_USERS_CONFIGURED":
        st.error("🔒 Login obrigatório, mas nenhum usuário seguro foi configurado.")
        st.caption("Configure ATLASQUANT_USERS_JSON com hashes PBKDF2; credenciais em texto puro não são aceitas.")
        return {**decision,"session":None,"role":None,"registry":role_counts}

    if decision["allowed"]:
        c1,c2=st.sidebar.columns([3,1])
        c1.caption(f"🔐 {session.get('username','')} · {session.get('role','')}")
        if c2.button("Sair",key="atlasquant_logout"):
            clear_session()
            st.rerun()
        return {**decision,"session":session,"role":session.get("role"),"registry":role_counts}

    if decision["reason"]=="SESSION_REVOKED":
        clear_session()
        st.warning("Sua sessão foi encerrada porque a conta, o perfil ou a credencial mudou.")

    now=time.time()
    throttle=throttle_status(st.session_state.get(THROTTLE_KEY,{}),now)
    if throttle["locked"]:
        st.error("🔒 Muitas tentativas inválidas. Aguarde antes de tentar novamente.")
        st.caption("Nova tentativa em aproximadamente "+str(max(1,int(throttle["retry_after"]/60)+1))+" minuto(s).")
        return {**decision,"mode":"LOGIN_LOCKED","reason":"TOO_MANY_ATTEMPTS","session":None,"role":None,"registry":role_counts}

    st.markdown("## 🔐 AtlasQuant")
    st.caption("Acesso privado. Use sua conta autorizada.")
    with st.form("atlasquant_login_form",clear_on_submit=False):
        username=st.text_input("Usuário",autocomplete="username")
        password=st.text_input("Senha",type="password",autocomplete="current-password")
        submit=st.form_submit_button("Entrar",type="primary")
    if submit:
        authenticated=authenticate(username,password,users)
        if authenticated is None:
            st.session_state[THROTTLE_KEY]=record_login_failure(
                st.session_state.get(THROTTLE_KEY,{}),
                time.time(),
            )
            st.error("Usuário ou senha inválidos.")
        else:
            reset_login_throttle()
            now_login=time.time()
            authenticated["authenticated_at"]=now_login
            authenticated["last_seen"]=now_login
            st.session_state[SESSION_KEY]=authenticated
            st.rerun()
    return {**decision,"session":None,"role":None,"registry":role_counts}
