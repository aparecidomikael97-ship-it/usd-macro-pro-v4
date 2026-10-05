"""AION Library Index V1.

Deterministic, offline catalog for reviewed Library Foundation documents.
This module indexes metadata and excerpts only. It does not call models,
create embeddings, persist externally, promote memory, or infer truth.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re
import unicodedata

from atlasquant_aion_library_foundation import document_access
from atlasquant_aion_knowledge_graph import new_node, new_edge, graph_ref_id

SCHEMA = "ATLASQUANT_AION_LIBRARY_INDEX_V1"
INDEXABLE_STATES = ("VALIDATED", "CONFLICTING", "STALE")
PASSAGE_STATES = ("INDEXED", "HELD", "REJECTED")
MAX_DOCUMENTS = 2000
MAX_PASSAGES = 20000
MAX_PASSAGE_CHARS = 1800
MAX_TERMS = 120

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_/-]{1,63}", re.I)

def _clean(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]

def _fold(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold()

def _stable(value: Any, length: int = 24) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:length]

def _terms(value: Any) -> list[str]:
    seen=[]
    for token in _TOKEN_RE.findall(_fold(value)):
        if token not in seen:
            seen.append(token)
        if len(seen) >= MAX_TERMS:
            break
    return seen

@dataclass(frozen=True)
class IndexedPassage:
    passage_id: str
    document_id: str
    tenant_id: str
    workspace_id: str
    ordinal: int
    text: str
    terms: tuple[str, ...]
    state: str
    provenance_id: str
    evidence_refs: tuple[str, ...]
    truth_state: str
    authority: str = "NONE"
    external_persisted: bool = False
    executes_action: bool = False

    def as_dict(self) -> dict[str, Any]:
        data=asdict(self)
        data["terms"]=list(self.terms)
        data["evidence_refs"]=list(self.evidence_refs)
        return data
def empty_library_index() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "documents": [],
        "passages": [],
        "external_persisted": False,
        "memory_promoted": False,
        "execution_authorized": False,
        "external_action_executed": False,
    }

def index_document(
    index: Mapping[str, Any] | None,
    document: Mapping[str, Any],
    *,
    passages: Sequence[Any] | None,
    trusted_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Index one reviewed document and bounded excerpts."""
    base=dict(index or empty_library_index())
    row=dict(document or {})
    ctx=dict(trusted_context or {})
    tenant=_clean(ctx.get("tenant_id"),120)
    workspace=_clean(ctx.get("workspace_id"),120)
    blockers=[]

    if row.get("tenant_id") != tenant or row.get("workspace_id") != workspace:
        blockers.append("SCOPE_MISMATCH")
    if row.get("state") not in INDEXABLE_STATES:
        blockers.append("DOCUMENT_NOT_INDEXABLE")
    access=document_access(
        row,
        requesting_tenant_id=tenant,
        requesting_domain_id="BIBLIOTECA",
        is_admin=_clean(ctx.get("role"),40).upper()=="ADMIN",
    )
    if access.get("allowed") is not True:
        blockers.extend("ACCESS_" + str(x).upper() for x in access.get("reasons", []))

    prov=dict(row.get("provenance") or {})
    provenance_id=_clean(prov.get("provenance_id"),80)
    if not provenance_id:
        blockers.append("PROVENANCE_MISSING")

    if blockers:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "blockers": list(dict.fromkeys(blockers)),
            "index": base,
            "indexed_passages": 0,
            "external_persisted": False,
            "memory_promoted": False,
            "execution_authorized": False,
            "external_action_executed": False,
        }

    docs=[dict(x) for x in list(base.get("documents") or []) if isinstance(x,Mapping)]
    existing=[
        x for x in docs
        if x.get("document_id")==row.get("document_id")
        and x.get("tenant_id")==tenant
        and x.get("workspace_id")==workspace
    ]
    doc_entry={
        "document_id": row.get("document_id"),
        "tenant_id": tenant,
        "workspace_id": workspace,
        "title": _clean(row.get("title"),400),
        "author": _clean(row.get("author"),240),
        "publisher": _clean(row.get("publisher"),240),
        "state": row.get("state"),
        "truth_state": row.get("truth_state") or "UNKNOWN",
        "source_reference": _clean(row.get("source_reference"),400),
        "checksum": _clean(row.get("checksum"),160),
        "provenance_id": provenance_id,
        "evidence_refs": list(row.get("evidence_refs") or []),
        "terms": _terms(" ".join([
            str(row.get("title") or ""),
            str(row.get("author") or ""),
            str(row.get("publisher") or ""),
            str(row.get("summary") or ""),
        ])),
        "authority": "NONE",
        "external_persisted": False,
        "executes_action": False,
    }
    if existing:
        docs=[
            doc_entry
            if (
                x.get("document_id")==row.get("document_id")
                and x.get("tenant_id")==tenant
                and x.get("workspace_id")==workspace
            )
            else x
            for x in docs
        ]
    elif len(docs)<MAX_DOCUMENTS:
        docs.append(doc_entry)

    current_passages=[
        dict(x) for x in list(base.get("passages") or [])
        if isinstance(x,Mapping)
        and not (
            x.get("document_id") == row.get("document_id")
            and x.get("tenant_id") == tenant
            and x.get("workspace_id") == workspace
        )
    ]
    created=[]
    for ordinal, raw in enumerate(list(passages or [])[:500], start=1):
        text=_clean(raw, MAX_PASSAGE_CHARS)
        if not text:
            continue
        pid="PASS-" + _stable({
            "document_id": row.get("document_id"),
            "ordinal": ordinal,
            "text": text,
        }).upper()
        created.append(IndexedPassage(
            passage_id=pid,
            document_id=str(row.get("document_id") or ""),
            tenant_id=tenant,
            workspace_id=workspace,
            ordinal=ordinal,
            text=text,
            terms=tuple(_terms(text)),
            state="INDEXED",
            provenance_id=provenance_id,
            evidence_refs=tuple(_clean(x,180) for x in list(row.get("evidence_refs") or []) if _clean(x,180)),
            truth_state=str(row.get("truth_state") or "UNKNOWN"),
        ).as_dict())
        if len(current_passages)+len(created)>=MAX_PASSAGES:
            break

    updated={
        "schema": SCHEMA,
        "documents": docs[-MAX_DOCUMENTS:],
        "passages": (current_passages+created)[-MAX_PASSAGES:],
        "external_persisted": False,
        "memory_promoted": False,
        "execution_authorized": False,
        "external_action_executed": False,
    }
    return {
        "schema": SCHEMA,
        "status": "INDEXED",
        "index": updated,
        "indexed_passages": len(created),
        "document_id": row.get("document_id"),
        "external_persisted": False,
        "memory_promoted": False,
        "execution_authorized": False,
        "external_action_executed": False,
    }
