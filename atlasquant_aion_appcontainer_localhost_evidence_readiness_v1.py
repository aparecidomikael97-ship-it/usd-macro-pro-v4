"""AION controlled AppContainer LOCAL LOOPBACK evidence readiness — CI-only.

This module only checks synthetic/untrusted observation structures. It never
creates an AppContainer, launches a child, connects a socket or touches Windows.
Even a structurally complete candidate is not signed/attested evidence that
the operating system denied a real connection. The 16-surface network matrix,
12-category physical sandbox, and installer remain BLOCKED.

The previous owner-Windows PowerShell child TIMEOUT was INCONCLUSIVE, never a
network denial. We must observe an actual completed connect attempt and a
specific OS access-denied error without a positive parent listener hit.
"""
from __future__ import annotations

import re
from typing import Any

from atlasquant_aion_windows_appcontainer_token_readonly_v1 import (
    MATCH_CANDIDATE,
    SCHEMA as TOKEN_SCHEMA,
)

SCHEMA = "AION_CONTROLLED_APPCONTAINER_LOOPBACK_EVIDENCE_READINESS_V1"
CANDIDATE = "LOCAL_LOOPBACK_DENIAL_CANDIDATE_UNTRUSTED"
METHOD = "APPCONTAINER_NO_NETWORK_CAPABILITIES"
PROFILE = re.compile(r"AtlasQuantAIONProbe[0-9a-f]{12}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
TOP = frozenset({
    "schema", "method", "probe_nonce", "profile_name",
    "expected_child_image_sha256", "observed_child_image_sha256",
    "token_readback", "normal_controls", "isolated_child",
    "cleanup",
})
TOKEN = frozenset({
    "schema", "state", "reason", "capability_count",
    "physical_attestation_verified", "real_host_identity_verified",
    "process_handle_origin_verified", "network_deny_verified",
    "installer_authorized", "build_authorized", "deploy_authorized",
})
CONTROLS = frozenset({
    "before_nonce", "before_reachable", "after_nonce", "after_reachable",
    "before_witness_verified_independently",
    "after_witness_verified_independently",
})
CHILD = frozenset({
    "attempt_nonce", "started", "completed",
    "connect_attempt_completed", "exit_code",
    "connect_result", "winsock_error_code",
    "stdout_nonce_correlated", "parent_received_probe_nonce",
    "token_checked_on_held_process_handle",
    "elapsed_ms",
})
CLEANUP = frozenset({
    "job_kill_on_close", "child_terminated",
    "process_handles_closed", "profile_deleted",
    "firewall_unchanged", "wfp_unchanged", "no_external_endpoint",
})
FALSE_GATES = {
    "physical_probe_executed_by_this_module": False,
    "owner_pc_accessed_by_this_module": False,
    "independent_collector_attested": False,
    "held_process_handle_origin_attested": False,
    "child_binary_identity_cryptographically_verified": False,
    "trusted_positive_control_attested": False,
    "os_network_denial_physically_verified": False,
    "all_16_network_surfaces_verified": False,
    "physical_sandbox_12_of_12_verified": False,
    "owner_identity_verified": False,
    "owner_key_custody_verified": False,
    "tpm_key_attested": False,
    "network_deny_verified": False,
    "installer_authorized": False,
    "build_authorized": False,
    "deploy_authorized": False,
    "safe_to_resume": False,
    "windows_security_settings_modified": False,
}


def _decision(state: str, reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": state,
        "reason": reason,
        "reference_data_only": True,
        "single_ipv4_tcp_loopback_surface_only": True,
        "physical_evidence_candidate_trusted": False,
        "separate_scoped_owner_approval_required": True,
        **FALSE_GATES,
    }


def _exact(record: Any, keys: frozenset[str]) -> bool:
    return type(record) is dict and set(record) == keys


def _all_true(record: dict[str, Any], names: tuple[str, ...]) -> bool:
    return all(record[name] is True for name in names)


def review_untrusted_appcontainer_localhost_observation(
    observation: Any,
) -> dict[str, Any]:
    """Return at MOST an UNTRUSTED local-loopback evidence shape candidate.

    Inputs do NOT possess provenance or an independent attestation signature.
    This cannot complete #1049 / #1087, nor permit any physical test.
    """
    if not _exact(observation, TOP):
        return _decision("BLOCKED", "EXACT_OBSERVATION_SCHEMA_REQUIRED")
    if (observation["schema"] != SCHEMA
        or observation["method"] != METHOD
        or type(observation["probe_nonce"]) is not str
        or not HEX64.fullmatch(observation["probe_nonce"])
        or type(observation["profile_name"]) is not str
        or not PROFILE.fullmatch(observation["profile_name"])):
        return _decision("BLOCKED", "SCOPE_OR_NONCE_INVALID")
    for field in ("expected_child_image_sha256", "observed_child_image_sha256"):
        value = observation[field]
        if type(value) is not str or not SHA.fullmatch(value):
            return _decision("BLOCKED", "CHILD_IMAGE_DIGEST_INVALID")
    if observation["expected_child_image_sha256"] != observation["observed_child_image_sha256"]:
        return _decision("BLOCKED", "CHILD_IMAGE_MISMATCH_NOT_ATTESTATION")

    token = observation["token_readback"]
    if not _exact(token, TOKEN):
        return _decision("BLOCKED", "TOKEN_READBACK_SCHEMA_INVALID")
    if (token["schema"] != TOKEN_SCHEMA
        or token["state"] != MATCH_CANDIDATE
        or token["reason"] != "MATCHING_SID_AND_ZERO_CAPABILITIES_STILL_REQUIRE_INDEPENDENT_ATTESTATION"
        or type(token["capability_count"]) is not int
        or token["capability_count"] != 0
        or any(token[k] is not False for k in (
            "physical_attestation_verified", "real_host_identity_verified",
            "process_handle_origin_verified", "network_deny_verified",
            "installer_authorized", "build_authorized", "deploy_authorized",
        ))):
        return _decision("BLOCKED", "HELD_TOKEN_CANDIDATE_NOT_ACCEPTABLE")

    parent = observation["normal_controls"]
    if not _exact(parent, CONTROLS):
        return _decision("BLOCKED", "CONTROL_WITNESS_SCHEMA_INVALID")
    for key in ("before_nonce", "after_nonce"):
        if type(parent[key]) is not str or not HEX64.fullmatch(parent[key]):
            return _decision("BLOCKED", "CONTROL_NONCE_INVALID")
    if len({parent["before_nonce"], parent["after_nonce"], observation["probe_nonce"]}) != 3:
        return _decision("BLOCKED", "REUSED_CONTROL_NONCE")
    for key in (
        "before_reachable", "after_reachable",
        "before_witness_verified_independently",
        "after_witness_verified_independently",
    ):
        if type(parent[key]) is not bool:
            return _decision("BLOCKED", "CONTROL_BOOL_INVALID")
    if not _all_true(parent, (
        "before_reachable", "after_reachable",
        "before_witness_verified_independently",
        "after_witness_verified_independently",
    )):
        return _decision("BLOCKED", "POSITIVE_CONTROL_BEFORE_AFTER_REQUIRED")

    child = observation["isolated_child"]
    if not _exact(child, CHILD):
        return _decision("BLOCKED", "CHILD_REPORT_SCHEMA_INVALID")
    if type(child["attempt_nonce"]) is not str or child["attempt_nonce"] != observation["probe_nonce"]:
        return _decision("BLOCKED", "ISOLATED_NONCE_NOT_BOUND")
    for field in (
        "started", "completed", "connect_attempt_completed",
        "stdout_nonce_correlated", "parent_received_probe_nonce",
        "token_checked_on_held_process_handle",
    ):
        if type(child[field]) is not bool:
            return _decision("BLOCKED", "CHILD_STATUS_BOOL_INVALID")
    if not _all_true(child, (
        "started", "completed", "connect_attempt_completed",
        "stdout_nonce_correlated", "token_checked_on_held_process_handle",
    )):
        return _decision("BLOCKED", "STARTUP_TIMEOUT_OR_TOKEN_NOT_PROOF_OF_DENIAL")
    if child["parent_received_probe_nonce"] is True:
        return _decision("BLOCKED", "PARENT_SAW_CHILD_NETWORK_ACCESS")
    if type(child["exit_code"]) is not int or child["exit_code"] != 0:
        return _decision("BLOCKED", "CHILD_EXIT_NOT_VALIDATED")
    if type(child["elapsed_ms"]) is not int or not 0 <= child["elapsed_ms"] <= 15000:
        return _decision("BLOCKED", "PROBE_DURATION_INVALID")
    if (child["connect_result"] != "OS_ACCESS_DENIED"
        or type(child["winsock_error_code"]) is not int
        or child["winsock_error_code"] != 10013):
        return _decision("BLOCKED", "EXPLICIT_WINSOCK_ACCESS_DENIED_REQUIRED")

    cleanup = observation["cleanup"]
    if not _exact(cleanup, CLEANUP):
        return _decision("BLOCKED", "CLEANUP_SCHEMA_INVALID")
    for field in CLEANUP:
        if type(cleanup[field]) is not bool:
            return _decision("BLOCKED", "CLEANUP_BOOL_INVALID")
    if not _all_true(cleanup, tuple(CLEANUP)):
        return _decision("BLOCKED", "CLEANUP_OR_NO_HOST_CHANGE_NOT_CONFIRMED")
    return _decision(
        CANDIDATE, "SELF_REPORTED_LOCAL_LOOPBACK_DENIAL_REQUIRES_INDEPENDENT_PHYSICAL_ATTESTATION",
    )


__all__ = (
    "SCHEMA", "METHOD", "CANDIDATE", "FALSE_GATES",
    "review_untrusted_appcontainer_localhost_observation",
)
