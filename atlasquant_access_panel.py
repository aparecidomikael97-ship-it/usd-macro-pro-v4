"""AtlasQuant optional Streamlit login gate.

Disabled by default. When authentication is required, configured users are
always enforced. During first-run bootstrap only, an explicitly bounded preview
may keep app:read available until the first secure user registry is configured.
The preview never creates users, sessions, admin/sales permissions or live trading.
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

LOGIN_REFERENCE_CSS = r"""
<style>
:root {
  --aq-login-bg:#040713;
  --aq-login-panel:rgba(10,16,35,.72);
  --aq-login-line:rgba(113,139,255,.24);
  --aq-login-text:#f4f7ff;
  --aq-login-muted:#93a0c7;
  --aq-login-cyan:#54d7ff;
  --aq-login-violet:#8e6dff;
}
[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(circle at 18% 18%, rgba(50,96,255,.18), transparent 28%),
    radial-gradient(circle at 78% 24%, rgba(142,109,255,.16), transparent 30%),
    linear-gradient(145deg,#03050d 0%,#071024 46%,#040713 100%);
}
[data-testid="stHeader"] { background:transparent; }
[data-testid="stSidebar"] { display:none; }
.block-container {
  max-width:1180px;
  padding-top:clamp(2rem,7vh,5.5rem);
  padding-bottom:3rem;
}
.aq-login-hero {
  min-height:560px;
  position:relative;
  overflow:hidden;
  padding:3.4rem 2.8rem;
  border:1px solid var(--aq-login-line);
  border-radius:28px;
  background:
    linear-gradient(145deg,rgba(12,24,55,.78),rgba(4,8,20,.72)),
    radial-gradient(circle at 50% 45%,rgba(84,215,255,.08),transparent 40%);
  box-shadow:0 28px 90px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.05);
  backdrop-filter:blur(18px);
}
.aq-login-eyebrow {
  color:var(--aq-login-cyan);
  font-size:.75rem;
  font-weight:800;
  letter-spacing:.18em;
  text-transform:uppercase;
}
.aq-login-title {
  color:var(--aq-login-text);
  font-size:clamp(2.2rem,5vw,4.7rem);
  line-height:.95;
  font-weight:900;
  letter-spacing:-.045em;
  margin:.8rem 0 1rem;
}
.aq-login-copy {
  color:var(--aq-login-muted);
  max-width:34rem;
  font-size:1rem;
  line-height:1.7;
}
.aq-login-tagline {
  color:#dce4ff;
  font-weight:700;
  margin-top:1.3rem;
}
.aq-login-orb {
  width:240px;
  height:240px;
  margin:2.3rem auto 1.2rem;
  border-radius:50%;
  position:relative;
  background:
    radial-gradient(circle at 35% 30%,rgba(255,255,255,.8),rgba(84,215,255,.48) 7%,rgba(66,90,255,.34) 28%,rgba(142,109,255,.22) 55%,rgba(3,7,18,.16) 72%),
    repeating-radial-gradient(circle at 50% 50%,transparent 0 14px,rgba(118,170,255,.12) 15px 16px);
  box-shadow:
    0 0 40px rgba(84,215,255,.28),
    0 0 95px rgba(142,109,255,.22),
    inset -28px -28px 70px rgba(3,8,26,.7);
}
.aq-login-orb:before,.aq-login-orb:after {
  content:"";
  position:absolute;
  inset:-18px;
  border-radius:50%;
  border:1px solid rgba(113,177,255,.26);
  transform:rotate(18deg) scaleY(.42);
}
.aq-login-orb:after {
  inset:-42px;
  border-color:rgba(142,109,255,.18);
  transform:rotate(-24deg) scaleY(.58);
}
.aq-login-pills {
  display:flex;
  gap:.55rem;
  flex-wrap:wrap;
  margin-top:1.2rem;
}
.aq-login-pill {
  border:1px solid rgba(115,142,255,.22);
  color:#cbd6ff;
  background:rgba(9,17,38,.55);
  border-radius:999px;
  padding:.42rem .7rem;
  font-size:.72rem;
  letter-spacing:.02em;
}
.aq-login-panel-title {
  color:var(--aq-login-text);
  font-size:1.45rem;
  font-weight:850;
  margin:.2rem 0 .25rem;
}
.aq-login-panel-copy {
  color:var(--aq-login-muted);
  font-size:.88rem;
  margin-bottom:.6rem;
}
div[data-testid="stForm"] {
  border:1px solid var(--aq-login-line);
  border-radius:26px;
  padding:1.45rem 1.35rem 1.2rem;
  background:var(--aq-login-panel);
  box-shadow:0 22px 70px rgba(0,0,0,.38), inset 0 1px 0 rgba(255,255,255,.04);
  backdrop-filter:blur(20px);
}
div[data-testid="stForm"] input {
  background:rgba(4,9,24,.78) !important;
}
div[data-testid="stFormSubmitButton"] button {
  min-height:3rem;
  border-radius:14px;
  font-weight:800;
}
@media (max-width: 760px) {
  .block-container { padding-top:1.15rem; }
  .aq-login-hero { min-height:auto; padding:2rem 1.25rem; border-radius:22px; }
  .aq-login-orb { width:165px; height:165px; margin:1.6rem auto .7rem; }
  .aq-login-title { font-size:2.6rem; }
}
/* Presentation-only final polish; actual form and authentication stay intact. */
*{box-sizing:border-box}
.block-container{padding-top:1.6rem;padding-bottom:1.6rem}
.aq-login-hero{min-height:510px;padding:2rem;border-color:#2b7da766;background:radial-gradient(circle at 75% 70%,#126a9833,transparent 55%),linear-gradient(145deg,#0c1833ee,#040917ee)}
.aq-login-brand{display:flex;align-items:center;gap:12px;margin-bottom:22px;font-size:21px;font-weight:800;color:#eaf6ff;letter-spacing:.06em}
.aq-login-brand img{width:46px;height:38px;object-fit:contain}.aq-login-brand small{display:block;font-size:9px;letter-spacing:.2em;color:#81dfff}
.aq-login-title{font-size:clamp(2rem,4vw,3.7rem)}.aq-login-copy{color:#bbcee6;line-height:1.55}.aq-login-orb{width:175px;height:175px;margin:1.6rem auto 1.2rem}
div[data-testid="stForm"]{border-color:#347aa166;border-radius:20px;background:linear-gradient(145deg,#0c1d35e6,#070f20ee)}
div[data-testid="stForm"] input{color:#f3faff!important;border-radius:8px}
div[data-testid="stForm"] input:focus{outline:2px solid #71dfff!important;outline-offset:-2px;box-shadow:inset 0 0 8px #21aeff22}
div[data-testid="stFormSubmitButton"] button{background:linear-gradient(110deg,#147bb6,#3bbcd9);color:#f8ffff;border:1px solid #6dd4ee}
div[data-testid="stFormSubmitButton"] button:hover,div[data-testid="stFormSubmitButton"] button:focus-visible{transform:none;outline:0;box-shadow:inset 0 0 0 2px #b5f5ff,0 0 18px #32caff33}
@media(max-width:760px){.block-container{padding:1rem}.aq-login-hero{padding:1.2rem;min-height:0}.aq-login-brand{font-size:18px;margin-bottom:12px}.aq-login-title{font-size:2rem;margin:.5rem 0}.aq-login-copy{font-size:.8rem;line-height:1.45}.aq-login-tagline{font-size:.85rem;margin-top:.7rem}.aq-login-orb{display:none}.aq-login-pills{margin-top:.8rem}.aq-login-pill{font-size:.65rem;padding:.35rem .55rem}div[data-testid="stForm"]{padding:1rem}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
</style>
"""

LOGIN_REFERENCE_HERO = """
<div class="aq-login-hero">
  <div class="aq-login-eyebrow">AtlasQuant · Market Intelligence</div>
  <div class="aq-login-title">Inteligência<br/>em perspectiva.</div>
  <div class="aq-login-copy">
    Um cockpit privado para navegar Trader, Negócios, Investimentos e AION
    sem misturar os ecossistemas.
  </div>
  <div class="aq-login-tagline">Poderoso por dentro. Simples por fora.</div>
  <div class="aq-login-orb" aria-hidden="true"></div>
  <div class="aq-login-pills">
    <span class="aq-login-pill">Trader</span>
    <span class="aq-login-pill">Negócios</span>
    <span class="aq-login-pill">Investimentos</span>
    <span class="aq-login-pill">AION</span>
  </div>
</div>
"""

def render_login_reference_shell():
    """Render the approved premium login composition without changing auth logic."""
    st.markdown(LOGIN_REFERENCE_CSS,unsafe_allow_html=True)
    hero_col,login_col=st.columns([1.14,.86],gap="large")
    with hero_col:
        from atlasquant_reference_ui import asset_uri
        brand = '<div class="aq-login-brand"><img src="' + asset_uri("trader-mark.webp") + '" alt="Logo AtlasQuant"><span>ATLASQUANT<small>ECOSSISTEMA</small></span></div>'
        st.markdown(LOGIN_REFERENCE_HERO.replace('<div class="aq-login-hero">','<div class="aq-login-hero">'+brand),unsafe_allow_html=True)
    return login_col

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
    try:
        from atlasquant_central_hub_ui import clear_login_greeting
        clear_login_greeting(st.session_state)
    except Exception:
        st.session_state.pop("aion_login_greeting_shown",None)

def evaluate_access(
    *,
    required:bool,
    users_count:int,
    session:dict[str,Any]|None,
    users:dict|None=None,
    allow_unconfigured_preview:bool=False,
)->dict[str,Any]:
    if not required:
        return {"allowed":True,"mode":"OPEN","reason":"AUTH_DISABLED"}
    if users_count<=0:
        if bool(allow_unconfigured_preview):
            return {
                "allowed":True,
                "mode":"PREVIEW",
                "reason":"BOOTSTRAP_PREVIEW_NO_USERS",
                "read_only":True,
            }
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
    bootstrap_preview=_bool_setting(_setting("ATLASQUANT_BOOTSTRAP_PREVIEW","true"))
    decision=evaluate_access(
        required=required,
        users_count=len(users),
        session=session,
        users=users,
        allow_unconfigured_preview=bootstrap_preview,
    )
    if decision.get("mode")=="PREVIEW":
        st.warning(
            "👁️ Visualização provisória: o administrador ainda não foi configurado. "
            "Acesso somente ao aplicativo; Vendas e Administração permanecem bloqueados."
        )
        st.caption(
            "Assim que ATLASQUANT_USERS_JSON receber a primeira conta segura, "
            "o login obrigatório passa a valer automaticamente."
        )
        return {**decision,"session":None,"role":"PREVIEW","registry":role_counts}
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

    login_col=render_login_reference_shell()
    with login_col:
        st.markdown('<div class="aq-login-eyebrow">Acesso privado</div>',unsafe_allow_html=True)
        st.markdown('<div class="aq-login-panel-title">Bem-vindo ao AtlasQuant</div>',unsafe_allow_html=True)
        st.markdown(
            '<div class="aq-login-panel-copy">Entre com sua conta autorizada para abrir sua central.</div>',
            unsafe_allow_html=True,
        )
        with st.form("atlasquant_login_form",clear_on_submit=False):
            username=st.text_input("Usuário",autocomplete="username")
            password=st.text_input("Senha",type="password",autocomplete="current-password")
            submit=st.form_submit_button("Entrar",type="primary",width="stretch")
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
