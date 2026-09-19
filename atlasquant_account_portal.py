"""AtlasQuant role-aware account portal.

Presentation/provisioning helper only. It never writes Streamlit secrets,
creates broker credentials, changes trading gates or enables real orders.
"""
from __future__ import annotations

from typing import Any, Mapping
import json
import re
import streamlit as st

from atlasquant_access_control import (
    ROLE_PERMISSIONS,
    hash_password,
    normalize_role,
    normalize_username,
    has_permission,
)

ROLE_LABELS={
    "USER":"Usuário",
    "SALES":"Vendas",
    "ADMIN":"Administrador",
    "OPEN":"Acesso aberto",
}

ROLE_DESCRIPTIONS={
    "USER":"Acesso ao aplicativo e às análises autorizadas.",
    "SALES":"Acesso ao aplicativo e à área comercial, sem poderes administrativos.",
    "ADMIN":"Acesso administrativo ao portal de contas; trading real continua independente e desativado.",
    "OPEN":"Autenticação ainda não exigida neste ambiente.",
}

def role_label(role:Any)->str:
    raw=str(role or "").strip().upper()
    return ROLE_LABELS.get(raw,"Sem perfil")

def role_description(role:Any)->str:
    raw=str(role or "").strip().upper()
    return ROLE_DESCRIPTIONS.get(raw,"Perfil inválido ou não autenticado.")

def role_sections(role:Any)->tuple[str,...]:
    raw=str(role or "").strip().upper()
    if raw=="ADMIN":
        return ("account","sales","admin")
    if raw=="SALES":
        return ("account","sales")
    if raw=="USER":
        return ("account",)
    if raw=="OPEN":
        return ("account",)
    return ()

def password_policy(password:Any)->dict[str,Any]:
    value=password if isinstance(password,str) else ""
    checks={
        "length":len(value)>=12,
        "upper":bool(re.search(r"[A-Z]",value)),
        "lower":bool(re.search(r"[a-z]",value)),
        "digit":bool(re.search(r"\d",value)),
        "symbol":bool(re.search(r"[^A-Za-z0-9]",value)),
    }
    return {"valid":all(checks.values()),"checks":checks}

def build_provisioning_record(
    username:Any,
    role:Any,
    password:Any,
    *,
    active:bool=True,
)->dict[str,Any]:
    name=normalize_username(username)
    normalized_role=normalize_role(role)
    policy=password_policy(password)
    if not name:
        raise ValueError("invalid username")
    if not normalized_role:
        raise ValueError("invalid role")
    if not isinstance(active,bool):
        raise ValueError("invalid active flag")
    if not policy["valid"]:
        raise ValueError("password policy failed")
    encoded=hash_password(str(password))
    return {
        name:{
            "role":normalized_role,
            "password_hash":encoded,
            "active":active,
        }
    }

def merge_provisioning_records(*records:Mapping[str,Any])->dict[str,Any]:
    users={}
    for record in records:
        if not isinstance(record,Mapping):
            raise ValueError("invalid record")
        for username,value in record.items():
            name=normalize_username(username)
            if not name or name in users:
                raise ValueError("duplicate or invalid username")
            users[name]=dict(value) if isinstance(value,Mapping) else value
    return {"users":users}

def provisioning_json(record:Mapping[str,Any])->str:
    if not isinstance(record,Mapping):
        raise ValueError("invalid record")
    return json.dumps({"users":dict(record)},ensure_ascii=False,indent=2,sort_keys=True)

def account_summary(access:Mapping[str,Any]|None)->dict[str,Any]:
    data=dict(access or {})
    session=data.get("session") if isinstance(data.get("session"),Mapping) else {}
    role=str(data.get("role") or session.get("role") or "OPEN").upper()
    username=str(session.get("username") or "")
    permissions=tuple(sorted(ROLE_PERMISSIONS.get(role,frozenset())))
    registry=data.get("registry") if isinstance(data.get("registry"),Mapping) else {}
    return {
        "mode":str(data.get("mode") or "OPEN"),
        "role":role if role in ROLE_LABELS else "INVALID",
        "role_label":role_label(role),
        "username":username,
        "permissions":permissions,
        "registry":{
            "USER":int(registry.get("USER",0) or 0),
            "SALES":int(registry.get("SALES",0) or 0),
            "ADMIN":int(registry.get("ADMIN",0) or 0),
            "TOTAL":int(registry.get("TOTAL",0) or 0),
        },
        "sections":role_sections(role),
        "authenticated":bool(role in ("USER","SALES","ADMIN") and username),
    }

