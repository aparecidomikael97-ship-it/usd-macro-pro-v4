"""Non-sensitive audit manifest for proposed AtlasQuant account changes.

The manifest stores only usernames, changed field names and a SHA-256 digest of
an exported registry. It never stores plaintext passwords or password hashes.
"""
from __future__ import annotations

from typing import Any, Mapping
import hashlib
import json

from atlasquant_access_control import normalize_username

SCHEMA="ATLASQUANT_ACCOUNT_CHANGE_AUDIT_V1"

def build_account_change_audit(
    *,
    actor:Any,
    diff:Mapping[str,Any],
    registry_json:str,
    generated_at:str,
)->dict[str,Any]:
    actor_name=normalize_username(actor)
    if not actor_name:
        raise ValueError("invalid actor")
    if not isinstance(diff,Mapping):
        raise ValueError("invalid diff")
    if not isinstance(registry_json,str) or not registry_json.strip():
        raise ValueError("invalid registry export")
    if not isinstance(generated_at,str) or not generated_at.strip():
        raise ValueError("invalid generated_at")
    if diff.get("destructive_removal_detected"):
        raise ValueError("destructive change cannot be audited as safe")

    added=[normalize_username(x) for x in (diff.get("added") or [])]
    if any(not x for x in added):
        raise ValueError("invalid added account")
    changed=[]
    for item in diff.get("changed") or []:
        if not isinstance(item,Mapping):
            raise ValueError("invalid changed item")
        name=normalize_username(item.get("username"))
        fields=[str(x) for x in (item.get("fields") or [])]
        allowed_fields={"role","active","credential"}
        if not name or not fields or any(x not in allowed_fields for x in fields):
            raise ValueError("invalid changed item")
        changed.append({"username":name,"fields":fields})

    digest=hashlib.sha256(registry_json.encode("utf-8")).hexdigest()
    return {
        "schema":SCHEMA,
        "actor":actor_name,
        "generated_at":generated_at.strip(),
        "added":added,
        "changed":changed,
        "registry_sha256":digest,
        "contains_password":False,
        "contains_password_hash":False,
        "automatic_apply":False,
    }

def account_change_audit_json(manifest:Mapping[str,Any])->str:
    if not isinstance(manifest,Mapping) or manifest.get("schema")!=SCHEMA:
        raise ValueError("invalid audit manifest")
    return json.dumps(dict(manifest),ensure_ascii=False,indent=2,sort_keys=True)
