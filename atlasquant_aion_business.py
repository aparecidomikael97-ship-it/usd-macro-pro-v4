"""AION Business research and unit-economics contracts.

Pure/offline. Product candidates and trend notes are administrator research
records. This module never claims a product is a bestseller without confirmed
evidence and never publishes a marketplace listing.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import hashlib
import json

from atlasquant_aion_core import guardian_decision, is_admin

SCHEMA="ATLASQUANT_AION_BUSINESS_V1"
MAX_PRODUCTS=300
CHANNELS=("Mercado Livre","TikTok Shop","Outro")
STATUSES=("RESEARCH","VALIDATE","APPROVED","PUBLISH_BLOCKED","LIVE","ARCHIVED")
TRUTH_STATES=("CONFIRMED","INFERENCE","HYPOTHESIS","UNKNOWN")


def _now()->str:
    return datetime.now(timezone.utc).isoformat()


def _text(value:Any,limit:int)->str:
    return " ".join(str(value or "").replace("\x00","").split())[:limit]


def _num(value:Any)->float:
    try:
        return max(0.0,float(value or 0))
    except Exception:
        return 0.0


def _truth(value:Any)->str:
    state=str(value or "UNKNOWN").strip().upper()
    return state if state in TRUTH_STATES else "UNKNOWN"


def _product_id(name:str,channel:str,created_at:str)->str:
    raw=f"{channel}|{name}|{created_at}".encode("utf-8")
    return "PRODUCT-"+hashlib.sha256(raw).hexdigest()[:12].upper()


def unit_economics(
    *,
    sale_price:Any,
    unit_cost:Any,
    platform_fee_pct:Any=0,
    shipping_cost:Any=0,
    tax_pct:Any=0,
    other_cost:Any=0,
)->dict[str,Any]:
    price=_num(sale_price)
    cost=_num(unit_cost)
    fee_pct=min(100.0,_num(platform_fee_pct))
    tax=min(100.0,_num(tax_pct))
    shipping=_num(shipping_cost)
    other=_num(other_cost)
    fee=price*(fee_pct/100.0)
    tax_value=price*(tax/100.0)
    total=cost+fee+shipping+tax_value+other
    profit=price-total
    margin=(profit/price*100.0) if price>0 else 0.0
    roi=(profit/cost*100.0) if cost>0 else 0.0
    return {
        "schema":SCHEMA,
        "sale_price":round(price,2),
        "unit_cost":round(cost,2),
        "platform_fee_pct":round(fee_pct,3),
        "platform_fee_value":round(fee,2),
        "shipping_cost":round(shipping,2),
        "tax_pct":round(tax,3),
        "tax_value":round(tax_value,2),
        "other_cost":round(other,2),
        "total_cost":round(total,2),
        "net_profit":round(profit,2),
        "net_margin_pct":round(margin,2),
        "roi_on_unit_cost_pct":round(roi,2),
        "profitable":bool(price>0 and profit>0),
    }


def new_product_candidate(
    name:Any,
    *,
    channel:Any="Mercado Livre",
    evidence_source:Any="",
    evidence_url:Any="",
    evidence_truth:Any="UNKNOWN",
    trend_note:Any="",
    supplier:Any="",
    sale_price:Any=0,
    unit_cost:Any=0,
    platform_fee_pct:Any=0,
    shipping_cost:Any=0,
    tax_pct:Any=0,
    other_cost:Any=0,
    source:Any="ADMIN",
    created_at:str|None=None,
)->dict[str,Any]:
    name_clean=_text(name,220)
    if not name_clean:
        raise ValueError("product name required")
    channel_clean=str(channel or "Mercado Livre").strip()
    if channel_clean not in CHANNELS:
        channel_clean="Outro"
    created=str(created_at or _now())
    economics=unit_economics(
        sale_price=sale_price,
        unit_cost=unit_cost,
        platform_fee_pct=platform_fee_pct,
        shipping_cost=shipping_cost,
        tax_pct=tax_pct,
        other_cost=other_cost,
    )
    truth=_truth(evidence_truth)
    return {
        "schema":SCHEMA,
        "product_id":_product_id(name_clean,channel_clean,created),
        "name":name_clean,
        "channel":channel_clean,
        "status":"RESEARCH",
        "research":{
            "truth_state":truth,
            "source":_text(evidence_source,220),
            "url":_text(evidence_url,600),
            "trend_note":_text(trend_note,1200),
            "bestseller_confirmed":False,
        },
        "supplier":_text(supplier,500),
        "economics":economics,
        "approval":{
            "approved":False,
            "approved_by":"",
            "approved_at":"",
        },
        "listing":{
            "live":False,
            "external_id":"",
            "url":"",
            "source":"",
            "confirmed_at":"",
        },
        "source":_text(source,100) or "ADMIN",
        "created_at":created,
        "updated_at":created,
    }


def normalize_product(raw:Mapping[str,Any])->dict[str,Any]:
    if not isinstance(raw,Mapping):
        raise ValueError("invalid product")
    research=raw.get("research") if isinstance(raw.get("research"),Mapping) else {}
    economics=raw.get("economics") if isinstance(raw.get("economics"),Mapping) else {}
    item=new_product_candidate(
        raw.get("name"),
        channel=raw.get("channel"),
        evidence_source=research.get("source"),
        evidence_url=research.get("url"),
        evidence_truth=research.get("truth_state"),
        trend_note=research.get("trend_note"),
        supplier=raw.get("supplier"),
        sale_price=economics.get("sale_price"),
        unit_cost=economics.get("unit_cost"),
        platform_fee_pct=economics.get("platform_fee_pct"),
        shipping_cost=economics.get("shipping_cost"),
        tax_pct=economics.get("tax_pct"),
        other_cost=economics.get("other_cost"),
        source=raw.get("source"),
        created_at=str(raw.get("created_at") or _now()),
    )
    if _text(raw.get("product_id"),64):
        item["product_id"]=_text(raw.get("product_id"),64)
    status=str(raw.get("status") or "RESEARCH").upper()
    item["status"]=status if status in STATUSES else "RESEARCH"
    item["updated_at"]=str(raw.get("updated_at") or item["created_at"])

    item["research"]["bestseller_confirmed"]=bool(
        (research or {}).get("bestseller_confirmed",False)
        and item["research"]["truth_state"]=="CONFIRMED"
        and item["research"]["source"]
    )

    approval=raw.get("approval")
    if isinstance(approval,Mapping):
        item["approval"]={
            "approved":bool(approval.get("approved",False)),
            "approved_by":_text(approval.get("approved_by"),80),
            "approved_at":_text(approval.get("approved_at"),80),
        }

    listing=raw.get("listing")
    if isinstance(listing,Mapping):
        item["listing"]={
            "live":bool(listing.get("live",False)),
            "external_id":_text(listing.get("external_id"),220),
            "url":_text(listing.get("url"),600),
            "source":_text(listing.get("source"),180),
            "confirmed_at":_text(listing.get("confirmed_at"),80),
        }
    if item["listing"]["live"] and not (
        item["listing"]["source"]
        and (item["listing"]["external_id"] or item["listing"]["url"])
    ):
        item["listing"]["live"]=False
        if item["status"]=="LIVE":
            item["status"]="APPROVED"
    return item


def normalize_products(rows:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    for raw in list(rows or [])[:MAX_PRODUCTS*2]:
        try:
            item=normalize_product(raw)
        except Exception:
            continue
        pid=item["product_id"]
        if pid in seen:
            continue
        seen.add(pid)
        out.append(item)
        if len(out)>=MAX_PRODUCTS:
            break
    return out


def upsert_product(
    rows:Sequence[Mapping[str,Any]]|None,
    product:Mapping[str,Any],
)->list[dict[str,Any]]:
    products=normalize_products(rows)
    item=normalize_product(product)
    for idx,current in enumerate(products):
        if current["product_id"]==item["product_id"]:
            products[idx]=item
            return products
    if len(products)>=MAX_PRODUCTS:
        raise ValueError("business capacity reached")
    products.append(item)
    return products


def trend_assessment(product:Mapping[str,Any])->dict[str,Any]:
    item=normalize_product(product)
    research=item["research"]
    confirmed=bool(
        research["truth_state"]=="CONFIRMED"
        and research["source"]
        and research["trend_note"]
    )
    return {
        "schema":SCHEMA,
        "product_id":item["product_id"],
        "truth_state":"CONFIRMED" if confirmed else research["truth_state"],
        "can_call_trending":confirmed,
        "can_call_bestseller":bool(confirmed and research["bestseller_confirmed"]),
        "message":(
            research["trend_note"]
            if confirmed else
            "Tendência não confirmada; falta evidência de fonte suficiente."
        ),
    }


def approve_product(
    product:Mapping[str,Any],
    access:Mapping[str,Any]|None,
)->dict[str,Any]:
    if not is_admin(access):
        raise PermissionError("ADMIN required")
    item=normalize_product(product)
    item["approval"]={
        "approved":True,
        "approved_by":_text((access or {}).get("username"),80) or "ADMIN",
        "approved_at":_now(),
    }
    item["status"]="APPROVED"
    item["updated_at"]=_now()
    return item


def marketplace_preflight(
    product:Mapping[str,Any],
    access:Mapping[str,Any]|None,
    *,
    feature_flags:Mapping[str,Any]|None=None,
    approved:bool=False,
)->dict[str,Any]:
    item=normalize_product(product)
    guardian=guardian_decision(
        "publish_marketplace",
        access,
        approved=approved,
        feature_flags=feature_flags,
    )
    product_approved=bool(item["approval"]["approved"])
    economics_ok=bool(item["economics"]["sale_price"]>0 and item["economics"]["unit_cost"]>=0)
    allowed=bool(product_approved and economics_ok and guardian["allowed"])
    if not product_approved:
        reason="Produto ainda não foi aprovado pelo administrador."
    elif not economics_ok:
        reason="Economia unitária incompleta."
    else:
        reason=guardian["reason"]
    return {
        "schema":SCHEMA,
        "product_id":item["product_id"],
        "allowed":allowed,
        "product_approved":product_approved,
        "economics_ok":economics_ok,
        "guardian":guardian,
        "reason":reason,
        "executes_publish":False,
    }


def mark_listing_live_from_evidence(
    product:Mapping[str,Any],
    evidence:Mapping[str,Any],
)->dict[str,Any]:
    item=normalize_product(product)
    data=dict(evidence or {})
    external_id=_text(data.get("external_id"),220)
    url=_text(data.get("url"),600)
    source=_text(data.get("source"),180)
    confirmed=bool(data.get("confirmed",False))
    if not confirmed or not source or not (external_id or url):
        raise ValueError("confirmed listing evidence required")
    item["listing"]={
        "live":True,
        "external_id":external_id,
        "url":url,
        "source":source,
        "confirmed_at":_text(data.get("confirmed_at"),80) or _now(),
    }
    item["status"]="LIVE"
    item["updated_at"]=_now()
    return item


def coverage_snapshot(system_cost_usd:Any,net_profit_sales_usd:Any)->dict[str,Any]:
    cost=_num(system_cost_usd)
    profit=_num(net_profit_sales_usd)
    pct=(profit/cost*100.0) if cost>0 else None
    remaining=max(0.0,cost-profit)
    return {
        "schema":SCHEMA,
        "system_cost_usd":round(cost,2),
        "net_profit_sales_usd":round(profit,2),
        "coverage_pct":None if pct is None else round(pct,2),
        "remaining_to_cover_usd":round(remaining,2),
        "covered":bool(cost>0 and profit>=cost),
        "source":"ADMIN_INPUT",
    }


def business_digest(rows:Sequence[Mapping[str,Any]]|None)->str:
    raw=json.dumps(normalize_products(rows),ensure_ascii=False,sort_keys=True,default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def business_summary(rows:Sequence[Mapping[str,Any]]|None)->dict[str,Any]:
    products=normalize_products(rows)
    by_status={status:0 for status in STATUSES}
    for item in products:
        by_status[item["status"]]+=1
    positive=sum(1 for item in products if item["economics"]["profitable"])
    confirmed_trends=sum(1 for item in products if trend_assessment(item)["can_call_trending"])
    return {
        "schema":SCHEMA,
        "total":len(products),
        "positive_margin_candidates":positive,
        "confirmed_trends":confirmed_trends,
        "live":by_status["LIVE"],
        "by_status":by_status,
    }


__all__=[
    "SCHEMA","CHANNELS","STATUSES","TRUTH_STATES","unit_economics",
    "new_product_candidate","normalize_product","normalize_products","upsert_product",
    "trend_assessment","approve_product","marketplace_preflight",
    "mark_listing_live_from_evidence","coverage_snapshot","business_digest","business_summary",
]
