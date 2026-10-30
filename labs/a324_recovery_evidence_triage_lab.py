"""A324 LAB: fail-closed triage for missing, delayed or conflicting receipts.

All receipts, pins and clock claims are supplied by ONE local test process.
No independent network witness, provider ACK, trust-root or real recovery.
The only database access is A323's marked read-only synthetic SQLite.
This verifier emits investigation categories; NEVER issues a retry or GO.
"""
from labs.a317_detached_signed_intent_anchor_lab import encode, sha
from labs.a320_offline_custody_ceremony_lab import _hex64, _nonneg_int, _safe_id
from labs.a323_readonly_recovery_reconciliation_lab import (
    verify_recovery_hold, HISTORY_FIELDS, GENESIS_FIELDS,
)

SCHEMA = "ATLASQUANT_AION_A324_RECOVERY_EVIDENCE_TRIAGE_LAB_V1"
RECEIPT_FIELDS = frozenset((
    "custodian_id", "claimed_received_at", "claimed_channel_id",
    "claimed_receipt_digest", "checkpoint_sha256", "root_generation",
    "incident_epoch", "sequence", "head_sha256", "intent_digest",
    "decision",
))
MAX_CLAIMED_RECEIPT_AGE = 120


def report(status, reasons, *, checked=0, local_consistent=False):
    # Deliberately no action queue, writable state, host callbacks or retries.
    return {
        "schema": SCHEMA, "status": status,
        "reasons": sorted(set(reasons)),
        "claimed_receipts_checked": checked,
        "synthetic_local_reconciliation_consistent": bool(local_consistent),
        "research_only": True, "synthetic_only": True,
        "investigation_only": True,
        "investigation_priority": (
            "CONFLICT" if status == "LAB_INVESTIGATE_CONFLICT_HOLD"
            else "MISSING_OR_DELAYED" if status == "LAB_INVESTIGATE_EVIDENCE_HOLD"
            else "PROCEDURAL_HOLD"
        ),
        "external_custodians_independently_authenticated": False,
        "delivery_channel_independently_authenticated": False,
        "trusted_clock_and_receipt_freshness_proven": False,
        "high_water_off_host_immutable_proven": False,
        "provider_outcome_verified": False,
        "real_semantic_idempotence_proven": False,
        "can_resolve_unknown_commit": False,
        "can_restore": False, "can_resume": False,
        "can_replay": False, "can_resend": False,
        "can_auto_retry": False, "can_authorize_real_effect": False,
        "automatic_retries": 0, "zero_auto_resend": True,
        "hard_no_go": True, "p0_homologated": 0,
        "no_worker_deploy_provider_orders": True,
        "new_paid_services": False,
    }


def _receipt_valid(receipt):
    return (
        type(receipt) is dict and set(receipt) == RECEIPT_FIELDS
        and _safe_id(receipt["custodian_id"])
        and _safe_id(receipt["claimed_channel_id"])
        and all(_nonneg_int(receipt[k]) for k in (
            "claimed_received_at", "root_generation",
            "incident_epoch", "sequence",
        ))
        and all(_hex64(receipt[k]) for k in (
            "claimed_receipt_digest", "checkpoint_sha256",
            "head_sha256", "intent_digest",
        ))
        and receipt["decision"] == "HOLD_ONLY"
    )


