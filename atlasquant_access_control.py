"""AtlasQuant local access-control primitives.

Security boundary for future ADMIN / SALES / USER login. Pure/offline helpers:
no network, no broker access, no automatic account provisioning.
Passwords must be stored as PBKDF2-SHA256 hashes; plaintext credentials are rejected.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
import hashlib
import hmac
import json
import re
import secrets

SCHEMA="ATLASQUANT_ACCESS_V1"
ROLES=("USER","SALES","ADMIN")
DEFAULT_ITERATIONS=310_000
MIN_ITERATIONS=200_000
MAX_ITERATIONS=2_000_000
_USERNAME_RE=re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")

ROLE_PERMISSIONS={
    "USER":frozenset({"app:read"}),
    "SALES":frozenset({"app:read","sales:read"}),
    "ADMIN":frozenset({"app:read","sales:read","admin:read","admin:manage_users"}),
}

@dataclass(frozen=True)
class AccessUser:
    username:str
    role:str
    password_hash:str
    active:bool=True

def normalize_username(value:Any)->str:
    username=str(value or "").strip().lower()
    return username if _USERNAME_RE.fullmatch(username) else ""

def normalize_role(value:Any)->str:
    role=str(value or "").strip().upper()
    return role if role in ROLES else ""

def hash_password(password:str, *, salt:bytes|None=None, iterations:int=DEFAULT_ITERATIONS)->str:
    if not isinstance(password,str) or len(password)<10:
        raise ValueError("password must have at least 10 characters")
    if isinstance(iterations,bool):
        raise ValueError("invalid iterations")
    try:
        it=int(iterations)
    except Exception as exc:
        raise ValueError("invalid iterations") from exc
    if it<MIN_ITERATIONS or it>MAX_ITERATIONS:
        raise ValueError("invalid iterations")
    raw_salt=bytes(salt) if salt is not None else secrets.token_bytes(16)
    if len(raw_salt)<16:
        raise ValueError("salt too short")
    digest=hashlib.pbkdf2_hmac("sha256",password.encode("utf-8"),raw_salt,it)
    return f"pbkdf2_sha256${it}${raw_salt.hex()}${digest.hex()}"

def verify_password(password:str, encoded:str)->bool:
    if not isinstance(password,str) or not isinstance(encoded,str):
        return False
    try:
        algorithm,it_raw,salt_hex,digest_hex=encoded.split("$",3)
        if algorithm!="pbkdf2_sha256":
            return False
        it=int(it_raw)
        if it<MIN_ITERATIONS or it>MAX_ITERATIONS:
            return False
        salt=bytes.fromhex(salt_hex)
        expected=bytes.fromhex(digest_hex)
        if len(salt)<16 or len(expected)!=32:
            return False
        actual=hashlib.pbkdf2_hmac("sha256",password.encode("utf-8"),salt,it)
        return hmac.compare_digest(actual,expected)
    except Exception:
        return False

def _valid_hash_format(encoded:str)->bool:
    try:
        parts=encoded.split("$")
        if len(parts)!=4 or parts[0]!="pbkdf2_sha256":
            return False
        it=int(parts[1]); salt=bytes.fromhex(parts[2]); digest=bytes.fromhex(parts[3])
        return MIN_ITERATIONS<=it<=MAX_ITERATIONS and len(salt)>=16 and len(digest)==32
    except Exception:
        return False

def _user_from_record(username:Any, record:Any)->AccessUser|None:
    name=normalize_username(username)
    if not name or not isinstance(record,Mapping):
        return None
    role=normalize_role(record.get("role"))
    encoded=str(record.get("password_hash") or "").strip()
    active=record.get("active",True)
    if not role or not isinstance(active,bool):
        return None
    if "password" in record or not _valid_hash_format(encoded):
        return None
    return AccessUser(name,role,encoded,active)

def load_users_config(raw:Any)->dict[str,AccessUser]:
    if raw is None or raw=="":
        return {}
    try:
        data=json.loads(raw) if isinstance(raw,str) else raw
    except Exception:
        return {}
    if not isinstance(data,Mapping):
        return {}
    users_raw=data.get("users",data)
    if not isinstance(users_raw,Mapping):
        return {}
    out={}
    for username,record in users_raw.items():
        user=_user_from_record(username,record)
        if user is None or user.username in out:
            continue
        out[user.username]=user
    return out

def authenticate(username:Any,password:Any,users:Mapping[str,AccessUser]|None)->dict[str,Any]|None:
    name=normalize_username(username)
    if not name or not isinstance(password,str) or not isinstance(users,Mapping):
        return None
    user=users.get(name)
    if not isinstance(user,AccessUser) or not user.active:
        return None
    if not verify_password(password,user.password_hash):
        return None
    return {"schema":SCHEMA,"username":user.username,"role":user.role,"permissions":sorted(ROLE_PERMISSIONS[user.role])}

def has_permission(session:Mapping[str,Any]|None, permission:str)->bool:
    if not isinstance(session,Mapping):
        return False
    role=normalize_role(session.get("role"))
    return bool(role and str(permission) in ROLE_PERMISSIONS[role])
