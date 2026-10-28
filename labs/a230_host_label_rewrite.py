"""A230 LAB: compare untrusted before/after labels under a simulated host rewrite.

No source, key, provider, independent witness or real authority is contacted.
The 'before' snapshot is supplied by the same untrusted caller and MUST NOT
be treated as authentic history. A vanished collision is only a synthetic signal.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_aion_external_evidence_intake import decode_candidate_json
from labs.a229_common_control_domain_claims import (
    CONTROL_LABEL_FIELDS, preflight_common_control_claims,
)

SCHEMA = "ATLASQUANT_AION_HOST_LABEL_REWRITE_UNTRUSTED_V0"
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_FIELDS = frozenset({
    "schema", "owner_id", "tenant_id", "workspace_id",
    "a229_reference_digest", "rewrite_state", "model_selection_state",
    "owner_signoff_state", "source_contact_state", "claimed_gate_state",
    "external_p0_homologated", "uncertain_resend_policy", "rewritten_sources",
})


@dataclass(frozen=True)
class HostLabelRewritePreflight:
    envelope_valid: bool
    untrusted_a229_bound: bool
    rewrite_graph_valid: bool
    before_visible_pair_count: int
    after_visible_pair_count: int
    disappeared_visible_pairs: int
    changed_label_cells: int
    changed_source_rows: int
    actual_control_domains_independent: bool
    actual_issuer_identities_verified: bool
    external_evidence_accepted: bool
    owner_signoff_valid: bool
    provider_final_effect_verified: bool
    external_p0_homologated: int
    may_accept_security_proof: bool
    may_select_model: bool
    may_contact_person: bool
    may_run_external_challenge: bool
    may_commit_budget: bool
    may_provision: bool
    may_generate_key: bool
    may_sign: bool
    may_connect: bool
    may_confirm: bool
    may_auto_resend: bool
    code: str
    local_claim_digest: str


def _out(code: str, *, valid: bool = False, before: int = 0,
         after: int = 0, disappeared: int = 0, cells: int = 0,
         rows: int = 0, digest: str = "") -> HostLabelRewritePreflight:
    return HostLabelRewritePreflight(
        envelope_valid=valid, untrusted_a229_bound=valid,
        rewrite_graph_valid=valid,
        before_visible_pair_count=before if valid else 0,
        after_visible_pair_count=after if valid else 0,
        disappeared_visible_pairs=disappeared if valid else 0,
        changed_label_cells=cells if valid else 0,
        changed_source_rows=rows if valid else 0,
        actual_control_domains_independent=False,
        actual_issuer_identities_verified=False,
        external_evidence_accepted=False,
        owner_signoff_valid=False, provider_final_effect_verified=False,
        external_p0_homologated=0,
        may_accept_security_proof=False, may_select_model=False,
        may_contact_person=False, may_run_external_challenge=False,
        may_commit_budget=False, may_provision=False,
        may_generate_key=False, may_sign=False, may_connect=False,
        may_confirm=False, may_auto_resend=False,
        code=code, local_claim_digest=digest if valid else "",
    )


def _visible_pairs(nodes: list[dict[str, Any]]) -> set[tuple[str, str]]:
    ordered = sorted(nodes, key=lambda row: row["requirement_id"])
    seen: set[tuple[str, str]] = set()
    for i, left in enumerate(ordered):
        lhs = {left[field] for field in CONTROL_LABEL_FIELDS}
        for right in ordered[i + 1:]:
            if lhs.intersection(right[field] for field in CONTROL_LABEL_FIELDS):
                seen.add((left["requirement_id"], right["requirement_id"]))
    return seen


def preflight_host_label_rewrite(
    candidate: Any, *, a229_graph: Any, a228_scenario: Any,
    a227_contract: Any, a226_claims: Any, a225_untrusted_claim: Any,
    a224_catalog: Any, a223_note: Any, a222_matrix: Any,
    expected_owner_id: Any, expected_tenant_id: Any,
    expected_workspace_id: Any,
) -> HostLabelRewritePreflight:
    """Detect only *visible* nominal collisions lost under synthetic rewriting."""
    if type(candidate) is str:
        try:
            candidate = decode_candidate_json(candidate)
        except (ValueError, TypeError):
            return _out("AMBIGUOUS_OR_OVERSIZED_REWRITE_JSON")
    if type(candidate) is not dict or set(candidate) != _FIELDS:
        return _out("REWRITE_ENVELOPE_NOT_EXACT")
    if candidate["schema"] != SCHEMA:
        return _out("REWRITE_SCHEMA_UNSUPPORTED")
    scope = {
        "owner_id": expected_owner_id,
        "tenant_id": expected_tenant_id,
        "workspace_id": expected_workspace_id,
    }
    if any(type(v) is not str or _TOKEN.fullmatch(v) is None for v in scope.values()):
        return _out("INVALID_EXPECTED_SCOPE")
    if any(type(candidate[k]) is not str or candidate[k] != v for k, v in scope.items()):
        return _out("REWRITE_SCOPE_MISMATCH")
    rules = {
        "rewrite_state": ("HOST_CONTROLLED_RENAME_STUDY_ONLY", "HOST_CANNOT_CLAIM_REAL_DEPENDENCY_AUDIT"),
        "model_selection_state": ("NO_MODEL_SELECTED", "HOST_CANNOT_SELECT_ROOT_MODEL"),
        "owner_signoff_state": ("NOT_REQUESTED", "HOST_CANNOT_CLAIM_OWNER_SIGNOFF"),
        "source_contact_state": ("NOT_CONTACTED", "HOST_CANNOT_CLAIM_EXTERNAL_CONTACT"),
        "claimed_gate_state": ("HARD_NO_GO", "HOST_CANNOT_OVERRIDE_HARD_NO_GO"),
        "uncertain_resend_policy": ("ZERO_AUTO_RESEND", "UNCERTAIN_ZERO_AUTO_RESEND_REQUIRED"),
    }
    for field, (expected, code) in rules.items():
        if type(candidate[field]) is not str or candidate[field] != expected:
            return _out(code)
    if type(candidate["external_p0_homologated"]) is not int or candidate["external_p0_homologated"] != 0:
        return _out("FALSE_EXTERNAL_P0_CLAIM")

    prior_args = dict(
        a228_scenario=a228_scenario, a227_contract=a227_contract,
        a226_claims=a226_claims, a225_untrusted_claim=a225_untrusted_claim,
        a224_catalog=a224_catalog, a223_note=a223_note, a222_matrix=a222_matrix,
        expected_owner_id=expected_owner_id, expected_tenant_id=expected_tenant_id,
        expected_workspace_id=expected_workspace_id,
    )
    baseline = preflight_common_control_claims(a229_graph, **prior_args)
    if not baseline.source_envelope_valid or baseline.external_evidence_accepted:
        return _out("A229_UNTRUSTED_BASELINE_REQUIRED")
    claimed_digest = candidate["a229_reference_digest"]
    if (type(claimed_digest) is not str or _HEX.fullmatch(claimed_digest) is None
            or claimed_digest != baseline.local_claim_digest):
        return _out("A229_LOCAL_REWRITE_BINDING_MISMATCH")

    new_sources = candidate["rewritten_sources"]
    if type(new_sources) is not list or len(new_sources) != 12:
        return _out("TWELVE_REWRITTEN_SOURCE_ROWS_REQUIRED")
    rewritten = dict(a229_graph)
    rewritten["sources"] = new_sources
    after = preflight_common_control_claims(rewritten, **prior_args)
    if not after.source_envelope_valid or after.external_evidence_accepted:
        return _out("REWRITTEN_A229_GRAPH_INVALID")

    old = {row["requirement_id"]: row for row in a229_graph["sources"]}
    new = {row["requirement_id"]: row for row in new_sources}
    for rid, source in old.items():
        if any(new[rid][key] != value for key, value in source.items()
               if key not in CONTROL_LABEL_FIELDS):
            return _out("REWRITE_CHANGED_SOURCE_IDENTITY_OR_PROVENANCE")

    cells = sum(
        old[rid][field] != new[rid][field]
        for rid in old for field in CONTROL_LABEL_FIELDS
    )
    rows = sum(
        any(old[rid][field] != new[rid][field] for field in CONTROL_LABEL_FIELDS)
        for rid in old
    )
    before_pairs = _visible_pairs(a229_graph["sources"])
    after_pairs = _visible_pairs(new_sources)
    gone = len(before_pairs - after_pairs)

    if gone and not after_pairs:
        code = "RENAME_REMOVED_ALL_VISIBLE_OVERLAPS_NOT_INDEPENDENCE"
    elif gone:
        code = "RENAME_REMOVED_SOME_VISIBLE_OVERLAPS_NOT_INDEPENDENCE"
    elif cells:
        code = "RENAMED_HOST_LABELS_STILL_NOT_INDEPENDENCE"
    else:
        code = "UNCHANGED_HOST_LABELS_STILL_NOT_INDEPENDENCE"

    canonical = dict(candidate)
    canonical["rewritten_sources"] = [dict(new[rid]) for rid in sorted(new)]
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return _out(code, valid=True, before=len(before_pairs),
                after=len(after_pairs), disappeared=gone, cells=cells,
                rows=rows, digest=sha256(payload).hexdigest())


__all__ = ["SCHEMA", "HostLabelRewritePreflight", "preflight_host_label_rewrite"]
