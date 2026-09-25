"""AION personal-tenant privacy and data-lifecycle contracts.

This module is readiness-only. It does not activate subscriber AION, persist
personal memory, delete data, provision access, call external providers, charge
customers, or execute trading.

Goals:
- make allowed personal-memory fields explicit;
- detect tenant mismatch and unexpected data before export/use;
- prepare a tenant-scoped export without ADMIN/project memory;
- prepare deletion/retention plans without executing them;
- surface credential-rotation orphan-cleanup requirements.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import hashlib
import json

from atlasquant_aion_tenant import (
    sanitize_tenant_memory,
    tenant_memory_seed,
    tenant_namespace,
    tenant_runtime_path,
)

SCHEMA="ATLASQUANT_AION_TENANT_PRIVACY_V1"

ALLOWED_TOP_LEVEL_FIELDS=frozenset({
    "schema",
    "tenant_id",
    "namespace",
    "created_at",
    "updated_at",
    "profile",
    "conversation_notes",
    "academy_progress",
    "watchlist",
    "truth_policy",
    "privacy",
    "permissions",
})

PERSONAL_DATA_CLASSES=(
    {
        "key":"profile",
        "label":"Perfil do AION pessoal",
        "purpose":"Preferências básicas de experiência do próprio assinante.",
        "sensitivity":"PERSONAL",
    },
    {
        "key":"conversation_notes",
        "label":"Notas de conversa",
        "purpose":"Continuidade opcional do AION pessoal do próprio assinante.",
        "sensitivity":"PERSONAL",
    },
    {
        "key":"academy_progress",
        "label":"Progresso Academy",
        "purpose":"Continuidade educacional dentro do próprio tenant.",
        "sensitivity":"PERSONAL",
    },
    {
        "key":"watchlist",
        "label":"Watchlist",
        "purpose":"Preferências de ativos do próprio assinante.",
        "sensitivity":"PERSONAL",
    },
)

FORBIDDEN_MEMORY_KEYS=frozenset({
    "admin_memory",
    "canonical_memory",
    "project_docs",
    "project_documents",
    "other_tenant_memory",
    "secrets",
    "password",
    "credential",
    "api_key",
    "token",
})

RETENTION_REVIEW_DAYS={
    "conversation_notes":180,
    "academy_progress":365,
    "watchlist":365,
    "profile":365,
}


def _now()->str:
    return datetime.now(timezone.utc).isoformat()


def _stable_digest(payload:Any)->str:
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def tenant_privacy_policy_snapshot()->dict[str,Any]:
    return {
        "schema":SCHEMA,
        "allowed_top_level_fields":sorted(ALLOWED_TOP_LEVEL_FIELDS),
        "personal_data_classes":[dict(x) for x in PERSONAL_DATA_CLASSES],
        "forbidden_memory_keys":sorted(FORBIDDEN_MEMORY_KEYS),
        "retention_review_days":dict(RETENTION_REVIEW_DAYS),
        "retention_enforcement_enabled":False,
        "automatic_deletion":False,
        "automatic_export":False,
        "admin_memory_inherited":False,
        "project_docs_inherited":False,
        "cross_tenant_copy":False,
        "external_provider_auto_enabled":False,
        "billing_auto_enabled":False,
        "real_trading_enabled":False,
        "legal_compliance_claimed":False,
        "executes_action":False,
    }


def _unexpected_keys(raw:Mapping[str,Any]|None)->list[str]:
    if not isinstance(raw,Mapping):
        return []
    return sorted(
        str(key)
        for key in raw.keys()
        if str(key) not in ALLOWED_TOP_LEVEL_FIELDS
    )


def _forbidden_key_hits(value:Any, *, path:str="$")->list[str]:
    hits=[]
    if isinstance(value,Mapping):
        for key,item in value.items():
            key_text=str(key or "").strip().casefold()
            child=f"{path}.{str(key)}"
            if key_text in FORBIDDEN_MEMORY_KEYS:
                hits.append(child)
            hits.extend(_forbidden_key_hits(item,path=child))
    elif isinstance(value,(list,tuple)):
        for idx,item in enumerate(value[:500]):
            hits.extend(_forbidden_key_hits(item,path=f"{path}[{idx}]"))
    return hits[:100]


def tenant_memory_privacy_audit(
    raw_memory:Mapping[str,Any]|None,
    access:Mapping[str,Any]|None,
)->dict[str,Any]:
    ns=tenant_namespace(access)
    if not ns.get("ready"):
        return {
            "schema":SCHEMA,
            "state":"BLOCKED",
            "reason":"AUTHENTICATED_TENANT_REQUIRED",
            "tenant_match":False,
            "unexpected_fields":[],
            "forbidden_key_hits":[],
            "export_safe":False,
            "deletion_plan_safe":False,
            "executes_action":False,
        }

    raw=dict(raw_memory or {})
    tenant_match=str(raw.get("tenant_id") or "")==str(ns.get("tenant_id") or "")
    unexpected=_unexpected_keys(raw)
    forbidden=_forbidden_key_hits(raw)
    state="CONFIRMED"
    reason="TENANT_MEMORY_BOUNDARY_CONFIRMED"
    if not tenant_match:
        state="BLOCKED"
        reason="TENANT_ID_MISMATCH"
    elif unexpected or forbidden:
        state="BLOCKED"
        reason="UNEXPECTED_OR_FORBIDDEN_MEMORY_FIELDS"

    return {
        "schema":SCHEMA,
        "state":state,
        "reason":reason,
        "tenant_id":str(ns.get("tenant_id") or ""),
        "tenant_match":tenant_match,
        "unexpected_fields":unexpected,
        "forbidden_key_hits":forbidden,
        "export_safe":state=="CONFIRMED",
        "deletion_plan_safe":state=="CONFIRMED",
        "admin_memory_detected":any("admin_memory" in x for x in forbidden),
        "project_docs_detected":any("project_doc" in x for x in forbidden),
        "other_tenant_data_detected":not tenant_match or any("other_tenant" in x for x in forbidden),
        "executes_action":False,
    }


def tenant_export_bundle(
    raw_memory:Mapping[str,Any]|None,
    access:Mapping[str,Any]|None,
)->dict[str,Any]:
    """Prepare a tenant-scoped export bundle; never writes/downloads automatically."""
    audit=tenant_memory_privacy_audit(raw_memory,access)
    if audit.get("state")!="CONFIRMED":
        return {
            "schema":SCHEMA,
            "status":"BLOCKED",
            "reason":audit.get("reason"),
            "bundle":None,
            "executes_action":False,
        }

    safe=sanitize_tenant_memory(raw_memory,access)
    bundle={
        "schema":SCHEMA,
        "export_type":"TENANT_PERSONAL_MEMORY",
        "generated_at":_now(),
        "tenant_id":safe.get("tenant_id"),
        "namespace":safe.get("namespace"),
        "data":{
            "profile":deepcopy(safe.get("profile") or {}),
            "conversation_notes":deepcopy(safe.get("conversation_notes") or []),
            "academy_progress":deepcopy(safe.get("academy_progress") or {}),
            "watchlist":deepcopy(safe.get("watchlist") or []),
        },
        "excluded":{
            "admin_memory":True,
            "project_docs":True,
            "other_tenants":True,
            "credentials":True,
            "secrets":True,
        },
    }
    bundle["digest"]=_stable_digest(bundle["data"])
    return {
        "schema":SCHEMA,
        "status":"READY",
        "reason":"TENANT_SCOPED_EXPORT_PREPARED",
        "bundle":bundle,
        "automatic_download":False,
        "external_transfer":False,
        "executes_action":False,
    }


def tenant_retention_review(
    raw_memory:Mapping[str,Any]|None,
    access:Mapping[str,Any]|None,
    *,
    now:datetime|None=None,
)->dict[str,Any]:
    """Flag old notes for review; never removes anything automatically."""
    audit=tenant_memory_privacy_audit(raw_memory,access)
    if audit.get("state")!="CONFIRMED":
        return {
            "schema":SCHEMA,
            "state":"BLOCKED",
            "reason":audit.get("reason"),
            "review_items":[],
            "automatic_deletion":False,
            "executes_action":False,
        }

    current=now or datetime.now(timezone.utc)
    safe=sanitize_tenant_memory(raw_memory,access)
    review=[]
    limit_days=int(RETENTION_REVIEW_DAYS["conversation_notes"])
    for idx,row in enumerate(list(safe.get("conversation_notes") or [])):
        created=str((row or {}).get("created_at") or "").strip()
        if not created:
            review.append({
                "class":"conversation_notes",
                "index":idx,
                "state":"DATE_UNKNOWN",
                "reason":"Nota sem data confirmável; revisão manual necessária.",
            })
            continue
        try:
            dt=datetime.fromisoformat(created.replace("Z","+00:00"))
            if dt.tzinfo is None:
                dt=dt.replace(tzinfo=timezone.utc)
            age_days=max(0,(current.astimezone(timezone.utc)-dt.astimezone(timezone.utc)).days)
            if age_days>=limit_days:
                review.append({
                    "class":"conversation_notes",
                    "index":idx,
                    "state":"RETENTION_REVIEW_DUE",
                    "age_days":age_days,
                    "review_after_days":limit_days,
                    "reason":"Elegível para revisão de retenção; nenhuma exclusão automática.",
                })
        except Exception:
            review.append({
                "class":"conversation_notes",
                "index":idx,
                "state":"DATE_INVALID",
                "reason":"Data inválida; revisão manual necessária.",
            })

    return {
        "schema":SCHEMA,
        "state":"CONFIRMED",
        "review_items":review,
        "review_due":len(review),
        "automatic_deletion":False,
        "retention_enforcement_enabled":False,
        "executes_action":False,
    }


def tenant_deletion_plan(
    raw_memory:Mapping[str,Any]|None,
    access:Mapping[str,Any]|None,
    *,
    explicit_request:bool=False,
)->dict[str,Any]:
    """Build a delete plan for the tenant's own namespace; never deletes."""
    audit=tenant_memory_privacy_audit(raw_memory,access)
    ns=tenant_namespace(access)
    if audit.get("state")!="CONFIRMED":
        return {
            "schema":SCHEMA,
            "status":"BLOCKED",
            "reason":audit.get("reason"),
            "steps":[],
            "executes_action":False,
        }
    if not explicit_request:
        return {
            "schema":SCHEMA,
            "status":"AWAITING_EXPLICIT_REQUEST",
            "reason":"EXPLICIT_TENANT_REQUEST_REQUIRED",
            "steps":[],
            "executes_action":False,
        }

    path=tenant_runtime_path(access)
    steps=[
        "Reconfirmar identidade e tenant_id no momento da execução.",
        "Exportar dados primeiro somente se o assinante solicitar.",
        f"Localizar exclusivamente o namespace {ns.get('namespace')} / {path}.",
        "Bloquear qualquer path ADMIN, projeto ou de outro tenant.",
        "Executar exclusão somente por mecanismo de runtime específico e auditado.",
        "Reler o namespace e confirmar ausência antes de afirmar exclusão concluída.",
        "Registrar somente metadados mínimos do pedido/resultado, sem reter o conteúdo apagado.",
    ]
    return {
        "schema":SCHEMA,
        "status":"PLAN_READY",
        "tenant_id":ns.get("tenant_id"),
        "namespace":ns.get("namespace"),
        "runtime_path":path,
        "steps":steps,
        "automatic_deletion":False,
        "deletion_executed":False,
        "requires_fresh_identity_confirmation":True,
        "requires_explicit_execution_approval":True,
        "executes_action":False,
    }


