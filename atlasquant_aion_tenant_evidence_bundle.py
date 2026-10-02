"""Portable local evidence bundle for AION tenant persistence.

The bundle binds persistence evidence to normalized source-file digests and a
real test-result digest. It is evidence for admin review only, never authority.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence
import hashlib
import json
import re

from atlasquant_aion_tenant_evidence_binding import (
    EVIDENCE_KINDS,
    build_evidence_record,
    validate_evidence_record,
)

SCHEMA = "ATLASQUANT_AION_TENANT_LOCAL_EVIDENCE_BUNDLE_V1"
_DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
_HEAD = re.compile(r"^[0-9a-f]{40}$")

SUBJECT_FILES = {
    "IDENTITY_REGISTRY": (
        "atlasquant_aion_tenant.py",
        "atlasquant_aion_tenant_durable_store.py",
    ),

    "ACL_STORE": (
        "atlasquant_aion_tenant_durable_store.py",
        "atlasquant_aion_tenant_persistence_gate.py",
    ),
    "DURABLE_STORE": (
        "atlasquant_aion_tenant_durable_store.py",
        "atlasquant_aion_tenant_store.py",
    ),
    "TENANT_E2E": (
        "atlasquant_aion_tenant_durable_store.py",
        "test_atlasquant_aion_tenant_durable_store.py",
    ),
    "BACKUP_RESTORE": (
        "atlasquant_aion_tenant_durable_store.py",
        "test_atlasquant_aion_tenant_durable_store.py",
    ),
    "REVOCATION_REPLAY": (
        "atlasquant_aion_entitlements.py",
        "atlasquant_aion_tenant_durable_store.py",
        "test_atlasquant_aion_tenant_durable_store.py",
    ),
}

def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), default=str,
    ).encode("utf-8")

def _sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()

def normalized_file_digest(root: Path, relative: str) -> str:
    path = (root / relative).resolve()
    if path.parent != root.resolve() and root.resolve() not in path.parents:
        raise ValueError("evidence path escaped repository root")
    text = path.read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def subject_digest(
    root: str | Path,
    files: Sequence[str],
) -> tuple[str, dict[str, str]]:
    base = Path(root).resolve()
    manifest = {
        str(relative): normalized_file_digest(base, str(relative))
        for relative in files
    }
    return _sha(manifest), manifest

def build_local_evidence_bundle(
    root: str | Path,
    *,
    result_digest: str,
    test_count: int,
    source_head_sha: str,
    generated_at: str,
) -> dict[str, Any]:

    result = str(result_digest or "").strip().lower()
    head = str(source_head_sha or "").strip().lower()
    if not _DIGEST.fullmatch(result):
        raise ValueError("invalid test result digest")
    if not _HEAD.fullmatch(head):
        raise ValueError("invalid source head sha")
    if int(test_count) <= 0:
        raise ValueError("test count must be positive")
    if not str(generated_at or "").strip():
        raise ValueError("generated_at required")

    records: dict[str, Any] = {}
    subjects: dict[str, Any] = {}
    for kind in EVIDENCE_KINDS:
        digest, manifest = subject_digest(root, SUBJECT_FILES[kind])
        subjects[kind] = {"digest": digest, "files": manifest}
        records[kind] = build_evidence_record(
            kind,
            subject_digest=digest,
            result_digest=result,
            test_count=int(test_count),
            producer="LOCAL_TEST_SUITE_V1",
        )

    body = {
        "schema": SCHEMA,
        "source_head_sha": head,
        "generated_at": str(generated_at),
        "result_digest": result,
        "test_count": int(test_count),
        "subjects": subjects,
        "records": records,

        "controls": {
            "manual_review_required": True,
            "evidence_is_authority": False,
            "automatic_activation": False,
            "production_persistence_activated": False,
        },
    }
    return {**body, "bundle_digest": _sha(body)}

def verify_local_evidence_bundle(
    root: str | Path,
    bundle: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = dict(bundle or {})
    reasons: list[str] = []
    if row.get("schema") != SCHEMA:
        reasons.append("SCHEMA_INVALID")
    supplied = str(row.get("bundle_digest") or "").strip().lower()
    body = dict(row)
    body.pop("bundle_digest", None)
    if not _DIGEST.fullmatch(supplied):
        reasons.append("BUNDLE_DIGEST_INVALID")
    elif supplied != _sha(body):
        reasons.append("BUNDLE_DIGEST_MISMATCH")
    if not _HEAD.fullmatch(str(row.get("source_head_sha") or "").strip().lower()):
        reasons.append("SOURCE_HEAD_INVALID")

    controls = dict(row.get("controls") or {})
    if controls.get("evidence_is_authority") is not False:
        reasons.append("AUTHORITY_FORBIDDEN")
    if controls.get("automatic_activation") is not False:
        reasons.append("AUTO_ACTIVATION_FORBIDDEN")

    records = dict(row.get("records") or {})
    subjects = dict(row.get("subjects") or {})
    for kind in EVIDENCE_KINDS:
        checked = validate_evidence_record(records.get(kind), expected_kind=kind)
        if checked.get("valid") is not True:
            reasons.append(f"{kind}_RECORD_INVALID")
            continue
        try:
            expected_digest, expected_files = subject_digest(root, SUBJECT_FILES[kind])
        except Exception:
            reasons.append(f"{kind}_SOURCE_UNAVAILABLE")
            continue
        subject = dict(subjects.get(kind) or {})
        if subject.get("digest") != expected_digest:
            reasons.append(f"{kind}_SUBJECT_STALE")
        if dict(subject.get("files") or {}) != expected_files:
            reasons.append(f"{kind}_FILE_MANIFEST_STALE")
        if checked.get("subject_digest") != expected_digest:
            reasons.append(f"{kind}_RECORD_SUBJECT_STALE")

    return {
        "valid": not reasons,
        "reasons": list(dict.fromkeys(reasons)),
        "bundle_digest": supplied if not reasons else "",
        "evidence_is_authority": False,
        "automatic_activation": False,
    }

__all__ = [
    "SCHEMA", "SUBJECT_FILES", "normalized_file_digest", "subject_digest",
    "build_local_evidence_bundle", "verify_local_evidence_bundle",
]
