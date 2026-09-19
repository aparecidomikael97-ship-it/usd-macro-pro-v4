"""Safe offline registry administration for AtlasQuant accounts.

Pure helpers only. They never write Streamlit secrets, never call the network,
never delete users destructively and never affect trading configuration.
All changes are exported as a replacement JSON registry for manual review.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping
import json

from atlasquant_access_control import (
    AccessUser,
    MAX_USERS,
    hash_password,
    load_users_config,
    normalize_role,
    normalize_username,
)

SCHEMA="ATLASQUANT_REGISTRY_ADMIN_V1"

def registry_to_mapping(users:Mapping[str,AccessUser]|None)->dict[str,dict[str,Any]]:
    if not isinstance(users,Mapping):
        return {}
    out={}
    for username,user in users.items():
        if not isinstance(user,AccessUser):
            continue
        name=normalize_username(username)
        if not name or name!=user.username:
            continue
        out[name]={
            "role":user.role,
            "password_hash":user.password_hash,
            "active":bool(user.active),
        }
    validated=load_users_config({"users":out})
    if set(validated)!=set(out):
        return {}
    return out

def export_registry_json(users:Mapping[str,AccessUser]|None)->str:
    mapped=registry_to_mapping(users)
    if users and not mapped:
        raise ValueError("invalid registry")
    return json.dumps({"users":mapped},ensure_ascii=False,indent=2,sort_keys=True)

def add_account(
    users:Mapping[str,AccessUser]|None,
    *,
    username:Any,
    role:Any,
    password:Any,
    active:bool=True,
)->dict[str,AccessUser]:
    current=registry_to_mapping(users)
    name=normalize_username(username)
    normalized_role=normalize_role(role)
    if not name or not normalized_role or not isinstance(active,bool):
        raise ValueError("invalid account metadata")
    if name in current:
        raise ValueError("account already exists")
    if len(current)>=MAX_USERS:
        raise ValueError("registry capacity reached")
    encoded=hash_password(password)
    current[name]={
        "role":normalized_role,
        "password_hash":encoded,
        "active":active,
    }
    validated=load_users_config({"users":current})
    if set(validated)!=set(current):
        raise ValueError("registry validation failed")
    return validated

def set_account_active(
    users:Mapping[str,AccessUser]|None,
    username:Any,
    active:Any,
)->dict[str,AccessUser]:
    if not isinstance(active,bool):
        raise ValueError("invalid active flag")
    current=registry_to_mapping(users)
    name=normalize_username(username)
    if not name or name not in current:
        raise ValueError("account not found")
    current[name]["active"]=active
    validated=load_users_config({"users":current})
    if set(validated)!=set(current):
        raise ValueError("registry validation failed")
    return validated

def set_account_role(
    users:Mapping[str,AccessUser]|None,
    username:Any,
    role:Any,
)->dict[str,AccessUser]:
    current=registry_to_mapping(users)
    name=normalize_username(username)
    normalized_role=normalize_role(role)
    if not name or name not in current or not normalized_role:
        raise ValueError("invalid role change")
    current[name]["role"]=normalized_role
    validated=load_users_config({"users":current})
    if set(validated)!=set(current):
        raise ValueError("registry validation failed")
    return validated

def rotate_account_password(
    users:Mapping[str,AccessUser]|None,
    username:Any,
    password:Any,
)->dict[str,AccessUser]:
    current=registry_to_mapping(users)
    name=normalize_username(username)
    if not name or name not in current:
        raise ValueError("account not found")
    current[name]["password_hash"]=hash_password(password)
    validated=load_users_config({"users":current})
    if set(validated)!=set(current):
        raise ValueError("registry validation failed")
    return validated

def registry_diff(
    before:Mapping[str,AccessUser]|None,
    after:Mapping[str,AccessUser]|None,
)->dict[str,Any]:
    a=registry_to_mapping(before)
    b=registry_to_mapping(after)
    added=sorted(set(b)-set(a))
    missing=sorted(set(a)-set(b))
    changed=[]
    for name in sorted(set(a)&set(b)):
        fields=[]
        for field in ("role","active","password_hash"):
            if a[name].get(field)!=b[name].get(field):
                fields.append("credential" if field=="password_hash" else field)
        if fields:
            changed.append({"username":name,"fields":fields})
    return {
        "schema":SCHEMA,
        "added":added,
        "missing":missing,
        "changed":changed,
        "destructive_removal_detected":bool(missing),
        "safe_for_manual_export":not missing,
    }

def apply_non_destructive_change(
    before:Mapping[str,AccessUser]|None,
    after:Mapping[str,AccessUser]|None,
)->str:
    diff=registry_diff(before,after)
    if diff["destructive_removal_detected"]:
        raise ValueError("destructive account removal is not allowed")
    return export_registry_json(after)
