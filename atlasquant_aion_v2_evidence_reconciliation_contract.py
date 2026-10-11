"""Data-only Shadow/Flight reconciliation binding. NEVER admits a real write.

The existing journal/CAS/witness references remain the reference mechanisms;
this module only describes exact evidence bytes and rejects unsafe observations.
Caller-supplied scope, hashes and generations are not enrolled identity or a
protected high-watermark. Even a full match cannot release a quarantine.
"""
from __future__ import annotations

from hashlib import sha1, sha256
import json
import re

from atlasquant_aion_core_intelligence.context import Context, Domain
from atlasquant_aion_v2_github_write_url_guard import guard_github_token_read_destination
from atlasquant_aion_v2_one_shot_unknown_outcome_journal_reference import STATE_CLAIMED, STATE_UNKNOWN

SCHEMA = "AION_EVIDENCE_RECONCILIATION_REFERENCE_V2"
MAX_CONTENT_BYTES = 1024 * 1024
PATHS = {"shadow": "dados/atlasquant_shadow_samples.jsonl",
         "flight": "dados/atlasquant_flight_recorder.jsonl"}
DOMAIN = b"AION_EVIDENCE_RECONCILIATION_REFERENCE_V2\0"
HEX = re.compile(r"[0-9a-f]{64}\Z")
SCOPE_KEYS = frozenset({"tenant_id", "workspace_id", "actor_id", "task_id", "domain",
                       "repo", "branch", "sink", "path", "policy_generation"})
KEYS = frozenset({"schema", "scope", "scope_digest", "content_sha256", "blob_sha",
                  "content_size", "nonce_hex", "semantic_id", "operation_id"})


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(DOMAIN + _canonical(value)).hexdigest()


def _blob(raw: bytes) -> str:
    return sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def _valid_scope(scope: object) -> bool:
    if type(scope) is not dict or set(scope) != SCOPE_KEYS:
        return False
    if any(type(scope[k]) is not str for k in SCOPE_KEYS - {"policy_generation"}):
        return False
    if len(scope["repo"]) > 200 or len(scope["branch"]) > 200:
        return False
    try:
        Context(scope["tenant_id"], scope["workspace_id"], scope["actor_id"],
                scope["task_id"], Domain(scope["domain"]))
        if scope["domain"] not in {"ADMIN", "RESEARCH", "DEVELOPER"}:
            return False
        if type(scope["policy_generation"]) is not int or not 1 <= scope["policy_generation"] < 2**63:
            return False
        if scope["sink"] not in PATHS or scope["path"] != PATHS[scope["sink"]]:
            return False
        if type(scope["repo"]) is not str or type(scope["branch"]) is not str:
            return False
        # Exact scope binding only: this guard grants no repo/token authorization.
        guard_github_token_read_destination("https://api.github.com/repos/" + scope["repo"] + "/contents/" + scope["path"])
        from atlasquant_runtime_store import require_runtime_branch
        return require_runtime_branch(scope["branch"]) == scope["branch"]
    except (ValueError, TypeError, KeyError):
        return False


def _sealed(body: dict) -> dict:
    body = dict(body)
    body["semantic_id"] = _digest({"scope_digest": body["scope_digest"],
                                    "content_sha256": body["content_sha256"],
                                    "blob_sha": body["blob_sha"], "content_size": body["content_size"]})
    body["operation_id"] = _digest(body)
    return body


def build_reference_intent(*, context: Context, repo: str, branch: str, sink: str,
                           exact_content: bytes, nonce_hex: str, policy_generation: int) -> dict:
    """Deterministic binding, not approval; semantic ID prevents nonce rewrapping."""
    if type(context) is not Context or type(exact_content) is not bytes or not 0 < len(exact_content) <= MAX_CONTENT_BYTES:
        raise ValueError("EXACT_BOUNDED_CONTENT_AND_CONTEXT_REQUIRED")
    if type(nonce_hex) is not str or not HEX.fullmatch(nonce_hex) or nonce_hex == "0" * 64:
        raise ValueError("NONZERO_REFERENCE_NONCE_REQUIRED")
    scope = {"tenant_id": context.tenant_id, "workspace_id": context.workspace_id,
             "actor_id": context.actor_id, "task_id": context.task_id, "domain": context.domain.value,
             "repo": repo, "branch": branch, "sink": sink, "path": PATHS.get(sink),
             "policy_generation": policy_generation}
    if not _valid_scope(scope):
        raise ValueError("EXACT_EVIDENCE_SCOPE_REQUIRED")
    return _sealed({"schema": SCHEMA, "scope": scope, "scope_digest": _digest(scope),
                    "content_sha256": sha256(exact_content).hexdigest(), "blob_sha": _blob(exact_content),
                    "content_size": len(exact_content), "nonce_hex": nonce_hex})


def _valid_intent(intent: object) -> bool:
    if type(intent) is not dict or set(intent) != KEYS or intent["schema"] != SCHEMA:
        return False
    if not _valid_scope(intent["scope"]):
        return False
    if any(type(intent[k]) is not str or not HEX.fullmatch(intent[k])
           for k in ("scope_digest", "content_sha256", "nonce_hex", "semantic_id", "operation_id")):
        return False
    if intent["nonce_hex"] == "0" * 64 or type(intent["blob_sha"]) is not str or not re.fullmatch(r"[0-9a-f]{40}", intent["blob_sha"]):
        return False
    if type(intent["content_size"]) is not int or not 0 < intent["content_size"] <= MAX_CONTENT_BYTES:
        return False
    body = {k: v for k, v in intent.items() if k not in {"operation_id", "semantic_id"}}
    return intent["scope_digest"] == _digest(intent["scope"]) and _sealed(body) == intent


def review_reference_observation(*, expected_intent: object, observed_intent: object,
                                 observed_content: object, journal_state: object,
                                 current_generation: object) -> dict:
    """Read-only math review. NOT_FOUND, local presence and a match never admit retry."""
    reason = "MATCH_UNTRUSTED_NO_INDEPENDENT_WITNESS"
    match = False
    if not _valid_intent(expected_intent) or not _valid_intent(observed_intent):
        reason = "INVALID_CLOSED_BINDING"
    elif type(current_generation) is not int or current_generation != expected_intent["scope"]["policy_generation"]:
        reason = "GENERATION_MISMATCH"
    elif expected_intent != observed_intent:
        reason = "OPERATION_OR_SCOPE_MISMATCH"
    elif journal_state not in (STATE_CLAIMED, STATE_UNKNOWN):
        reason = "UNCERTAIN_JOURNAL_STATE_REQUIRED"
    elif observed_content is None:
        reason = "READ_UNAVAILABLE_NOT_PROOF_OF_ABSENCE"
    elif type(observed_content) is not bytes or len(observed_content) != expected_intent["content_size"]:
        reason = "CONTENT_MISMATCH"
    elif sha256(observed_content).hexdigest() != expected_intent["content_sha256"] or _blob(observed_content) != expected_intent["blob_sha"]:
        reason = "CONTENT_MISMATCH"
    else:
        match = True
    return {"schema": SCHEMA, "state": "PENDING_RECONCILIATION" if match or observed_content is None else "HARD_DENY",
            "reason": reason, "content_match_reference_only": match, "reference_only": True,
            "reconciliation_required": True, "independent_evidence_verified": False,
            "durable_admission_verified": False, "human_approval_verified": False,
            "execution_authorized": False, "safe_to_resume": False, "safe_to_retry": False,
            "writer_called": False, "network_called": False}


__all__ = ["build_reference_intent", "review_reference_observation"]