def projection_manifest(index: Mapping[str, Any] | None) -> dict[str, Any]:
    """Describe the index as a disposable derived projection, never source of truth."""
    state=dict(index or empty_library_index())
    docs=[dict(x) for x in list(state.get("documents") or []) if isinstance(x,Mapping)]
    passages=[dict(x) for x in list(state.get("passages") or []) if isinstance(x,Mapping)]
    identity=[
        {
            "tenant_id":x.get("tenant_id"),
            "workspace_id":x.get("workspace_id"),
            "document_id":x.get("document_id"),
            "checksum":x.get("checksum"),
            "provenance_id":x.get("provenance_id"),
        }
        for x in docs
    ]
    passage_identity=[
        {
            "tenant_id":x.get("tenant_id"),
            "workspace_id":x.get("workspace_id"),
            "document_id":x.get("document_id"),
            "passage_id":x.get("passage_id"),
        }
        for x in passages
    ]
    return {
        "schema": SCHEMA,
        "documents": len(docs),
        "passages": len(passages),
        "projection_digest": "sha256:" + sha256(
            json.dumps(
                {"documents":identity,"passages":passage_identity},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",",":"),
                default=str,
            ).encode("utf-8")
        ).hexdigest(),
        "source_of_truth": False,
        "disposable": True,
        "rebuild_requires_source_documents": True,
        "memory_promoted": False,
        "execution_authorized": False,
        "external_persisted": False,
    }


