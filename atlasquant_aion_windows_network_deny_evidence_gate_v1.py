"""AION Windows network-deny physical evidence *candidate* contract V1.

Planning and structurally checking synthetic evidence; never configures
AppContainer, WFP, Windows Firewall, TCP/IP, DNS, or a real child process.
All caller observations remain UNTRUSTED, even if every surface appears denied.
Independent authenticated collector/verification per #1049 is required.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

SCHEMA = "ATLASQUANT_AION_WINDOWS_NETWORK_DENY_EVIDENCE_GATE_V1"
PLAN_STATE = "READY_FOR_CONTROLLED_NETWORK_DENY_PROBE_DESIGN_REVIEW"
UNTRUSTED_CANDIDATE = "DENY_EVIDENCE_CANDIDATE_UNTRUSTED"
BLOCKED = "BLOCKED"
METHODS = ("APPCONTAINER_NO_NETWORK_CAPABILITIES", "WFP_CHILD_SCOPED_DYNAMIC_FILTERS")
SURFACES = (
    "TCP_LOOPBACK_IPV4",
    "TCP_LOOPBACK_IPV6",
    "UDP_LOOPBACK_IPV4",
    "UDP_LOOPBACK_IPV6",
    "TCP_OUTBOUND_IPV4",
    "TCP_OUTBOUND_IPV6",
    "UDP_OUTBOUND_IPV4",
    "UDP_OUTBOUND_IPV6",
    "DNS_UDP_IPV4",
    "DNS_UDP_IPV6",
    "DNS_TCP_IPV4",
    "DNS_TCP_IPV6",
    "HTTP_CONNECT_PROXY",
    "SOCKS_PROXY",
    "REMOTE_SMB_NAMED_PIPE",
    "INHERITED_SOCKET_HANDLE",
)
RECORD_FIELDS = frozenset({"surface", "normal_control", "isolated_observation"})
NORMAL_RESULTS = frozenset({"REACHABLE", "NOT_RUN", "FAILED"})
ISOLATED_RESULTS = frozenset({"BLOCKED_BY_OS", "ALLOWED", "NOT_RUN", "ERROR"})
EXPLICIT_UNTRUSTED_CLAIM_KEYS = frozenset({
    "physical_proof_verified", "network_deny_verified", "independently_verified",
    "sandbox_verified", "build_authorized", "package_install_authorized",
})


def network_denial_plan() -> dict[str, Any]:
    """No actual sockets or host mutations; future probe controls only."""
    return {
        "schema": SCHEMA,
        "state": PLAN_STATE,
        "required_parent_contract": "WINDOWS_NETWORK_DENY_PHYSICAL_PROOF_REQUIRED",
        "allowed_candidate_methods": list(METHODS),
        "surfaces": [
            {
                "surface": surface,
                "positive_control": "REACHABLE_IN_INDEPENDENT_NORMAL_CONTEXT",
                "negative_control": "BLOCKED_BY_OS_IN_BOUND_ISOLATED_CHILD",
                "requires_actual_os_observation": True,
            }
            for surface in SURFACES
        ],
        "required_real_boundaries": [
            "CHILD_IDENTITY_BOUND_TO_TRUSTED_COLLECTOR",
            "COLLECTOR_BINARY_AND_PLAN_DIGEST_PINNED",
            "CANDIDATE_EVIDENCE_INDEPENDENTLY_VERIFIED",
            "FRESHNESS_NOT_GREATER_THAN_60_SECONDS",
            "NO_CAPABILITIES_OR_LOOPBACK_EXEMPTION_BYPASS",
            "NO_INHERITED_NETWORK_HANDLES_OR_UNREVIEWED_BROKERS",
            "EXTERNAL_PROBES_SEPARATELY_AUTHORIZED_AND_CONTROLLED",
            "FAIL_CLOSED_ON_ANY_ALLOWED_OR_UNMEASURED_SURFACE",
        ],
        "profile_created": False,
        "wfp_filter_added": False,
        "network_probe_executed": False,
        "physical_proof_verified": False,
        "network_deny_verified": False,
        "build_authorized": False,
        "package_install_authorized": False,
        "deploy_authorized": False,
    }


def _blocked(reason: str, *, checked: int = 0, failed: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": BLOCKED,
        "reason": reason, "surfaces_checked": checked,
        "failing_surfaces": list(failed),
        "structurally_complete": False,
        "physical_proof_verified": False,
        "network_deny_verified": False,
        "build_authorized": False,
        "package_install_authorized": False,
        "deploy_authorized": False,
    }


def assess_untrusted_network_candidate(
    observations: Sequence[Mapping[str, Any]] | None,
    *,
    method: str,
    claims: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Examine a bounded candidate matrix; never accept it as physical proof.

    Even a complete set of self-asserted BLOCKED_BY_OS observations is not a
    verified Windows firewall decision. The real collector and verifier are
    explicitly outside this V1 implementation.
    """
    if type(method) is not str or method not in METHODS:
        return _blocked("UNAPPROVED_NETWORK_ISOLATION_METHOD")
    if claims is not None:
        if type(claims) is not dict:
            return _blocked("CALLER_CLAIMS_INVALID")
        if any(key in claims for key in EXPLICIT_UNTRUSTED_CLAIM_KEYS):
            return _blocked("SELF_ASSERTED_VERIFICATION_FORBIDDEN")
        if claims:
            return _blocked("UNRECOGNIZED_CALLER_CLAIMS")
    if type(observations) not in (list, tuple) or len(observations) != len(SURFACES):
        return _blocked("EXACT_SURFACE_COVERAGE_REQUIRED")
    parsed: dict[str, Mapping[str, Any]] = {}
    for obj in observations:
        if type(obj) is not dict or set(obj) != RECORD_FIELDS:
            return _blocked("OBSERVATION_RECORD_SHAPE_INVALID")
        surface = obj.get("surface")
        control = obj.get("normal_control")
        isolated = obj.get("isolated_observation")
        if type(surface) is not str or surface not in SURFACES or surface in parsed:
            return _blocked("DUPLICATE_OR_UNKNOWN_SURFACE")
        if type(control) is not str or control not in NORMAL_RESULTS:
            return _blocked("UNKNOWN_POSITIVE_CONTROL")
        if type(isolated) is not str or isolated not in ISOLATED_RESULTS:
            return _blocked("UNKNOWN_ISOLATED_OBSERVATION")
        parsed[surface] = obj
    if set(parsed) != set(SURFACES):
        return _blocked("EXACT_SURFACE_COVERAGE_REQUIRED")
    not_denied = tuple(
        surface for surface in SURFACES
        if parsed[surface]["isolated_observation"] != "BLOCKED_BY_OS"
    )
    if not_denied:
        return _blocked(
            "ANY_ALLOWED_ERROR_OR_UNMEASURED_TRAFFIC_FAILS_CLOSED",
            checked=len(parsed), failed=not_denied,
        )
    unverified_controls = tuple(
        surface for surface in SURFACES
        if parsed[surface]["normal_control"] != "REACHABLE"
    )
    if unverified_controls:
        return _blocked(
            "INDEPENDENT_REACHABILITY_CONTROLS_REQUIRED",
            checked=len(parsed), failed=unverified_controls,
        )
    return {
        "schema": SCHEMA,
        "state": UNTRUSTED_CANDIDATE,
        "reason": "SELF_REPORTED_OS_RESULTS_REQUIRE_INDEPENDENT_ATTESTATION",
        "method": method,
        "surfaces_checked": len(SURFACES),
        "failing_surfaces": [],
        "structurally_complete": True,
        "physical_proof_verified": False,
        "network_deny_verified": False,
        "build_authorized": False,
        "package_install_authorized": False,
        "deploy_authorized": False,
    }


__all__ = [
    "SCHEMA", "METHODS", "SURFACES", "PLAN_STATE",
    "UNTRUSTED_CANDIDATE", "BLOCKED", "network_denial_plan",
    "assess_untrusted_network_candidate",
]
