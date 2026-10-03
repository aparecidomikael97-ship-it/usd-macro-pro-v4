"""Fail-closed mapping between evidence truth and Library review states.

The existing evidence engine and Library use different vocabularies. This
adapter gives the unified runtime one conservative operational interpretation
without changing either source contract and without promoting knowledge to
memory or decision authority.
"""
from __future__ import annotations

from typing import Any

from atlasquant_aion_library_foundation import DOCUMENT_STATES
from atlasquant_aion_truth import FRESHNESS_STATES, TRUTH_STATES

SCHEMA = "ATLASQUANT_AION_TRUTH_MAPPING_V1"
INDEXABLE_LIBRARY_STATES = frozenset({"VALIDATED", "CONFLICTING", "STALE"})


def map_truth_knowledge_state(
    *,
    evidence_truth_state: Any = "UNKNOWN",
    library_state: Any = "",
    library_truth_state: Any = "",
    freshness: Any = "UNVERIFIED",
    provenance_review_status: Any = "",
) -> dict[str, Any]:
    evidence = str(evidence_truth_state or "UNKNOWN").strip().upper()
    library = str(library_state or "").strip().upper()
    library_truth = str(library_truth_state or "").strip().upper()
    fresh = str(freshness or "UNVERIFIED").strip().upper()
    provenance = str(provenance_review_status or "").strip().upper()
    reasons: list[str] = []

    if evidence not in TRUTH_STATES:
        evidence = "UNKNOWN"
        reasons.append("EVIDENCE_TRUTH_INVALID")
    if library and library not in DOCUMENT_STATES:
        reasons.append("LIBRARY_STATE_INVALID")
        library = ""
    if fresh not in FRESHNESS_STATES:
        fresh = "UNVERIFIED"
        reasons.append("FRESHNESS_INVALID")

    candidate = evidence
    if library_truth == "SUPPORTED":
        candidate = "CONFIRMED"
    elif library_truth in TRUTH_STATES:
        candidate = library_truth
    elif library_truth:
        reasons.append("LIBRARY_TRUTH_UNMAPPED")

    retrieval_allowed = not library or library in INDEXABLE_LIBRARY_STATES

    if library in {"QUARANTINED", "REVIEW_REQUIRED", "REJECTED"}:
        operational = "UNKNOWN"
        reasons.append("LIBRARY_NOT_REVIEWED_FOR_OPERATIONAL_TRUTH")
    elif library == "CONFLICTING":
        operational = "UNKNOWN"
        reasons.append("LIBRARY_CONFLICT")
    elif library == "STALE" or fresh == "STALE":
        operational = "UNKNOWN"
        reasons.append("STALE_KNOWLEDGE")
    elif library == "VALIDATED" and provenance in {
        "UNREVIEWED", "QUARANTINED", "REJECTED", "CONFLICTING", "STALE",
    }:
        operational = "UNKNOWN"
        reasons.append("PROVENANCE_NOT_OPERATIONALLY_VALIDATED")
    else:
        operational = candidate

    if operational not in TRUTH_STATES:
        operational = "UNKNOWN"
        reasons.append("OPERATIONAL_TRUTH_FAIL_CLOSED")

    usable_as_confirmed_fact = operational == "CONFIRMED" and not reasons
    return {
        "schema": SCHEMA,
        "evidence_truth_state": evidence,
        "library_state": library or "NOT_APPLICABLE",
        "library_truth_state": library_truth or "UNKNOWN",
        "freshness": fresh,
        "provenance_review_status": provenance or "UNKNOWN",
        "operational_truth_state": operational,
        "retrieval_allowed": retrieval_allowed,
        "usable_as_confirmed_fact": usable_as_confirmed_fact,
        "memory_quarantine_eligible": library in INDEXABLE_LIBRARY_STATES,
        "requires_review": not usable_as_confirmed_fact,
        "reason_codes": list(dict.fromkeys(reasons)),
        "automatic_memory_promotion": False,
        "official_decision_authority": False,
        "external_action_executed": False,
    }


__all__ = ["SCHEMA", "INDEXABLE_LIBRARY_STATES", "map_truth_knowledge_state"]
