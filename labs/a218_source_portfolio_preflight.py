"""A218 LAB: candidate source catalog; no vendor chosen, no P0 approved.

Research options for root custody, provider effect receipts and independent
witnessing. This DOES NOT authenticate any institution, provision a key,
connect to a provider, approve a budget, or certify external evidence.
All outputs retain may_provision=False, may_connect=False, may_confirm=False.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_aion_external_evidence_intake import decode_candidate_json


SCHEMA = "ATLASQUANT_AION_EXTERNAL_SOURCE_PORTFOLIO_RESEARCH_V0"
_OPTIONS = {
    "OWNER_OFFLINE_ROOT": "ROOT",
    "SEPARATE_DOMAIN_HSM": "ROOT",
    "PROVIDER_SIGNED_FINAL_RECEIPT": "PROVIDER",
    "PROVIDER_AUTHORITATIVE_QUERY": "PROVIDER",
    "INDEPENDENT_APPEND_ONLY_LOG": "WITNESS",
    "OFFHOST_CHECKPOINT_FLOOR": "WITNESS",
}
_PORTFOLIO_KEYS = frozenset({
    "schema", "owner_id", "tenant_id", "workspace_id", "decision_state",
    "owner_approval_state", "selected_option_ids",
    "p0_external_homologated", "candidates",
})
_OPTION_KEYS = frozenset({
    "role", "option", "source_id", "control_domain",
    "evidence_state", "contact_state", "estimated_cost_state", "status",
})
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


@dataclass(frozen=True)
class SourcePortfolioPreflight:
    catalog_complete: bool
    independent_root_verified: bool
    owner_decision_approved: bool
    external_p0_homologated: int
    may_provision: bool
    may_connect: bool
    may_confirm: bool
    code: str
    catalog_digest: str


def _deny(code: str) -> SourcePortfolioPreflight:
    return SourcePortfolioPreflight(
        catalog_complete=False,
        independent_root_verified=False,
        owner_decision_approved=False,
        external_p0_homologated=0,
        may_provision=False,
        may_connect=False,
        may_confirm=False,
        code=code,
        catalog_digest="",
    )


def _token(value: Any) -> bool:
    return isinstance(value, str) and _TOKEN.fullmatch(value) is not None


def preflight_source_portfolio(
    proposal: Any,
    *,
    expected_owner_id: Any,
    expected_tenant_id: Any,
    expected_workspace_id: Any,
) -> SourcePortfolioPreflight:
    """Only validate a vendor-neutral OPTIONS list. Never choose or enable."""
    if isinstance(proposal, str):
        try:
            proposal = decode_candidate_json(proposal)
        except ValueError:
            return _deny("AMBIGUOUS_OR_OVERSIZED_PORTFOLIO_JSON")
    if not isinstance(proposal, Mapping) or set(proposal) != _PORTFOLIO_KEYS:
        return _deny("PORTFOLIO_ENVELOPE_NOT_EXACT")
    if proposal.get("schema") != SCHEMA:
        return _deny("PORTFOLIO_SCHEMA_UNSUPPORTED")

    expected_scope = {
        "owner_id": expected_owner_id,
        "tenant_id": expected_tenant_id,
        "workspace_id": expected_workspace_id,
    }
    if any(not _token(v) for v in expected_scope.values()):
        return _deny("INVALID_EXPECTED_OWNER_SCOPE")
    if any(
        not isinstance(proposal.get(k), str) or proposal[k] != v
        for k, v in expected_scope.items()
    ):
        return _deny("OWNER_SCOPE_MISMATCH")

    if proposal.get("decision_state") != "AWAITING_OWNER_SOURCE_CHOICE":
        return _deny("PREMATURE_SOURCE_DECISION")
    if proposal.get("owner_approval_state") != "NOT_REQUESTED":
        return _deny("OWNER_APPROVAL_NOT_ESTABLISHED")
    if type(proposal.get("selected_option_ids")) is not list or proposal["selected_option_ids"]:
        return _deny("SOURCE_SELECTION_PREMATURE")
    if type(proposal.get("p0_external_homologated")) is not int or proposal["p0_external_homologated"] != 0:
        return _deny("FALSE_EXTERNAL_P0_HOMOLOGATION")

    options = proposal.get("candidates")
    if not isinstance(options, list) or len(options) != len(_OPTIONS):
        return _deny("SOURCE_OPTIONS_INCOMPLETE")
    seen_ids = set()
    seen_options = set()
    for c in options:
        if not isinstance(c, Mapping) or set(c) != _OPTION_KEYS:
            return _deny("SOURCE_CANDIDATE_ENVELOPE_NOT_EXACT")
        name = c.get("option")
        if not isinstance(name, str) or name not in _OPTIONS:
            return _deny("UNSUPPORTED_RESEARCH_OPTION")
        if c.get("role") != _OPTIONS[name]:
            return _deny("SOURCE_ROLE_OPTION_MISMATCH")
        if not _token(c.get("source_id")):
            return _deny("INVALID_SOURCE_CANDIDATE_ID")
        if c["source_id"] in seen_ids or name in seen_options:
            return _deny("DUPLICATED_SOURCE_OPTION_OR_ID")
        seen_ids.add(c["source_id"])
        seen_options.add(name)
        if c.get("control_domain") != "UNASSIGNED":
            return _deny("PREMATURE_CONTROL_DOMAIN_SELECTION")
        if c.get("evidence_state") != "NOT_OBTAINED":
            return _deny("EXTERNAL_EVIDENCE_UNVERIFIED")
        if c.get("contact_state") != "NOT_CONTACTED":
            return _deny("EXTERNAL_COORDINATION_NOT_AUTHORIZED")
        if c.get("estimated_cost_state") != "NOT_QUOTED":
            return _deny("FINANCIAL_COMMITMENT_NOT_AUTHORIZED")
        if c.get("status") != "RESEARCH_ONLY":
            return _deny("SOURCE_CANDIDATE_PREMATURELY_TRUSTED")
    if seen_options != set(_OPTIONS):
        return _deny("SOURCE_OPTION_COVERAGE_MISMATCH")

    encoded = json.dumps(
        dict(proposal), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    # Catalog hash is a commitment to a draft, not approval or evidence.
    return SourcePortfolioPreflight(
        catalog_complete=True,
        independent_root_verified=False,
        owner_decision_approved=False,
        external_p0_homologated=0,
        may_provision=False,
        may_connect=False,
        may_confirm=False,
        code="CANDIDATE_OPTIONS_COMPLETE_OWNER_AND_EXTERNAL_PROOF_PENDING",
        catalog_digest=sha256(encoded).hexdigest(),
    )


__all__ = ["SCHEMA", "SourcePortfolioPreflight", "preflight_source_portfolio"]
