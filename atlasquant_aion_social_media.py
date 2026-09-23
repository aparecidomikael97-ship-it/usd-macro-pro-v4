"""AION Social Media Command Center contract.

AION may plan, create, review and analyze social content, but publishing is
always approval-gated. Provider adapters hold OAuth credentials outside model
context. No trading/money authority is inherited from social connections.
"""
from __future__ import annotations
from typing import Any,Mapping,Sequence
from datetime import datetime,timezone
import hashlib

SCHEMA="AION_SOCIAL_COMMAND_V1"
PLATFORMS=("instagram","youtube","tiktok")
CONTENT_STATES=("IDEA","DRAFT","EDITING","READY_FOR_REVIEW","APPROVED","PUBLISHING","PUBLISHED","REJECTED","FAILED")

def social_platform_registry()->dict[str,Any]:
    return {
        "schema":SCHEMA,
        "assistant_name":"AION",
        "platforms":{
            "instagram":{
                "read":["ACCOUNT_INSIGHTS","FOLLOWERS","REACH","VIEWS","LIKES","COMMENTS","SAVES","SHARES","CONTENT_LIST"],
                "write":["PUBLISH_IMAGE","PUBLISH_VIDEO","PUBLISH_REEL","CAPTION_UPDATE_WHEN_SUPPORTED"],
            },
            "youtube":{
                "read":["CHANNEL_INSIGHTS","SUBSCRIBERS","VIEWS","WATCH_TIME","LIKES","COMMENTS","CONTENT_LIST"],
                "write":["UPLOAD_VIDEO","UPDATE_METADATA","PLAYLIST_WRITE","THUMBNAIL_UPDATE_WHEN_SUPPORTED"],
            },
            "tiktok":{
                "read":["ACCOUNT_INSIGHTS","FOLLOWERS","VIEWS","LIKES","COMMENTS","SHARES","CONTENT_LIST"],
                "write":["PUBLISH_VIDEO","UPDATE_METADATA_WHEN_SUPPORTED"],
            },
        },
        "publish_requires_explicit_approval":True,
        "delete_requires_explicit_approval":True,
        "credentials_in_model_context":False,
        "audit_required":True,
        "real_orders_enabled":False,
        "voice_can_authorize_orders":False,
    }

def build_social_content_job(*,platforms:Sequence[str],title:str,objective:str,
                             source_assets:Sequence[str]|None=None,created_by:str="AION",
                             now:datetime|None=None)->dict[str,Any]:
    clean_platforms=[]
    for raw in platforms or []:
        p=str(raw or "").strip().lower()
        if p not in PLATFORMS: raise ValueError(f"unsupported platform: {p}")
        if p not in clean_platforms:clean_platforms.append(p)
    if not clean_platforms:raise ValueError("at least one platform required")
    clean_title=" ".join(str(title or "").strip().split())
    clean_objective=" ".join(str(objective or "").strip().split())
    if not clean_title or not clean_objective:raise ValueError("title and objective required")
    current=now or datetime.now(timezone.utc)
    if current.tzinfo is None:current=current.replace(tzinfo=timezone.utc)
    seed=f"{'|'.join(clean_platforms)}|{clean_title}|{clean_objective}|{current.isoformat()}"
    job_id="SOC-"+hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
    return {
        "schema":SCHEMA,
        "job_id":job_id,
        "state":"DRAFT",
        "platforms":clean_platforms,
        "title":clean_title,
        "objective":clean_objective,
        "source_assets":list(source_assets or []),
        "created_by":str(created_by or "AION"),
        "created_at":current.astimezone(timezone.utc).isoformat(),
        "deliverables":{
            "script":None,"video_master":None,"image_or_thumbnail":None,
            "captions":{},"titles":{},"descriptions":{},"hashtags":{},
            "platform_variants":{},
        },
        "approval":{
            "required":True,
            "approved":False,
            "approved_by":None,
            "approved_at":None,
            "content_hash":None,
        },
        "publish":{
            "requested":False,
            "published":False,
            "results":{},
        },
        "real_orders_enabled":False,
        "voice_can_authorize_orders":False,
    }

