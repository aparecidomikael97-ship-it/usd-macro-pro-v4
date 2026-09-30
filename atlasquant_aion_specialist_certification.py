"""Certification gate for AION domain specialists.

Skill/plugin certification is a different contract. This gate records whether
Trader, Business and Investments proved routing, isolation, permissions, truth,
safety, tests and a real boolean human review. It does not activate a
specialist, call a tool, or widen authority.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Callable, Mapping, Sequence
import json
import re

SCHEMA = "ATLASQUANT_AION_SPECIALIST_CERTIFICATION_V1"
STATES = ("CANDIDATE", "TESTED", "CERTIFIED", "SUSPENDED", "REVOKED")
SPECIALISTS = ("TRADER", "BUSINESS", "INVESTMENTS")
DIMENSIONS = ("routing", "isolation", "permissions", "truth", "safety", "tests")
_SHA = re.compile(r"^[0-9a-f]{7,64}$")


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


def _refs(values: Any) -> list[str]:
    found: list[str] = []
    for raw in list(values or [])[:20]:
        text = _clean(raw, 240)
        if text and text not in found:
            found.append(text)
    return sorted(found)


def evidence_body(specialist: Any, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Canonical proof body. Claimed fingerprint, provenance and review stay outside it."""
    payload = _mapping(evidence)
    tests = _section(payload, "tests")
    version = _clean(payload.get("version") or tests.get("version"), 80)
    return {
        "specialist": _clean(specialist or payload.get("specialist"), 40).upper(),
        "version": version,
        "routing": _section(payload, "routing"),
        "isolation": _section(payload, "isolation"),
        "permissions": _section(payload, "permissions"),
        "truth": _section(payload, "truth"),
        "safety": _section(payload, "safety"),
        "tests": {
            "state": _clean(tests.get("state"), 40).upper(),
            "passed": tests.get("passed") is True,
            "suite": _clean(tests.get("suite"), 180),
            "version": _clean(tests.get("version") or version, 80),
            "sha": _clean(tests.get("sha"), 80).lower(),
            "refs": _refs(tests.get("refs")),
            "evidence_id": _clean(tests.get("evidence_id") or payload.get("evidence_id"), 80),
        },
    }


def evidence_fingerprint(payload: Mapping[str, Any], *, specialist: str = "") -> str:
    tests = _mapping(payload.get("tests"))
    already_body = bool(
        payload.get("specialist")
        and "routing" in payload
        and "fingerprint" not in tests
        and "provenance" not in tests
    )
    body = payload if already_body else evidence_body(specialist or payload.get("specialist"), payload)
    return sha256(_canonical(body).encode("utf-8")).hexdigest()


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


def _test_details(evidence: Mapping[str, Any]) -> dict[str, Any]:
    section = _section(evidence, "tests")
    return {
        "state": _clean(section.get("state"), 40).upper(),
        "suite": _clean(section.get("suite"), 180),
        "fingerprint": _clean(section.get("fingerprint"), 128).lower(),
        "provenance": _clean(section.get("provenance"), 240),
        "version": _clean(section.get("version"), 80),
        "sha": _clean(section.get("sha"), 80).lower(),
        "refs": _refs(section.get("refs")),
        "passed": _exact_true(section.get("passed")),
        "present": bool(section),
    }