def investigate_recovery_evidence(
    *, genesis_package, history_package, local_db_path,
    witness_receipts, declared_now_epoch, incident_reopened=False,
    operation="INVESTIGATE_ONLY",
):
    """Compare two claimed deliveries to BOTH A321 signed head checkpoints.

    Never trust a receipt's claimed channel/time/custody, and never treat
    a matching pair as independent testimony. All paths stay HOLD.
    """
    if (type(incident_reopened) is not bool or type(operation) is not str
            or type(declared_now_epoch) is not int
            or declared_now_epoch < 0):
        return report("LAB_PROCEDURAL_HOLD", ["CONTROL_SHAPE_INVALID"])
    if incident_reopened:
        return report("LAB_PROCEDURAL_HOLD", ["INCIDENT_REOPENED"])
    if operation != "INVESTIGATE_ONLY":
        return report("LAB_PROCEDURAL_HOLD", ["ACTION_REQUEST_DENIED"])
    if (type(genesis_package) is not dict
            or set(genesis_package) != GENESIS_FIELDS):
        return report("LAB_INVESTIGATE_EVIDENCE_HOLD",
                      ["GENESIS_EVIDENCE_MISSING"])
    if (type(history_package) is not dict
            or set(history_package) != HISTORY_FIELDS):
        return report("LAB_INVESTIGATE_EVIDENCE_HOLD",
                      ["SIGNED_HISTORY_MISSING"])
    if type(witness_receipts) not in (tuple, list) or len(witness_receipts) != 2:
        return report("LAB_INVESTIGATE_EVIDENCE_HOLD",
                      ["TWO_CUSTODIAN_DELIVERIES_REQUIRED"])
    try:
        last = history_package["checkpoints"][-1]
        if type(last) not in (tuple, list) or len(last) != 2:
            return report("LAB_INVESTIGATE_EVIDENCE_HOLD",
                          ["TWO_LATEST_CHECKPOINTS_REQUIRED"])
        pins = history_package["ceremony_request"]["custodian_pins"]
        if type(pins) is not dict or len(pins) != 2:
            return report("LAB_INVESTIGATE_EVIDENCE_HOLD",
                          ["CUSTODIAN_PINSET_MISSING"])
        if (any(type(x) is not dict or
                type(x.get("custodian_id")) is not str for x in last)):
            return report("LAB_INVESTIGATE_EVIDENCE_HOLD",
                          ["LATEST_SIGNED_CHECKPOINT_INVALID"])
        signed = {x["custodian_id"]: x for x in last}
        if set(signed) != set(pins):
            return report("LAB_INVESTIGATE_CONFLICT_HOLD",
                          ["LATEST_CHECKPOINT_CUSTODIANS_DISAGREE"])
    except (TypeError, KeyError, IndexError, ValueError):
        return report("LAB_INVESTIGATE_EVIDENCE_HOLD",
                      ["LATEST_SIGNED_CHECKPOINT_MISSING"])
    issues_missing, issues_conflict = set(), set()
    checked = 0
    seen, channels = set(), set()
    for receipt in witness_receipts:
        if not _receipt_valid(receipt):
            issues_missing.add("RECEIPT_SHAPE_INVALID")
            continue
        who = receipt["custodian_id"]
        if who in seen:
            issues_conflict.add("DUPLICATE_CUSTODIAN_CLAIM")
        seen.add(who)
        channel = receipt["claimed_channel_id"]
        if channel in channels:
            issues_conflict.add("SHARED_DECLARED_DELIVERY_CHANNEL")
        channels.add(channel)
        if who not in signed:
            issues_conflict.add("UNKNOWN_CUSTODIAN_CLAIM")
            continue
        expected = signed[who]
        checked += 1
        # Compare the entire signed A321 checkpoint (including its signature).
        if receipt["checkpoint_sha256"] != sha(encode(expected)):
            issues_conflict.add("SIGNED_CHECKPOINT_DIGEST_MISMATCH")
        for field in ("root_generation", "incident_epoch", "sequence",
                      "head_sha256", "intent_digest"):
            if receipt[field] != expected.get(field):
                issues_conflict.add("CLAIMED_" + field.upper() + "_CONFLICT")
        if receipt["claimed_receipt_digest"] != sha(encode({
            "checkpoint_sha256": receipt["checkpoint_sha256"],
            "custodian_id": who,
            "claimed_channel_id": channel,
            "claimed_received_at": receipt["claimed_received_at"],
        })):
            issues_conflict.add("RECEIPT_ENVELOPE_DIGEST_MISMATCH")
        when = receipt["claimed_received_at"]
        if (when < expected.get("issued_at", -1)
                or when > declared_now_epoch):
            issues_missing.add("RECEIPT_TIME_INCONSISTENT")
        elif declared_now_epoch - when > MAX_CLAIMED_RECEIPT_AGE:
            issues_missing.add("RECEIPT_DELAYED_OR_STALE")
        if when >= expected.get("expires_at", -1):
            issues_missing.add("RECEIPT_AFTER_SIGNED_WINDOW")
    if seen != set(pins):
        issues_missing.add("MISSING_OR_UNPINNED_CUSTODIAN_DELIVERY")
    if issues_conflict:
        return report("LAB_INVESTIGATE_CONFLICT_HOLD",
                      issues_conflict | issues_missing, checked=checked)
    if issues_missing:
        return report("LAB_INVESTIGATE_EVIDENCE_HOLD",
                      issues_missing, checked=checked)
    # A323 independently rechecks A322 genesis, A321 all historical signed
    # checkpoints AND real synthetic SQLite bytes; we never accept a
    # status field supplied by the caller as evidence.
    try:
        reconciliation = verify_recovery_hold(
            genesis_package=genesis_package, history_package=history_package,
            local_db_path=local_db_path,
            incident_reopened=False, operation="OBSERVE_ONLY",
        )
    except (TypeError, ValueError, AttributeError, KeyError, OverflowError):
        return report("LAB_INVESTIGATE_EVIDENCE_HOLD",
                      ["A323_RECONCILIATION_UNVERIFIABLE"], checked=checked)
    if reconciliation["status"] == "LAB_RECOVERY_CONFLICT_VETO":
        return report("LAB_INVESTIGATE_CONFLICT_HOLD",
                      ["A323_RECOVERY_CONFLICT"] + reconciliation["issues"],
                      checked=checked)
    if reconciliation["status"] != "LAB_RECOVERY_CONSISTENT_HOLD_NO_EXTERNAL_AUTHORITY":
        return report("LAB_INVESTIGATE_EVIDENCE_HOLD",
                      ["A323_EVIDENCE_NOT_CONCLUSIVE"] +
                      reconciliation["issues"], checked=checked)
    return report("LAB_COHERENT_EVIDENCE_STILL_HOLD",
                  ["EXTERNAL_INDEPENDENCE_UNPROVEN",
                   "PROVIDER_ACK_NOT_AUTHENTICATED"],
                  checked=checked, local_consistent=True)


__all__ = [
    "SCHEMA", "RECEIPT_FIELDS", "MAX_CLAIMED_RECEIPT_AGE",
    "investigate_recovery_evidence",
]
