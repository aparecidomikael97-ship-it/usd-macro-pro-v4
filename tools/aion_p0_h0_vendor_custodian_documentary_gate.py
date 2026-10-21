"""AION P0 H0 documentary provider/custodian two-role gate, read only.

Success means a conservative *comparison document* is coherent. It cannot
attest credentials, inspect another administrative domain, send messages,
reserve first attempts or promote any candidate to GO. It never accesses a
network, paid API, real provider, local secrets, or a trust-root registry.
"""
from __future__ import annotations

from pathlib import Path
import json
import sys
from collections import Counter
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/"docs/aion/evidence/aion_p0_h0_vendor_custodian_two_role_review_20261021.json"
SCHEMA="AION_P0_H0_VENDOR_CUSTODIAN_TWO_ROLE_DOCUMENTARY_GATE_V1"
PROVIDERS={
    "ONESIGNAL_SMS_NOTIFICATIONS",
    "TWILIO_CLASSIC_MESSAGES",
    "TWILIO_BULK_MESSAGES",
}
CUSTODIANS={"CLOUDFLARE_DO_SQLITE","AWS_DYNAMODB_CONDITIONAL"}
DOCUMENTED={"documented","best_effort","unknown","not_established"}
REQUIRED_PROOFS=(
    "producer_and_custodian_must_be_distinct_authority_domains",
    "local_executor_cannot_administer_both_roots",
    "highwater_must_be_authenticated_from_external_independent_source",
    "provider_receipt_must_be_authenticated_from_provider_source",
    "provider_terminal_no_effect_requires_enforced_future_effect_fence",
    "client_dedupe_not_equal_to_terminal_no_effect",
    "operation_id_not_equal_to_create_idempotency",
    "no_evidence_from_timeout_404_or_empty_list",
    "delivery_status_not_equal_to_first_attempt_effect_receipt",
)
DENIED_FIELDS=(
    "worker_enabled","automatic_resend_enabled","approved_merchant_or_sms_send",
    "provider_account_connected","custodian_account_provisioned","owner_approval_verified",
)


class DocumentaryGateError(ValueError):
    """Fail-closed contract violation; never changes runtime authority."""


def _require(condition:bool,message:str)->None:
    if not condition:
        raise DocumentaryGateError(message)


