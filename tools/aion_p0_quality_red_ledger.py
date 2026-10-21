"""Read-only AION P0 Quality RED evidence auditor; never grants worker authority.

A canonical failing test must remain visible. This tool does not skip tests,
reinterpret FAIL as PASS, change provider enrollment, or resolve homologation.
It compares exact unittest error/failed identifiers and validates source
counts and module selection. Use the *raw GitHub Actions job log* from the
canonical Quality job, not a screenshot or abridged/partial log.

Usage:
 python -B tools/aion_p0_quality_red_ledger.py --check-ledger
 python -B tools/aion_p0_quality_red_ledger.py --compare-log /path/job.log
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "docs/aion/evidence/aion_p0_quality_85_red_baseline_20261021.json"
SCHEMA = "aion.p0.quality.red_ledger.v1"
TEST_LINE = re.compile(r"\b(FAIL|ERROR): (test_[A-Za-z0-9_]+ \(.+\))\s*$")
MODULE_LINE = re.compile(r"\bAION_P0_CANONICAL_UNMODIFIED_MODULES\s+(\d+)\b")
HEAD_LINE = re.compile(r"\bAION_P0_CANONICAL_ROOT_HEAD\s+([0-9a-f]{40})\b")
RUN_LINE = re.compile(r"\bRan\s+(\d+)\s+tests\s+in\s+[\d.]+s\b")
FAIL_LINE = re.compile(r"\bFAILED\s+\(failures=(\d+),\s*errors=(\d+)\)")
CATEGORIES = {
    "INDEPENDENT_PRODUCER_GATE",
    "LEGACY_ACTIVATION_PLAN_EXPECTATION",
    "LEGACY_WORKER_EXPECTATION",
}


class EvidenceError(ValueError):
    """Fail closed on missing, ambiguous, duplicate or truncated evidence."""


def validate_ledger(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("schema") != SCHEMA:
        raise EvidenceError("LEDGER_SCHEMA_INVALID")
    b = raw.get("baseline")
    records = raw.get("entries")
    policy = raw.get("rules")
    if not isinstance(b, dict) or not isinstance(records, list) or not isinstance(policy, dict):
        raise EvidenceError("LEDGER_STRUCTURE_INVALID")
    if policy.get("workflow_governance") != "HARD_NO_GO":
        raise EvidenceError("LEDGER_NO_GO_MISSING")
    if policy.get("worker_enabled") is not False or policy.get("automatic_resend_allowed") is not False:
        raise EvidenceError("LEDGER_UNSAFE_AUTHORITY_CLAIM")
    if policy.get("legacy_tests_waived") is not False:
        raise EvidenceError("LEDGER_MUST_NOT_WAIVE_LEGACY_TESTS")
    if policy.get("removing_failures_requires_manual_evidence") is not True:
        raise EvidenceError("LEDGER_REMOVAL_REVIEW_REQUIRED")
    totals = (b.get("modules"), b.get("tests"), b.get("pass"), b.get("fail"), b.get("error"))
    if totals != (588, 6895, 6810, 51, 34):
        raise EvidenceError("LEDGER_COUNTS_CHANGED")
    if not isinstance(b.get("head_sha"), str) or not re.fullmatch(r"[0-9a-f]{40}", b["head_sha"]):
        raise EvidenceError("LEDGER_SHA_INVALID")
    if len(records) != b["fail"] + b["error"]:
        raise EvidenceError("LEDGER_RECORD_COUNT_MISMATCH")
    ids: list[str] = []
    kinds: list[str] = []
    for r in records:
        if not isinstance(r, dict) or r.get("family") not in CATEGORIES:
            raise EvidenceError("LEDGER_CATEGORY_INVALID")
        identifier = r.get("identifier")
        if not isinstance(identifier, str) or TEST_LINE.search(identifier) is None:
            raise EvidenceError("LEDGER_IDENTIFIER_INVALID")
        kind = identifier.split(":", 1)[0]
        if kind != r.get("kind"):
            raise EvidenceError("LEDGER_KIND_INVALID")
        match = re.search(r"\((test_[A-Za-z0-9_]+)\.", identifier)
        if match is None or match.group(1) != r.get("module"):
            raise EvidenceError("LEDGER_MODULE_INVALID")
        if not isinstance(r.get("observed_exception"), str):
            raise EvidenceError("LEDGER_CAUSE_UNREADABLE")
        ids.append(identifier)
        kinds.append(kind)
    if len(set(ids)) != len(ids):
        raise EvidenceError("LEDGER_DUPLICATE_IDENTIFIER")
    if Counter(kinds) != Counter({"FAIL": b["fail"], "ERROR": b["error"]}):
        raise EvidenceError("LEDGER_KIND_COUNTS_MISMATCH")
    return raw


def extract_canonical_job(log: str) -> dict[str, Any]:
    """Require complete 588-module/6895-test Quality output, not A79 alone."""
    if not isinstance(log, str) or not log.strip():
        raise EvidenceError("CANONICAL_LOG_UNAVAILABLE")
    lines = log.splitlines()
    modules = [int(m.group(1)) for l in lines if (m := MODULE_LINE.search(l))]
    heads = [m.group(1) for l in lines if (m := HEAD_LINE.search(l))]
    totals = [int(m.group(1)) for l in lines if (m := RUN_LINE.search(l))]
    failures = [tuple(map(int, m.groups())) for l in lines if (m := FAIL_LINE.search(l))]
    if len(modules) != 1 or len(heads) != 1 or len(failures) != 1:
        raise EvidenceError("CANONICAL_LOG_INCOMPLETE_OR_AMBIGUOUS")
    if modules[0] != 588 or 6895 not in totals:
        raise EvidenceError("CANONICAL_LOG_WRONG_SUITE")
    identifiers = []
    for line in lines:
        match = TEST_LINE.search(line)
        if match:
            identifiers.append(f"{match.group(1)}: {match.group(2)}")
    if len(identifiers) != len(set(identifiers)):
        raise EvidenceError("CANONICAL_DUPLICATE_IDENTIFIERS")
    if len(identifiers) != sum(failures[0]):
        raise EvidenceError("CANONICAL_FAILURE_HEADERS_INCOMPLETE")
    if Counter(x.split(":", 1)[0] for x in identifiers) != Counter(
        {"FAIL": failures[0][0], "ERROR": failures[0][1]}
    ):
        raise EvidenceError("CANONICAL_FAILURE_HEADER_COUNTS_INCONSISTENT")
    return {
        "head_sha": heads[0],
        "modules": modules[0],
        "tests": 6895,
        "fail": failures[0][0],
        "error": failures[0][1],
        "identifiers": sorted(identifiers),
    }


def compare_log(baseline: dict[str, Any], log: str) -> dict[str, Any]:
    validate_ledger(baseline)
    parsed = extract_canonical_job(log)
    old = {r["identifier"] for r in baseline["entries"]}
    new = set(parsed["identifiers"])
    new_ids = sorted(new - old)
    missing_ids = sorted(old - new)
    # A disappeared failure is NOT auto-homologated or proof of a fix.
    # An added failure must never be hidden by an unchanged total count.
    equal = (
        not new_ids and not missing_ids
        and parsed["fail"] == baseline["baseline"]["fail"]
        and parsed["error"] == baseline["baseline"]["error"]
    )
    return {
        "schema": SCHEMA + ".comparison",
        "current_head_sha": parsed["head_sha"],
        "baseline_head_sha": baseline["baseline"]["head_sha"],
        "same_identifiers": equal,
        "added_failure_identifiers": new_ids,
        "missing_failure_identifiers_require_manual_review": missing_ids,
        "current_fail": parsed["fail"],
        "current_error": parsed["error"],
        "quality_pass": False,
        "worker_activation_allowed": False,
        "auto_resend_allowed": False,
        "homologated_p0_count": 0,
        "governance": "HARD_NO_GO",
        "verdict": "STABLE_RED_NO_HOMOLOGATION" if equal else "RED_DRIFT_MANUAL_REVIEW",
    }


def load_ledger(path: Path = BASELINE) -> dict[str, Any]:
    return validate_ledger(json.loads(path.read_text(encoding="utf-8")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check-ledger", action="store_true")
    action.add_argument("--compare-log", type=Path)
    args = parser.parse_args(argv)
    try:
        baseline = load_ledger(args.baseline)
        if args.check_ledger:
            output = {
                "valid": True,
                "entries": len(baseline["entries"]),
                "categories": dict(Counter(v["family"] for v in baseline["entries"])),
                "governance": "HARD_NO_GO",
                "quality_pass": False,
            }
            status = 0
        else:
            output = compare_log(baseline, args.compare_log.read_text(encoding="utf-8"))
            status = 0 if output["same_identifiers"] else 2
        print(json.dumps(output, indent=2, sort_keys=True))
        return status
    except (EvidenceError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc), "governance": "HARD_NO_GO", "quality_pass": False}), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
