"""P0/H0 READ-ONLY provider evidence crosswalk audit (NOT an admission gate).

Links every historical external producer error to an exact current canonical
Quality failure, without upgrading paper claims to real provider authority.

Never reads credentials, network, provider SDK, SQLite, Worker or service.
Never approves dispatch, retry, reactivation, receipt or effect claims.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs/aion/evidence/aion_p0_h0_32_provider_errors_current_6895_crosswalk_20261021.json"
LEDGER = ROOT / "docs/aion/evidence/aion_p0_quality_85_red_baseline_20261021.json"
HISTORICAL = ROOT / "docs/aion/AION_P0_32_EXTERNAL_PRODUCER_EVIDENCE_MATRIX_20261020.json"
SCHEMA = "AION_P0_H0_32_CURRENT_PROVIDER_BLOCKER_CROSSWALK_LAB_V1"
GATE_COUNTS = {
    "PRE_ADAPTER_PRODUCER_ENROLLMENT": 23,
    "CAUSAL_COMMITTED_EFFECT_RECEIPT": 8,
    "TERMINAL_NO_EFFECT_FENCE": 1,
}
FORBIDDEN_NEGATIVE = {"404", "empty_list", "timeout", "to_from_date_filters", "no_immediate_result"}
PROHIBITIONS = (
    "approved_for_real_send", "producer_enrolled_independently",
    "external_receipt_authenticated", "external_no_effect_fence_verified",
    "human_owner_authenticated", "worker_allowed",
    "automatic_resend_allowed",
)


class CrosswalkError(ValueError):
    """An incomplete/mismatched provider-error inventory is not admissible."""


def _expect_exact_false(d: dict, names: tuple[str, ...], code: str) -> None:
    if any(d.get(n) is not False for n in names):
        raise CrosswalkError(code)


def _expected_identifier(case: dict) -> str:
    try:
        c=case["class_name"]
        module=case["module"]
        name=case["test_method"]
        sub=case["subtest_context"]
    except (KeyError, TypeError) as exc:
        raise CrosswalkError("HISTORICAL_CASE_STRUCTURE_INVALID") from exc
    return (
        f"ERROR: {name} ({module}.{c}.{name})"
        + (f" ({sub})" if sub else "")
    )


def audit(
    proposal: dict[str, Any], ledger: dict[str, Any], historical: dict[str, Any],
) -> dict[str, Any]:
    if not all(isinstance(x, dict) for x in (proposal, ledger, historical)):
        raise CrosswalkError("CROSSWALK_INVALID_OBJECT")
    if proposal.get("schema") != SCHEMA:
        raise CrosswalkError("CROSSWALK_SCHEMA_INVALID")
    if ledger.get("schema") != "aion.p0.quality.red_ledger.v1":
        raise CrosswalkError("CURRENT_QUALITY_LEDGER_SCHEMA_INVALID")
    if historical.get("schema") != "AION_P0_32_EXTERNAL_PRODUCER_EVIDENCE_REQUIREMENTS_LAB_V1":
        raise CrosswalkError("HISTORICAL_MATRIX_SCHEMA_INVALID")
    quality = ledger.get("baseline", {})
    source = proposal.get("sources", {})
    expected_origin = {
        "current_85_ledger": str(LEDGER.relative_to(ROOT)),
        "current_quality_sha": quality.get("head_sha"),
        "current_quality_run": quality.get("workflow_run"),
        "current_quality_job": quality.get("job_id"),
        "current_quality_tests": quality.get("tests"),
        "legacy_32_matrix": str(HISTORICAL.relative_to(ROOT)),
        "legacy_matrix_origin_sha": historical.get("source_commit"),
        "legacy_matrix_origin_run": historical.get("source_run"),
        "legacy_quality_tests": historical.get("historical_quality", {}).get("tests"),
        "verified_current_quality_sha": "a4789ab097f7a80bc6b25da9b893ed312b03f794",
        "verified_current_quality_run": 39638294268,
        "verified_current_quality_job": 119354806058,
        "verified_current_quality_tests": 6895,
    }
    if source != expected_origin or quality.get("tests") != 6895:
        raise CrosswalkError("CROSSWALK_PROVENANCE_MISMATCH")

    current = ledger.get("entries")
    original = historical.get("cases")
    entries = proposal.get("cases")
    if not (isinstance(current,list) and isinstance(original,list) and isinstance(entries,list)):
        raise CrosswalkError("CROSSWALK_MISSING_CASES")
    current_errors = {x.get("identifier"):x for x in current
                      if isinstance(x,dict) and x.get("family")=="INDEPENDENT_PRODUCER_GATE"}
    legacy_cases = {x.get("case_id"):x for x in original if isinstance(x,dict)}
    new_cases = {x.get("case_id"):x for x in entries if isinstance(x,dict)}
    if (
        len(current_errors)!=32 or len(original)!=32 or len(entries)!=32
        or len(legacy_cases)!=32 or len(new_cases)!=32
        or set(new_cases)!=set(legacy_cases)
    ):
        raise CrosswalkError("CROSSWALK_32_ONE_TO_ONE_REQUIRED")

    matched=set()
    gate_counts=Counter()
    for case_id, historical_case in legacy_cases.items():
        record = new_cases[case_id]
        ident = _expected_identifier(historical_case)
        actual = current_errors.get(ident)
        if actual is None:
            raise CrosswalkError("CROSSWALK_CURRENT_CASE_UNMATCHED")
        if ident in matched:
            raise CrosswalkError("CROSSWALK_DUPLICATE_CURRENT_IDENTIFIER")
        matched.add(ident)
        expected = {
            "case_id":case_id,
            "current_identifier":ident,
            "current_error":actual.get("observed_exception"),
            "current_module":actual.get("module"),
            "old_gate":historical_case.get("observed_gate"),
            "legacy_behavior_family":historical_case.get("behavior_family_inferred_from_test_name"),
            "required_external_proof":historical_case.get("exit_evidence_missing"),
            "gate_unwaived":True,
            "independent_producer_credential_verified":False,
            "authenticated_provider_receipt_verified":False,
            "external_no_effect_fence_verified":False,
            "local_lab_pass_does_not_close_gate":True,
        }
        if record != expected or actual.get("observed_exception")!=historical_case.get("observed_error"):
            raise CrosswalkError("CROSSWALK_CASE_OR_PROOF_DRIFT")
        gate_counts[historical_case.get("observed_gate")]+=1
    if matched!=set(current_errors) or dict(gate_counts)!=GATE_COUNTS:
        raise CrosswalkError("CROSSWALK_GATE_DISTRIBUTION_INVALID")
    if proposal.get("counts") != {
        "historical":32,"current":32,"matched":32,
        "pre_adapter":23,"causal_receipt":8,"terminal_no_effect_fence":1,
    }:
        raise CrosswalkError("CROSSWALK_COUNTS_INCORRECT")

    req=proposal.get("gate_requirements")
    if not isinstance(req,list) or len(req)!=3:
        raise CrosswalkError("CROSSWALK_MISSING_EXTERNAL_REQUIREMENTS")
    rmap={x.get("gate"):x for x in req if isinstance(x,dict)}
    if set(rmap)!=set(GATE_COUNTS):
        raise CrosswalkError("CROSSWALK_GATE_REQUIREMENTS_INCOMPLETE")
    for gate,item in rmap.items():
        if not isinstance(item.get("missing"),list) or not item["missing"]:
            raise CrosswalkError("CROSSWALK_UNQUALIFIED_EXTERNAL_PROOF")
        if not isinstance(item.get("cannot_substitute"),list) or not item["cannot_substitute"]:
            raise CrosswalkError("CROSSWALK_UNTRUSTED_SUBSTITUTES_NOT_DENIED")
    if not FORBIDDEN_NEGATIVE.issubset(set(rmap["TERMINAL_NO_EFFECT_FENCE"]["cannot_substitute"])):
        raise CrosswalkError("CROSSWALK_FALSE_NEGATIVE_EVIDENCE_ALLOWLIST")

    vendor=proposal.get("provider_assessment")
    if not isinstance(vendor,dict):
        raise CrosswalkError("CROSSWALK_VENDOR_UNKNOWN")
    if (
        vendor.get("provider")!="Twilio Programmable Messaging classic"
        or vendor.get("endpoint")!="POST /2010-04-01/Accounts/{AccountSid}/Messages.json"
        or vendor.get("status")!="HARD_NO_GO"
        or vendor.get("assessment_type")!="documentary only, no live account access"
        or vendor.get("do_not_generalize_to_other_twilio_apis") is not True
        or not isinstance(vendor.get("missing_independently_audited_guarantees"),list)
        or len(vendor["missing_independently_audited_guarantees"])<4
    ):
        raise CrosswalkError("CROSSWALK_VENDOR_NO_GO_CONTRACT_MISSING")
    authority=proposal.get("authority")
    if not isinstance(authority,dict):
        raise CrosswalkError("CROSSWALK_AUTHORITY_MISSING")
    _expect_exact_false(authority,PROHIBITIONS,"CROSSWALK_UNVERIFIED_AUTHORITY_CLAIM")
    if (
        authority.get("homologated_p0_count")!=0
        or authority.get("governance")!="HARD_NO_GO"
        or authority.get("all_cases_open_not_waived") is not True
    ):
        raise CrosswalkError("CROSSWALK_HARD_NO_GO_VIOLATED")

    return {
        "schema":SCHEMA,
        "matched_32_provider_errors":len(matched),
        "historical_quality_tests":historical["historical_quality"]["tests"],
        "current_quality_tests":quality["tests"],
        "gates":dict(sorted(gate_counts.items())),
        "evidence_complete":False,
        "identity_independently_enrolled":False,
        "provider_receipt_authentic":False,
        "terminal_no_effect_fenced":False,
        "worker_allowed":False,
        "automatic_resend_allowed":False,
        "homologated_p0_count":0,
        "verdict":"HARD_NO_GO_EXTERNAL_EVIDENCE_MISSING",
    }


def load() -> tuple[dict[str,Any],dict[str,Any],dict[str,Any]]:
    return (
        json.loads(BASE.read_text(encoding="utf-8")),
        json.loads(LEDGER.read_text(encoding="utf-8")),
        json.loads(HISTORICAL.read_text(encoding="utf-8")),
    )


def main(argv: list[str]|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-crosswalk",action="store_true",required=True)
    parser.parse_args(argv)
    try:
        result=audit(*load())
        print(json.dumps(result,sort_keys=True,indent=2))
        return 0  # inventory valid, NOT production GO
    except (CrosswalkError,ValueError,TypeError,KeyError,OSError,UnicodeError,json.JSONDecodeError) as exc:
        print(json.dumps({"verdict":"HARD_NO_GO", "error":str(exc)}),file=sys.stderr)
        return 3


if __name__=="__main__":
    raise SystemExit(main())
