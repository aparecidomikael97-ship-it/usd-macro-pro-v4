"""External evidence bridge for AION BUSINESS certification.

This module does not perform network I/O itself. It accepts a read-only source
reader supplied by the host, validates GitHub Actions evidence for an exact SHA,
and returns the trusted verifier shape consumed by the BUSINESS certification
package. No runtime activation or external action is authorized here.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from atlasquant_aion_business_certification_package import (
    ATTESTATION_SCHEMA,
    EVIDENCE_ID,
    PROVENANCE,
    SUITE,
    VERSION,
    build_business_specialist_evidence,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_EXTERNAL_ATTESTATION_V1"
REPOSITORY_FULL_NAME = "aparecidomikael97-ship-it/usd-macro-pro-v4"
REQUIRED_WORKFLOWS = {
    ".github/workflows/quality-tests.yml": "Quality tests",
    ".github/workflows/aion-core-security-gate.yml": "AION Core Security Gate",
    ".github/workflows/atlasquant-release-readiness.yml": "AtlasQuant - Release Readiness",
}
MAX_RUNS = 30


def _clean(value: Any, limit: int = 300) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _exact_true(value: Any) -> bool:
    return type(value) is bool and value is True


def _sequence(value: Any) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return list(value)[:MAX_RUNS]


def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def build_business_ci_attestation_candidate(
    *,
    sha: str,
    refs: Sequence[str],
    test_count: int,
) -> dict[str, Any]:
    """Build the payload whose truth must still be confirmed by the source reader."""
    clean_sha = _clean(sha, 80).lower()
    clean_refs = sorted({_clean(item, 300) for item in refs if _clean(item, 300)})
    count = _int(test_count)
    candidate = {
        "schema": ATTESTATION_SCHEMA,
        "state": "VERIFIED",
        "tests_passed": True,
        "evidence_verified": True,
        "provenance_verified": True,
        "specialist": "BUSINESS",
        "version": VERSION,
        "suite": SUITE,
        "provenance": PROVENANCE,
        "evidence_id": EVIDENCE_ID,
        "sha": clean_sha,
        "refs": clean_refs,
        "fingerprint": "",
        "test_count": count,
    }
    evidence = build_business_specialist_evidence(candidate)
    candidate["fingerprint"] = evidence["tests"]["fingerprint"]
    return candidate


def _run_key(run: Mapping[str, Any]) -> tuple[int, int]:
    return (_int(run.get("run_attempt")), _int(run.get("id")))


def _normalize_run(raw: Any) -> dict[str, Any]:
    run = dict(raw) if isinstance(raw, Mapping) else {}
    path = _clean(run.get("path") or run.get("workflow_path"), 220)
    return {
        "id": _int(run.get("id")),
        "run_attempt": _int(run.get("run_attempt")),
        "name": _clean(run.get("name"), 160),
        "path": path,
        "event": _clean(run.get("event"), 60),
        "status": _clean(run.get("status"), 40),
        "conclusion": _clean(run.get("conclusion"), 40),
        "head_sha": _clean(run.get("head_sha"), 80).lower(),
        "repository_full_name": _clean(
            run.get("repository_full_name")
            or (run.get("repository") or {}).get("full_name")
            if isinstance(run.get("repository"), Mapping)
            else run.get("repository_full_name"),
            220,
        ),
        "html_url": _clean(run.get("html_url"), 400),
    }


def verify_github_actions_source(
    record: Mapping[str, Any],
    source: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Validate externally read GitHub Actions state against one certification record."""
    data = dict(source or {}) if isinstance(source, Mapping) else {}
    sha = _clean(record.get("sha"), 80).lower()
    source_repo = _clean(data.get("repository_full_name"), 220)
    source_sha = _clean(data.get("sha"), 80).lower()
    test_count = _int(data.get("quality_test_count"))
    runs = [_normalize_run(item) for item in _sequence(data.get("runs"))]

    latest_by_path: dict[str, dict[str, Any]] = {}
    for run in runs:
        path = run["path"]
        if path not in REQUIRED_WORKFLOWS:
            continue
        current = latest_by_path.get(path)
        if current is None or _run_key(run) > _run_key(current):
            latest_by_path[path] = run

    workflow_states: dict[str, dict[str, Any]] = {}
    workflows_ok = True
    for path, expected_name in REQUIRED_WORKFLOWS.items():
        run = latest_by_path.get(path)
        if not run:
            workflows_ok = False
            workflow_states[path] = {
                "present": False,
                "verified": False,
                "name": expected_name,
                "run_id": 0,
            }
            continue
        verified = bool(
            run["name"] == expected_name
            and run["head_sha"] == sha
            and run["status"] == "completed"
            and run["conclusion"] == "success"
            and run["event"] in {"pull_request", "push", "workflow_dispatch"}
            and (not run["repository_full_name"] or run["repository_full_name"] == REPOSITORY_FULL_NAME)
            and run["id"] > 0
        )
        workflows_ok = workflows_ok and verified
        workflow_states[path] = {
            "present": True,
            "verified": verified,
            "name": run["name"],
            "run_id": run["id"],
            "run_attempt": run["run_attempt"],
            "event": run["event"],
            "conclusion": run["conclusion"],
            "html_url": run["html_url"],
        }

    valid = bool(
        _clean(record.get("schema"), 120) == ATTESTATION_SCHEMA
        and _clean(record.get("specialist"), 40).upper() == "BUSINESS"
        and _clean(record.get("version"), 80) == VERSION
        and _clean(record.get("suite"), 180) == SUITE
        and _clean(record.get("provenance"), 240) == PROVENANCE
        and _clean(record.get("evidence_id"), 80) == EVIDENCE_ID
        and source_repo == REPOSITORY_FULL_NAME
        and source_sha == sha
        and workflows_ok
        and test_count > 0
        and _clean(record.get("fingerprint"), 128)
    )
    return {
        "schema": SCHEMA,
        "state": "VERIFIED" if valid else "REJECTED",
        "valid": valid,
        "repository_full_name": source_repo,
        "sha": source_sha if valid else "",
        "quality_test_count": test_count if valid else 0,
        "workflow_states": workflow_states,
        "provider_called": False,
        "external_write": False,
        "runtime_activated": False,
    }