def content_fingerprint(job:Mapping[str,Any])->str:
    import json
    stable={
        "platforms":list(job.get("platforms",[]) or []),
        "title":job.get("title"),
        "objective":job.get("objective"),
        "deliverables":dict(job.get("deliverables",{}) or {}),
    }
    raw=json.dumps(stable,sort_keys=True,separators=(",",":"),ensure_ascii=False,default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def submit_for_review(job:Mapping[str,Any])->dict[str,Any]:
    out=dict(job or {})
    if str(out.get("state","")).upper() not in {"DRAFT","EDITING"}:
        raise ValueError("job not reviewable")
    deliverables=dict(out.get("deliverables",{}) or {})
    if not deliverables.get("script") and not deliverables.get("video_master") and not deliverables.get("image_or_thumbnail"):
        raise ValueError("content evidence missing")
    out["state"]="READY_FOR_REVIEW"
    approval=dict(out.get("approval",{}) or {})
    approval.update({"required":True,"approved":False,"approved_by":None,"approved_at":None,
                     "content_hash":content_fingerprint(out)})
    out["approval"]=approval
    return out

def approve_content(job:Mapping[str,Any],*,approved_by:str,now:datetime|None=None)->dict[str,Any]:
    out=dict(job or {})
    if str(out.get("state","")).upper()!="READY_FOR_REVIEW":raise ValueError("job not ready for approval")
    who=" ".join(str(approved_by or "").strip().split())
    if not who:raise ValueError("approver required")
    approval=dict(out.get("approval",{}) or {})
    expected=str(approval.get("content_hash",""))
    if not expected or expected!=content_fingerprint(out):raise ValueError("content changed after review")
    current=now or datetime.now(timezone.utc)
    if current.tzinfo is None:current=current.replace(tzinfo=timezone.utc)
    approval.update({"approved":True,"approved_by":who,"approved_at":current.astimezone(timezone.utc).isoformat()})
    out["approval"]=approval;out["state"]="APPROVED"
    return out

def publication_policy(job:Mapping[str,Any],*,connected_platforms:Sequence[str]|None=None)->dict[str,Any]:
    j=dict(job or {});connected={str(x).strip().lower() for x in (connected_platforms or [])}
    reasons=[];platforms=list(j.get("platforms",[]) or [])
    if str(j.get("state","")).upper()!="APPROVED":reasons.append("CONTENT_NOT_APPROVED")
    approval=dict(j.get("approval",{}) or {})
    if approval.get("approved") is not True:reasons.append("APPROVAL_MISSING")
    if str(approval.get("content_hash",""))!=content_fingerprint(j):reasons.append("CONTENT_CHANGED_AFTER_APPROVAL")
    missing=[p for p in platforms if p not in connected]
    if missing:reasons.append("PLATFORM_NOT_CONNECTED:"+",".join(missing))
    return {
        "publish_allowed":not reasons,
        "reasons":reasons,
        "explicit_approval_required":True,
        "platforms":platforms,
        "real_orders_enabled":False,
        "voice_can_authorize_orders":False,
    }

def normalize_social_metrics(platform:str,raw:Mapping[str,Any]|None)->dict[str,Any]:
    p=str(platform or "").strip().lower()
    if p not in PLATFORMS:raise ValueError("unsupported platform")
    src=dict(raw or {});out={"platform":p}
    keys=("followers","subscribers","views","reach","watch_time_minutes","likes","comments","shares","saves","published_content")
    for key in keys:
        value=src.get(key)
        if value is None:continue
        try:
            number=float(value)
            if number<0:raise ValueError
            out[key]=number
        except Exception:
            out[key]=None
    out["captured_at"]=str(src.get("captured_at") or "")
    return out