def credential_rotation_cleanup_plan(
    previous_tenant_id:Any,
    access:Mapping[str,Any]|None,
)->dict[str,Any]:
    """Describe cleanup needed after credential-bound namespace rotation."""
    ns=tenant_namespace(access)
    if not ns.get("ready"):
        return {
            "schema":SCHEMA,
            "status":"BLOCKED",
            "reason":"AUTHENTICATED_TENANT_REQUIRED",
            "executes_action":False,
        }
    previous=str(previous_tenant_id or "").strip()
    current=str(ns.get("tenant_id") or "")
    if not previous or previous==current:
        return {
            "schema":SCHEMA,
            "status":"NO_ROTATION_DETECTED",
            "previous_tenant_id":previous,
            "current_tenant_id":current,
            "cleanup_required":False,
            "executes_action":False,
        }
    return {
        "schema":SCHEMA,
        "status":"CLEANUP_REVIEW_REQUIRED",
        "previous_tenant_id":previous,
        "current_tenant_id":current,
        "cleanup_required":True,
        "automatic_migration":False,
        "automatic_deletion":False,
        "reason":"Credential-bound namespace changed; old namespace must not follow silently.",
        "steps":[
            "Confirmar que a rotação pertence ao mesmo assinante autenticado.",
            "Não copiar memória antiga automaticamente para o novo namespace.",
            "Oferecer exportação/revisão somente após confirmação de identidade.",
            "Planejar limpeza do namespace antigo com auditoria e aprovação explícita.",
        ],
        "executes_action":False,
    }


