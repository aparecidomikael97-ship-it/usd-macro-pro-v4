"""AION P0 H0 LAB: proposed authority/control graph, NEVER enrolled proof.

A design-level, offline threat-model guard for the *CLAIMED* separation of
H0 roles. Even a graph with zero detected conflicts is caller-supplied and
cannot prove the absence of undisclosed shared cloud/org/admin/MFA roots.
The graph is not a credential registry or authorization gate. It makes NO
network requests, persists NOTHING, and grants ZERO external permission.
"""
from __future__ import annotations

import re
from typing import Any

SCHEMA = "AION_P0_H0_AUTHORITY_GRAPH_LAB_V1"
REQUIRED_ROLES = frozenset((
    "executor", "reservation_signer", "readback_witness",
    "nonce_custodian", "head_issuer", "independent_verifier",
))
TOP_FIELDS = frozenset(("schema", "roles", "delegations"))
ROLE_FIELDS = frozenset((
    "security_domain_id", "cloud_account_id", "organization_id",
    "signer_fingerprint_sha256", "admin_controllers",
    "recovery_controllers", "deployment_controllers", "billing_controllers",
))
EDGE_FIELDS = frozenset(("controller", "controlled"))
NODE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@/-]{7,127}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
AUTHORITY_FALSE = {
    "issuer_independently_enrolled": False,
    "administrative_independence_authenticated": False,
    "credential_revocation_authenticated": False,
    "external_nonce_custody_authenticated": False,
    "remote_readback_authenticated": False,
    "latest_head_authenticated": False,
    "physical_rollback_ruled_out": False,
    "producer_effect_or_no_effect_authenticated": False,
    "human_owner_authenticated": False,
    "first_external_effect_allowed": False,
    "worker_arming_allowed": False,
    "automatic_retry_allowed": False,
    "external_action_executed": False,
}
PERMANENT_BLOCKERS = (
    "CALLER_SUPPLIED_TOPOLOGY_NOT_AUTHENTICATED",
    "OUT_OF_BAND_ISSUER_ENROLLMENT_NOT_PROVEN",
    "EXTERNAL_NONCE_AND_FRESH_HEAD_NOT_PROVEN",
    "SIGNED_REVOCATION_AND_RECOVERY_NOT_PROVEN",
    "PRODUCER_CAUSAL_RECEIPT_NOT_PROVEN",
    "HUMAN_OWNER_CONSENT_NOT_PROVEN",
    "PHYSICAL_RESTORE_NOT_TESTED",
    "CANONICAL_QUALITY_NOT_GREEN",
)
MAX_DELEGATIONS = 128
MAX_NODES = 512


def _id(v: Any) -> bool:
    return type(v) is str and NODE.fullmatch(v) is not None


def _hex(v: Any) -> bool:
    return type(v) is str and HEX.fullmatch(v) is not None


def _result(findings: set[str], consistent: bool) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "HARD_NO_GO",
        "allowed": False,
        "simulation_only": True,
        "claimed_topology_consistent_lab": consistent and not findings,
        "findings": tuple(sorted(findings)),
        "blockers": PERMANENT_BLOCKERS,
        **AUTHORITY_FALSE,
    }


def _plain_keys(obj: Any, fields: frozenset[str]) -> bool:
    """Do not call hostile field equality or serialization on non-str keys."""
    return (type(obj) is dict and all(type(k) is str for k in obj)
            and frozenset(obj) == fields)


def _controllers(value: Any) -> tuple[str, ...] | None:
    if (type(value) is not list or not 1 <= len(value) <= 16
            or any(not _id(item) for item in value)
            or len(value) != len(set(value))):
        return None
    return tuple(value)


def _has_cycle(parents: dict[str, set[str]]) -> bool:
    seen: set[str] = set()
    active: set[str] = set()
    def visit(node: str) -> bool:
        if node in active:
            return True
        if node in seen:
            return False
        active.add(node)
        for parent in parents.get(node, ()):
            if visit(parent):
                return True
        active.remove(node)
        seen.add(node)
        return False
    return any(visit(node) for node in parents)


def _ancestors(node: str, parents: dict[str, set[str]]) -> set[str]:
    out: set[str] = set()
    remaining = [node]
    while remaining:
        cur = remaining.pop()
        if cur not in out:
            out.add(cur)
            remaining.extend(parents.get(cur, ()))
    return out