def _verify_proof(
    specialist: str,
    evidence: Mapping[str, Any],
    verifier: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None,
) -> dict[str, Any]:
    details = _test_details(evidence)
    body = evidence_body(specialist, evidence)
    calculated = evidence_fingerprint(body)
    fingerprint_ok = bool(details["fingerprint"]) and details["fingerprint"] == calculated
    sha_present = bool(details["sha"])
    sha_ok = (not sha_present) or bool(_SHA.fullmatch(details["sha"]))
    verifier_result: Mapping[str, Any] = {}
    verifier_error = False
    if callable(verifier):
        try:
            raw = verifier({
                "specialist": body["specialist"],
                "version": body["version"],
                "fingerprint": calculated,
                "claimed_fingerprint": details["fingerprint"],
                "provenance": details["provenance"],
                "sha": details["sha"],
                "refs": details["refs"],
                "body": body,
            })
        except Exception:
            raw = {}
            verifier_error = True
        if isinstance(raw, Mapping):
            verifier_result = raw
        else:
            verifier_error = True
    source_refs = _section(evidence, "tests").get("refs")
    if isinstance(source_refs, (list, tuple)):
        refs_overflow = len(source_refs) > 20 or any(len(str(item or "")) > 240 for item in source_refs[:40])
    else:
        refs_overflow = source_refs not in (None, "")
    payload_version = _clean(evidence.get("version"), 80)
    version_conflict = bool(payload_version and details["version"] and payload_version != details["version"])
    verifier_fingerprint = _clean(verifier_result.get("fingerprint"), 128).lower()
    verifier_sha = _clean(verifier_result.get("sha"), 80).lower()
    bound_refs = _refs(verifier_result.get("bound_refs"))
    provenance_ok = _exact_true(verifier_result.get("provenance_verified"))
    evidence_ok = _exact_true(verifier_result.get("evidence_verified"))
    state_ok = verifier_result.get("state") == "VERIFIED"
    fingerprint_bound = verifier_fingerprint == calculated
    refs_ok = (not details["refs"]) or bound_refs == details["refs"]
    sha_bound = (not sha_present) or (sha_ok and verifier_sha == details["sha"])
    echo_ok = (
        _clean(verifier_result.get("specialist"), 40).upper() == body["specialist"]
        and _clean(verifier_result.get("version"), 80) == body["version"]
        and _clean(verifier_result.get("suite"), 180) == details["suite"]
        and _clean(verifier_result.get("evidence_id"), 80) == body["tests"]["evidence_id"]
    )
    verified = bool(
        state_ok and provenance_ok and evidence_ok and fingerprint_bound and fingerprint_ok
        and refs_ok and sha_bound and echo_ok and not refs_overflow and not version_conflict
        and sha_ok and not verifier_error
    )
    claimed = details["present"] and (
        details["state"] or details["suite"] or details["fingerprint"] or details["provenance"] or details["version"] or details["passed"]
    )
    tests_pass = bool(
        details["state"] == "PASS"
        and details["passed"]
        and details["suite"]
        and details["version"]
        and fingerprint_ok
        and verified
        and sha_ok
        and not refs_overflow
        and not version_conflict
        and body["specialist"] == specialist
    )
    if not claimed:
        tests_state = "NOT_EVIDENCED"
    elif tests_pass:
        tests_state = "PASS"
    else:
        tests_state = "FAIL"
    return {
        "tests_state": tests_state,
        "tests_pass": tests_pass,
        "evidence_verified": verified,
        "fingerprint": calculated if fingerprint_ok else details["fingerprint"],
        "calculated_fingerprint": calculated,
        "fingerprint_matches": fingerprint_ok,
        "provenance": details["provenance"],
        "provenance_verified": provenance_ok and state_ok,
        "sha": details["sha"],
        "refs": details["refs"],
        "version": details["version"] or body["version"],
        "suite": details["suite"],
        "verifier_error": verifier_error,
    }


def _dimensions(evidence: Mapping[str, Any], tests_state: str) -> dict[str, str]:
    return {
        "routing": _routing_status(evidence),
        "isolation": _isolation_status(evidence),
        "permissions": _permission_status(evidence),
        "truth": _truth_status(evidence),
        "safety": _safety_status(evidence),
        "tests": tests_state,
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
    evidence_verifier: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Judge one specialist from bound evidence. A self-declared payload is not proof."""
    payload = _mapping(evidence)
    name = _clean(specialist, 40).upper()
    review_value = payload.get("human_review_approved", False) if human_review_approved is None else human_review_approved
    review_approved = _exact_true(review_value)
    proof = _verify_proof(name, payload, evidence_verifier)
    dimensions = _dimensions(payload, proof["tests_state"])
    technical_pass = all(dimensions[key] == "PASS" for key in DIMENSIONS) and proof["evidence_verified"] is True
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
        "version": _clean(payload.get("version") or proof.get("version"), 80),
        "state": state,
        "dimensions": dimensions,
        "tests_pass": proof["tests_pass"] is True,
        "evidence_verified": proof["evidence_verified"] is True,
        "human_review_approved": review_approved,
        "human_review_input_accepted": review_approved,
        "fingerprint": proof["calculated_fingerprint"],
        "claimed_fingerprint": _test_details(payload)["fingerprint"],
        "fingerprint_matches": proof["fingerprint_matches"] is True,
        "provenance": proof["provenance"],
        "provenance_verified": proof["provenance_verified"] is True,
        "sha": proof["sha"],
        "refs": list(proof["refs"]),
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
    *,
    evidence_verifier: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Read-only matrix. PASS is copied from verified evidence, never from code presence."""
    supplied = _mapping(evidence_by_specialist)
    rows: dict[str, Any] = {}
    for specialist in SPECIALISTS:
        raw = supplied.get(specialist)
        if not isinstance(raw, Mapping):
            rows[specialist] = _blank_row(specialist)
            continue
        review = raw.get("human_review_approved", False)
        assessment = assess_specialist_certification(
            specialist,
            raw,
            human_review_approved=review,
            evidence_verifier=evidence_verifier,
        )
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
    "evidence_body",
    "evidence_fingerprint",
    "assess_specialist_certification",
    "specialist_readiness_matrix",
]