def tenant_privacy_readiness(
    *,
    sample_memory:Mapping[str,Any]|None=None,
    sample_access:Mapping[str,Any]|None=None,
)->dict[str,Any]:
    policy=tenant_privacy_policy_snapshot()
    audit=None
    if sample_memory is not None or sample_access is not None:
        audit=tenant_memory_privacy_audit(sample_memory,sample_access)
    return {
        "schema":SCHEMA,
        "policy_defined":True,
        "allowed_data_classes":len(PERSONAL_DATA_CLASSES),
        "retention_policy_defined":True,
        "export_contract_ready":True,
        "deletion_plan_contract_ready":True,
        "credential_rotation_cleanup_contract_ready":True,
        "cross_tenant_audit_ready":True,
        "persistence_enabled":False,
        "subscriber_shell_enabled":False,
        "automatic_deletion":False,
        "automatic_export":False,
        "legal_compliance_claimed":False,
        "sample_audit":audit,
        "executes_action":False,
        "policy":policy,
    }


__all__=[
    "SCHEMA",
    "ALLOWED_TOP_LEVEL_FIELDS",
    "PERSONAL_DATA_CLASSES",
    "FORBIDDEN_MEMORY_KEYS",
    "RETENTION_REVIEW_DAYS",
    "tenant_privacy_policy_snapshot",
    "tenant_memory_privacy_audit",
    "tenant_export_bundle",
    "tenant_retention_review",
    "tenant_deletion_plan",
    "credential_rotation_cleanup_plan",
    "tenant_privacy_readiness",
]
