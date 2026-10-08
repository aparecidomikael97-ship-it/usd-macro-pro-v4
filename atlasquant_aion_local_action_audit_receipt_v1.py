"""AION Local Action Audit Receipt V1.

Pure, non-executing receipt and audit-chain contract for the future signed
Windows local adapter.

The module records what a trusted adapter says happened after exactly one
dispatch-ready local action request. It never launches an application, retries
an action, opens the network, reads credentials, resolves executable paths or
persists receipts.

Outcome truth is derived from per-action evidence and can only be:
- CONFIRMED_SUCCESS;
- CONFIRMED_PARTIAL;
- CONFIRMED_TERMINAL_FAILURE;
- OUTCOME_UNKNOWN.

OUTCOME_UNKNOWN is never promoted to success or failure by silence. It forbids
automatic retry because a repeated local action can duplicate side effects.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from atlasquant_aion_secure_local_agent_v1 import (
    APP_REGISTRY,
    READINESS_SCHEMA,
    REQUEST_SCHEMA,
    SUPPORTED_ACTIONS,
    verify_local_action_request,
)


SCHEMA = "ATLASQUANT_AION_LOCAL_ACTION_AUDIT_RECEIPT_V1"
ADAPTER_OBSERVATION_SCHEMA = "ATLASQUANT_AION_SIGNED_LOCAL_ADAPTER_OBSERVATION_V1"
VERIFY_SCHEMA = "ATLASQUANT_AION_LOCAL_ACTION_AUDIT_RECEIPT_VERIFY_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_LOCAL_ACTION_AUDIT_POLICY_V1"

OUTCOME_STATES = (
    "CONFIRMED_SUCCESS",
    "CONFIRMED_PARTIAL",
    "CONFIRMED_TERMINAL_FAILURE",
    "OUTCOME_UNKNOWN",
)
ACTION_OUTCOME_STATES = (
    "CONFIRMED_SUCCESS",
    "CONFIRMED_TERMINAL_FAILURE",
    "OUTCOME_UNKNOWN",
)

AMBIGUITY_TRIGGERS = (
    "ADAPTER_CRASH_AFTER_DISPATCH",
    "IPC_LOST_AFTER_DISPATCH",
    "OS_ACK_MISSING",
    "POSTCONDITION_NOT_OBSERVED",
    "OBSERVATION_TIMEOUT",
    "MACHINE_SLEEP_OR_SHUTDOWN",
    "CONFLICTING_OS_OBSERVATIONS",
    "MEDIA_SESSION_STATE_AMBIGUOUS",
    "EVIDENCE_INCOMPLETE",
)

EVIDENCE_KINDS = (
    "OS_APP_ACTIVATION_CONFIRMATION",
    "OS_APP_LAUNCH_TERMINAL_ERROR",
    "MEDIA_SESSION_CONFIRMATION",
    "MEDIA_SESSION_TERMINAL_ERROR",
    "SIGNED_ADAPTER_OBSERVATION",
    "AMBIGUOUS_OS_OBSERVATION",
)

_FORBIDDEN_MATERIAL_KEYS = frozenset({
    "path",
    "executable",
    "binary",
    "command",
    "command_line",
    "argv",
    "args",
    "shell",
    "powershell",
    "cwd",
    "environment",
    "env",
    "stdout",
    "stderr",
    "raw_output",
    "process_output",
    "url",
    "uri",
    "password",
    "passwd",
    "secret",
    "token",
    "jwt",
    "cookie",
    "authorization",
    "api_key",
    "apikey",
    "private_key",
    "database_url",
    "dsn",
})
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _clean(value: Any, limit: int = 400) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256(value: Any) -> str:
    token = _clean(value, 90)
    return token if _SHA256_RE.fullmatch(token) else ""


def _identity(value: Any, limit: int = 160) -> str:
    if type(value) is not str:
        return ""
    if not value or len(value) > limit or "\x00" in value:
        return ""
    if " ".join(value.split()) != value:
        return ""
    return value


def _aware_datetime(value: Any, label: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception as exc:
            raise ValueError(f"{label} invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} timezone required")
    return parsed.astimezone(timezone.utc)


def _contains_forbidden_material(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = _clean(key, 120).casefold()
            if normalized in _FORBIDDEN_MATERIAL_KEYS:
                return True
            if _contains_forbidden_material(item):
                return True
    elif isinstance(value, (list, tuple, set, frozenset)):
        return any(_contains_forbidden_material(item) for item in value)
    return False


def _action_identity(action: Mapping[str, Any]) -> dict[str, str]:
    return {
        "action": _clean(action.get("action"), 80).upper(),
        "logical_app_id": _clean(action.get("logical_app_id"), 80).upper(),
    }


def _expected_actions(request: Mapping[str, Any]) -> list[dict[str, str]]:
    rows = request.get("actions")
    if not isinstance(rows, list):
        return []
    out: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            return []
        identity = _action_identity(row)
        if identity["action"] not in SUPPORTED_ACTIONS:
            return []
        if not identity["logical_app_id"]:
            return []
        parameters = row.get("parameters")
        if not isinstance(parameters, Mapping):
            return []
        out.append({
            **identity,
            "parameters_digest": _digest(dict(parameters)),
        })
    return out


def _action_set_digest(request: Mapping[str, Any]) -> str:
    return _digest(_expected_actions(request))


def _dispatch_digest(dispatch: Mapping[str, Any]) -> str:
    return _digest(dict(dispatch))


def local_action_bindings(
    request: Mapping[str, Any] | None,
) -> list[dict[str, str]]:
    """Safe per-action bindings, including a digest of bounded parameters."""
    return [dict(row) for row in _expected_actions(dict(request or {}))]


def local_action_set_digest(request: Mapping[str, Any] | None) -> str:
    """Canonical logical action-set digest for the future signed adapter."""
    return _action_set_digest(dict(request or {}))


def dispatch_readiness_digest(
    dispatch_readiness: Mapping[str, Any] | None,
) -> str:
    """Canonical digest of the non-executing dispatch-readiness decision."""
    return _dispatch_digest(dict(dispatch_readiness or {}))


def _validate_dispatch(
    request: Mapping[str, Any],
    dispatch_readiness: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    dispatch = dict(dispatch_readiness or {})
    blockers: list[str] = []
    if dispatch.get("schema") != READINESS_SCHEMA:
        blockers.append("DISPATCH_SCHEMA_MISMATCH")
    if dispatch.get("state") != "DISPATCH_READY":
        blockers.append("DISPATCH_NOT_READY")
    if dispatch.get("dispatch_ready") is not True:
        blockers.append("DISPATCH_READY_FLAG_REQUIRED")
    if _clean(dispatch.get("request_digest"), 90) != _clean(
        request.get("request_digest"), 90
    ):
        blockers.append("DISPATCH_REQUEST_DIGEST_MISMATCH")
    if dispatch.get("adapter_must_reverify_before_execution") is not True:
        blockers.append("ADAPTER_REVERIFICATION_REQUIREMENT_MISSING")
    for key in (
        "physical_binding_included",
        "executable_path_included",
        "launch_command_included",
        "execution_command_generated",
        "execution_command_executed",
        "subprocess_called",
        "network_called",
        "microphone_opened",
        "physical_execution_performed",
        "external_action_executed",
        "executes_action",
    ):
        if dispatch.get(key) is not False:
            blockers.append("DISPATCH_BOUNDARY_INVALID:" + key)
    if _contains_forbidden_material(dispatch):
        blockers.append("DISPATCH_CONTAINS_FORBIDDEN_MATERIAL")
    return dispatch, list(dict.fromkeys(blockers))


def _validate_action_result(
    expected: Mapping[str, Any],
    observed: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    expected_id = _action_identity(expected)
    observed_id = _action_identity(observed)

    if observed_id != expected_id:
        blockers.append("ACTION_IDENTITY_MISMATCH")

    expected_parameters_digest = _sha256(expected.get("parameters_digest"))
    observed_parameters_digest = _sha256(observed.get("parameters_digest"))
    if not expected_parameters_digest or observed_parameters_digest != expected_parameters_digest:
        blockers.append("ACTION_PARAMETERS_DIGEST_MISMATCH")

    state = _clean(observed.get("outcome_state"), 60).upper()
    if state not in ACTION_OUTCOME_STATES:
        blockers.append("ACTION_OUTCOME_INVALID")

    evidence_digest = _sha256(observed.get("evidence_digest"))
    if not evidence_digest:
        blockers.append("ACTION_EVIDENCE_DIGEST_REQUIRED")

    evidence_kind = _clean(observed.get("evidence_kind"), 100).upper()
    if evidence_kind not in EVIDENCE_KINDS:
        blockers.append("ACTION_EVIDENCE_KIND_INVALID")

    postcondition = observed.get("postcondition_verified") is True
    terminal_failure = observed.get("terminal_failure_verified") is True
    ambiguity = _clean(observed.get("ambiguity_trigger"), 120).upper()

    if state == "CONFIRMED_SUCCESS":
        if postcondition is not True:
            blockers.append("SUCCESS_POSTCONDITION_REQUIRED")
        if terminal_failure:
            blockers.append("SUCCESS_CANNOT_HAVE_TERMINAL_FAILURE")
        if ambiguity:
            blockers.append("SUCCESS_CANNOT_HAVE_AMBIGUITY")
    elif state == "CONFIRMED_TERMINAL_FAILURE":
        if terminal_failure is not True:
            blockers.append("TERMINAL_FAILURE_EVIDENCE_REQUIRED")
        if postcondition:
            blockers.append("TERMINAL_FAILURE_CANNOT_HAVE_SUCCESS_POSTCONDITION")
        if ambiguity:
            blockers.append("TERMINAL_FAILURE_CANNOT_HAVE_AMBIGUITY")
    elif state == "OUTCOME_UNKNOWN":
        if postcondition or terminal_failure:
            blockers.append("UNKNOWN_CANNOT_HAVE_TERMINAL_ASSERTION")
        if ambiguity not in AMBIGUITY_TRIGGERS:
            blockers.append("UNKNOWN_REQUIRES_VALID_AMBIGUITY_TRIGGER")

    if _contains_forbidden_material(observed):
        blockers.append("ACTION_RESULT_CONTAINS_FORBIDDEN_MATERIAL")

    projection = {
        **expected_id,
        "parameters_digest": expected_parameters_digest,
        "outcome_state": state,
        "evidence_kind": evidence_kind,
        "evidence_digest": evidence_digest,
        "postcondition_verified": postcondition,
        "terminal_failure_verified": terminal_failure,
        "ambiguity_trigger": ambiguity,
    }
    return projection, list(dict.fromkeys(blockers))


def _derive_outcome(action_results: Sequence[Mapping[str, Any]]) -> str:
    states = [_clean(row.get("outcome_state"), 60).upper() for row in action_results]
    if not states or any(state == "OUTCOME_UNKNOWN" for state in states):
        return "OUTCOME_UNKNOWN"
    if all(state == "CONFIRMED_SUCCESS" for state in states):
        return "CONFIRMED_SUCCESS"
    if all(state == "CONFIRMED_TERMINAL_FAILURE" for state in states):
        return "CONFIRMED_TERMINAL_FAILURE"
    return "CONFIRMED_PARTIAL"


def _receipt_material(receipt: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(receipt)
    raw.pop("receipt_digest", None)
    raw.pop("receipt_id", None)
    return raw


def build_local_action_audit_receipt(
    request: Mapping[str, Any] | None,
    dispatch_readiness: Mapping[str, Any] | None,
    adapter_observation: Mapping[str, Any] | None,
    *,
    observed_at: Any,
) -> dict[str, Any]:
    """Build an immutable evidence receipt without performing the local action."""
    req = dict(request or {})
    observation = dict(adapter_observation or {})
    blockers: list[str] = []

    if req.get("schema") != REQUEST_SCHEMA:
        blockers.append("REQUEST_SCHEMA_MISMATCH")
    request_digest = _sha256(req.get("request_digest"))
    if not request_digest:
        blockers.append("REQUEST_DIGEST_INVALID")

    dispatch, dispatch_blockers = _validate_dispatch(req, dispatch_readiness)
    blockers.extend(dispatch_blockers)
    dispatch_digest = _dispatch_digest(dispatch)

    if observation.get("schema") != ADAPTER_OBSERVATION_SCHEMA:
        blockers.append("ADAPTER_OBSERVATION_SCHEMA_MISMATCH")
    if observation.get("verified") is not True:
        blockers.append("ADAPTER_OBSERVATION_NOT_VERIFIED")
    if observation.get("source") != "SIGNED_LOCAL_ADAPTER":
        blockers.append("ADAPTER_SOURCE_INVALID")
    if observation.get("adapter_signature_verified") is not True:
        blockers.append("ADAPTER_SIGNATURE_NOT_VERIFIED")

    adapter_instance_id = _identity(observation.get("adapter_instance_id"), 160)
    attempt_id = _identity(observation.get("attempt_id"), 160)
    adapter_binary_digest = _sha256(observation.get("adapter_binary_digest"))
    evidence_bundle_digest = _sha256(observation.get("evidence_bundle_digest"))
    if not adapter_instance_id:
        blockers.append("ADAPTER_INSTANCE_ID_REQUIRED")
    if not attempt_id:
        blockers.append("ATTEMPT_ID_REQUIRED")
    if not adapter_binary_digest:
        blockers.append("ADAPTER_BINARY_DIGEST_REQUIRED")
    if not evidence_bundle_digest:
        blockers.append("EVIDENCE_BUNDLE_DIGEST_REQUIRED")

    if _clean(observation.get("request_digest"), 90) != request_digest:
        blockers.append("OBSERVATION_REQUEST_DIGEST_MISMATCH")
    if _clean(observation.get("dispatch_readiness_digest"), 90) != dispatch_digest:
        blockers.append("OBSERVATION_DISPATCH_DIGEST_MISMATCH")

    expected_actions = _expected_actions(req)
    action_set_digest = _action_set_digest(req)
    if _clean(observation.get("action_set_digest"), 90) != action_set_digest:
        blockers.append("OBSERVATION_ACTION_SET_DIGEST_MISMATCH")

    observed_rows = observation.get("action_results")
    projected_results: list[dict[str, Any]] = []
    if not expected_actions:
        blockers.append("REQUEST_ACTIONS_INVALID")
    if not isinstance(observed_rows, list):
        blockers.append("ACTION_RESULTS_REQUIRED")
    elif len(observed_rows) != len(expected_actions):
        blockers.append("ACTION_RESULT_COUNT_MISMATCH")
    else:
        for expected, row in zip(expected_actions, observed_rows):
            if not isinstance(row, Mapping):
                blockers.append("ACTION_RESULT_INVALID")
                continue
            projected, result_blockers = _validate_action_result(expected, row)
            projected_results.append(projected)
            blockers.extend(result_blockers)

    try:
        started = _aware_datetime(observation.get("attempt_started_at"), "attempt_started_at")
        request_check = verify_local_action_request(req, now=started)
        if request_check.get("current") is not True:
            blockers.append("REQUEST_NOT_CURRENT_AT_ATTEMPT_START")

        observed = _aware_datetime(observed_at, "observed_at")
        completed_raw = observation.get("attempt_completed_at")
        completed = (
            _aware_datetime(completed_raw, "attempt_completed_at")
            if completed_raw not in (None, "")
            else None
        )
        if observed < started:
            blockers.append("OBSERVED_BEFORE_ATTEMPT_START")
        if completed is not None:
            if completed < started:
                blockers.append("ATTEMPT_COMPLETED_BEFORE_START")
            if observed < completed:
                blockers.append("OBSERVED_BEFORE_ATTEMPT_COMPLETION")
    except ValueError:
        started = None
        completed = None
        observed = None
        blockers.append("OBSERVATION_TIME_INVALID")

    derived_outcome = _derive_outcome(projected_results)
    declared = _clean(observation.get("declared_outcome_state"), 60).upper()
    if declared and declared != derived_outcome:
        blockers.append("DECLARED_OUTCOME_MISMATCH")

    if derived_outcome != "OUTCOME_UNKNOWN" and completed is None:
        blockers.append("TERMINAL_OUTCOME_REQUIRES_COMPLETION_TIME")

    if _contains_forbidden_material(observation):
        blockers.append("ADAPTER_OBSERVATION_CONTAINS_FORBIDDEN_MATERIAL")

    blockers = list(dict.fromkeys(blockers))
    if blockers:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "blockers": blockers,
            "outcome_state": "",
            "request_digest": request_digest,
            "receipt_id": "",
            "receipt_digest": "",
            "records_physical_attempt": False,
            "physical_effect_confirmed": False,
            "automatic_retry_allowed": False,
            "receipt_builder_executed_action": False,
            "external_action_executed_by_this_module": False,
            "executes_action": False,
        }

    ambiguity = sorted({
        row["ambiguity_trigger"]
        for row in projected_results
        if row.get("ambiguity_trigger")
    })
    physical_effect_confirmed = derived_outcome in {
        "CONFIRMED_SUCCESS",
        "CONFIRMED_PARTIAL",
    }
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "state": "RECEIPT_READY",
        "outcome_state": derived_outcome,
        "request_digest": request_digest,
        "dispatch_readiness_digest": dispatch_digest,
        "action_set_digest": action_set_digest,
        "attempt_id": attempt_id,
        "adapter_instance_id": adapter_instance_id,
        "adapter_binary_digest": adapter_binary_digest,
        "evidence_bundle_digest": evidence_bundle_digest,
        "attempt_started_at": started.isoformat() if started else "",
        "attempt_completed_at": completed.isoformat() if completed else "",
        "observed_at": observed.isoformat() if observed else "",
        "action_results": projected_results,
        "ambiguity_triggers": ambiguity,
        "records_physical_attempt": True,
        "physical_effect_confirmed": physical_effect_confirmed,
        "terminal_failure_confirmed": (
            derived_outcome == "CONFIRMED_TERMINAL_FAILURE"
        ),
        "partial_effect_confirmed": derived_outcome == "CONFIRMED_PARTIAL",
        "outcome_unknown": derived_outcome == "OUTCOME_UNKNOWN",
        "automatic_retry_allowed": False,
        "automatic_reconciliation_allowed": False,
        "separate_reconciliation_required": derived_outcome == "OUTCOME_UNKNOWN",
        "new_attempt_requires_fresh_owner_command": True,
        "new_attempt_requires_new_nonce": True,
        "receipt_persisted": False,
        "receipt_signed_by_this_module": False,
        "raw_command_included": False,
        "raw_process_output_included": False,
        "executable_material_included": False,
        "credential_material_included": False,
        "receipt_builder_executed_action": False,
        "external_action_executed_by_this_module": False,
        "executes_action": False,
        "receipt_id": "",
        "receipt_digest": "",
    }
    receipt["receipt_digest"] = _digest(_receipt_material(receipt))
    receipt["receipt_id"] = "LAR-" + receipt["receipt_digest"].split(":", 1)[1][:24].upper()
    return receipt


def verify_local_action_audit_receipt(
    receipt: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw = dict(receipt or {})
    blockers: list[str] = []

    if raw.get("schema") != SCHEMA:
        blockers.append("RECEIPT_SCHEMA_MISMATCH")
    if raw.get("state") != "RECEIPT_READY":
        blockers.append("RECEIPT_NOT_READY")

    outcome = _clean(raw.get("outcome_state"), 60).upper()
    if outcome not in OUTCOME_STATES:
        blockers.append("RECEIPT_OUTCOME_INVALID")

    supplied_digest = _sha256(raw.get("receipt_digest"))
    expected_digest = _digest(_receipt_material(raw))
    if supplied_digest != expected_digest:
        blockers.append("RECEIPT_DIGEST_MISMATCH")

    expected_id = (
        "LAR-" + supplied_digest.split(":", 1)[1][:24].upper()
        if supplied_digest
        else ""
    )
    if raw.get("receipt_id") != expected_id:
        blockers.append("RECEIPT_ID_MISMATCH")

    results = raw.get("action_results")
    if not isinstance(results, list) or not results:
        blockers.append("RECEIPT_ACTION_RESULTS_REQUIRED")
        derived = "OUTCOME_UNKNOWN"
    else:
        derived = _derive_outcome(results)
        if derived != outcome:
            blockers.append("RECEIPT_DERIVED_OUTCOME_MISMATCH")

    if raw.get("automatic_retry_allowed") is not False:
        blockers.append("AUTOMATIC_RETRY_MUST_BE_FALSE")
    if raw.get("automatic_reconciliation_allowed") is not False:
        blockers.append("AUTOMATIC_RECONCILIATION_MUST_BE_FALSE")
    if raw.get("new_attempt_requires_fresh_owner_command") is not True:
        blockers.append("FRESH_OWNER_COMMAND_REQUIRED_FOR_NEW_ATTEMPT")
    if raw.get("new_attempt_requires_new_nonce") is not True:
        blockers.append("NEW_NONCE_REQUIRED_FOR_NEW_ATTEMPT")
    if raw.get("receipt_persisted") is not False:
        blockers.append("RECEIPT_PERSISTENCE_MUST_NOT_BE_CLAIMED")
    if raw.get("receipt_signed_by_this_module") is not False:
        blockers.append("RECEIPT_SIGNATURE_MUST_NOT_BE_CLAIMED")
    if raw.get("receipt_builder_executed_action") is not False:
        blockers.append("RECEIPT_BUILDER_MUST_NOT_EXECUTE")
    if raw.get("external_action_executed_by_this_module") is not False:
        blockers.append("MODULE_EXTERNAL_EXECUTION_MUST_BE_FALSE")
    if raw.get("executes_action") is not False:
        blockers.append("EXECUTES_ACTION_MUST_BE_FALSE")

    if outcome == "OUTCOME_UNKNOWN":
        if raw.get("outcome_unknown") is not True:
            blockers.append("UNKNOWN_FLAG_REQUIRED")
        if raw.get("separate_reconciliation_required") is not True:
            blockers.append("UNKNOWN_REQUIRES_SEPARATE_RECONCILIATION")
        if not raw.get("ambiguity_triggers"):
            blockers.append("UNKNOWN_AMBIGUITY_TRIGGER_REQUIRED")
        if raw.get("physical_effect_confirmed") is not False:
            blockers.append("UNKNOWN_CANNOT_CONFIRM_PHYSICAL_EFFECT")
    else:
        if raw.get("outcome_unknown") is not False:
            blockers.append("NON_UNKNOWN_OUTCOME_FLAG_INVALID")

    if _contains_forbidden_material(raw):
        blockers.append("RECEIPT_CONTAINS_FORBIDDEN_MATERIAL")

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": VERIFY_SCHEMA,
        "state": "VALID" if not blockers else "INVALID",
        "valid": not blockers,
        "blockers": blockers,
        "receipt_id": _clean(raw.get("receipt_id"), 80),
        "receipt_digest": supplied_digest,
        "outcome_state": outcome,
        "executes_action": False,
    }


def local_action_audit_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "outcome_states": list(OUTCOME_STATES),
        "action_outcome_states": list(ACTION_OUTCOME_STATES),
        "success_requires_positive_postcondition_evidence": True,
        "terminal_failure_requires_authoritative_failure_evidence": True,
        "partial_outcome_is_explicit": True,
        "ambiguity_always_becomes_outcome_unknown": True,
        "absence_of_error_is_success": False,
        "absence_of_response_is_terminal_failure": False,
        "outcome_unknown_automatic_retry": False,
        "outcome_unknown_automatic_reconciliation": False,
        "outcome_unknown_separate_reconciliation_required": True,
        "new_attempt_requires_fresh_owner_command": True,
        "new_attempt_requires_new_nonce": True,
        "raw_process_output_allowed": False,
        "executable_material_allowed": False,
        "credential_material_allowed": False,
        "receipt_persisted": False,
        "receipt_signed": False,
        "physical_action_performed_by_contract": False,
        "network_called": False,
        "worker_armed": False,
        "deploy_executed": False,
        "core_checkpoint_write": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "ADAPTER_OBSERVATION_SCHEMA",
    "VERIFY_SCHEMA",
    "POLICY_SCHEMA",
    "OUTCOME_STATES",
    "ACTION_OUTCOME_STATES",
    "AMBIGUITY_TRIGGERS",
    "EVIDENCE_KINDS",
    "local_action_bindings",
    "local_action_set_digest",
    "dispatch_readiness_digest",
    "build_local_action_audit_receipt",
    "verify_local_action_audit_receipt",
    "local_action_audit_policy",
]
