"""PLAN ONLY writer preflight for the Step 1 sandbox lifecycle ledger.

The append decision contract stays the source of the frozen digests. This
layer checks the on-disk GENESIS ledger against that decision and returns a
verifiable plan. It does not append, does not authorize Step 2, and does not
accept generic language as a write.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import json
import os
import re

from atlasquant_aion_business_team_access_sandbox_lifecycle_evidence_ledger import (
    GENESIS_DIGEST,
    SCHEMA as LEDGER_SCHEMA,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_plan import (
    LIFECYCLE_STEP_IDS,
)
from atlasquant_aion_business_team_access_step1_ledger_append_contract import (
    REQUIRED_ACKNOWLEDGEMENTS,
    build_ledger_append_decision_request,
    validate_ledger_append_decision,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_STEP1_LEDGER_PERSISTENT_WRITER_V1"
VERSION = "1"
MAX_PREFLIGHT_STATE = "READY_FOR_EXPLICIT_STEP1_LEDGER_PERSISTENCE_AUTHORIZATION"
LOCK_NAME = ".step1-ledger-writer.lock"
GENERIC_PHRASES = frozenset({
    "ok",
    "okay",
    "yes",
    "sim",
    "approved",
    "approve",
    "pode",
    "pode seguir",
    "vamos la",
    "vamos lá",
})
FUTURE_PROOF_METHODS = frozenset({"WINDOWS_HELLO", "FIDO2"})

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")
_SECRET = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|authorization|credential)\b\s*[:=]\s*\S+"
)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def recalculable_digest(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _fold_phrase(value: Any) -> str:
    text = _clean(value, 80).casefold()
    return text.replace("á", "a").replace("à", "a").replace("ã", "a")


def _timestamp_valid(value: Any) -> datetime | None:
    token = _clean(value, 100)
    if not token:
        return None
    try:
        parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def genesis_logical_payload(document: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "plan_digest": _clean(document.get("plan_digest"), 80).lower(),
        "authorization_record_digest": _clean(
            document.get("authorization_record_digest"), 80
        ).lower(),
        "authorization_package_digest": _clean(
            document.get("authorization_package_digest"), 80
        ).lower(),
        "materialization_digest": _clean(
            document.get("materialization_digest"), 80
        ).lower(),
        "entries": [],
        "completed_count": 0,
        "chain_head_digest": GENESIS_DIGEST,
    }


def ledger_writer_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "mode": "PLAN_ONLY",
        "state": "STEP1_LEDGER_PERSISTENT_WRITER_PLAN_ONLY",
        "maximum_preflight_state": MAX_PREFLIGHT_STATE,
        "banner": "PERSISTENCE NOT AUTHORIZED",
        "source_ledger_digest": "",
        "canonical_receipt_digest": "",
        "ledger_append_decision_digest": "",
        "target_ledger_digest": "",
        "current_receipt_count": None,
        "expected_receipt_count": 1,
        "atomic_write_status": "PLANNED_NOT_EXECUTED",
        "rollback_readiness": "PLAN_ONLY",
        "lock_status": "NOT_ACQUIRED",
        "next_expected_lifecycle_step": LIFECYCLE_STEP_IDS[1],
        "next_step_authorized": False,
        "persistence_authorized": False,
        "ledger_write_performed": False,
        "apply_command_available": False,
        "generic_language_is_authorization": False,
        "strong_auth_verifier_implemented": False,
        "step2_execution_authorized": False,
        "executor_enabled": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "external_runtime_authorized": False,
        "sandbox_only": True,
        "executes_action": False,
    }


def _decision_payload(
    request: Mapping[str, Any],
    record: Mapping[str, Any],
) -> dict[str, Any]:
    acknowledgements = _mapping(record.get("acknowledgements"))
    return {
        "decision": _clean(request.get("required_decision_token"), 300),
        "receipt_review_digest": _clean(
            request.get("receipt_review_digest"), 80
        ).lower(),
        "canonical_receipt_digest": _clean(
            request.get("canonical_receipt_digest"), 80
        ).lower(),
        "source_ledger_digest": _clean(
            request.get("source_ledger_digest"), 80
        ).lower(),
        "target_ledger_digest": _clean(
            request.get("target_ledger_digest"), 80
        ).lower(),
        "decided_by": _clean(record.get("decided_by"), 120),
        "decided_at": _clean(record.get("decided_at"), 100),
        "sandbox_only": True,
        "production_targeted": False,
        "automatic_ledger_append_requested": False,
        "step2_execution_requested": False,
        "secret_material_included": False,
        "acknowledgements": {
            name: acknowledgements.get(name) is True
            for name in REQUIRED_ACKNOWLEDGEMENTS
        },
    }


def _inside_root(root: Path, candidate: Path) -> bool:
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return False
    return ".." not in relative.parts and bool(relative.parts)


def _resolve_ledger(allowed_root: Path, ledger_path: Path) -> tuple[Path | None, str]:
    root = Path(allowed_root)
    path = Path(ledger_path)
    if not root.is_absolute() or not path.is_absolute():
        return None, "path_not_absolute"
    if "sandbox" not in root.parts:
        return None, "sandbox_only"
    if root.is_symlink() or not root.is_dir():
        return None, "allowed_root_unsafe"
    if ".." in path.parts or ".." in root.parts:
        return None, "path_not_allowed"
    if not _inside_root(root, path):
        return None, "path_not_allowed"
    current = root
    for part in path.relative_to(root).parts:
        current = current / part
        if current.is_symlink():
            return None, "symlink"
    if not current.is_file():
        return None, "ledger_missing"
    return current, ""


def _read_bytes(path: Path) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags)
    try:
        chunks = []
        while True:
            block = os.read(fd, 65536)
            if not block:
                break
            chunks.append(block)
            if sum(len(item) for item in chunks) > 1_000_000:
                raise ValueError("ledger too large")
        return b"".join(chunks)
    finally:
        os.close(fd)


def _lock_status(root: Path, lock_path: Path | None) -> str:
    candidate = Path(lock_path) if lock_path is not None else root / LOCK_NAME
    if candidate.is_symlink() or not _inside_root(root, candidate):
        return "UNSAFE"
    if candidate.exists():
        return "HELD"
    return "CLEAR"


def claim_local_writer_lock(allowed_root: Path, lock_path: Path | None = None) -> dict[str, Any]:
    """Create an exclusive local lock. This does not write the lifecycle ledger."""
    root = Path(allowed_root)
    candidate = Path(lock_path) if lock_path is not None else root / LOCK_NAME
    if candidate.is_symlink() or not _inside_root(root, candidate):
        return {"acquired": False, "reason": "lock_path_unsafe", "wrote_ledger": False}
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(candidate, flags, 0o600)
    except FileExistsError:
        return {"acquired": False, "reason": "writer_lock_held", "wrote_ledger": False}
    except OSError:
        return {"acquired": False, "reason": "writer_lock_held", "wrote_ledger": False}
    try:
        os.write(fd, b'{"schema":"STEP1_LEDGER_WRITER_LOCK","wrote_ledger":false}\n')
    finally:
        os.close(fd)
    return {"acquired": True, "reason": "", "wrote_ledger": False}


def release_local_writer_lock(allowed_root: Path, lock_path: Path | None = None) -> None:
    root = Path(allowed_root)
    candidate = Path(lock_path) if lock_path is not None else root / LOCK_NAME
    if candidate.is_symlink() or not _inside_root(root, candidate):
        return
    if candidate.is_file() and candidate.name == LOCK_NAME:
        candidate.unlink()


def _sequence_blockers(entries: Any) -> list[str]:
    if not isinstance(entries, list):
        return ["sequence_not_monotonic"]
    blockers = []
    previous = GENESIS_DIGEST
    for index, row in enumerate(entries[:20]):
        if not isinstance(row, Mapping):
            blockers.append("sequence_not_monotonic")
            break
        if row.get("step_order") != index + 1:
            blockers.append("sequence_not_monotonic")
        prior = _clean(row.get("previous_entry_digest"), 80).lower()
        if not prior:
            blockers.append("previous_entry_digest")
        elif prior != previous:
            blockers.append("sequence_not_monotonic")
        receipt = _clean(row.get("receipt_digest"), 80).lower()
        previous = receipt or previous
    return blockers


def build_ledger_writer_preflight(
    *,
    allowed_root: Path,
    ledger_path: Path,
    step1_preflight_packet: Mapping[str, Any] | None,
    receipt_review: Mapping[str, Any] | None,
    decision_record: Mapping[str, Any] | None,
    decision_review: Mapping[str, Any] | None = None,
    mode: Any = "PLAN_ONLY",
    lock_path: Path | None = None,
) -> dict[str, Any]:
    """Return a verifiable plan. The ledger file is only read."""
    before = None
    resolved, path_error = _resolve_ledger(allowed_root, ledger_path)
    if resolved is not None:
        before = _read_bytes(resolved)
    request = build_ledger_append_decision_request(
        step1_preflight_packet, receipt_review
    )
    fresh = validate_ledger_append_decision(request, decision_record)
    presented = _mapping(decision_review) or fresh
    review = _mapping(receipt_review)
    canonical = _mapping(review.get("canonical_lifecycle_receipt"))
    target = _mapping(review.get("ledger_preview"))
    recomputed_decision = (
        recalculable_digest(_decision_payload(request, _mapping(decision_record)))
        if fresh.get("ledger_append_decision_verified") is True
        else ""
    )
    blockers: list[str] = []
    if _clean(mode, 40).upper() != "PLAN_ONLY":
        blockers.append("mode_not_plan_only")
    if path_error:
        blockers.append(path_error)
    if fresh.get("state") != "EXPLICIT_STEP1_LEDGER_APPEND_DECISION_VERIFIED":
        blockers.append("decision_not_verified")
    if (
        recomputed_decision
        and _clean(presented.get("ledger_append_decision_digest"), 80).lower()
        != recomputed_decision
    ):
        blockers.append("decision_digest")
    if fresh.get("ledger_append_decision_digest") not in ("", recomputed_decision):
        blockers.append("decision_digest")
    source_digest = _clean(fresh.get("source_ledger_digest"), 80).lower()
    target_digest = _clean(fresh.get("target_ledger_digest"), 80).lower()
    receipt_digest = _clean(fresh.get("canonical_receipt_digest"), 80).lower()
    review_digest = _clean(fresh.get("receipt_review_digest"), 80).lower()
    if _clean(target.get("ledger_digest"), 80).lower() != target_digest:
        blockers.append("target_ledger_digest")
    if _clean(canonical.get("receipt_digest"), 80).lower() != receipt_digest:
        blockers.append("canonical_receipt_digest")
    if _clean(review.get("receipt_review_digest"), 80).lower() != review_digest:
        blockers.append("receipt_review_digest")
    if _clean(canonical.get("previous_entry_digest"), 80).lower() != GENESIS_DIGEST:
        blockers.append("previous_entry_digest")
    if canonical.get("step_order") != 1:
        blockers.append("step1_binding")
    if _clean(canonical.get("step_id"), 120).upper() != LIFECYCLE_STEP_IDS[0]:
        blockers.append("step1_binding")

    document: dict[str, Any] = {}
    raw_text = ""
    byte_digest = ""
    logical_digest = ""
    observed_lock = "NOT_ACQUIRED"
    if resolved is not None and before is not None:
        raw_text = before.decode("utf-8", errors="replace")
        if _SECRET.search(raw_text):
            blockers.append("secret_material")
        try:
            parsed = json.loads(before.decode("utf-8"))
        except Exception:
            parsed = None
            blockers.append("ledger_malformed")
        if isinstance(parsed, Mapping):
            document = dict(parsed)
            logical = genesis_logical_payload(document)
            logical_digest = recalculable_digest(logical)
            byte_digest = sha256(before).hexdigest()
            again = _read_bytes(resolved)
            if again != before:
                blockers.append("source_changed_during_preflight")
            entries = document.get("entries")
            if (
                document.get("schema") != LEDGER_SCHEMA
                or document.get("state") != "READY_FOR_FIRST_SANDBOX_LIFECYCLE_STEP"
                or document.get("completed_count") != 0
                or entries != []
                or _clean(document.get("chain_head_digest"), 80).lower() != GENESIS_DIGEST
                or document.get("next_expected_step_order") != 1
                or _clean(document.get("next_expected_step_id"), 120).upper()
                != LIFECYCLE_STEP_IDS[0]
                or document.get("executor_enabled") is not False
                or document.get("production_authorized") is not False
                or document.get("executes_action") is not False
            ):
                blockers.append("source_ledger_not_genesis")
            if _clean(document.get("ledger_digest"), 80).lower() != logical_digest:
                blockers.append("source_ledger_digest")
            if logical_digest != source_digest:
                blockers.append("source_ledger_digest")
            if document.get("completed_count") not in (0, None):
                blockers.append("duplicate_append")
            if isinstance(entries, list):
                seen = []
                for row in entries[:20]:
                    if not isinstance(row, Mapping):
                        continue
                    item = _clean(row.get("receipt_digest"), 80).lower()
                    if item and item == receipt_digest:
                        blockers.append("duplicate_receipt")
                    if item and item in seen:
                        blockers.append("duplicate_receipt")
                    if item:
                        seen.append(item)
                blockers.extend(_sequence_blockers(entries))
        observed_lock = _lock_status(Path(allowed_root), lock_path)
        if observed_lock != "CLEAR":
            blockers.append(
                "writer_lock_held" if observed_lock == "HELD" else "lock_unsafe"
            )
    blockers = list(dict.fromkeys(blockers))
    ready = not blockers and fresh.get("ledger_append_decision_verified") is True
    relative = (
        resolved.relative_to(allowed_root).as_posix()
        if resolved is not None
        else ""
    )
    plan = {
        "schema": SCHEMA,
        "version": VERSION,
        "mode": "PLAN_ONLY",
        "state": MAX_PREFLIGHT_STATE if ready else "STEP1_LEDGER_WRITER_PREFLIGHT_BLOCKED",
        "blockers": blockers,
        "source_ledger_path": relative,
        "source_ledger_digest": source_digest if ready else "",
        "source_bytes_digest": byte_digest if ready else "",
        "logical_ledger_digest": logical_digest if ready else "",
        "current_receipt_count": 0 if ready else None,
        "expected_receipt_count": 1 if ready else None,
        "canonical_receipt_digest": receipt_digest if ready else "",
        "receipt_review_digest": review_digest if ready else "",
        "expected_admin_id": _clean(fresh.get("decided_by"), 120) if ready else "",
        "ledger_append_decision_digest": recomputed_decision if ready else "",
        "target_ledger_digest": target_digest if ready else "",
        "expected_completed_count": 1 if ready else None,
        "expected_next_lifecycle_step": LIFECYCLE_STEP_IDS[1] if ready else "",
        "atomic_write_strategy": {
            "method": "TEMP_FILE_FSYNC_ATOMIC_REPLACE",
            "temp_relative_path": (relative + ".tmp") if relative else "",
            "fsync_file": True,
            "fsync_directory": True,
            "executed": False,
        },
        "rollback_strategy": {
            "method": "PREIMAGE_BACKUP_BEFORE_REPLACE",
            "backup_relative_path": (relative + ".bak") if relative else "",
            "source_bytes_digest": byte_digest if ready else "",
            "backup_created": False,
            "executed": False,
        },
        "atomic_write_status": "PLANNED_NOT_EXECUTED",
        "rollback_readiness": "PLAN_ONLY",
        "lock_status": observed_lock if ready or observed_lock in {"HELD", "UNSAFE", "CLEAR"} else "NOT_ACQUIRED",
        "banner": "PERSISTENCE NOT AUTHORIZED",
        "persistence_authorized": False,
        "ready_means_write_permission": False,
        "ledger_write_performed": False,
        "ledger_append_performed": False,
        "step2_execution_authorized": False,
        "executor_enabled": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "external_runtime_authorized": False,
        "sandbox_only": True,
        "executes_action": False,
        "secret_material_included": False,
    }
    if resolved is not None and before is not None and _read_bytes(resolved) != before:
        plan["state"] = "STEP1_LEDGER_WRITER_PREFLIGHT_BLOCKED"
        plan["blockers"] = list(dict.fromkeys([*plan["blockers"], "source_changed_during_preflight"]))
        plan["persistence_authorized"] = False
        plan["ledger_write_performed"] = False
    rendered = json.dumps(plan, ensure_ascii=False, sort_keys=True)
    if _SECRET.search(rendered) or (raw_text and _SECRET.search(raw_text) and _SECRET.search(rendered)):
        plan = {
            "schema": SCHEMA,
            "state": "STEP1_LEDGER_WRITER_PREFLIGHT_BLOCKED",
            "blockers": ["secret_material"],
            "banner": "PERSISTENCE NOT AUTHORIZED",
            "persistence_authorized": False,
            "ledger_write_performed": False,
            "step2_execution_authorized": False,
            "executes_action": False,
            "secret_material_included": False,
        }
    return plan


def recheck_writer_preflight(
    plan: Mapping[str, Any] | None,
    *,
    allowed_root: Path,
    ledger_path: Path,
) -> dict[str, Any]:
    """Fail closed when the ledger bytes changed after a ready plan."""
    current = _mapping(plan)
    resolved, path_error = _resolve_ledger(allowed_root, ledger_path)
    blockers = []
    if current.get("state") != MAX_PREFLIGHT_STATE:
        blockers.append("preflight_not_ready")
    if path_error:
        blockers.append(path_error)
    observed = _clean(current.get("source_bytes_digest"), 80).lower()
    if resolved is not None and observed:
        actual = sha256(_read_bytes(resolved)).hexdigest()
        if actual != observed:
            blockers.append("source_changed_after_preflight")
    elif resolved is None:
        blockers.append("source_changed_after_preflight")
    blocked = bool(blockers)
    return {
        "schema": SCHEMA,
        "state": "SOURCE_CHANGED_AFTER_PREFLIGHT" if blocked else MAX_PREFLIGHT_STATE,
        "blockers": blockers,
        "persistence_authorized": False,
        "ledger_write_performed": False,
        "step2_execution_authorized": False,
        "executes_action": False,
    }


def evaluate_future_persistence_authorization(
    plan: Mapping[str, Any] | None,
    presented: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
    seen_nonces: set[str] | None = None,
) -> dict[str, Any]:
    """Record a future strong-auth binding. This version never verifies proof."""
    current = _mapping(plan)
    raw = _mapping(presented)
    phrase = _fold_phrase(raw.get("phrase") or raw.get("decision") or "")
    issued = _timestamp_valid(raw.get("issued_at"))
    current_time = now.astimezone(timezone.utc) if isinstance(now, datetime) and now.tzinfo else None
    nonce = _clean(raw.get("nonce"), 80)
    method = _clean(raw.get("proof_method"), 40).upper()
    admin = _clean(raw.get("admin_id"), 120)
    expected_admin = _clean(current.get("expected_admin_id"), 120)
    blockers = []
    if phrase in GENERIC_PHRASES:
        blockers.append("generic_language")
    if current.get("state") != MAX_PREFLIGHT_STATE:
        blockers.append("preflight_not_ready")
    for field, expected in (
        ("source_ledger_digest", current.get("source_ledger_digest")),
        ("target_ledger_digest", current.get("target_ledger_digest")),
        ("canonical_receipt_digest", current.get("canonical_receipt_digest")),
        ("ledger_append_decision_digest", current.get("ledger_append_decision_digest")),
    ):
        expected_text = _clean(expected, 80).lower()
        if _clean(raw.get(field), 80).lower() != expected_text or not _DIGEST64.fullmatch(expected_text):
            blockers.append(field)
    if not admin or (expected_admin and admin != expected_admin):
        blockers.append("admin_id")
    if not _clean(raw.get("session_id"), 120):
        blockers.append("session_id")
    if issued is None or current_time is None:
        blockers.append("freshness")
    else:
        delta = abs((current_time - issued).total_seconds())
        if delta > 900:
            blockers.append("freshness")
    if len(nonce) < 16:
        blockers.append("nonce")
    elif nonce in (seen_nonces or set()):
        blockers.append("nonce_replay")
    if method not in FUTURE_PROOF_METHODS:
        blockers.append("proof_method")
    if raw.get("cryptographic_proof") not in (None, "") and not isinstance(raw.get("cryptographic_proof"), Mapping):
        blockers.append("proof_malformed")
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": SCHEMA,
        "state": (
            "FUTURE_STRONG_AUTH_BINDING_INCOMPLETE"
            if blockers
            else "FUTURE_STRONG_AUTH_BINDING_RECORDED_NOT_VERIFIED"
        ),
        "blockers": blockers,
        "cryptographic_proof_verified": False,
        "strong_auth_verifier_implemented": False,
        "accepted_future_methods": sorted(FUTURE_PROOF_METHODS),
        "facial_recognition_accepted": False,
        "persistence_authorized": False,
        "ledger_write_performed": False,
        "step2_execution_authorized": False,
        "generic_language_is_authorization": False,
        "executes_action": False,
    }


def apply_step1_ledger_persistence(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    """Physical apply is not implemented. This function never writes a ledger."""
    return {
        "schema": SCHEMA,
        "state": "STEP1_LEDGER_PERSISTENCE_APPLY_REFUSED",
        "reason": "PHYSICAL_APPLY_NOT_IMPLEMENTED",
        "banner": "PERSISTENCE NOT AUTHORIZED",
        "persistence_authorized": False,
        "ledger_write_performed": False,
        "step2_execution_authorized": False,
        "executor_enabled": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "external_runtime_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "MAX_PREFLIGHT_STATE",
    "LOCK_NAME",
    "canonical_json",
    "recalculable_digest",
    "genesis_logical_payload",
    "ledger_writer_policy",
    "claim_local_writer_lock",
    "release_local_writer_lock",
    "build_ledger_writer_preflight",
    "recheck_writer_preflight",
    "evaluate_future_persistence_authorization",
    "apply_step1_ledger_persistence",
]