def inspect_authority_graph_lab(proposal: Any) -> dict[str, Any]:
    """Conservative structure/graph examination, NOT an independence proof.

    Every input is an unauthenticated assertion, even if roles, key digests,
    tenant accounts, and their entire claimed control ancestry look distinct.
    This function MUST NEVER be wired to AION Worker or external outbox.
    """
    findings: set[str] = set()
    if not _plain_keys(proposal, TOP_FIELDS):
        return _result({"PROPOSAL_SCHEMA_OR_SHAPE_INVALID"}, False)
    if type(proposal["schema"]) is not str or proposal["schema"] != SCHEMA:
        return _result({"PROPOSAL_SCHEMA_OR_SHAPE_INVALID"}, False)
    roles = proposal["roles"]
    if (type(roles) is not dict
            or any(type(k) is not str for k in roles)
            or frozenset(roles) != REQUIRED_ROLES):
        return _result({"ROLE_SET_INVALID"}, False)
    assigned: dict[str, dict[str, Any]] = {}
    for role, attrs in roles.items():
        if not _plain_keys(attrs, ROLE_FIELDS):
            return _result({"ROLE_SHAPE_INVALID:" + role}, False)
        for field in ("security_domain_id", "cloud_account_id", "organization_id"):
            if not _id(attrs[field]):
                findings.add("ROLE_IDENTIFIER_INVALID:" + role + ":" + field)
        if not _hex(attrs["signer_fingerprint_sha256"]):
            findings.add("SIGNER_FINGERPRINT_INVALID:" + role)
        for field in ("admin_controllers", "recovery_controllers", "deployment_controllers", "billing_controllers"):
            if _controllers(attrs[field]) is None:
                findings.add("ROLE_CONTROLLERS_INVALID:" + role + ":" + field)
        assigned[role] = attrs
    if findings:
        return _result(findings, False)

    # A distinct Ed25519 public key or fingerprint is NOT an independent
    # operator: organizational control chains must be checked separately.
    for field in ("security_domain_id", "cloud_account_id", "organization_id",
                  "signer_fingerprint_sha256"):
        values = [assigned[r][field] for r in sorted(REQUIRED_ROLES)]
        if len(set(values)) != len(values):
            findings.add("SHARED_CLAIMED_ROOT_OR_KEY:" + field)

    raw_edges = proposal["delegations"]
    if type(raw_edges) is not list or len(raw_edges) > MAX_DELEGATIONS:
        return _result(findings | {"DELEGATIONS_SHAPE_OR_LIMIT_INVALID"}, False)
    parents: dict[str, set[str]] = {}
    for edge in raw_edges:
        if not _plain_keys(edge, EDGE_FIELDS):
            return _result(findings | {"DELEGATION_EDGE_INVALID"}, False)
        source, target = edge["controller"], edge["controlled"]
        if not _id(source) or not _id(target) or source == target:
            return _result(findings | {"DELEGATION_EDGE_INVALID"}, False)
        parents.setdefault(target, set()).add(source)
        parents.setdefault(source, set())
    if len(parents) > MAX_NODES:
        return _result(findings | {"DELEGATION_NODE_LIMIT_EXCEEDED"}, False)
    if _has_cycle(parents):
        return _result(findings | {"CONTROL_DELEGATION_CYCLE"}, False)

    for role_a in sorted(REQUIRED_ROLES):
        a = assigned[role_a]
        controllers_a = {
            x for field in ("admin_controllers", "recovery_controllers",
                            "deployment_controllers", "billing_controllers") for x in a[field]
        }
        # Include every ancestor: a recovery/admin controller's own root can
        # dominate two otherwise disjoint direct controlling principals.
        closure_a: set[str] = set()
        for controller in controllers_a:
            closure_a.update(_ancestors(controller, parents))
        for role_b in sorted(REQUIRED_ROLES):
            if role_b <= role_a:
                continue
            b = assigned[role_b]
            controllers_b = {
                x for field in ("admin_controllers", "recovery_controllers",
                                "deployment_controllers", "billing_controllers") for x in b[field]
            }
            closure_b: set[str] = set()
            for controller in controllers_b:
                closure_b.update(_ancestors(controller, parents))
            if closure_a & closure_b:
                findings.add("SHARED_DIRECT_OR_TRANSITIVE_CONTROL:" + role_a + ":" + role_b)

    # Not a success state. There is no trusted source proving that the caller
    # reported *all* transitive administrators, MFA/recovery roots, or org ties.
    return _result(findings, True)
