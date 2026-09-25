"""AION Knowledge Graph contracts.

Auditable relationship layer over existing Checkpoint knowledge. The graph only
creates structural links that are explicit in source records (evidence refs,
source episode ids, applies_to, confirmed error causes, experiment versions).
It does not infer hidden causality, contradiction or semantic relationships.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

SCHEMA="ATLASQUANT_AION_KNOWLEDGE_GRAPH_V1"
MAX_NODES=6000
MAX_EDGES=12000

NODE_TYPES=(
    "LESSON","EPISODE","EXPERIMENT","VERSION","EVIDENCE","SCOPE","CAUSE",
    "COMPONENT","POLICY","CONCEPT","RISK",
)
EDGE_TYPES=(
    "SUPPORTED_BY","DERIVED_FROM","APPLIES_TO","CAUSED_BY","EVALUATES",
    "DEPENDS_ON","CONTRADICTS","RELATED_TO","INVALIDATES","GOVERNED_BY",
)
TRUTH_STATES=("CONFIRMED","INFERENCE","HYPOTHESIS","UNKNOWN")
_SAFE_ID=re.compile(r"^[a-z0-9][a-z0-9:._/-]{1,159}$")


def _clean(value:Any,limit:int=1200)->str:
    return " ".join(str(value or "").replace("\x00","").split())[:limit]


def _stable(value:Any,length:int=24)->str:
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:length]


def _safe_id(value:Any)->str:
    text=_clean(value,160).lower()
    if not _SAFE_ID.fullmatch(text):
        raise ValueError("invalid graph id")
    return text


def _truth(value:Any)->str:
    text=_clean(value,40).upper()
    return text if text in TRUTH_STATES else "UNKNOWN"


def _refs(values:Sequence[Any]|None,limit:int=60)->list[str]:
    out=[]
    for raw in list(values or [])[:limit*2]:
        text=_clean(raw,280)
        if text and text not in out:
            out.append(text)
        if len(out)>=limit:
            break
    return out


def graph_ref_id(prefix:str,value:Any)->str:
    base=_clean(value,500)
    return _safe_id(f"{prefix}:{_stable(base,20)}")


def new_node(
    node_id:Any,
    *,
    node_type:Any,
    label:Any,
    domain:Any="general",
    truth_state:Any="UNKNOWN",
    evidence_refs:Sequence[Any]|None=None,
    source_ref:Any="",
    metadata:Mapping[str,Any]|None=None,
)->dict[str,Any]:
    nid=_safe_id(node_id)
    ntype=_clean(node_type,40).upper()
    if ntype not in NODE_TYPES:
        raise ValueError("unsupported graph node type")
    truth=_truth(truth_state)
    refs=_refs(evidence_refs)
    if truth=="CONFIRMED" and not refs and ntype not in {"EVIDENCE","VERSION","SCOPE","CAUSE","COMPONENT","POLICY","CONCEPT","RISK"}:
        # Confirmed content-bearing knowledge must remain evidence-backed.
        truth="UNKNOWN"
    return {
        "schema":SCHEMA,
        "node_id":nid,
        "node_type":ntype,
        "label":_clean(label,500) or nid,
        "domain":_clean(domain,100).lower() or "general",
        "truth_state":truth,
        "evidence_refs":refs,
        "source_ref":_clean(source_ref,280),
        "metadata":dict(metadata or {}),
        "automatic_action":False,
        "real_trading_enabled":False,
    }


def new_edge(
    source_id:Any,
    relation:Any,
    target_id:Any,
    *,
    truth_state:Any="UNKNOWN",
    evidence_refs:Sequence[Any]|None=None,
    source_ref:Any="",
)->dict[str,Any]:
    source=_safe_id(source_id)
    target=_safe_id(target_id)
    rel=_clean(relation,50).upper()
    if rel not in EDGE_TYPES:
        raise ValueError("unsupported graph relation")
    truth=_truth(truth_state)
    refs=_refs(evidence_refs)
    if rel=="CAUSED_BY" and (truth!="CONFIRMED" or not refs):
        raise ValueError("causal edge requires confirmed truth and evidence refs")
    eid="edge:"+_stable({"s":source,"r":rel,"t":target},24)
    return {
        "schema":SCHEMA,
        "edge_id":eid,
        "source_id":source,
        "relation":rel,
        "target_id":target,
        "truth_state":truth,
        "evidence_refs":refs,
        "source_ref":_clean(source_ref,280),
        "automatic_action":False,
        "real_trading_enabled":False,
    }


def normalize_nodes(rows:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    out=[]
    seen=set()
    for raw in list(rows or [])[:MAX_NODES*2]:
        if not isinstance(raw,Mapping):
            continue
        try:
            item=new_node(
                raw.get("node_id"),
                node_type=raw.get("node_type"),
                label=raw.get("label"),
                domain=raw.get("domain"),
                truth_state=raw.get("truth_state"),
                evidence_refs=raw.get("evidence_refs") if isinstance(raw.get("evidence_refs"),(list,tuple)) else [],
                source_ref=raw.get("source_ref"),
                metadata=raw.get("metadata") if isinstance(raw.get("metadata"),Mapping) else {},
            )
        except Exception:
            continue
        if item["node_id"] in seen:
            continue
        seen.add(item["node_id"])
        out.append(item)
        if len(out)>=MAX_NODES:
            break
    return out


def normalize_edges(
    rows:Sequence[Mapping[str,Any]]|None,
    *,
    node_ids:set[str]|None=None,
)->list[dict[str,Any]]:
    out=[]
    seen=set()
    allowed=set(node_ids or [])
    for raw in list(rows or [])[:MAX_EDGES*2]:
        if not isinstance(raw,Mapping):
            continue
        try:
            item=new_edge(
                raw.get("source_id"),
                raw.get("relation"),
                raw.get("target_id"),
                truth_state=raw.get("truth_state"),
                evidence_refs=raw.get("evidence_refs") if isinstance(raw.get("evidence_refs"),(list,tuple)) else [],
                source_ref=raw.get("source_ref"),
            )
        except Exception:
            continue
        if allowed and (item["source_id"] not in allowed or item["target_id"] not in allowed):
            continue
        if item["edge_id"] in seen:
            continue
        seen.add(item["edge_id"])
        out.append(item)
        if len(out)>=MAX_EDGES:
            break
    return out


def _upsert_node(nodes:list[dict[str,Any]],node:dict[str,Any])->None:
    idx=next((i for i,x in enumerate(nodes) if x["node_id"]==node["node_id"]),None)
    if idx is None:
        nodes.append(node)
    else:
        nodes[idx]=node


def _append_edge(edges:list[dict[str,Any]],edge:dict[str,Any])->None:
    if all(x["edge_id"]!=edge["edge_id"] for x in edges):
        edges.append(edge)


def derive_graph(
    *,
    wisdom_entries:Sequence[Mapping[str,Any]]|None=None,
    learning_episodes:Sequence[Mapping[str,Any]]|None=None,
    experiments:Sequence[Mapping[str,Any]]|None=None,
    research_refs:Sequence[Mapping[str,Any]]|None=None,
)->dict[str,Any]:
    """Build only explicit structural relations from recorded Checkpoint fields."""
    nodes:list[dict[str,Any]]=[]
    edges:list[dict[str,Any]]=[]

    for raw in list(wisdom_entries or []):
        if not isinstance(raw,Mapping):
            continue
        wid=_clean(raw.get("wisdom_id"),100)
        if not wid:
            continue
        nid=_safe_id(f"wisdom:{wid.lower()}")
        refs=_refs(raw.get("evidence_refs") if isinstance(raw.get("evidence_refs"),(list,tuple)) else [])
        _upsert_node(nodes,new_node(
            nid,node_type="LESSON",label=raw.get("topic") or wid,
            domain=raw.get("domain") or "general",
            truth_state=raw.get("truth_state") or "UNKNOWN",
            evidence_refs=refs,source_ref=wid,
            metadata={"state":_clean(raw.get("state"),40),"confidence_pct":raw.get("confidence_pct")},
        ))
        for ref in refs:
            eid=graph_ref_id("evidence",ref)
            _upsert_node(nodes,new_node(eid,node_type="EVIDENCE",label=ref,truth_state="UNKNOWN",source_ref=ref))
            _append_edge(edges,new_edge(nid,"SUPPORTED_BY",eid,truth_state="CONFIRMED",evidence_refs=[ref],source_ref=wid))
        for episode_id in _refs(raw.get("source_episode_ids") if isinstance(raw.get("source_episode_ids"),(list,tuple)) else []):
            enid=_safe_id(f"episode:{episode_id.lower()}")
            _upsert_node(nodes,new_node(enid,node_type="EPISODE",label=episode_id,truth_state="UNKNOWN",source_ref=episode_id))
            _append_edge(edges,new_edge(nid,"DERIVED_FROM",enid,truth_state="CONFIRMED",evidence_refs=[episode_id],source_ref=wid))
        for scope in _refs(raw.get("applies_to") if isinstance(raw.get("applies_to"),(list,tuple)) else []):
            sid=graph_ref_id("scope",scope)
            _upsert_node(nodes,new_node(sid,node_type="SCOPE",label=scope,truth_state="UNKNOWN",source_ref=scope))
            _append_edge(edges,new_edge(nid,"APPLIES_TO",sid,truth_state="CONFIRMED",evidence_refs=[wid],source_ref=wid))

    for raw in list(learning_episodes or []):
        if not isinstance(raw,Mapping):
            continue
        eid=_clean(raw.get("episode_id"),100)
        if not eid:
            continue
        nid=_safe_id(f"episode:{eid.lower()}")
        refs=_refs(raw.get("evidence_refs") if isinstance(raw.get("evidence_refs"),(list,tuple)) else [])
        settled=_clean(raw.get("state"),40).upper()=="SETTLED"
        truth="CONFIRMED" if settled and refs else ("HYPOTHESIS" if not settled else "UNKNOWN")
        _upsert_node(nodes,new_node(
            nid,node_type="EPISODE",label=raw.get("subject") or eid,
            domain=raw.get("domain") or "general",truth_state=truth,
            evidence_refs=refs,source_ref=eid,
            metadata={"evaluation":_clean(raw.get("evaluation"),80),"model_version":_clean(raw.get("model_version"),120)},
        ))
        for ref in refs:
            evid=graph_ref_id("evidence",ref)
            _upsert_node(nodes,new_node(evid,node_type="EVIDENCE",label=ref,truth_state="UNKNOWN",source_ref=ref))
            _append_edge(edges,new_edge(nid,"SUPPORTED_BY",evid,truth_state="CONFIRMED",evidence_refs=[ref],source_ref=eid))
        cause=_clean(raw.get("error_cause"),80).upper()
        cause_confirmed=_clean(raw.get("error_cause_truth"),40).upper()=="CONFIRMED"
        if cause and cause!="UNKNOWN" and cause_confirmed and refs:
            cid=graph_ref_id("cause",cause)
            _upsert_node(nodes,new_node(cid,node_type="CAUSE",label=cause,truth_state="CONFIRMED",evidence_refs=refs,source_ref=eid))
            _append_edge(edges,new_edge(nid,"CAUSED_BY",cid,truth_state="CONFIRMED",evidence_refs=refs,source_ref=eid))

    for raw in list(experiments or []):
        if not isinstance(raw,Mapping):
            continue
        xid=_clean(raw.get("experiment_id"),100)
        if not xid:
            continue
        nid=_safe_id(f"experiment:{xid.lower()}")
        refs=_refs(raw.get("evidence_refs") if isinstance(raw.get("evidence_refs"),(list,tuple)) else [])
        _upsert_node(nodes,new_node(
            nid,node_type="EXPERIMENT",label=xid,truth_state="HYPOTHESIS",
            evidence_refs=refs,source_ref=xid,
            metadata={"state":_clean(raw.get("state"),60),"rationale":_clean(raw.get("rationale"),600)},
        ))
        for field in ("champion_version","challenger_version"):
            version=_clean(raw.get(field),140)
            if not version:
                continue
            vid=graph_ref_id("version",version)
            _upsert_node(nodes,new_node(vid,node_type="VERSION",label=version,truth_state="UNKNOWN",source_ref=version))
            _append_edge(edges,new_edge(nid,"EVALUATES",vid,truth_state="CONFIRMED",evidence_refs=[xid],source_ref=xid))

    for raw in list(research_refs or []):
        if not isinstance(raw,Mapping):
            continue
        ref=_clean(raw.get("ref_id"),280)
        if not ref:
            continue
        evid=graph_ref_id("evidence",ref)
        _upsert_node(nodes,new_node(
            evid,node_type="EVIDENCE",label=ref,truth_state="UNKNOWN",source_ref=ref,
            metadata={"kind":_clean(raw.get("kind"),60),"strategy":_clean(raw.get("strategy"),180)},
        ))

    nodes=normalize_nodes(nodes)
    node_ids={x["node_id"] for x in nodes}
    edges=normalize_edges(edges,node_ids=node_ids)
    return {
        "schema":SCHEMA,
        "nodes":nodes,
        "edges":edges,
        "digest":knowledge_graph_digest(nodes,edges),
        "semantic_inference_automatic":False,
        "causality_inferred_automatically":False,
        "automatic_rule_change":False,
        "real_trading_enabled":False,
    }


def normalize_knowledge_graph(raw:Mapping[str,Any]|None)->dict[str,Any]:
    item=dict(raw or {})
    nodes=normalize_nodes(item.get("nodes") if isinstance(item.get("nodes"),(list,tuple)) else [])
    node_ids={x["node_id"] for x in nodes}
    edges=normalize_edges(
        item.get("edges") if isinstance(item.get("edges"),(list,tuple)) else [],
        node_ids=node_ids,
    )
    return {
        "schema":SCHEMA,
        "nodes":nodes,
        "edges":edges,
        "digest":knowledge_graph_digest(nodes,edges),
        "semantic_inference_automatic":False,
        "causality_inferred_automatically":False,
        "automatic_rule_change":False,
        "real_trading_enabled":False,
    }


def synchronize_knowledge_graph(
    existing:Mapping[str,Any]|None,
    *,
    wisdom_entries:Sequence[Mapping[str,Any]]|None=None,
    learning_episodes:Sequence[Mapping[str,Any]]|None=None,
    experiments:Sequence[Mapping[str,Any]]|None=None,
    research_refs:Sequence[Mapping[str,Any]]|None=None,
)->dict[str,Any]:
    current=normalize_knowledge_graph(existing)
    derived=derive_graph(
        wisdom_entries=wisdom_entries,
        learning_episodes=learning_episodes,
        experiments=experiments,
        research_refs=research_refs,
    )
    node_map={x["node_id"]:x for x in current["nodes"]}
    for node in derived["nodes"]:
        node_map[node["node_id"]]=node
    edge_map={x["edge_id"]:x for x in current["edges"]}
    for edge in derived["edges"]:
        edge_map[edge["edge_id"]]=edge
    return normalize_knowledge_graph({
        "nodes":list(node_map.values())[:MAX_NODES],
        "edges":list(edge_map.values())[:MAX_EDGES],
    })


def graph_neighborhood(
    graph:Mapping[str,Any]|None,
    query:Any,
    *,
    limit:int=40,
)->dict[str,Any]:
    state=normalize_knowledge_graph(graph)
    needle=_clean(query,300).casefold()
    matches=[
        x for x in state["nodes"]
        if needle and (needle in x["node_id"].casefold() or needle in x["label"].casefold())
    ]
    matched_ids={x["node_id"] for x in matches[:max(1,min(limit,100))]}
    related_edges=[
        x for x in state["edges"]
        if x["source_id"] in matched_ids or x["target_id"] in matched_ids
    ][:max(1,min(limit*2,200))]
    related_ids=set(matched_ids)
    for edge in related_edges:
        related_ids.add(edge["source_id"])
        related_ids.add(edge["target_id"])
    related_nodes=[x for x in state["nodes"] if x["node_id"] in related_ids][:max(1,min(limit*3,300))]
    return {
        "schema":SCHEMA,
        "query":_clean(query,300),
        "nodes":related_nodes,
        "edges":related_edges,
        "matched_nodes":len(matches),
        "executes_action":False,
        "real_trading_enabled":False,
    }


def knowledge_graph_digest(
    nodes:Sequence[Mapping[str,Any]]|None,
    edges:Sequence[Mapping[str,Any]]|None,
)->str:
    payload={"nodes":normalize_nodes(nodes)}
    ids={x["node_id"] for x in payload["nodes"]}
    payload["edges"]=normalize_edges(edges,node_ids=ids)
    return _stable(payload,24)


def knowledge_graph_summary(raw:Mapping[str,Any]|None)->dict[str,Any]:
    state=normalize_knowledge_graph(raw)
    nodes=state["nodes"]
    edges=state["edges"]
    return {
        "schema":SCHEMA,
        "nodes":len(nodes),
        "edges":len(edges),
        "confirmed_nodes":sum(1 for x in nodes if x["truth_state"]=="CONFIRMED"),
        "confirmed_causal_edges":sum(1 for x in edges if x["relation"]=="CAUSED_BY" and x["truth_state"]=="CONFIRMED"),
        "unknown_nodes":sum(1 for x in nodes if x["truth_state"]=="UNKNOWN"),
        "semantic_inference_automatic":False,
        "causality_inferred_automatically":False,
        "digest":state["digest"],
        "executes_action":False,
        "real_trading_enabled":False,
    }


__all__=[
    "SCHEMA","NODE_TYPES","EDGE_TYPES","TRUTH_STATES",
    "new_node","new_edge","normalize_nodes","normalize_edges","derive_graph",
    "normalize_knowledge_graph","synchronize_knowledge_graph","graph_neighborhood",
    "knowledge_graph_digest","knowledge_graph_summary","graph_ref_id",
]
