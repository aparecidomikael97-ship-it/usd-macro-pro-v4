"""AION H0 read-only RFI intake gate: response collection is NOT provider enrollment.

Safely verifies a public questionnaire and its answer tracking. Vendor support
replies, email content, attached proofs and secrets are NOT fetched/stored by
this tool; even referenced vendor answers are UNVERIFIED candidate evidence.
No production admission, no network, no Worker and no automatic resend.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
import re
import sys
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
LEDGER=ROOT/"docs/aion/evidence/aion_p0_h0_vendor_rfi_34_open_questions_20261021.json"
TEMPLATE=ROOT/"docs/aion/p0-h0-unsent-onesignal-cloudflare-aws-technical-rfi-20261021.md"
SCHEMA="AION_P0_H0_VENDOR_RFI_INTAKE_NO_EFFECTS_V1"
GROUPS={
    "ONESIGNAL_SMS_PRODUCER":("P",14),
    "CLOUDFLARE_DO_CUSTODIAN":("C",12),
    "AWS_DYNAMODB_ALTERNATIVE":("A",8),
}
BLOCKERS={
    "PRE_ADAPTER_PRODUCER_ENROLLMENT",
    "CAUSAL_COMMITTED_EFFECT_RECEIPT",
    "TERMINAL_NO_EFFECT_FENCE",
}
STATES={"UNANSWERED","ANSWERED_UNVERIFIED","NOT_SUPPORTED","NEEDS_CLARIFICATION"}
DENIED={
    "live_external_tests_performed":False,
    "identity_independently_verified":False,
    "owner_consent_authenticated":False,
    "provider_effect_receipt_authenticated":False,
    "terminal_no_effect_fenced":False,
    "independent_latest_head_witness_verified":False,
    "quality_historical_85_waived":False,
    "external_approval_granted":False,
    "worker_enabled":False,
    "auto_resend_enabled":False,
    "approved_spend_brl":0,
    "homologated_p0_count":0,
    "producers_and_custodians_not_enrolled":True,
    "verdict":"HARD_NO_GO_EXTERNAL_EVIDENCE_MISSING",
}

class IntakeError(ValueError):
    """Reject structural drift and all attempts to claim authority in public RFI."""


def require(condition:bool,reason:str)->None:
    if not condition:
        raise IntakeError(reason)


def audit(manifest:dict[str,Any],document:str)->dict[str,Any]:
    require(isinstance(manifest,dict) and manifest.get("schema")==SCHEMA,"INTAKE_SCHEMA_INVALID")
    require(manifest.get("as_of")=="2026-10-21","INTAKE_ORIGIN_DATE_CHANGED")
    require(manifest.get("source_pr")==1407 and manifest.get("source_sha")=="1972670a88ab9413d074d0cb595246cae11c50c3","INTAKE_SOURCE_PR_CHANGED")
    require(manifest.get("rfi_document")==TEMPLATE.relative_to(ROOT).as_posix(),"INTAKE_TEMPLATE_SOURCE_CHANGED")
    require(manifest.get("provider_to_custodian_separation_mandatory") is True,"INTAKE_ROLE_SEPARATION_MISSING")
    require(manifest.get("rfi_delivery_status")=="DRAFT_UNSENT_IN_THIS_ROUND" and
            manifest.get("historical_contacts_not_claimed_absent") is True and
            manifest.get("no_private_support_text_in_git") is True,"INTAKE_FALSE_COMMUNICATION_OR_PRIVACY_CLAIM")
    require(set(manifest.get("allowed_response_states",[]))==STATES,"INTAKE_RESPONSE_STATUS_UNSAFE")
    require(isinstance(document,str) and document.startswith("# AION P0/H0"),"INTAKE_RFI_DOCUMENT_MISSING")
    require("(NOT SENT)" in document and
            "No external inquiry or action was submitted in this PR." in document,
            "INTAKE_UNSENT_DISCLOSURE_MISSING")

    records=manifest.get("answers")
    require(isinstance(records,list) and len(records)==34,"INTAKE_QUESTION_COUNT_MISMATCH")
    seen=set()
    counts=Counter()
    for row in records:
        require(isinstance(row,dict),"INTAKE_ROW_INVALID")
        row_id=row.get("id")
        subject=row.get("subject")
        require(subject in GROUPS,"INTAKE_UNKNOWN_SUBJECT")
        prefix,maximum=GROUPS[subject]
        require(isinstance(row_id,str) and re.fullmatch(rf"{prefix}-(?:0[1-9]|[12]\d)",row_id) and
                1<=int(row_id.split("-")[1])<=maximum,"INTAKE_QUESTION_ID_OUT_OF_RANGE")
        require(row_id not in seen,"INTAKE_DUPLICATE_QUESTION_ID")
        seen.add(row_id)
        counts[subject]+=1
        require(bool(re.search(rf"\*\*{re.escape(row_id)}\.",document)),
                "INTAKE_UNDOCUMENTED_QUESTION")
        require(isinstance(row.get("critical"),bool),"INTAKE_CRITICALITY_MISSING")
        codes=row.get("related_h0_producer_gate_classes")
        require(isinstance(codes,list) and bool(codes) and set(codes)<=BLOCKERS,
                "INTAKE_UNMAPPED_H0_BARRIER")
        state=row.get("response_state")
        require(state in STATES,"INTAKE_RESPONSE_STATUS_UNSAFE")
        require(row.get("verified_by_independent_reviewer") is False and
                row.get("independently_authenticated_evidence") is False and
                row.get("claim_of_production_authority") is False and
                row.get("open_item") is True,
                "INTAKE_RESPONSE_MINTED_UNVERIFIED_AUTHORITY")
        if state=="UNANSWERED":
            require(row.get("response_observed_at") is None and
                    row.get("vendor_response_reference") is None,
                    "INTAKE_UNANSWERED_RESPONSE_FABRICATED")
        else:
            # Explicit reference for future manual corroboration; never a
            # credential, raw email text or proof of issuer enrollment.
            ref=row.get("vendor_response_reference")
            date=row.get("response_observed_at")
            require(isinstance(ref,str) and ref.startswith("PRIVATE_RECORD:") and
                    len(ref)<=256 and not any(c in ref for c in "\n\r@"),
                    "INTAKE_VENDOR_REPLY_PRIVATE_REFERENCE_REQUIRED")
            require(isinstance(date,str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}",date),
                    "INTAKE_VENDOR_REPLY_DATE_REQUIRED")
    expected={name:n for name,(_,n) in GROUPS.items()}
    require(dict(counts)==expected,"INTAKE_MISSING_QUESTION_GROUP")
    require(all(f"{prefix}-{k:02d}" in seen for _,(prefix,n) in GROUPS.items()
                for k in range(1,n+1)), "INTAKE_MISSING_NUMBERED_QUESTION")
    governance=manifest.get("governance")
    require(isinstance(governance,dict) and
            all(governance.get(k)==v and type(governance.get(k)) is type(v) for k,v in DENIED.items()),
            "INTAKE_UNVERIFIED_PRODUCTION_AUTHORITY")
    interpret=manifest.get("interpretation")
    require(isinstance(interpret,dict) and all(interpret.get(k) is True for k in (
        "documentary_RFI_only",
        "return_code_zero_never_authorizes_operations",
        "answer_from_support_is_not_a_signed_external_provider_receipt",
        "absent_response_does_not_imply_no_effect",
        "no_success_by_any_combination_of_local_assertions",
    )), "INTAKE_DOCUMENTARY_ONLY_GUARD_REMOVED")
    return {
        "schema":SCHEMA+".audit",
        "questions":len(records),
        "by_group":dict(sorted(counts.items())),
        "pending":sum(x["response_state"]=="UNANSWERED" for x in records),
        "vendor_answer_candidates_unverified":sum(x["response_state"]!="UNANSWERED" for x in records),
        "technical_submission_performed":False,
        "external_proof_authenticated":False,
        "worker_allowed":False,
        "automatic_resend_allowed":False,
        "quality_85_waived":False,
        "homologated_p0_count":0,
        "verdict":"HARD_NO_GO_EXTERNAL_EVIDENCE_MISSING",
    }


def main()->int:
    try:
        rows=json.loads(LEDGER.read_text(encoding="utf-8"))
        template=TEMPLATE.read_text(encoding="utf-8")
        print(json.dumps(audit(rows,template),indent=2,sort_keys=True))
        return 0
    except (IntakeError,OSError,UnicodeError,ValueError,TypeError) as e:
        print(json.dumps({"error":str(e),"verdict":"HARD_NO_GO"},sort_keys=True),file=sys.stderr)
        return 3


if __name__=="__main__":
    raise SystemExit(main())
