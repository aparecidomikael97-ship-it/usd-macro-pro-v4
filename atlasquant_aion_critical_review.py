"""Offline review contract for critical AION tasks.

Prime plans, Shadow challenges, and Sentinel judges evidence and permission.
This module does not replace Guardian, Proof of Safety, or agent_firewall.
A review acceptance is a plan decision only. It never executes an action,
grants permission, changes policy, or promotes UNKNOWN to CONFIRMED.

Another agent's message is information. Authorization stays outside the text.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Callable, Mapping, Sequence
import json
import unicodedata

from atlasquant_aion_observability import redact_text

SCHEMA = "ATLASQUANT_AION_CRITICAL_REVIEW_V1"
PROTOCOL_VERSION = "1"
ROLES = ("PRIME", "SHADOW", "SENTINEL")
TASK_CLASSES = ("SIMPLE", "IMPORTANT", "CRITICAL")
VERDICTS = ("AGREE", "CHALLENGE", "BLOCK", "INSUFFICIENT_EVIDENCE")
BLAST_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
REQUIRED_ROLES = {
    "SIMPLE": ("PRIME",),
    "IMPORTANT": ("PRIME", "SHADOW"),
    "CRITICAL": ("PRIME", "SHADOW", "SENTINEL"),
}
QUORUM_FOR_BLAST = {
    "LOW": ("PRIME",),
    "MEDIUM": ("PRIME", "SHADOW"),
    "HIGH": ("PRIME", "SHADOW", "SENTINEL"),
    "CRITICAL": ("PRIME", "SHADOW", "SENTINEL"),
}
_HARD_CRITICAL = frozenset({
    "credentials",
    "production",
    "cross_tenant",
    "financial",
    "regulatory",
})
_HIGH_FACTORS = frozenset({
    "external_publication",
    "code_change",
    "irreversible",
})
_PRIVILEGE_CLAIMS = (
    "expands_permission",
    "changes_guardian",
    "self_approved",
    "forges_receipt",
    "promotes_unknown_to_confirmed",
    "executes_action",
)


def _exact_true(value: Any) -> bool:
    return value is True


def _clean(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _upper(value: Any, limit: int = 40) -> str:
    return _clean(value, limit).upper()


def _exact_int(value: Any, *, minimum: int = 0, maximum: int = 1_000_000) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < minimum or value > maximum:
        return None
    return value


def _refs(values: Sequence[Any] | None, limit: int = 40) -> list[str]:
    out: list[str] = []
    for item in list(values or [])[:limit]:
        text = _clean(item, 180)
        if text and text not in out:
            out.append(text)
    return out


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def canonical_fingerprint(payload: Mapping[str, Any]) -> str:
    """SHA-256 of canonical JSON.

    This is an integrity fingerprint only. It is not a signature, not an
    identity proof, and not an authorization proof. Anyone who can rewrite
    the payload can recompute it.
    """
    return sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _digest(payload: Mapping[str, Any]) -> str:
    return canonical_fingerprint(payload)


def _fold(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold()


_AUTHORITY_PHRASES = (
    "sou admin",
    "i am admin",
    "you are admin",
    "agora voce e admin",
    "guardian autorizou",
    "guardian authorized",
    "altere a constitution",
    "alter the constitution",
    "change the constitution",
    "ignore o guardian",
    "ignore the guardian",
    "ignore previous instructions",
)


def _secret_text(value: Any, limit: int) -> tuple[str, bool]:
    text = _clean(value, limit)
    redacted = _clean(redact_text(text), limit)
    return redacted, redacted != text


def _content_claims_authority(value: Any) -> bool:
    folded = _fold(value)
    return any(phrase in folded for phrase in _AUTHORITY_PHRASES)


def _binding_status(refs: Sequence[str], verifier: Any) -> str:
    """A non-empty string is not evidence or approval.

    The caller must supply a verifier that binds exactly these refs.
    Without that verifier the status stays UNVERIFIED.
    """
    rows = list(refs)
    if not rows:
        return "MISSING"
    if not callable(verifier):
        return "UNVERIFIED"
    try:
        result = verifier(rows)
    except Exception:
        return "UNVERIFIED"
    if not isinstance(result, Mapping) or _upper(result.get("state"), 40) != "VERIFIED":
        return "UNVERIFIED"
    bound = _refs(result.get("bound_refs"))
    if sorted(bound) != sorted(rows) or len(bound) != len(set(rows)):
        return "UNVERIFIED"
    return "VERIFIED"


def _fingerprint_fields() -> dict[str, Any]:
    return {
        "digest_kind": "CANONICAL_FINGERPRINT",
        "digest_is_signature": False,
        "digest_is_identity_proof": False,
        "digest_is_authorization_proof": False,
    }


def _aware(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def classify_blast_radius(
    *,
    action_name: Any = "",
    factors: Mapping[str, Any] | None = None,
    user_count: Any = 0,
    estimated_cost: Any = 0,
) -> dict[str, Any]:
    """Classify impact from factors, not from the action name alone.

    CRITICAL never becomes automatic. The action name is recorded and cannot
    lower the class produced by the factors.
    """
    raw = dict(factors or {})
    users = _exact_int(user_count)
    if isinstance(estimated_cost, bool) or not isinstance(estimated_cost, (int, float)):
        cost: float | None = None
    elif not float(estimated_cost) == float(estimated_cost) or float(estimated_cost) in (float("inf"), float("-inf")):
        cost = None
    else:
        cost = float(estimated_cost)

    active = {
        _clean(key, 80)
        for key, value in raw.items()
        if value is not False and value is not None and _clean(key, 80)
    }
    unknown = sorted(key for key in active if key not in _HARD_CRITICAL and key not in _HIGH_FACTORS)
    blockers: list[str] = []
    if users is None:
        blockers.append("USER_COUNT_INVALID")
    if cost is None or cost < 0:
        blockers.append("COST_INVALID")

    if active & _HARD_CRITICAL or "USER_COUNT_INVALID" in blockers or "COST_INVALID" in blockers:
        level = "CRITICAL"
    elif active & _HIGH_FACTORS or unknown or (users or 0) >= 100 or (cost or 0) > 0:
        level = "HIGH"
    elif (users or 0) >= 2:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "schema": SCHEMA,
        "action_name": _clean(action_name, 120),
        "level": level,
        "active_factors": sorted(active),
        "unknown_factors": unknown,
        "user_count": users,
        "estimated_cost": None if cost is None else round(cost, 4),
        "required_roles": list(QUORUM_FOR_BLAST[level]),
        "human_approval_required": level == "CRITICAL" or bool(blockers),
        "automatic_execution": False,
        "blockers": blockers,
        "executes_action": False,
        "grants_permission": False,
    }


def adjudicate_critical_task(
    *,
    task_class: Any,
    reviews: Sequence[Mapping[str, Any]] | None,
    trusted_assignments: Mapping[str, Any] | None,
    workspace_id: Any,
    tenant_id: Any,
    evidence_refs: Sequence[Any] | None,
    sensitive: Any = False,
    approval_refs: Sequence[Any] | None = None,
    task_ref: Any = "",
    plan_version: Any = "",
    evidence_verifier: Callable[[Sequence[str]], Mapping[str, Any]] | None = None,
    approval_verifier: Callable[[Sequence[str]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Decide whether a plan may proceed to Guardian.

    Divergent or incomplete reviews block or escalate. They are never resolved
    by picking the most convenient verdict.
    """
    kind = _upper(task_class, 40)
    assignments = {
        _upper(role, 40): _clean(agent, 160)
        for role, agent in dict(trusted_assignments or {}).items()
    }
    evidence = _refs(evidence_refs)
    approvals = _refs(approval_refs)
    evidence_status = _binding_status(evidence, evidence_verifier)
    blockers: list[str] = []
    if sensitive is True:
        sensitive_exact = True
    elif sensitive is False:
        sensitive_exact = False
    else:
        blockers.append("SENSITIVE_TYPE_INVALID")
        sensitive_exact = True
    if approvals or sensitive_exact:
        approval_status = _binding_status(approvals, approval_verifier)
    else:
        approval_status = "NOT_REQUIRED"
    if kind not in TASK_CLASSES:
        blockers.append("TASK_CLASS_INVALID")
        required: tuple[str, ...] = ()
    else:
        required = REQUIRED_ROLES[kind]
        principals = [assignments.get(role, "") for role in required if assignments.get(role, "")]
        if len(principals) != len(set(principals)):
            blockers.append("REVIEWER_INDEPENDENCE")
    expected_task = _clean(task_ref, 160)
    expected_plan = _clean(plan_version, 40)
    task_tenant = _clean(tenant_id, 120)
    task_workspace = _clean(workspace_id, 120)
    if kind in {"IMPORTANT", "CRITICAL"} and (not expected_task or not expected_plan):
        blockers.append("REVIEW_BINDING_MISSING")
    if not _clean(workspace_id, 120):
        blockers.append("WORKSPACE_MISSING")
    if not _clean(tenant_id, 120):
        blockers.append("TENANT_MISSING")
    if evidence_status == "MISSING":
        blockers.append("EVIDENCE_MISSING")
    elif evidence_status != "VERIFIED":
        blockers.append("EVIDENCE_UNVERIFIED")
    if approval_status == "MISSING":
        blockers.append("APPROVAL_MISSING")
    elif approval_status == "UNVERIFIED":
        blockers.append("APPROVAL_UNVERIFIED")

    seen: dict[str, Mapping[str, Any]] = {}
    for raw in list(reviews or []):
        if not isinstance(raw, Mapping):
            blockers.append("REVIEW_INVALID")
            continue
        role = _upper(raw.get("role"), 40)
        agent = _clean(raw.get("agent_id"), 160)
        verdict = _upper(raw.get("verdict"), 40)
        if role not in ROLES:
            blockers.append("ROLE_INVALID")
            continue
        if role in seen:
            blockers.append(f"DUPLICATE_REVIEWER:{role}")
            continue
        expected = assignments.get(role, "")
        if not expected or agent != expected:
            blockers.append(f"SPOOFED_ROLE:{role}")
            continue
        review_tenant = _clean(raw.get("tenant_id"), 120)
        review_workspace = _clean(raw.get("workspace_id"), 120)
        review_task = _clean(raw.get("task_ref"), 160)
        review_plan = _clean(raw.get("plan_version"), 40)
        strict_binding = kind in {"IMPORTANT", "CRITICAL"}
        scope_mismatch = (
            (strict_binding and (not review_tenant or review_tenant != task_tenant))
            or (review_tenant and review_tenant != task_tenant)
            or (strict_binding and (not review_workspace or review_workspace != task_workspace))
            or (review_workspace and review_workspace != task_workspace)
        )
        task_mismatch = (
            (strict_binding and (not review_task or review_task != expected_task))
            or (review_task and expected_task and review_task != expected_task)
        )
        plan_mismatch = (
            (strict_binding and (not review_plan or review_plan != expected_plan))
            or (review_plan and expected_plan and review_plan != expected_plan)
        )
        if scope_mismatch:
            blockers.append(f"REVIEW_SCOPE:{role}")
            continue
        if task_mismatch:
            blockers.append(f"REVIEW_TASK:{role}")
            continue
        if plan_mismatch:
            blockers.append(f"REVIEW_PLAN:{role}")
            continue
        if verdict not in VERDICTS:
            blockers.append(f"VERDICT_INVALID:{role}")
            continue
        for claim in _PRIVILEGE_CLAIMS:
            if _exact_true(raw.get(claim)):
                blockers.append(f"PRIVILEGE_CLAIM:{role}:{claim}")
        if verdict in {"BLOCK", "INSUFFICIENT_EVIDENCE"}:
            blockers.append(f"REVIEW_{verdict}:{role}")
        elif verdict == "CHALLENGE":
            blockers.append(f"DIVERGENCE:{role}")
        seen[role] = raw

    for role in required:
        if role not in seen and f"SPOOFED_ROLE:{role}" not in blockers and f"DUPLICATE_REVIEWER:{role}" not in blockers:
            blockers.append(f"MISSING_REVIEWER:{role}")

    divergence = [item for item in blockers if item.startswith("DIVERGENCE:")]
    hard = [item for item in blockers if not item.startswith("DIVERGENCE:")]
    if hard:
        state = "BLOCK"
    elif divergence:
        state = "ESCALATE"
    else:
        state = "ACCEPT_PLAN"

    return {
        "schema": SCHEMA,
        "state": state,
        "task_class": kind if kind in TASK_CLASSES else "INVALID",
        "required_roles": list(required),
        "received_roles": sorted(seen),
        "workspace_id": _clean(workspace_id, 120),
        "tenant_id": _clean(tenant_id, 120),
        "evidence_refs": evidence,
        "approval_refs": approvals,
        "evidence_status": evidence_status,
        "approval_status": approval_status,
        "blockers": blockers,
        "truth_state": "UNKNOWN",
        "truth_promoted": False,
        "eligible_for_guardian": state == "ACCEPT_PLAN",
        "executes_action": False,
        "grants_permission": False,
        "changes_guardian": False,
        "self_approved": False,
    }


