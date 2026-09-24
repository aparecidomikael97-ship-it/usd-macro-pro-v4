"""AION Studio persistent content-workspace contracts.

Pure/offline planning only. Creating or approving a content project never posts
to Instagram, TikTok, YouTube or any other network. Publication remains behind
Guardian + feature flag + explicit approval + real connector evidence.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import hashlib
import json

from atlasquant_aion_core import guardian_decision, is_admin

SCHEMA="ATLASQUANT_AION_STUDIO_V1"
MAX_PROJECTS=200
PLATFORMS=("Instagram","TikTok","YouTube")
STATUSES=("IDEA","SCRIPT","REVIEW","APPROVED","PUBLISH_BLOCKED","PUBLISHED","ARCHIVED")
FORMATS=("9:16","16:9","1:1")


def _now()->str:
    return datetime.now(timezone.utc).isoformat()


def _text(value:Any,limit:int)->str:
    return " ".join(str(value or "").replace("\x00","").split())[:limit]


def _project_id(title:str,created_at:str)->str:
    raw=f"{title}|{created_at}".encode("utf-8")
    return "CONTENT-"+hashlib.sha256(raw).hexdigest()[:12].upper()


def _platforms(values:Sequence[Any]|None)->list[str]:
    out=[]
    for raw in list(values or []):
        value=str(raw or "").strip()
        if value in PLATFORMS and value not in out:
            out.append(value)
    return out or ["Instagram"]


def new_content_project(
    title:Any,
    *,
    objective:Any="",
    platforms:Sequence[Any]|None=None,
    format_ratio:Any="9:16",
    duration_seconds:Any=60,
    audience:Any="",
    tone:Any="humanizado, profissional e simples",
    cta:Any="",
    source:Any="ADMIN",
    created_at:str|None=None,
)->dict[str,Any]:
    title_clean=_text(title,220)
    if not title_clean:
        raise ValueError("content title required")
    created=str(created_at or _now())
    try:
        duration=max(10,min(600,int(duration_seconds)))
    except Exception:
        duration=60
    ratio=str(format_ratio or "9:16").strip()
    if ratio not in FORMATS:
        ratio="9:16"
    return {
        "schema":SCHEMA,
        "content_id":_project_id(title_clean,created),
        "title":title_clean,
        "objective":_text(objective,1200),
        "platforms":_platforms(platforms),
        "format_ratio":ratio,
        "duration_seconds":duration,
        "audience":_text(audience,600),
        "tone":_text(tone,400),
        "cta":_text(cta,500),
        "status":"IDEA",
        "approval":{
            "approved":False,
            "approved_by":"",
            "approved_at":"",
        },
        "publication":{
            "executed":False,
            "external_id":"",
            "url":"",
            "confirmed_at":"",
            "source":"",
        },
        "source":_text(source,100) or "ADMIN",
        "created_at":created,
        "updated_at":created,
    }


def normalize_project(raw:Mapping[str,Any])->dict[str,Any]:
    if not isinstance(raw,Mapping):
        raise ValueError("invalid project")
    project=new_content_project(
        raw.get("title"),
        objective=raw.get("objective"),
        platforms=raw.get("platforms") if isinstance(raw.get("platforms"),list) else [],
        format_ratio=raw.get("format_ratio"),
        duration_seconds=raw.get("duration_seconds",60),
        audience=raw.get("audience"),
        tone=raw.get("tone"),
        cta=raw.get("cta"),
        source=raw.get("source"),
        created_at=str(raw.get("created_at") or _now()),
    )
    if _text(raw.get("content_id"),64):
        project["content_id"]=_text(raw.get("content_id"),64)
    status=str(raw.get("status") or "IDEA").upper()
    project["status"]=status if status in STATUSES else "IDEA"
    project["updated_at"]=str(raw.get("updated_at") or project["created_at"])
    approval=raw.get("approval")
    if isinstance(approval,Mapping):
        project["approval"]={
            "approved":bool(approval.get("approved",False)),
            "approved_by":_text(approval.get("approved_by"),80),
            "approved_at":_text(approval.get("approved_at"),80),
        }
    publication=raw.get("publication")
    if isinstance(publication,Mapping):
        project["publication"]={
            "executed":bool(publication.get("executed",False)),
            "external_id":_text(publication.get("external_id"),200),
            "url":_text(publication.get("url"),500),
            "confirmed_at":_text(publication.get("confirmed_at"),80),
            "source":_text(publication.get("source"),160),
        }
    if project["publication"]["executed"] and not (
        project["publication"]["external_id"] or project["publication"]["url"]
    ):
        # Do not preserve an unsupported claim of publication.
        project["publication"]["executed"]=False
        if project["status"]=="PUBLISHED":
            project["status"]="APPROVED"
    return project


def normalize_projects(rows:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    for raw in list(rows or [])[:MAX_PROJECTS*2]:
        try:
            project=normalize_project(raw)
        except Exception:
            continue
        pid=project["content_id"]
        if pid in seen:
            continue
        seen.add(pid)
        out.append(project)
        if len(out)>=MAX_PROJECTS:
            break
    return out


def upsert_project(
    rows:Sequence[Mapping[str,Any]]|None,
    project:Mapping[str,Any],
)->list[dict[str,Any]]:
    projects=normalize_projects(rows)
    item=normalize_project(project)
    for idx,current in enumerate(projects):
        if current["content_id"]==item["content_id"]:
            projects[idx]=item
            return projects
    if len(projects)>=MAX_PROJECTS:
        raise ValueError("studio capacity reached")
    projects.append(item)
    return projects


def script_blueprint(project:Mapping[str,Any])->dict[str,Any]:
    item=normalize_project(project)
    duration=item["duration_seconds"]
    hook=max(3,min(8,round(duration*0.10)))
    problem=max(5,round(duration*0.20))
    demo=max(8,round(duration*0.45))
    proof=max(5,round(duration*0.15))
    used=hook+problem+demo+proof
    cta=max(3,duration-used)
    return {
        "schema":SCHEMA,
        "content_id":item["content_id"],
        "title":item["title"],
        "total_seconds":duration,
        "segments":[
            {"name":"Gancho","seconds":hook,"instruction":"Abrir com benefício ou problema concreto, sem promessa de lucro."},
            {"name":"Contexto","seconds":problem,"instruction":"Explicar para quem serve e qual problema resolve."},
            {"name":"Demonstração","seconds":demo,"instruction":"Mostrar recurso real do AtlasQuant e o fluxo na interface."},
            {"name":"Prova/clareza","seconds":proof,"instruction":"Mostrar evidência verificável, limites e o que ainda está em validação."},
            {"name":"CTA","seconds":cta,"instruction":item["cta"] or "Convidar para conhecer o AtlasQuant sem urgência artificial."},
        ],
        "truth_guard":[
            "Não prometer rentabilidade.",
            "Não chamar backtest de resultado futuro.",
            "Não afirmar integração ou recurso que não esteja confirmado.",
            "Separar demonstração real de conceito futuro.",
        ],
        "executes_publish":False,
    }


def approve_project(
    project:Mapping[str,Any],
    access:Mapping[str,Any]|None,
)->dict[str,Any]:
    if not is_admin(access):
        raise PermissionError("ADMIN required")
    item=normalize_project(project)
    item["approval"]={
        "approved":True,
        "approved_by":_text((access or {}).get("username"),80) or "ADMIN",
        "approved_at":_now(),
    }
    item["status"]="APPROVED"
    item["updated_at"]=_now()
    return item


def publication_preflight(
    project:Mapping[str,Any],
    access:Mapping[str,Any]|None,
    *,
    feature_flags:Mapping[str,Any]|None=None,
    approved:bool=False,
)->dict[str,Any]:
    item=normalize_project(project)
    guardian=guardian_decision(
        "publish_social",
        access,
        approved=approved,
        feature_flags=feature_flags,
    )
    project_approved=bool(item["approval"]["approved"])
    allowed=bool(project_approved and guardian["allowed"])
    reason=(
        "Conteúdo aprovado e Guardian liberou publicação."
        if allowed else
        "Projeto ainda não está aprovado pelo administrador."
        if not project_approved else guardian["reason"]
    )
    return {
        "schema":SCHEMA,
        "content_id":item["content_id"],
        "allowed":allowed,
        "project_approved":project_approved,
        "guardian":guardian,
        "reason":reason,
        "executes_publish":False,
    }


def mark_published_from_evidence(
    project:Mapping[str,Any],
    evidence:Mapping[str,Any],
)->dict[str,Any]:
    """Record publication only when a connector returns concrete evidence."""
    item=normalize_project(project)
    data=dict(evidence or {})
    external_id=_text(data.get("external_id"),200)
    url=_text(data.get("url"),500)
    source=_text(data.get("source"),160)
    confirmed=bool(data.get("confirmed",False))
    if not confirmed or not source or not (external_id or url):
        raise ValueError("confirmed publication evidence required")
    item["publication"]={
        "executed":True,
        "external_id":external_id,
        "url":url,
        "confirmed_at":_text(data.get("confirmed_at"),80) or _now(),
        "source":source,
    }
    item["status"]="PUBLISHED"
    item["updated_at"]=_now()
    return item


def studio_digest(rows:Sequence[Mapping[str,Any]]|None)->str:
    raw=json.dumps(normalize_projects(rows),ensure_ascii=False,sort_keys=True,default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def studio_summary(rows:Sequence[Mapping[str,Any]]|None)->dict[str,Any]:
    projects=normalize_projects(rows)
    by_status={status:0 for status in STATUSES}
    for item in projects:
        by_status[item["status"]]+=1
    return {
        "schema":SCHEMA,
        "total":len(projects),
        "approved":by_status["APPROVED"],
        "published":by_status["PUBLISHED"],
        "in_review":by_status["REVIEW"],
        "by_status":by_status,
    }


__all__=[
    "SCHEMA","PLATFORMS","STATUSES","FORMATS","new_content_project",
    "normalize_project","normalize_projects","upsert_project","script_blueprint",
    "approve_project","publication_preflight","mark_published_from_evidence",
    "studio_digest","studio_summary",
]
