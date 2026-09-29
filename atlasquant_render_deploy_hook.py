"""Authorization contract for a Render Deploy Hook.

The hook URL is read only from RENDER_DEPLOY_HOOK_URL. This module never
stores, logs, or returns that URL, and it never performs the HTTP call.
Presence of the variable is not authorization. A dispatch requires
human_approved is True and still stays unsent here.
"""
from __future__ import annotations

from typing import Mapping
import os


SCHEMA="ATLASQUANT_RENDER_DEPLOY_HOOK_V1"


def _configured(value:object)->bool:
    if not isinstance(value, str):
        return False
    text=value.strip()
    if not text.startswith("https://") or any(ch.isspace() for ch in text):
        return False
    return True


def deploy_hook_status(
    env:Mapping[str,str]|None=None,
    *,
    human_approved:object=False,
)->dict[str,object]:
    data=os.environ if env is None else env
    raw=data.get("RENDER_DEPLOY_HOOK_URL") if hasattr(data, "get") else None
    configured=_configured(raw)
    approved=human_approved is True
    if not configured:
        state="NOT_CONFIGURED"
    elif not approved:
        state="APPROVAL_REQUIRED"
    else:
        state="APPROVED_NOT_SENT"
    return {
        "schema":SCHEMA,
        "state":state,
        "configured":configured,
        "human_approved":approved,
        "authorized":configured and approved,
        "executes_request":False,
        "dispatches_hook":False,
        "hook_url_included":False,
    }


__all__=["SCHEMA","deploy_hook_status"]
