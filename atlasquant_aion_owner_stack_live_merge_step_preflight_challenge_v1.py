"""AION Owner Stack Live Merge Step Preflight + Challenge V1.

Pure, non-mutating preparation for future HUMAN_OWNER-authorized repository
mutations in the #1015-#1029 merge sequence.

This layer can:
- validate one live merge-step snapshot against the pinned stack;
- build an exact owner authorization challenge candidate;
- verify challenge integrity/freshness.

It does NOT:
- accept chat text as authorization;
- verify a real HUMAN_OWNER signature;
- mark a PR ready;
- retarget/rebase a PR;
- merge a PR;
- delete a branch;
- deploy;
- activate Worker/provider/persistence;
- mutate GitHub in any way.

A positive challenge state is only OWNER_AUTHORIZATION_CHALLENGE_READY.
It is not authorization.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from atlasquant_aion_owner_stack_pre_merge_readiness_v1 import STACK


SCHEMA = "ATLASQUANT_AION_OWNER_STACK_LIVE_MERGE_STEP_PREFLIGHT_CHALLENGE_V1"
PREFLIGHT_SCHEMA = "ATLASQUANT_AION_OWNER_STACK_LIVE_MERGE_STEP_PREFLIGHT_V1"
CHALLENGE_SCHEMA = "ATLASQUANT_AION_OWNER_STACK_MERGE_OWNER_CHALLENGE_V1"
VERIFY_SCHEMA = "ATLASQUANT_AION_OWNER_STACK_MERGE_OWNER_CHALLENGE_VERIFY_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_OWNER_STACK_LIVE_MERGE_STEP_POLICY_V1"

MUTATIONS = (
    "PR_DRAFT_TO_READY",
    "PR_RETARGET_TO_MAIN",
    "SQUASH_MERGE_TO_MAIN",
)
MAX_CHALLENGE_WINDOW_SECONDS = 120

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,239}$")


def _clean(value: Any, limit: int = 500) -> str:
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


def _sha(value: Any) -> str:
    token = _clean(value, 60)
    return token if _SHA_RE.fullmatch(token) else ""


def _sha256(value: Any) -> str:
    token = _clean(value, 90)
    return token if _DIGEST_RE.fullmatch(token) else ""


def _identity(value: Any, limit: int = 240) -> str:
    if type(value) is not str:
        return ""
    text = _clean(value, limit)
    if text != value or not _ID_RE.fullmatch(text):
        return ""
    return text


def _aware(value: Any, label: str) -> datetime:
    try:
        if isinstance(value, datetime):
            dt = value
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception as exc:
        raise ValueError(f"{label} invalid") from exc
    if dt.tzinfo is None:
        raise ValueError(f"{label} timezone required")
    return dt.astimezone(timezone.utc)


def _expected_pr(number: int) -> Mapping[str, Any] | None:
    for item in STACK:
        if item["number"] == number:
            return item
    return None


def _file_names(value: Any) -> list[str]:
    rows = value if isinstance(value, (list, tuple)) else []
    out: list[str] = []
    for row in rows:
        if isinstance(row, str):
            name = _clean(row, 420)
        elif isinstance(row, Mapping):
            name = _clean(row.get("filename"), 420)
        else:
            name = ""
        if name:
            out.append(name)
    return out


def _gate_map(value: Any) -> dict[str, bool]:
    rows = value if isinstance(value, (list, tuple)) else []
    out: dict[str, bool] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        name = _clean(row.get("name"), 240)
        if not name:
            continue
        out[name] = (
            _clean(row.get("status"), 40).lower() == "completed"
            and _clean(row.get("conclusion"), 40).lower() == "success"
        )
    return out


def build_live_merge_step_preflight(
    *,
    pr_number: Any,
    requested_mutation: Any,
    observed_main_sha: Any,
    observed_main_tree_sha: Any,
    observed_pr_state: Any,
    observed_draft: bool,
    observed_mergeable: bool,
    observed_base: Any,
    observed_head: Any,
    observed_head_sha: Any,
    observed_files: Sequence[Any] | None,
    observed_workflows: Sequence[Mapping[str, Any]] | None,
    parent_confirmed_in_main: bool,
    current_readiness_digest: Any,
    rollback_plan_digest: Any,
) -> dict[str, Any]:
    """Validate one live step snapshot. Never performs repository mutation."""
    blockers: list[str] = []

    try:
        number = int(pr_number)
    except Exception:
        number = 0
        blockers.append("PR_NUMBER_INVALID")

    item = _expected_pr(number)
    mutation = _clean(requested_mutation, 80).upper()
    if item is None:
        blockers.append("PR_NOT_IN_OWNER_STACK")
    if mutation not in MUTATIONS:
        blockers.append("REQUESTED_MUTATION_INVALID")

    main_sha = _sha(observed_main_sha)
    main_tree_sha = _sha(observed_main_tree_sha)
    head_sha = _sha(observed_head_sha)
    readiness_digest = _sha256(current_readiness_digest)
    rollback_digest = _sha256(rollback_plan_digest)

    if not main_sha:
        blockers.append("LIVE_MAIN_SHA_REQUIRED")
    if not main_tree_sha:
        blockers.append("LIVE_MAIN_TREE_SHA_REQUIRED")
    if not head_sha:
        blockers.append("LIVE_HEAD_SHA_REQUIRED")
    if not readiness_digest:
        blockers.append("CURRENT_READINESS_DIGEST_REQUIRED")
    if not rollback_digest:
        blockers.append("ROLLBACK_PLAN_DIGEST_REQUIRED")

    state = _clean(observed_pr_state, 40).lower()
    base = _clean(observed_base, 260)
    head = _clean(observed_head, 260)
    if state != "open":
        blockers.append("PR_MUST_BE_OPEN")
    if observed_mergeable is not True:
        blockers.append("PR_MUST_BE_MERGEABLE")

    file_names = _file_names(observed_files)
    gate_map = _gate_map(observed_workflows)

    if item is not None:
        if head != item["head"]:
            blockers.append("HEAD_BRANCH_MISMATCH")
        if head_sha != item["head_sha"]:
            blockers.append("HEAD_SHA_MISMATCH")
        if sorted(file_names) != sorted(item["files"]):
            blockers.append("EXACT_FILE_DELTA_REQUIRED")
        if len(file_names) != 4:
            blockers.append("FOUR_FILE_DELTA_REQUIRED")
        for workflow in item["required_workflows"]:
            if gate_map.get(workflow) is not True:
                blockers.append("REQUIRED_WORKFLOW_NOT_GREEN:" + workflow)

        index = [row["number"] for row in STACK].index(number)
        parent = STACK[index - 1] if index else None

        if mutation == "PR_DRAFT_TO_READY":
            if observed_draft is not True:
                blockers.append("PR_MUST_CURRENTLY_BE_DRAFT")
            expected_base = "main" if number == 1015 else item["base"]
            if base != expected_base:
                blockers.append("DRAFT_TRANSITION_BASE_MISMATCH")
            if parent is not None and parent_confirmed_in_main is not True:
                blockers.append("PARENT_CONFIRMATION_REQUIRED")

        elif mutation == "PR_RETARGET_TO_MAIN":
            if number == 1015:
                blockers.append("ROOT_PR_DOES_NOT_REQUIRE_RETARGET")
            if observed_draft is not False:
                blockers.append("PR_MUST_BE_READY_BEFORE_RETARGET")
            if base != item["base"]:
                blockers.append("RETARGET_SOURCE_BASE_MISMATCH")
            if parent_confirmed_in_main is not True:
                blockers.append("PARENT_CONFIRMATION_REQUIRED")

        elif mutation == "SQUASH_MERGE_TO_MAIN":
            if observed_draft is not False:
                blockers.append("PR_MUST_BE_READY_BEFORE_MERGE")
            if base != "main":
                blockers.append("MERGE_BASE_MUST_BE_MAIN")
            if number != 1015 and parent_confirmed_in_main is not True:
                blockers.append("PARENT_CONFIRMATION_REQUIRED")

    blockers = list(dict.fromkeys(blockers))
    material = {
        "pr_number": number,
        "requested_mutation": mutation,
        "observed_main_sha": main_sha,
        "observed_main_tree_sha": main_tree_sha,
        "observed_pr_state": state,
        "observed_draft": observed_draft is True,
        "observed_mergeable": observed_mergeable is True,
        "observed_base": base,
        "observed_head": head,
        "observed_head_sha": head_sha,
        "observed_files_digest": _digest(sorted(file_names)),
        "observed_workflows_digest": _digest(
            sorted(
                (
                    _clean(row.get("name"), 240),
                    _clean(row.get("status"), 40),
                    _clean(row.get("conclusion"), 40),
                )
                for row in list(observed_workflows or [])
                if isinstance(row, Mapping)
            )
        ),
        "parent_confirmed_in_main": parent_confirmed_in_main is True,
        "current_readiness_digest": readiness_digest,
        "rollback_plan_digest": rollback_digest,
    }

    return {
        "schema": PREFLIGHT_SCHEMA,
        "state": "LIVE_STEP_PREFLIGHT_READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "preflight_digest": _digest(material) if not blockers else "",
        "live_state_revalidation_required_immediately_before_mutation": True,
        "owner_authorization_challenge_required": True,
        "generic_chat_is_authorization": False,
        "real_owner_signature_verified": False,
        "authorization_granted": False,
        "repository_mutation_authorized": False,
        "repository_mutation_performed": False,
        "merge_executed": False,
        "retarget_executed": False,
        "draft_transition_executed": False,
        "deploy_executed": False,
        "worker_activated": False,
        "provider_activated": False,
        "executes_action": False,
    }


def build_owner_authorization_challenge(
    preflight: Mapping[str, Any] | None,
    *,
    challenge_id: Any,
    owner_subject: Any,
    owner_binding_digest: Any,
    nonce_digest: Any,
    issued_at: Any,
    expires_at: Any,
) -> dict[str, Any]:
    """Build exact HUMAN_OWNER challenge material. It does not grant authority."""
    row = dict(preflight or {})
    blockers: list[str] = []

    if row.get("schema") != PREFLIGHT_SCHEMA:
        blockers.append("PREFLIGHT_SCHEMA_MISMATCH")
    if row.get("state") != "LIVE_STEP_PREFLIGHT_READY":
        blockers.append("LIVE_STEP_PREFLIGHT_REQUIRED")
    if row.get("repository_mutation_authorized") is not False:
        blockers.append("PREFLIGHT_MUST_NOT_PREAUTHORIZE_MUTATION")
    if row.get("repository_mutation_performed") is not False:
        blockers.append("PREFLIGHT_MUST_BE_NON_MUTATING")

    cid = _identity(challenge_id, 180)
    subject = _identity(owner_subject, 240)
    owner_digest = _sha256(owner_binding_digest)
    nonce = _sha256(nonce_digest)

    if not cid:
        blockers.append("CHALLENGE_ID_REQUIRED")
    if not subject:
        blockers.append("OWNER_SUBJECT_REQUIRED")
    if not owner_digest:
        blockers.append("OWNER_BINDING_DIGEST_REQUIRED")
    if not nonce:
        blockers.append("NONCE_DIGEST_REQUIRED")

    try:
        issued = _aware(issued_at, "issued_at")
        expires = _aware(expires_at, "expires_at")
        if expires <= issued:
            blockers.append("CHALLENGE_EXPIRY_INVALID")
        if (expires - issued).total_seconds() > MAX_CHALLENGE_WINDOW_SECONDS:
            blockers.append("CHALLENGE_WINDOW_TOO_LONG")
    except ValueError:
        issued = None
        expires = None
        blockers.append("CHALLENGE_TIME_INVALID")

    blockers = list(dict.fromkeys(blockers))
    confirmation = (
        f"AUTHORIZE {row.get('requested_mutation')} PR #{row.get('pr_number')} "
        f"HEAD {row.get('observed_head_sha')} ON MAIN {row.get('observed_main_sha')}"
        if not blockers
        else ""
    )

    material = {
        "challenge_id": cid,
        "purpose": "HUMAN_OWNER_EXPLICIT_REPOSITORY_MUTATION_AUTHORIZATION",
        "owner_subject": subject,
        "owner_binding_digest": owner_digest,
        "nonce_digest": nonce,
        "pr_number": row.get("pr_number"),
        "requested_mutation": row.get("requested_mutation"),
        "preflight_digest": _sha256(row.get("preflight_digest")),
        "main_sha": row.get("observed_main_sha"),
        "main_tree_sha": row.get("observed_main_tree_sha"),
        "head_branch": row.get("observed_head"),
        "head_sha": row.get("observed_head_sha"),
        "base_branch": row.get("observed_base"),
        "file_delta_digest": row.get("observed_files_digest"),
        "workflow_snapshot_digest": row.get("observed_workflows_digest"),
        "readiness_digest": row.get("current_readiness_digest"),
        "rollback_plan_digest": row.get("rollback_plan_digest"),
        "confirmation_text": confirmation,
        "issued_at": issued.isoformat() if issued else "",
        "expires_at": expires.isoformat() if expires else "",
    }

    return {
        "schema": CHALLENGE_SCHEMA,
        "state": "OWNER_AUTHORIZATION_CHALLENGE_READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "challenge_digest": _digest(material) if not blockers else "",
        "challenge_is_authorization": False,
        "generic_chat_is_authorization": False,
        "chat_acknowledgement_accepted_as_signature": False,
        "owner_signature_required": True,
        "external_signature_verification_required": True,
        "persistent_nonce_replay_rejection_required": True,
        "single_use_authorization_required": True,
        "state_rebuild_match_required_at_execution_time": True,
        "real_owner_signature_verified": False,
        "authorization_granted": False,
        "repository_mutation_authorized": False,
        "repository_mutation_performed": False,
        "merge_executed": False,
        "retarget_executed": False,
        "draft_transition_executed": False,
        "deploy_executed": False,
        "worker_activated": False,
        "provider_activated": False,
        "executes_action": False,
    }


def verify_owner_authorization_challenge(
    challenge: Mapping[str, Any] | None,
    *,
    now: Any,
) -> dict[str, Any]:
    """Verify deterministic challenge integrity/freshness, never a signature."""
    raw = dict(challenge or {})
    blockers: list[str] = []

    if raw.get("schema") != CHALLENGE_SCHEMA:
        blockers.append("CHALLENGE_SCHEMA_MISMATCH")
    if raw.get("state") != "OWNER_AUTHORIZATION_CHALLENGE_READY":
        blockers.append("READY_CHALLENGE_REQUIRED")

    material = {
        key: raw.get(key)
        for key in (
            "challenge_id",
            "purpose",
            "owner_subject",
            "owner_binding_digest",
            "nonce_digest",
            "pr_number",
            "requested_mutation",
            "preflight_digest",
            "main_sha",
            "main_tree_sha",
            "head_branch",
            "head_sha",
            "base_branch",
            "file_delta_digest",
            "workflow_snapshot_digest",
            "readiness_digest",
            "rollback_plan_digest",
            "confirmation_text",
            "issued_at",
            "expires_at",
        )
    }
    supplied = _sha256(raw.get("challenge_digest"))
    expected = _digest(material)
    if not supplied or supplied != expected:
        blockers.append("CHALLENGE_DIGEST_MISMATCH")

    try:
        current = _aware(now, "now")
        issued = _aware(raw.get("issued_at"), "issued_at")
        expires = _aware(raw.get("expires_at"), "expires_at")
        if current < issued:
            blockers.append("CHALLENGE_FROM_FUTURE")
        if current > expires:
            blockers.append("CHALLENGE_EXPIRED")
    except ValueError:
        blockers.append("CHALLENGE_TIME_INVALID")

    if raw.get("challenge_is_authorization") is not False:
        blockers.append("CHALLENGE_MUST_NOT_BE_AUTHORIZATION")
    if raw.get("generic_chat_is_authorization") is not False:
        blockers.append("GENERIC_CHAT_AUTHORITY_BOUNDARY_INVALID")
    if raw.get("real_owner_signature_verified") is not False:
        blockers.append("SIGNATURE_MUST_REMAIN_UNVERIFIED_HERE")
    if raw.get("authorization_granted") is not False:
        blockers.append("AUTHORIZATION_MUST_REMAIN_FALSE_HERE")
    if raw.get("repository_mutation_authorized") is not False:
        blockers.append("REPOSITORY_MUTATION_MUST_REMAIN_UNAUTHORIZED")
    if raw.get("repository_mutation_performed") is not False:
        blockers.append("REPOSITORY_MUTATION_MUST_REMAIN_UNPERFORMED")

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": VERIFY_SCHEMA,
        "state": "VALID_CHALLENGE" if not blockers else "INVALID",
        "valid": not blockers,
        "blockers": blockers,
        "challenge_digest": supplied,
        "signature_verified": False,
        "authorization_granted": False,
        "repository_mutation_authorized": False,
        "repository_mutation_performed": False,
        "executes_action": False,
    }


def live_merge_step_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "supported_mutations": list(MUTATIONS),
        "live_main_sha_required": True,
        "live_main_tree_sha_required": True,
        "exact_head_sha_required": True,
        "exact_four_file_delta_required": True,
        "required_gates_green_required": True,
        "parent_confirmation_required_for_children": True,
        "draft_to_ready_is_separate_mutation": True,
        "retarget_to_main_is_separate_mutation": True,
        "squash_merge_is_separate_mutation": True,
        "authorization_reuse_across_mutations_allowed": False,
        "authorization_reuse_across_prs_allowed": False,
        "challenge_window_max_seconds": MAX_CHALLENGE_WINDOW_SECONDS,
        "generic_chat_is_authorization": False,
        "chat_acknowledgement_accepted_as_signature": False,
        "owner_signature_required": True,
        "external_signature_verification_required": True,
        "persistent_nonce_replay_rejection_required": True,
        "single_use_authorization_required": True,
        "state_rebuild_match_required_at_execution_time": True,
        "challenge_is_authorization": False,
        "authorization_granted": False,
        "repository_mutation_authorized": False,
        "repository_mutation_performed": False,
        "automatic_draft_transition_allowed": False,
        "automatic_retarget_allowed": False,
        "automatic_rebase_allowed": False,
        "automatic_merge_allowed": False,
        "automatic_branch_delete_allowed": False,
        "automatic_deploy_allowed": False,
        "worker_activation_allowed": False,
        "provider_activation_allowed": False,
        "merge_executed": False,
        "retarget_executed": False,
        "draft_transition_executed": False,
        "deploy_executed": False,
        "external_action_executed": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "PREFLIGHT_SCHEMA",
    "CHALLENGE_SCHEMA",
    "VERIFY_SCHEMA",
    "POLICY_SCHEMA",
    "MUTATIONS",
    "MAX_CHALLENGE_WINDOW_SECONDS",
    "build_live_merge_step_preflight",
    "build_owner_authorization_challenge",
    "verify_owner_authorization_challenge",
    "live_merge_step_policy",
]