def github_actions_business_ci_verifier(
    source_reader: Callable[[Mapping[str, Any]], Mapping[str, Any]],
):
    """Return the trusted verifier consumed by business_attestation_verifier()."""
    def verify(record: Mapping[str, Any]) -> dict[str, Any]:
        source: Mapping[str, Any] = {}
        reader_error = False
        if callable(source_reader):
            try:
                raw = source_reader({
                    "repository_full_name": REPOSITORY_FULL_NAME,
                    "sha": _clean(record.get("sha"), 80).lower(),
                    "required_workflows": dict(REQUIRED_WORKFLOWS),
                })
            except Exception:
                raw = {}
                reader_error = True
            if isinstance(raw, Mapping):
                source = raw
            else:
                reader_error = True
        else:
            reader_error = True

        checked = verify_github_actions_source(record, source)
        valid = checked["valid"] and not reader_error
        refs = record.get("refs") if isinstance(record.get("refs"), Sequence) and not isinstance(record.get("refs"), (str, bytes, bytearray)) else []
        return {
            "state": "VERIFIED" if valid else "REJECTED",
            "provenance_verified": valid,
            "evidence_verified": valid,
            "specialist": "BUSINESS",
            "version": VERSION,
            "suite": SUITE,
            "evidence_id": EVIDENCE_ID,
            "sha": _clean(record.get("sha"), 80).lower() if valid else "",
            "bound_refs": sorted({_clean(item, 300) for item in refs if _clean(item, 300)}) if valid else [],
            "fingerprint": _clean(record.get("fingerprint"), 128).lower() if valid else "",
            "source_state": checked["state"],
            "quality_test_count": checked["quality_test_count"],
            "workflow_states": checked["workflow_states"],
            "reader_error": reader_error,
            "provider_called": False,
            "external_write": False,
            "runtime_activated": False,
        }

    return verify


__all__ = [
    "SCHEMA",
    "REPOSITORY_FULL_NAME",
    "REQUIRED_WORKFLOWS",
    "build_business_ci_attestation_candidate",
    "verify_github_actions_source",
    "github_actions_business_ci_verifier",
]