def purge_document_projection(
    index: Mapping[str, Any] | None,
    document_id: Any,
    *,
    trusted_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Remove only one tenant/workspace document projection and its passages."""
    state=dict(index or empty_library_index())
    ctx=dict(trusted_context or {})
    tenant=_clean(ctx.get("tenant_id"),120)
    workspace=_clean(ctx.get("workspace_id"),120)
    target=_clean(document_id,120)
    if not tenant or not workspace or not target:
        return {
            "schema":SCHEMA,"status":"BLOCKED",
            "blockers":["TRUSTED_SCOPE_OR_DOCUMENT_MISSING"],
            "index":state,"removed_documents":0,"removed_passages":0,
            "source_of_truth":False,"executes_action":False,
        }
    docs=[dict(x) for x in list(state.get("documents") or []) if isinstance(x,Mapping)]
    passages=[dict(x) for x in list(state.get("passages") or []) if isinstance(x,Mapping)]
    all_targets=[x for x in docs if x.get("document_id")==target]
    scoped=[
        x for x in all_targets
        if x.get("tenant_id")==tenant and x.get("workspace_id")==workspace
    ]
    if all_targets and not scoped:
        return {
            "schema":SCHEMA,"status":"BLOCKED",
            "blockers":["CROSS_SCOPE_DOCUMENT_PURGE_DENIED"],
            "index":state,"removed_documents":0,"removed_passages":0,
            "source_of_truth":False,"executes_action":False,
        }
    next_docs=[
        x for x in docs
        if not (
            x.get("document_id")==target
            and x.get("tenant_id")==tenant
            and x.get("workspace_id")==workspace
        )
    ]
    removed_passages=[
        x for x in passages
        if (
            x.get("document_id")==target
            and x.get("tenant_id")==tenant
            and x.get("workspace_id")==workspace
        )
    ]
    next_passages=[
        x for x in passages
        if not (
            x.get("document_id")==target
            and x.get("tenant_id")==tenant
            and x.get("workspace_id")==workspace
        )
    ]
    updated={
        "schema":SCHEMA,
        "documents":next_docs,
        "passages":next_passages,
        "external_persisted":False,
        "memory_promoted":False,
        "execution_authorized":False,
        "external_action_executed":False,
    }
    return {
        "schema":SCHEMA,
        "status":"PURGED" if scoped else "NOOP",
        "index":updated,
        "removed_documents":len(docs)-len(next_docs),
        "removed_passages":len(removed_passages),
        "tenant_id":tenant,
        "workspace_id":workspace,
        "document_id":target,
        "source_of_truth":False,
        "disposable_projection":True,
        "executes_action":False,
    }


def purge_scope_projection(
    index: Mapping[str, Any] | None,
    *,
    trusted_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Delete derived projection rows for exactly one trusted tenant/workspace."""
    state=dict(index or empty_library_index())
    ctx=dict(trusted_context or {})
    tenant=_clean(ctx.get("tenant_id"),120)
    workspace=_clean(ctx.get("workspace_id"),120)
    if not tenant or not workspace:
        return {
            "schema":SCHEMA,"status":"BLOCKED",
            "blockers":["TRUSTED_SCOPE_MISSING"],"index":state,
            "removed_documents":0,"removed_passages":0,
            "executes_action":False,
        }
    docs=[dict(x) for x in list(state.get("documents") or []) if isinstance(x,Mapping)]
    passages=[dict(x) for x in list(state.get("passages") or []) if isinstance(x,Mapping)]
    next_docs=[
        x for x in docs
        if not (x.get("tenant_id")==tenant and x.get("workspace_id")==workspace)
    ]
    next_passages=[
        x for x in passages
        if not (x.get("tenant_id")==tenant and x.get("workspace_id")==workspace)
    ]
    updated={
        "schema":SCHEMA,
        "documents":next_docs,
        "passages":next_passages,
        "external_persisted":False,
        "memory_promoted":False,
        "execution_authorized":False,
        "external_action_executed":False,
    }
    return {
        "schema":SCHEMA,"status":"PURGED",
        "index":updated,
        "removed_documents":len(docs)-len(next_docs),
        "removed_passages":len(passages)-len(next_passages),
        "tenant_id":tenant,"workspace_id":workspace,
        "source_of_truth":False,"disposable_projection":True,
        "executes_action":False,
    }


def rebuild_scope_projection(
    documents: Sequence[Mapping[str, Any]] | None,
    passage_map: Mapping[str, Sequence[Any]] | None,
    *,
    trusted_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Rebuild a disposable scope projection only from supplied reviewed sources."""
    ctx=dict(trusted_context or {})
    tenant=_clean(ctx.get("tenant_id"),120)
    workspace=_clean(ctx.get("workspace_id"),120)
    if not tenant or not workspace:
        return {
            "schema":SCHEMA,"status":"BLOCKED",
            "blockers":["TRUSTED_SCOPE_MISSING"],
            "index":empty_library_index(),"executes_action":False,
        }
    source_docs=[dict(x) for x in list(documents or []) if isinstance(x,Mapping)]
    if any(
        row.get("tenant_id")!=tenant or row.get("workspace_id")!=workspace
        for row in source_docs
    ):
        return {
            "schema":SCHEMA,"status":"BLOCKED",
            "blockers":["CROSS_SCOPE_REBUILD_SOURCE_DENIED"],
            "index":empty_library_index(),"executes_action":False,
        }
    state=empty_library_index()
    mapping=dict(passage_map or {})
    for row in source_docs:
        result=index_document(
            state,
            row,
            passages=mapping.get(str(row.get("document_id") or ""), []),
            trusted_context=ctx,
        )
        if result.get("status")!="INDEXED":
            return {
                "schema":SCHEMA,"status":"BLOCKED",
                "blockers":list(result.get("blockers") or ["REBUILD_SOURCE_REJECTED"]),
                "index":empty_library_index(),"executes_action":False,
            }
        state=result["index"]
    return {
        "schema":SCHEMA,"status":"REBUILT",
        "index":state,
        "manifest":projection_manifest(state),
        "source_of_truth":False,
        "rebuild_source_count":len(source_docs),
        "executes_action":False,
    }


def search_library_index(
    index: Mapping[str, Any] | None,
    query: Any,
    *,
    trusted_context: Mapping[str, Any] | None,
    limit: int = 20,
) -> dict[str, Any]:
    """Lexical retrieval only; does not make semantic or truth claims."""
    state=dict(index or empty_library_index())
    ctx=dict(trusted_context or {})
    tenant=_clean(ctx.get("tenant_id"),120)
    workspace=_clean(ctx.get("workspace_id"),120)
    query_text=_clean(query,500)
    qterms=set(_terms(query_text))
    cap=max(1,min(int(limit or 20),100))

    if not tenant or not workspace or not qterms:
        return {
            "schema": SCHEMA,
            "query": query_text,
            "hits": [],
            "status": "BLOCKED",
            "blockers": ["TRUSTED_SCOPE_OR_QUERY_MISSING"],
            "semantic_search": False,
            "external_persisted": False,
            "execution_authorized": False,
        }

    docs={
        str(x.get("document_id")):x for x in list(state.get("documents") or [])
        if isinstance(x,Mapping)
        and x.get("tenant_id")==tenant
        and x.get("workspace_id")==workspace
    }
    hits=[]
    for row in list(state.get("passages") or []):
        if not isinstance(row,Mapping):
            continue
        if row.get("tenant_id")!=tenant or row.get("workspace_id")!=workspace:
            continue
        doc=docs.get(str(row.get("document_id")))
        if not doc:
            continue
        rterms=set(str(x) for x in list(row.get("terms") or []))
        overlap=sorted(qterms & rterms)
        if not overlap:
            continue
        score=len(overlap)/max(1,len(qterms))
        hits.append({
            "document_id": row.get("document_id"),
            "passage_id": row.get("passage_id"),
            "title": doc.get("title"),
            "text": row.get("text"),
            "score": round(score,4),
            "matched_terms": overlap,
            "document_state": doc.get("state"),
            "truth_state": row.get("truth_state") or "UNKNOWN",
            "provenance_id": row.get("provenance_id"),
            "evidence_refs": list(row.get("evidence_refs") or []),
            "authority": "NONE",
        })
    hits.sort(key=lambda x:(-x["score"],str(x["document_id"]),str(x["passage_id"])))
    return {
        "schema": SCHEMA,
        "query": query_text,
        "hits": hits[:cap],
        "status": "RESULTS" if hits else "NO_RESULTS",
        "semantic_search": False,
        "provider_called": False,
        "web_research_executed": False,
        "external_persisted": False,
        "execution_authorized": False,
        "external_action_executed": False,
    }
def classification_snapshot(index: Mapping[str, Any] | None) -> dict[str, Any]:
    state=dict(index or empty_library_index())
    docs=[x for x in list(state.get("documents") or []) if isinstance(x,Mapping)]
    by_state={name:0 for name in INDEXABLE_STATES}
    for row in docs:
        key=str(row.get("state") or "")
        if key in by_state:
            by_state[key]+=1
    return {
        "schema": SCHEMA,
        "documents": len(docs),
        "passages": len([x for x in list(state.get("passages") or []) if isinstance(x,Mapping)]),
        "by_state": by_state,
        "external_persisted": False,
        "execution_authorized": False,
    }

def document_graph_fragment(document: Mapping[str, Any]) -> dict[str, Any]:
    """Create an optional explicit Knowledge Graph fragment.

    No semantic relation is invented. Document -> evidence is explicit only.
    """
    row=dict(document or {})
    doc_id=_clean(row.get("document_id"),120)
    prov=dict(row.get("provenance") or {})
    provenance_id=_clean(prov.get("provenance_id"),120)
    if not doc_id or not provenance_id:
        return {"schema":SCHEMA,"nodes":[],"edges":[],"status":"BLOCKED"}
    doc_node=graph_ref_id("concept",doc_id)
    evid_node=graph_ref_id("evidence",provenance_id)
    refs=list(row.get("evidence_refs") or []) or [provenance_id]
    nodes=[
        new_node(
            doc_node,node_type="CONCEPT",label=row.get("title") or doc_id,
            domain="biblioteca",truth_state="UNKNOWN",evidence_refs=refs,source_ref=doc_id,
            metadata={"library_document_id":doc_id,"document_state":row.get("state")},
        ),
        new_node(
            evid_node,node_type="EVIDENCE",label=provenance_id,
            domain="biblioteca",truth_state="UNKNOWN",source_ref=provenance_id,
        ),
    ]
    edges=[
        new_edge(
            doc_node,"SUPPORTED_BY",evid_node,
            truth_state="CONFIRMED",evidence_refs=refs,source_ref=doc_id,
        )
    ]
    return {
        "schema":SCHEMA,
        "nodes":nodes,
        "edges":edges,
        "status":"FRAGMENT",
        "semantic_inference_automatic":False,
        "causality_inferred_automatically":False,
        "execution_authorized":False,
    }

__all__=[
    "SCHEMA","INDEXABLE_STATES","PASSAGE_STATES","IndexedPassage",
    "empty_library_index","index_document","search_library_index",
    "projection_manifest","purge_document_projection","purge_scope_projection",
    "rebuild_scope_projection","classification_snapshot","document_graph_fragment",
]