def seal_agent_message(
    payload: Mapping[str, Any] | None,
    *,
    trusted_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Bind a message to trusted context and a digest.

    Identity fields from the payload are ignored. The caller supplies the
    trusted context from outside the message.
    """
    context = dict(trusted_context or {})
    incoming = dict(payload or {})
    role = _upper(context.get("role"), 40)
    agent_id = _clean(context.get("agent_id"), 160)
    workspace_id = _clean(context.get("workspace_id"), 120)
    tenant_id = _clean(context.get("tenant_id"), 120)
    capability = _upper(incoming.get("capability") or incoming.get("requested_capability"), 80)
    allowed = {_upper(item, 80) for item in list(context.get("capabilities") or []) if _upper(item, 80)}
    requested_permissions = _refs(incoming.get("permissions"))
    blockers: list[str] = []
    if role not in ROLES or not agent_id:
        blockers.append("TRUSTED_CONTEXT_INVALID")
    if not workspace_id or not tenant_id:
        blockers.append("SCOPE_MISSING")
    if capability and capability not in allowed:
        blockers.append("CAPABILITY_NOT_IN_TRUSTED_CONTEXT")
    if any(_upper(item, 80) not in allowed for item in requested_permissions):
        blockers.append("PERMISSION_OUTSIDE_TRUSTED_CONTEXT")
    issued_at = _aware(incoming.get("issued_at"))
    if issued_at is None:
        blockers.append("TIMESTAMP_INVALID")
    nonce = _clean(incoming.get("nonce"), 120)
    if not nonce:
        blockers.append("NONCE_MISSING")
    content, content_secret = _secret_text(incoming.get("content"), 1000)
    evidence_refs: list[str] = []
    approval_refs: list[str] = []
    secret_in_refs = False
    for ref in _refs(incoming.get("evidence_refs")):
        redacted, found = _secret_text(ref, 180)
        evidence_refs.append(redacted)
        secret_in_refs = secret_in_refs or found
    for ref in _refs(incoming.get("approval_refs")):
        redacted, found = _secret_text(ref, 180)
        approval_refs.append(redacted)
        secret_in_refs = secret_in_refs or found
    if content_secret or secret_in_refs:
        blockers.append("SECRET_DETECTED")

    body = {
        "version": PROTOCOL_VERSION,
        "agent_id": agent_id,
        "role": role if role in ROLES else "INVALID",
        "capability": capability,
        "workspace_id": workspace_id,
        "tenant_id": tenant_id,
        "requested_action": _clean(incoming.get("requested_action"), 160),
        "evidence_refs": evidence_refs,
        "confidence": _upper(incoming.get("confidence"), 40) or "UNKNOWN",
        "risk_level": _upper(incoming.get("risk_level"), 40) if _upper(incoming.get("risk_level"), 40) in BLAST_LEVELS else "UNKNOWN",
        "permissions": [item for item in requested_permissions if _upper(item, 80) in allowed],
        "approval_refs": approval_refs,
        "issued_at": issued_at.isoformat() if issued_at else "",
        "nonce": nonce,
        "content": content,
    }
    digest = _digest(body)
    return {
        "schema": SCHEMA,
        "state": "BLOCKED" if blockers else "SEALED",
        "message": {**body, "digest": digest},
        "blockers": blockers,
        "content_is_authority": False,
        "executes_action": False,
        "grants_permission": False,
        "sealed_means_authenticated": False,
        **_fingerprint_fields(),
    }


def validate_agent_message(
    message: Mapping[str, Any] | None,
    *,
    trusted_context: Mapping[str, Any] | None,
    expected_workspace_id: Any,
    expected_tenant_id: Any,
    seen_digests: Sequence[Any] | None = None,
    now: datetime | None = None,
    max_age_seconds: Any = 900,
    evidence_verifier: Callable[[Sequence[str]], Mapping[str, Any]] | None = None,
    approval_verifier: Callable[[Sequence[str]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Re-check a message at read time. A past seal is not ongoing trust.

    The digest is a canonical fingerprint. A rewritten payload with a
    recomputed digest still has to match the trusted context, and evidence
    or approval strings stay UNVERIFIED until a caller-supplied verifier
    binds them. The message remains information, never authorization.
    """
    raw = dict(message or {})
    presented = _clean(raw.get("digest"), 80)
    body = {key: raw.get(key) for key in (
        "version",
        "agent_id",
        "role",
        "capability",
        "workspace_id",
        "tenant_id",
        "requested_action",
        "evidence_refs",
        "confidence",
        "risk_level",
        "permissions",
        "approval_refs",
        "issued_at",
        "nonce",
        "content",
    )}
    for key in ("evidence_refs", "permissions", "approval_refs"):
        body[key] = list(body[key] or [])
    actual = _digest(body)
    context = dict(trusted_context or {})
    allowed = {_upper(item, 80) for item in list(context.get("capabilities") or []) if _upper(item, 80)}
    capability = _upper(raw.get("capability"), 80)
    permissions = [_upper(item, 80) for item in list(raw.get("permissions") or []) if _upper(item, 80)]
    evidence = _refs(raw.get("evidence_refs"))
    approvals = _refs(raw.get("approval_refs"))
    evidence_status = _binding_status(evidence, evidence_verifier)
    risk = _upper(raw.get("risk_level"), 40)
    if approvals or risk in {"HIGH", "CRITICAL"}:
        approval_status = _binding_status(approvals, approval_verifier)
    else:
        approval_status = "NOT_REQUIRED"
    trusted_workspace = _clean(context.get("workspace_id"), 120)
    trusted_tenant = _clean(context.get("tenant_id"), 120)
    message_workspace = _clean(raw.get("workspace_id"), 120)
    message_tenant = _clean(raw.get("tenant_id"), 120)
    expected_workspace = _clean(expected_workspace_id, 120)
    expected_tenant = _clean(expected_tenant_id, 120)
    blockers: list[str] = []
    if presented != actual:
        blockers.append("DIGEST_INVALID")
    if _clean(raw.get("version"), 20) != PROTOCOL_VERSION:
        blockers.append("VERSION_UNSUPPORTED")
    if not _clean(raw.get("nonce"), 120):
        blockers.append("NONCE_MISSING")
    presented_schema = raw.get("schema")
    if presented_schema not in (None, "") and _clean(presented_schema, 80) != SCHEMA:
        blockers.append("SCHEMA_UNSUPPORTED")
    if (
        _secret_text(raw.get("content"), 1000)[1]
        or any(_secret_text(item, 180)[1] for item in list(raw.get("evidence_refs") or []))
        or any(_secret_text(item, 180)[1] for item in list(raw.get("approval_refs") or []))
    ):
        blockers.append("SECRET_PRESENT")
    if _upper(raw.get("role"), 40) != _upper(context.get("role"), 40) or _upper(context.get("role"), 40) not in ROLES:
        blockers.append("SPOOFED_ROLE")
    if _clean(raw.get("agent_id"), 160) != _clean(context.get("agent_id"), 160) or not _clean(context.get("agent_id"), 160):
        blockers.append("SPOOFED_AGENT")
    if not message_workspace or len({message_workspace, expected_workspace, trusted_workspace}) != 1:
        blockers.append("WORKSPACE_MISMATCH")
    if not message_tenant or len({message_tenant, expected_tenant, trusted_tenant}) != 1:
        blockers.append("TENANT_MISMATCH")
    if not capability or capability not in allowed:
        blockers.append("CAPABILITY_OUTSIDE_TRUSTED_CONTEXT")
    if any(item not in allowed for item in permissions):
        blockers.append("PERMISSION_OUTSIDE_TRUSTED_CONTEXT")
    if presented and presented in {_clean(item, 80) for item in list(seen_digests or [])}:
        blockers.append("REPLAY")
    if evidence_status == "MISSING":
        blockers.append("EVIDENCE_MISSING")
    elif evidence_status != "VERIFIED":
        blockers.append("EVIDENCE_UNVERIFIED")
    if approval_status == "MISSING":
        blockers.append("APPROVAL_MISSING")
    elif approval_status == "UNVERIFIED":
        blockers.append("APPROVAL_UNVERIFIED")
    issued = _aware(raw.get("issued_at"))
    age_limit = _exact_int(max_age_seconds, minimum=1, maximum=86_400)
    current = now if isinstance(now, datetime) and now.tzinfo is not None else None
    if issued is None or current is None or age_limit is None:
        blockers.append("TIMESTAMP_INVALID")
    else:
        delta = (current - issued).total_seconds()
        if delta < 0 or delta > age_limit:
            blockers.append("STALE_OR_FUTURE")
    if (
        _exact_true(raw.get("grants_permission"))
        or _exact_true(raw.get("content_is_authority"))
        or _content_claims_authority(raw.get("content"))
    ):
        blockers.append("CONTENT_IS_NOT_AUTHORITY")

    return {
        "schema": SCHEMA,
        "state": "BLOCK" if blockers else "INFORMATION_ONLY",
        "digest_ok": presented == actual,
        "evidence_status": evidence_status,
        "approval_status": approval_status,
        "blockers": list(dict.fromkeys(blockers)),
        "content_is_authority": False,
        "authorization": "NONE",
        "truth_state": "UNKNOWN",
        "executes_action": False,
        "grants_permission": False,
        **_fingerprint_fields(),
    }
