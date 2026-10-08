"""AION network localhost observer: separate witness from child self-report.

Data-only verifier: NEVER infers a certified Windows AppContainer network
deny from a child's timeout, OS error, or unsourced caller boolean.

Only the companion CI runner creates a 127.0.0.1 listener / normal child.
This verifier is deliberately pure (no Windows API, network, or process launch).
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "AION_LOCAL_LOOPBACK_INDEPENDENT_OBSERVER_RECEIPT_V1"
RESULT_SCHEMA = "AION_LOCAL_LOOPBACK_INDEPENDENT_OBSERVER_CLASSIFICATION_V1"
ENDPOINT = "127.0.0.1"
PROTOCOL = "TCP_IPV4_LOOPBACK_ONLY"
TOKEN_MODE = "NORMAL_CI_CHILD_NOT_APPCONTAINER"
RECEIPT_FIELDS = frozenset({
    "schema", "probe_run_id", "endpoint", "protocol", "port",
    "normal_control_reachable", "server_received_child_nonce",
    "child_started", "child_completed", "child_exit_code",
    "child_reported_status", "child_reported_error_code",
    "child_nonce_matches", "child_token_mode", "elapsed_ms",
})
STATUSES = frozenset({"CONNECTED", "OS_ERROR", "TIMEOUT", "START_ERROR"})
POTENTIAL_OS_DENY_ERROR_CODES = frozenset({10013, 13})
MAX_ELAPSED_MS = 15000


def _result(state: str, reason: str) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "state": state,
        "reason": reason,
        "independent_observer_review": True,
        "candidate_os_access_denial": False,
        "physical_network_denial_verified": False,
        "all_network_surfaces_verified": False,
        "appcontainer_token_verified": False,
        "installer_authorized": False,
        "build_authorized": False,
        "deployment_authorized": False,
    }


def classify_localhost_receipt(receipt: Mapping[str, Any] | None) -> dict[str, Any]:
    """Classify *untrusted* stdout/server observations, not certify the host.

    The local server witness has higher evidentiary priority than a child's
    assertion, but this function cannot verify the receipt's origin or
    AppContainer token. A future trusted physical collector must supply a
    separately verified attestation before a production decision.
    """
    if type(receipt) is not dict or set(receipt) != RECEIPT_FIELDS:
        return _result("INVALID", "EXACT_RECEIPT_FIELDS_REQUIRED")
    if receipt["schema"] != SCHEMA:
        return _result("INVALID", "SCHEMA_MISMATCH")
    token = receipt["probe_run_id"]
    if (
        type(token) is not str or len(token) != 32
        or any(ch not in "0123456789abcdef" for ch in token)
    ):
        return _result("INVALID", "RUN_NONCE_INVALID")
    if (
        receipt["endpoint"] != ENDPOINT
        or receipt["protocol"] != PROTOCOL
        or receipt["child_token_mode"] != TOKEN_MODE
    ):
        return _result("INVALID", "UNSUPPORTED_ENDPOINT_OR_EXECUTION_MODE")
    if type(receipt["port"]) is not int or not (1024 <= receipt["port"] <= 65535):
        return _result("INVALID", "LOCAL_EPHEMERAL_PORT_INVALID")
    if (
        type(receipt["elapsed_ms"]) is not int
        or not (0 <= receipt["elapsed_ms"] <= MAX_ELAPSED_MS)
    ):
        return _result("INVALID", "PROBE_TIME_WINDOW_INVALID")
    for key in (
        "normal_control_reachable", "server_received_child_nonce",
        "child_started", "child_completed", "child_nonce_matches",
    ):
        if type(receipt[key]) is not bool:
            return _result("INVALID", "OBSERVATION_BOOL_INVALID")
    if type(receipt["child_reported_status"]) is not str or receipt["child_reported_status"] not in STATUSES:
        return _result("INVALID", "CHILD_STATUS_INVALID")
    ec = receipt["child_exit_code"]
    ne = receipt["child_reported_error_code"]
    if ec is not None and (type(ec) is not int or ec < 0 or ec > 0xffffffff):
        return _result("INVALID", "CHILD_EXIT_CODE_INVALID")
    if ne is not None and (type(ne) is not int or ne < 0 or ne > 0xffffffff):
        return _result("INVALID", "CHILD_SOCKET_ERROR_INVALID")

    if not receipt["normal_control_reachable"]:
        return _result("INCONCLUSIVE", "NORMAL_POSITIVE_CONTROL_NOT_REACHABLE")
    if not receipt["child_started"] or not receipt["child_completed"]:
        return _result("INCONCLUSIVE", "CHILD_STARTUP_OR_TIMEOUT_NOT_NETWORK_DENIAL")
    if not receipt["child_nonce_matches"]:
        return _result("INVALID", "CHILD_CHALLENGE_RESPONSE_MISSING_OR_MISMATCHED")
    if receipt["child_exit_code"] != 0:
        return _result("INCONCLUSIVE", "CHILD_NONZERO_EXIT_NOT_NETWORK_DENIAL")
    if receipt["child_reported_status"] == "TIMEOUT":
        return _result("INCONCLUSIVE", "CHILD_TIMEOUT_NOT_NETWORK_DENIAL")
    if receipt["child_reported_status"] == "START_ERROR":
        return _result("INCONCLUSIVE", "CHILD_START_ERROR_NOT_NETWORK_DENIAL")

    server_hit = receipt["server_received_child_nonce"]
    child_hit = receipt["child_reported_status"] == "CONNECTED"
    if server_hit and not child_hit:
        return _result("CONTRADICTORY", "SERVER_RECEIVED_NONCE_DESPITE_CHILD_DENIAL_CLAIM")
    if child_hit and not server_hit:
        return _result("CONTRADICTORY", "CHILD_CONNECTED_WITHOUT_SERVER_NONCE_WITNESS")
    if server_hit and child_hit:
        return _result("NETWORK_ACCESS_OBSERVED", "LOCAL_TCP_CONNECTED_IN_NONISOLATED_CI_CHILD")

    if receipt["child_reported_status"] == "OS_ERROR":
        if ne in POTENTIAL_OS_DENY_ERROR_CODES:
            result = _result(
                "UNTRUSTED_DENIAL_CANDIDATE",
                "ACCESS_DENIED_ERROR_REPORTED_NOT_INDEPENDENTLY_ATTESTED",
            )
            result["candidate_os_access_denial"] = True
            return result
        return _result("INCONCLUSIVE", "NON_ACCESS_DENIED_NETWORK_ERROR")
    return _result("INVALID", "UNCLASSIFIABLE_RECEIPT")


__all__ = [
    "SCHEMA", "RESULT_SCHEMA", "ENDPOINT", "PROTOCOL", "TOKEN_MODE",
    "RECEIPT_FIELDS", "POTENTIAL_OS_DENY_ERROR_CODES",
    "classify_localhost_receipt",
]