def render_account_portal(access:Mapping[str,Any]|None)->dict[str,Any]:
    summary=account_summary(access)
    st.subheader("👤 Conta & Acesso")
    st.caption(
        "Perfis USER / SALES / ADMIN são separados do motor de trading. "
        "Esta área não habilita broker, ordens reais, promoção automática ou mudança automática de gates."
    )

    c1,c2,c3=st.columns(3)
    c1.metric("Perfil",summary["role_label"])
    c2.metric("Sessão","AUTENTICADA" if summary["authenticated"] else "ABERTA/LOCAL")
    c3.metric("Trading real","DESATIVADO")

    if summary["username"]:
        st.info("Conta ativa: **"+summary["username"]+"**")
    st.write(role_description(summary["role"]))

    if summary["role"]=="OPEN":
        st.warning(
            "O login privado está desativado neste ambiente. "
            "Para produção comercial, ATLASQUANT_AUTH_REQUIRED deve ser ativado somente após configurar usuários seguros."
        )
        return summary

    if "sales" in summary["sections"]:
        st.markdown("### 💼 Área de Vendas")
        st.caption(
            "Perfil comercial: acesso a materiais e acompanhamento comercial. "
            "Não pode administrar usuários nem alterar o motor operacional."
        )
        sales_rows=[
            {"Recurso":"Aplicativo AtlasQuant","Acesso":"SIM"},
            {"Recurso":"Área comercial","Acesso":"SIM"},
            {"Recurso":"Criar/alterar usuários","Acesso":"SIM" if summary["role"]=="ADMIN" else "NÃO"},
            {"Recurso":"Alterar motor de trading","Acesso":"NÃO"},
            {"Recurso":"Ativar ordens reais","Acesso":"NÃO"},
        ]
        st.dataframe(sales_rows,width="stretch",hide_index=True)

    if "admin" in summary["sections"]:
        st.markdown("### 🛡️ Administração de Contas")
        registry=summary.get("registry",{})
        r1,r2,r3,r4=st.columns(4)
        r1.metric("Usuários",int(registry.get("USER",0)))
        r2.metric("Vendas",int(registry.get("SALES",0)))
        r3.metric("Admins",int(registry.get("ADMIN",0)))
        r4.metric("Total ativo",int(registry.get("TOTAL",0)))
        st.caption(
            "Gera um registro seguro para ATLASQUANT_USERS_JSON. "
            "Nada é gravado automaticamente nos Secrets e a senha em texto puro não é persistida."
        )
        with st.form("atlasquant_admin_create_user",clear_on_submit=True):
            username=st.text_input("Novo usuário",help="3–64 caracteres: letras, números, ponto, hífen ou underscore.")
            role=st.selectbox("Perfil",["USER","SALES","ADMIN"],index=0)
            password=st.text_input("Senha temporária",type="password")
            confirm=st.text_input("Confirmar senha",type="password")
            active=st.checkbox("Conta ativa",value=True)
            submit=st.form_submit_button("Gerar registro seguro")
        if submit:
            if password!=confirm:
                st.error("As senhas não conferem.")
            else:
                try:
                    record=build_provisioning_record(username,role,password,active=active)
                    snippet=provisioning_json(record)
                    st.session_state["atlasquant_admin_provisioning_snippet"]=snippet
                    st.success("Registro gerado localmente. A senha em texto puro não foi armazenada.")
                except Exception:
                    st.error(
                        "Não foi possível gerar a conta. Use usuário válido e senha com 12+ caracteres, "
                        "maiúscula, minúscula, número e símbolo."
                    )
        snippet=st.session_state.get("atlasquant_admin_provisioning_snippet","")
        if isinstance(snippet,str) and snippet:
            st.code(snippet,language="json")
            st.download_button(
                "Baixar registro JSON",
                data=snippet.encode("utf-8"),
                file_name="atlasquant_user_record.json",
                mime="application/json",
                key="atlasquant_admin_download_user_record",
            )
            st.caption(
                "Adicione o registro ao JSON de usuários existente com cuidado. "
                "Usuários duplicados após normalização são rejeitados por segurança."
            )

    return summary