def audit(d:dict[str,Any])->dict[str,Any]:
    _require(isinstance(d,dict) and d.get("schema")==SCHEMA,"INVALID_SCHEMA")
    _require(d.get("as_of")=="2026-10-21","REVIEW_DATE_DRIFT")
    _require(d.get("independent_roles")==["PRODUCER","CUSTODIAN"],"ROLE_COLLAPSE")
    g=d.get("global_governance")
    _require(isinstance(g,dict),"GLOBAL_GOVERNANCE_MISSING")
    _require(g.get("hard_no_go") is True,"HARD_NO_GO_REMOVED")
    _require(all(g.get(k) is False for k in DENIED_FIELDS),"UNVERIFIED_AUTHORITY_MINTED")
    _require(g.get("new_spend_authorized_brl")==0,"UNAUTHORIZED_SPEND")
    _require(g.get("homologated_p0_count")==0,"P0_PREMATURE_HOMOLOGATION")
    sources=d.get("input_sources")
    _require(isinstance(sources,list) and len(sources)==3 and len(set(sources))==3,"PROVENANCE_INCOMPLETE")
    _require(all(isinstance(s,str) and s.startswith("docs/aion/") for s in sources),"PROVENANCE_NOT_LOCAL_REVIEW")

    producers=d.get("provider_candidates")
    custodians=d.get("custodian_candidates")
    _require(isinstance(producers,list) and isinstance(custodians,list),"CANDIDATES_MISSING")
    _require({x.get("id") for x in producers if isinstance(x,dict)}==PROVIDERS and len(producers)==3,"PROVIDER_ENDPOINTS_CHANGED")
    _require({x.get("id") for x in custodians if isinstance(x,dict)}==CUSTODIANS and len(custodians)==2,"CUSTODIAN_SET_CHANGED")
    for role,records in (("PRODUCER",producers),("CUSTODIAN",custodians)):
        for record in records:
            _require(record.get("role")==role,"ROLE_SUBSTITUTION")
            _require(record.get("decision")=="DOCUMENTATION_ONLY_HARD_NO_GO","CANDIDATE_PROMOTED")
            _require(all(record.get(k) is False for k in (
                "independent_enrollment_verified","actual_account_tested",
                "authenticated_external_receipt_verified","terminal_no_effect_verified",
                "approved_for_effects"
            )),"UNVERIFIED_PROVIDER_OR_CUSTODIAN_CLAIM")
            ref=record.get("official_references")
            _require(isinstance(ref,list) and bool(ref) and all(
                isinstance(s,str) and s.startswith("https://") and
                ("documentation.onesignal.com" in s or "www.twilio.com" in s or
                 "developers.cloudflare.com" in s or "docs.aws.amazon.com" in s or
                 "aws.amazon.com" in s) for s in ref
            ),"UNSUPPORTED_DOCUMENT_REFERENCE")
            _require(isinstance(record.get("missing_real_h0_guarantees"),list)
                     and len(record["missing_real_h0_guarantees"])>=4,
                     "CRITICAL_EXTERNAL_PROOFS_MISSING")
            cost=record.get("cost_evidence")
            _require(isinstance(cost,dict) and cost.get("amount_brl_monthly") is None
                     and cost.get("live_usage_authorized") is False,
                     "UNVERIFIED_COST_OR_SPEND")
    p={r["id"]:r for r in producers}
    c={r["id"]:r for r in custodians}
    one=p["ONESIGNAL_SMS_NOTIFICATIONS"]["documented_capabilities"]
    _require(one.get("dedupe_key")=="idempotency_key UUID" and
             one.get("dedupe_duration_days")==30 and
             one.get("dedupe_scope")=="notification_create",
             "ONESIGNAL_DEDUPE_SCOPE_OR_EXPIRY_FALSIFIED")
    bulk=p["TWILIO_BULK_MESSAGES"]["documented_capabilities"]
    _require(bulk.get("tracking_id")=="operationId issued after acceptance"
             and bulk.get("client_create_idempotency")=="NOT_ESTABLISHED_BY_OPERATION_ID",
             "OPERATION_ID_CONFUSED_WITH_IDEMPOTENCY")
    classic=p["TWILIO_CLASSIC_MESSAGES"]["documented_capabilities"]
    _require(classic.get("dedupe_key")=="NO_NATIVE_CLIENT_CREATE_TOKEN_EVIDENCED"
             and classic.get("dedupe_duration_days") is None,
             "TWILIO_CLASSIC_DEDUPE_FABRICATED")
    _require(
        c["CLOUDFLARE_DO_SQLITE"]["documented_capabilities"].get("free_tier_storage_account_gb")==5,
        "CLOUDFLARE_FREE_TIER_CHANGED_WITHOUT_REVIEW",
    )
    _require(
        c["AWS_DYNAMODB_CONDITIONAL"]["documented_capabilities"].get("strongly_consistent_read_option")=="documented",
        "DYNAMODB_READ_MODEL_CHANGED",
    )
    gate=d.get("cross_role_gate")
    _require(isinstance(gate,dict),"TWO_ROLE_GATE_MISSING")
    _require(all(gate.get(k) is True for k in REQUIRED_PROOFS),"EXTERNAL_FENCE_PRETENDED")
    _require(gate.get("when_any_proof_missing")=="UNKNOWN_BLOCKED" and
             gate.get("when_lost_first_response")=="UNKNOWN_BLOCKED_ZERO_AUTO_RESEND",
             "FIRST_ATTEMPT_UNSAFE_RESEND")
    shortlist=d.get("shortlist_for_documentary_RFI_only")
    _require(isinstance(shortlist,dict) and shortlist.get("provider") in PROVIDERS
             and shortlist.get("custodian") in CUSTODIANS and
             shortlist.get("status")=="RESEARCH_PRIORITY_ONLY_NOT_INTEGRATION_GO"
             and isinstance(shortlist.get("requires_before_any_spend"),list)
             and len(shortlist["requires_before_any_spend"])>=5,
             "SHORTLIST_MISTAKEN_FOR_APPROVAL")
    pairs=d.get("non_go_pairs")
    expected={(a,b) for a in PROVIDERS for b in CUSTODIANS}
    _require(isinstance(pairs,list) and len(pairs)==6,"PAIR_COVERAGE_MISSING")
    seen=set()
    for x in pairs:
        _require(isinstance(x,dict),"PAIR_SCHEMA_INVALID")
        pair=(x.get("provider"),x.get("custodian"))
        _require(pair in expected and pair not in seen,"PAIR_INVALID_OR_DUPLICATED")
        seen.add(pair)
        _require(x.get("provisional")=="HARD_NO_GO_EXTERNAL_EVIDENCE_MISSING" and
                 x.get("can_dispatch") is False and x.get("can_retry_uncertain_first_attempt") is False
                 and x.get("can_homologate") is False,
                 "PAIR_UNVERIFIED_AUTHORIZATION")
    _require(seen==expected,"PAIR_NOT_EXHAUSTIVE")
    return {
        "schema":SCHEMA+".audit",
        "provider_count":len(producers),
        "custodian_count":len(custodians),
        "pair_count":len(pairs),
        "shortlist_is_documentary_only":True,
        "actual_external_trust_verified":False,
        "effect_or_absence_proven":False,
        "worker_allowed":False,
        "automatic_resend_allowed":False,
        "new_spend_authorized_brl":0,
        "homologated_p0_count":0,
        "verdict":"HARD_NO_GO_EXTERNAL_EVIDENCE_MISSING",
    }


def main()->int:
    try:
        data=json.loads(PATH.read_text(encoding="utf-8"))
        print(json.dumps(audit(data),indent=2,sort_keys=True))
        return 0
    except (DocumentaryGateError,UnicodeError,OSError,ValueError,TypeError) as exc:
        print(json.dumps({"error":str(exc),"verdict":"HARD_NO_GO"}),file=sys.stderr)
        return 3


if __name__=="__main__":
    raise SystemExit(main())
