"""AION unified approval inbox.

Pure/offline aggregation only. It consolidates records that have reached a
state that genuinely asks for administrator review. It does not approve,
publish, charge, activate, deploy, modify accounts or execute trading.
"""
from __future__ import annotations

from typing import Any, Mapping

from atlasquant_aion_operations import normalize_queue
from atlasquant_aion_studio import normalize_projects
from atlasquant_aion_business import normalize_products
from atlasquant_aion_promotions import normalize_campaigns
from atlasquant_aion_entitlements import normalize_entitlements

SCHEMA="ATLASQUANT_AION_APPROVAL_INBOX_V1"
KINDS=("TASK","STUDIO","BUSINESS","PROMOTION","ENTITLEMENT")
_KIND_RANK={
    "TASK":0,
    "ENTITLEMENT":1,
    "PROMOTION":2,
    "STUDIO":3,
    "BUSINESS":4,
}
_PRIORITY_RANK={"P0":0,"P1":1,"P2":2,"P3":3}


def _text(value:Any,limit:int=500)->str:
    return " ".join(str(value or "").replace("\x00","").split())[:limit]


def _row(
    kind:str,
    item_id:Any,
    title:Any,
    *,
    area:str,
    status:str,
    reason:str,
    created_at:Any="",
    priority:str="P2",
    action:str="",
)->dict[str,Any]:
    k=str(kind or "").upper()
    if k not in KINDS:
        raise ValueError("invalid approval kind")
    p=str(priority or "P2").upper()
    if p not in _PRIORITY_RANK:
        p="P2"
    return {
        "schema":SCHEMA,
        "kind":k,
        "item_id":_text(item_id,80),
        "title":_text(title,240),
        "area":_text(area,80),
        "status":_text(status,80).upper(),
        "reason":_text(reason,700),
        "priority":p,
        "action":_text(action,120),
        "created_at":_text(created_at,100),
        "approval_required":True,
        "approved":False,
        "executes_action":False,
    }


def collect_approval_inbox(
    checkpoint:Mapping[str,Any]|None,
)->dict[str,Any]:
    cp=dict(checkpoint or {})
    items=[]

    operating=cp.get("operating") if isinstance(cp.get("operating"),Mapping) else {}
    tasks=normalize_queue(operating.get("tasks") if isinstance(operating,Mapping) else [])
    for task in tasks:
        approval=task.get("approval") if isinstance(task.get("approval"),Mapping) else {}
        waiting=task.get("status")=="WAITING_APPROVAL"
        required=bool(approval.get("required",False))
        approved=bool(approval.get("approved",False))
        if not approved and (waiting or required):
            items.append(_row(
                "TASK",
                task.get("task_id"),
                task.get("title"),
                area=str(task.get("domain") or "secretary"),
                status=str(task.get("status") or "WAITING_APPROVAL"),
                reason=(
                    "Tarefa operacional marcada como aguardando aprovação explícita."
                    if waiting else
                    "Tarefa possui requisito de aprovação registrado."
                ),
                created_at=task.get("created_at"),
                priority=str(task.get("priority") or "P2"),
                action=str(task.get("action") or ""),
            ))

    studio=cp.get("studio") if isinstance(cp.get("studio"),Mapping) else {}
    for project in normalize_projects(studio.get("projects") if isinstance(studio,Mapping) else []):
        approval=project.get("approval") if isinstance(project.get("approval"),Mapping) else {}
        if project.get("status")=="REVIEW" and not bool(approval.get("approved",False)):
            items.append(_row(
                "STUDIO",
                project.get("content_id"),
                project.get("title"),
                area="studio",
                status="REVIEW",
                reason="Conteúdo chegou ao estágio de revisão e ainda não foi aprovado pelo ADMIN.",
                created_at=project.get("created_at"),
                priority="P2",
                action="approve_content",
            ))

    business=cp.get("business") if isinstance(cp.get("business"),Mapping) else {}
    for product in normalize_products(business.get("products") if isinstance(business,Mapping) else []):
        approval=product.get("approval") if isinstance(product.get("approval"),Mapping) else {}
        if product.get("status")=="VALIDATE" and not bool(approval.get("approved",False)):
            items.append(_row(
                "BUSINESS",
                product.get("product_id"),
                product.get("name"),
                area="business",
                status="VALIDATE",
                reason="Candidato de negócio chegou à validação e ainda não foi aprovado pelo ADMIN.",
                created_at=product.get("created_at"),
                priority="P2",
                action="approve_product",
            ))

    promotions=cp.get("promotions") if isinstance(cp.get("promotions"),Mapping) else {}
    for campaign in normalize_campaigns(promotions.get("campaigns") if isinstance(promotions,Mapping) else []):
        approval=campaign.get("approval") if isinstance(campaign.get("approval"),Mapping) else {}
        if campaign.get("status")=="DRAFT" and not bool(approval.get("approved",False)):
            items.append(_row(
                "PROMOTION",
                campaign.get("campaign_id"),
                campaign.get("name"),
                area="promotions",
                status="DRAFT",
                reason="Campanha criada e ainda não aprovada; nenhum benefício foi ativado.",
                created_at=campaign.get("created_at"),
                priority="P1",
                action="approve_campaign",
            ))

    entitlements=cp.get("entitlements") if isinstance(cp.get("entitlements"),Mapping) else {}
    for entitlement in normalize_entitlements(entitlements.get("records") if isinstance(entitlements,Mapping) else []):
        approval=entitlement.get("approval") if isinstance(entitlement.get("approval"),Mapping) else {}
        if entitlement.get("status")=="DRAFT" and not bool(approval.get("approved",False)):
            items.append(_row(
                "ENTITLEMENT",
                entitlement.get("entitlement_id"),
                f"{entitlement.get('subject_ref')} · {entitlement.get('scope')}",
                area="promotions",
                status="DRAFT",
                reason=(
                    "Solicitação de direito de acesso ainda não aprovada. "
                    "Aprovação não altera conta nem concede acesso automaticamente."
                ),
                created_at=entitlement.get("created_at"),
                priority="P1",
                action="approve_entitlement",
            ))

    items.sort(key=lambda x:(
        _PRIORITY_RANK.get(x["priority"],99),
        _KIND_RANK.get(x["kind"],99),
        str(x.get("created_at") or ""),
        str(x.get("item_id") or ""),
    ))

    by_kind={kind:0 for kind in KINDS}
    by_priority={key:0 for key in _PRIORITY_RANK}
    for item in items:
        by_kind[item["kind"]]+=1
        by_priority[item["priority"]]+=1

    return {
        "schema":SCHEMA,
        "items":items,
        "total":len(items),
        "by_kind":by_kind,
        "by_priority":by_priority,
        "has_pending":bool(items),
        "next_items":items[:10],
        "automatic_approval":False,
        "executes_action":False,
        "real_orders_enabled":False,
    }


def approval_rows(inbox:Mapping[str,Any]|None)->list[dict[str,Any]]:
    items=(inbox or {}).get("items") if isinstance(inbox,Mapping) else []
    rows=[]
    for item in list(items or []):
        if not isinstance(item,Mapping):
            continue
        rows.append({
            "Prioridade":item.get("priority"),
            "Tipo":item.get("kind"),
            "Área":item.get("area"),
            "Status":item.get("status"),
            "Item":item.get("title"),
            "Motivo":item.get("reason"),
        })
    return rows


__all__=["SCHEMA","KINDS","collect_approval_inbox","approval_rows"]
