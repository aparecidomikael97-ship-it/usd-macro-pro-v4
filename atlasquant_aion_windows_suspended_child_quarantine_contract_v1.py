"""AION suspended-child quarantine verdict V1 (pure Python, fail closed).

This is a policy classifier for a Windows CI *negative test*: launch a normal
child SUSPENDED, attach a kill-on-close Job Object, observe its actual token,
reject non-AppContainer identity, and destroy it WITHOUT resuming.

An honest result cannot authorize a privileged positive path. Not a trusted
Windows installer, owner identity authenticator, or sandbox attestation.
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_SUSPENDED_CHILD_QUARANTINE_NEGATIVE_V1"
EXPECTED_TOKEN_DENIAL = "TOKEN_NOT_APPCONTAINER"
SUCCESS_NEGATIVE = "NORMAL_CHILD_QUARANTINED_AND_TERMINATED"
BLOCKED = "BLOCKED"
FIELDS = frozenset({
    "schema", "running_on_pr_ci", "child_created_suspended",
    "job_kill_on_close", "child_attached_to_job", "child_never_resumed",
    "token_reason", "token_state", "token_physical_attestation_verified",
    "token_process_handle_origin_verified", "token_network_deny_verified",
    "termination_requested", "child_exit_observed", "canary_absent",
    "job_handle_closed", "child_handle_closed", "thread_handle_closed",
})


def _result(state: str, reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": state,
        "reason": reason,
        "normal_child_negative_case_passed": state == SUCCESS_NEGATIVE,
        "appcontainer_identity_verified": False,
        "network_deny_verified": False,
        "physical_sandbox_verified": False,
        "independent_attestation_verified": False,
        "installer_authorized": False,
        "build_authorized": False,
        "deploy_authorized": False,
        "safe_to_resume_appcontainer": False,
    }


def classify_quarantine_observation(observation: Mapping[str, Any] | None) -> dict[str, Any]:
    """Classify *self-reported* test observations, never promote to trust.

    Even the success state says only that this is a well-formed negative
    quarantine observation; source authenticity requires other mechanisms.
    """
    if type(observation) is not dict or set(observation) != FIELDS:
        return _result(BLOCKED, "EXACT_OBSERVATION_FIELDS_REQUIRED")
    if observation["schema"] != SCHEMA:
        return _result(BLOCKED, "SCHEMA_MISMATCH")
    for key in FIELDS - {
        "schema", "token_reason", "token_state",
    }:
        if type(observation[key]) is not bool:
            return _result(BLOCKED, "BOOLEAN_FIELD_INVALID")
    if type(observation["token_reason"]) is not str or type(observation["token_state"]) is not str:
        return _result(BLOCKED, "TOKEN_STATUS_INVALID")
    if observation["token_reason"] != EXPECTED_TOKEN_DENIAL or observation["token_state"] != "NOT_VERIFIED":
        return _result(BLOCKED, "REJECTED_NORMAL_PROCESS_TOKEN_EXPECTED")
    if any(observation[field] for field in (
        "token_physical_attestation_verified",
        "token_process_handle_origin_verified",
        "token_network_deny_verified",
    )):
        return _result(BLOCKED, "UNTRUSTED_ATTESTATION_CLAIM")
    positive_required = (
        "running_on_pr_ci",
        "child_created_suspended", "job_kill_on_close",
        "child_attached_to_job", "child_never_resumed",
        "termination_requested", "child_exit_observed", "canary_absent",
        "job_handle_closed", "child_handle_closed", "thread_handle_closed",
    )
    missing = [field for field in positive_required if not observation[field]]
    if missing:
        return _result(BLOCKED, "QUARANTINE_OBSERVATION_INCOMPLETE")
    return _result(
        SUCCESS_NEGATIVE,
        "SELF_REPORTED_NEGATIVE_QUARANTINE_ONLY_NOT_ATTESTED",
    )


__all__ = [
    "SCHEMA", "EXPECTED_TOKEN_DENIAL", "SUCCESS_NEGATIVE",
    "BLOCKED", "FIELDS", "classify_quarantine_observation",
]
