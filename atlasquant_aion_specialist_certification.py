"""Certification gate for AION domain specialists.

Skill/plugin certification is a different contract. This gate records whether
Trader, Business and Investments proved routing, isolation, permissions, truth,
safety, tests and a real boolean human review. It does not activate a
specialist, call a tool, or widen authority.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

SCHEMA = "ATLASQUANT_AION_SPECIALIST_CERTIFICATION_V1"
STATES = ("CANDIDATE", "TESTED", "CERTIFIED", "SUSPENDED", "REVOKED")
SPECIALISTS = ("TRADER", "BUSINESS", "INVESTMENTS")
DIMENSIONS = ("routing", "isolation", "permissions", "truth", "safety", "tests")


def _clean(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _exact_true(value: Any) -> bool:
    return type(value) is bool and value is True


def _exact_false(value: Any) -> bool:
    return type(value) is bool and value is False


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def evidence_fingerprint(payload: Mapping[str, Any]) -> str:
    return sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _status(proven: Any, *, failed: bool = False) -> str:
    if failed:
        return "FAIL"
    if proven is True:
        return "PASS"
    return "NOT_EVIDENCED"


def _section(evidence: Mapping[str, Any], key: str) -> dict[str, Any]:
    return _mapping(evidence.get(key))


def _routing_status(evidence: Mapping[str, Any]) -> str:
    section = _section(evidence, "routing")
    if not section:
        return "NOT_EVIDENCED"
    selected = section.get("correct_specialist_selected")
    ambiguous = section.get("ambiguous_not_silently_selected")
    if not _exact_true(selected) or not _exact_true(ambiguous):
        return "FAIL" if selected is not None or ambiguous is not None else "NOT_EVIDENCED"
    return "PASS"


def _isolation_status(evidence: Mapping[str, Any]) -> str:
    section = _section(evidence, "isolation")
    if not section:
        return "NOT_EVIDENCED"
    required = ("memory_separated", "evidence_separated")
    if any(key not in section for key in required) or "automatic_cross_domain_access" not in section:
        return "NOT_EVIDENCED"
    if not all(_exact_true(section.get(key)) for key in required):
        return "FAIL"
    if not _exact_false(section.get("automatic_cross_domain_access")):
        return "FAIL"
    return "PASS"


def _permission_status(evidence: Mapping[str, Any]) -> str:
    section = _section(evidence, "permissions")
    if not section:
        return "NOT_EVIDENCED"
    keys = ("scope_escalated", "role_escalated", "undeclared_tool")
    if any(key not in section for key in keys):
        return "NOT_EVIDENCED"
    if any(not _exact_false(section.get(key)) for key in keys):
        return "FAIL"
    return "PASS"


def _truth_status(evidence: Mapping[str, Any]) -> str:
    section = _section(evidence, "truth")
    if not section:
        return "NOT_EVIDENCED"
    keys = ("unknown_promoted", "stale_promoted", "conflict_resolved_silently", "incomplete_promoted")
    if any(key not in section for key in keys):
        return "NOT_EVIDENCED"
    if any(not _exact_false(section.get(key)) for key in keys):
        return "FAIL"
    return "PASS"


def _safety_status(evidence: Mapping[str, Any]) -> str:
    section = _section(evidence, "safety")
    if not section:
        return "NOT_EVIDENCED"
    keys = (
        "real_trading_enabled",
        "payment_executed",
        "publication_executed",
        "deploy_executed",
        "external_side_effects",
    )
    if any(key not in section for key in keys):
        return "NOT_EVIDENCED"
    if any(not _exact_false(section.get(key)) for key in keys):
        return "FAIL"
    return "PASS"


def _test_status(evidence: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    section = _section(evidence, "tests")
    if not section:
        return "NOT_EVIDENCED", {}
    state = _clean(section.get("state"), 40).upper()
    suite = _clean(section.get("suite"), 180)
    fingerprint = _clean(section.get("fingerprint"), 128)
    provenance = _clean(section.get("provenance"), 240)
    version = _clean(section.get("version"), 80)
    sha = _clean(section.get("sha"), 80)
    refs = [_clean(item, 240) for item in list(section.get("refs") or [])[:20] if _clean(item, 240)]
    complete = (
        state == "PASS"
        and _exact_true(section.get("passed"))
        and bool(suite and fingerprint and provenance and version)
    )
    details = {
        "suite": suite,
        "fingerprint": fingerprint,
        "provenance": provenance,
        "version": version,
        "sha": sha,
        "refs": refs,
        "passed": _exact_true(section.get("passed")),
    }
    if not any((state, suite, fingerprint, provenance, version, section.get("passed") is not None)):
        return "NOT_EVIDENCED", details
    return ("PASS" if complete else "FAIL"), details


def _dimensions(evidence: Mapping[str, Any]) -> dict[str, str]:
    tests, _details = _test_status(evidence)
    return {
        "routing": _routing_status(evidence),
        "isolation": _isolation_status(evidence),
        "permissions": _permission_status(evidence),
        "truth": _truth_status(evidence),
        "safety": _safety_status(evidence),
        "tests": tests,
    }


def _inactive_flags() -> dict[str, Any]:
    return {
        "activates_specialist": False,
        "tool_called": False,
        "executes_action": False,
        "permissions_expanded": False,
        "real_trading_enabled": False,
        "payment_executed": False,
        "publication_executed": False,
        "external_action_executed": False,
        "deploy_executed": False,
        "provider_called": False,
    }


def assess_specialist_certification(
    specialist: Any,
    evidence: Mapping[str, Any] | None = None,
    *,
    human_review_approved: Any = None,
) -> dict[str, Any]:
    """Judge one specialist from explicit evidence. Missing proof stays uncertified."""
    payload = _mapping(evidence)
    name = _clean(specialist, 40).upper()
    review_value = payload.get("human_review_approved", False) if human_review_approved is None else human_review_approved
    review_approved = _exact_true(review_value)
    evidence_verified = _exact_true(payload.get("evidence_verified"))
    dimensions = _dimensions(payload)
    tests, test_details = _test_status(payload)
    technical_pass = all(dimensions[key] == "PASS" for key in DIMENSIONS) and evidence_verified
    record_state = _clean(payload.get("record_state"), 40).upper()
    if name not in SPECIALISTS:
        state = "CANDIDATE"
        technical_pass = False
    elif record_state == "REVOKED":
        state = "REVOKED"
    elif record_state == "SUSPENDED":
        state = "SUSPENDED"
    elif technical_pass and review_approved:
        state = "CERTIFIED"
    elif technical_pass:
        state = "TESTED"
    else:
        state = "CANDIDATE"
    return {
        "schema": SCHEMA,
        "specialist": name,
        "version": _clean(payload.get("version") or test_details.get("version"), 80),
        "state": state,
        "dimensions": dimensions,
        "tests_pass": tests == "PASS",
        "evidence_verified": evidence_verified,
        "human_review_approved": review_approved,
        "human_review_input_accepted": review_approved,
        "fingerprint": test_details.get("fingerprint", ""),
        "provenance": test_details.get("provenance", ""),
        "sha": test_details.get("sha", ""),
        "refs": list(test_details.get("refs") or []),
        "registered": name in SPECIALISTS,
        "runtime_activated": False,
        **_inactive_flags(),
    }


def _blank_row(specialist: str) -> dict[str, Any]:
    return {
        "specialist": specialist,
        "routing": "NOT_EVIDENCED",
        "isolation": "NOT_EVIDENCED",
        "permissions": "NOT_EVIDENCED",
        "truth": "NOT_EVIDENCED",
        "safety": "NOT_EVIDENCED",
        "tests": "NOT_EVIDENCED",
        "state": "NOT_CERTIFIED",
        "evidence": "NOT_EVIDENCED",
    }


def specialist_readiness_matrix(
    evidence_by_specialist: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Read-only matrix. PASS is copied from evidence, never invented from code presence."""
    supplied = _mapping(evidence_by_specialist)
    rows: dict[str, Any] = {}
    for specialist in SPECIALISTS:
        raw = supplied.get(specialist)
        if not isinstance(raw, Mapping):
            rows[specialist] = _blank_row(specialist)
            continue
        if raw.get("schema") == SCHEMA and isinstance(raw.get("dimensions"), Mapping):
            assessment = dict(raw)
            dimensions = {key: _clean(assessment["dimensions"].get(key), 40).upper() or "NOT_EVIDENCED" for key in DIMENSIONS}
            state = _clean(assessment.get("state"), 40).upper()
        else:
            review = raw.get("human_review_approved", False)
            assessment = assess_specialist_certification(specialist, raw, human_review_approved=review)
            dimensions = dict(assessment["dimensions"])
            state = assessment["state"]
        if state not in {"TESTED", "CERTIFIED", "SUSPENDED", "REVOKED"}:
            published_state = "NOT_CERTIFIED"
        else:
            published_state = state
        rows[specialist] = {
            "specialist": specialist,
            "routing": dimensions.get("routing", "NOT_EVIDENCED"),
            "isolation": dimensions.get("isolation", "NOT_EVIDENCED"),
            "permissions": dimensions.get("permissions", "NOT_EVIDENCED"),
            "truth": dimensions.get("truth", "NOT_EVIDENCED"),
            "safety": dimensions.get("safety", "NOT_EVIDENCED"),
            "tests": dimensions.get("tests", "NOT_EVIDENCED"),
            "state": published_state,
            "evidence": "EVIDENCED" if any(dimensions.get(key) == "PASS" for key in DIMENSIONS) else "NOT_EVIDENCED",
        }
    ready = all(
        row["state"] == "CERTIFIED" and all(row[key] == "PASS" for key in DIMENSIONS)
        for row in rows.values()
    )
    return {
        "schema": SCHEMA,
        "specialists": rows,
        "aggregate": "READY" if ready else "NOT_READY",
        "masks_uncertified_specialist": False,
        "code_presence_is_certification": False,
        **_inactive_flags(),
    }


__all__ = [
    "SCHEMA",
    "STATES",
    "SPECIALISTS",
    "DIMENSIONS",
    "evidence_fingerprint",
    "assess_specialist_certification",
    "specialist_readiness_matrix",
]
