"""A297 LAB: fail-closed independent-verifier port and incident reopening veto.

This is a model of the *missing* external authority boundary, NOT a trusted
implementation. No real keys, owner consent, outside custodian, provider,
Worker, deployment, trading or P0 homologation. Every real-effect decision
remains HARD_NO_GO, even with all-eight plausibly filled fake A296 claims.
"""
import secrets
import time

from labs.a296_external_authority_evidence_contract_lab import (
    evaluate_evidence_contract, synthetic_forged_complete_pack,
)

SCHEMA = "ATLASQUANT_AION_INCIDENT_REOPEN_INDEPENDENT_GATE_LAB_V1"
ROOT_ABSENT = "TRUST_ROOT_ABSENT"
INCIDENT_OPEN = "INCIDENT_OPEN"
ACK_UNCERTAIN = "ACK_UNCERTAIN"
PLAN_FIELDS = frozenset((
    "schema", "incident_id", "incident_generation", "requested_epoch",
    "intent_digest", "nonce", "expires_at", "evidence_pack",
))
HEX = frozenset("0123456789abcdef")


def _hex(value, length):
    return type(value) is str and len(value) == length and all(
        c in HEX for c in value
    )


def _base():
    return {
        "schema": SCHEMA,
        "research_only": True,
        "independent_external_key_configured": False,
        "owner_consent_authenticated": False,
        "durable_off_host_incident_journal": False,
        "native_sqlite_fd_authenticated": False,
        "zero_auto_resend": True,
        "can_authorize_real_effect": False,
        "can_deploy": False,
        "can_start_worker": False,
        "p0_homologated": 0,
        "hard_no_go": True,
        "decision": "HARD_NO_GO",
        "no_new_paid_services": True,
    }


class IsolatedIncidentAuthorityGate:
    """Local fail-closed coordinator; absent external roots can never be GO."""

    def __init__(self):
        self._state = ROOT_ABSENT
        self._generation = 0
        self._incident_id = None
        self._incident_ids = set()
        self._historical_epoch = None
        self._uncertain = False
        self._journal = []

    @property
    def generation(self):
        return self._generation

    @property
    def state(self):
        return self._state

    @property
    def incident_id(self):
        return self._incident_id

    @property
    def journal(self):
        return tuple(self._journal)

    def status(self):
        result = _base()
        result.update({
            "state": self._state,
            "incident_generation": self._generation,
            "incident_id": self._incident_id,
            "incident_reopened": self._generation > 0,
            "unknown_effect_outcome": self._uncertain,
            "incident_journal_entries": len(self._journal),
            "historical_epoch_bound": self._historical_epoch,
        })
        return result

    def record_lab_epoch(self, value):
        """Track untrusted local history, never grant operation authority."""
        if not _hex(value, 64):
            raise ValueError("LAB_EPOCH_INVALID")
        if self._generation or self._uncertain:
            return self._refuse("INCIDENT_OR_ACK_VETO")
        if self._historical_epoch is not None:
            return self._refuse("LOCAL_EPOCH_ALREADY_RECORDED")
        self._historical_epoch = value
        self._journal.append(("LAB_EPOCH_ONLY", value))
        return self._refuse("UNTRUSTED_LOCAL_EPOCH_NOT_AUTHORITY")

    @staticmethod
    def _refuse(reason, **context):
        return {
            **_base(),
            "approved": False,
            "reason": reason,
            **context,
        }

    def reopen_incident(self, *, incident_id, reason):
        """Reopening always increments generation and invalidates old plans."""
        if (
            type(incident_id) is not str
            or len(incident_id) > 128
            or not incident_id.strip()
        ):
            raise ValueError("INCIDENT_ID_INVALID")
        if type(reason) is not str or not reason.strip() or len(reason) > 256:
            raise ValueError("INCIDENT_REASON_INVALID")
        if incident_id in self._incident_ids:
            return self._refuse("INCIDENT_EVENT_REPLAY")
        self._incident_ids.add(incident_id)
        self._generation += 1
        self._incident_id = incident_id
        self._state = INCIDENT_OPEN
        self._journal.append((
            "INCIDENT_REOPEN", self._generation, incident_id
        ))
        return self._refuse(
            "INCIDENT_REOPEN_HARD_VETO",
            incident_generation=self._generation,
        )

    def mark_effect_ack_uncertain(self, *, intent_id):
        if (
            type(intent_id) is not str or not intent_id.strip()
            or len(intent_id) > 128
        ):
            raise ValueError("INTENT_ID_INVALID")
        self._uncertain = True
        self._state = ACK_UNCERTAIN
        self._journal.append(("ACK_OUTCOME_UNKNOWN", intent_id))
        return self._refuse("ACK_OUTCOME_UNKNOWN_ZERO_AUTO_RESEND")

    def make_plan(
        self, *, evidence_pack=None, requested_epoch=None,
        intent_digest=None, nonce=None, expires_at=None,
    ):
        return {
            "schema": SCHEMA,
            "incident_id": self._incident_id,
            "incident_generation": self._generation,
            "requested_epoch": (
                secrets.token_hex(32)
                if requested_epoch is None else requested_epoch
            ),
            "intent_digest": (
                secrets.token_hex(32)
                if intent_digest is None else intent_digest
            ),
            "nonce": (
                secrets.token_hex(16) if nonce is None else nonce
            ),
            "expires_at": (
                int(time.time()) + 120
                if expires_at is None else expires_at
            ),
            "evidence_pack": (
                synthetic_forged_complete_pack()
                if evidence_pack is None else evidence_pack
            ),
        }

    def review_recovery(self, plan, *, now=None):
        """Structure can be green; independent identity remains UNVERIFIED."""
        if self._uncertain:
            return self._refuse("ACK_OUTCOME_UNKNOWN_ZERO_AUTO_RESEND")
        if self._generation == 0 or self._incident_id is None:
            return self._refuse("NO_REOPENED_INCIDENT_CONTEXT")
        if type(plan) is not dict or frozenset(plan) != PLAN_FIELDS:
            return self._refuse("RECOVERY_PLAN_FIELDS_INVALID")
        if plan["schema"] != SCHEMA:
            return self._refuse("RECOVERY_PLAN_SCHEMA_INVALID")
        if (
            plan["incident_id"] != self._incident_id
            or type(plan["incident_generation"]) is not int
            or plan["incident_generation"] != self._generation
        ):
            return self._refuse("STALE_OR_WRONG_INCIDENT_GENERATION")
        if not _hex(plan["requested_epoch"], 64):
            return self._refuse("RECOVERY_EPOCH_INVALID")
        if not _hex(plan["intent_digest"], 64):
            return self._refuse("RECOVERY_INTENT_BINDING_INVALID")
        if not _hex(plan["nonce"], 32):
            return self._refuse("RECOVERY_NONCE_INVALID")
        checked_at = int(time.time()) if now is None else now
        if type(checked_at) is not int:
            raise ValueError("invalid time")
        expiry = plan["expires_at"]
        if (
            type(expiry) is not int
            or expiry <= checked_at or expiry > checked_at + 300
        ):
            return self._refuse("RECOVERY_EXPIRED_OR_UNBOUNDED")
        evidence = evaluate_evidence_contract(
            plan["evidence_pack"], now=checked_at
        )
        if not evidence["structurally_plausible"]:
            return self._refuse(
                "EXTERNAL_EVIDENCE_CONTRACT_INVALID",
                evidence_issues=evidence["issues"],
            )
        # This branch is intentional. Fake / self-asserted public-key labels
        # cannot override missing actual independent roots or incident custody.
        return self._refuse(
            "STRUCTURAL_EVIDENCE_NOT_EXTERNAL_AUTHORITY",
            structural_obligations=evidence["syntactically_complete_count"],
            authenticated_obligations=evidence["authenticated_obligations"],
        )

    def attempt_effect(self, *, intent_digest=None, plan=None):
        """No code path can dispatch an effect. Read-only denial semantics."""
        if intent_digest is not None and not _hex(intent_digest, 64):
            return self._refuse("EFFECT_INTENT_DIGEST_INVALID")
        if self._uncertain:
            return self._refuse("ACK_OUTCOME_UNKNOWN_ZERO_AUTO_RESEND")
        if self._generation > 0:
            return self._refuse("REOPENED_INCIDENT_VETO")
        return self._refuse("NO_INDEPENDENT_REAL_OWNER_AUTHORITY")


def probe_incident_reopening_cancels_stale_plan():
    result = _base()
    gate = IsolatedIncidentAuthorityGate()
    epoch = "a" * 64
    initial = gate.record_lab_epoch(epoch)
    denied_before = gate.attempt_effect(intent_digest="b" * 64)
    first_open = gate.reopen_incident(
        incident_id="incident-a297-1",
        reason="simulated owner trust crisis",
    )
    first_plan = gate.make_plan()
    first_review = gate.review_recovery(first_plan)
    second_open = gate.reopen_incident(
        incident_id="incident-a297-2",
        reason="incident reopened after prior review",
    )
    stale_review = gate.review_recovery(first_plan)
    new_plan = gate.make_plan()
    new_review = gate.review_recovery(new_plan)
    effect_denied = gate.attempt_effect(intent_digest="b" * 64)
    result.update({
        "initial_local_epoch_never_authorized": not initial["approved"],
        "normal_effect_denied_without_external_root": (
            denied_before["reason"] == "NO_INDEPENDENT_REAL_OWNER_AUTHORITY"
        ),
        "first_incident_vetoed": (
            first_open["reason"] == "INCIDENT_REOPEN_HARD_VETO"
        ),
        "complete_fake_evidence_rejected": (
            first_review["reason"] ==
            "STRUCTURAL_EVIDENCE_NOT_EXTERNAL_AUTHORITY"
            and first_review["structural_obligations"] == 8
            and first_review["authenticated_obligations"] == 0
        ),
        "incident_reopened_generation_advanced": (
            second_open["incident_generation"] == 2
        ),
        "old_recovery_plan_stale": (
            stale_review["reason"] == "STALE_OR_WRONG_INCIDENT_GENERATION"
        ),
        "new_fake_evidence_still_denied": (
            new_review["reason"] ==
            "STRUCTURAL_EVIDENCE_NOT_EXTERNAL_AUTHORITY"
        ),
        "effect_denied_after_reopen": (
            effect_denied["reason"] == "REOPENED_INCIDENT_VETO"
        ),
        "journal_count": len(gate.journal),
    })
    return result


def probe_unknown_ack_and_restart():
    result = _base()
    gate = IsolatedIncidentAuthorityGate()
    gate.reopen_incident(
        incident_id="incident-a297-ack",
        reason="synthetic ACK lost",
    )
    plan = gate.make_plan()
    unknown = gate.mark_effect_ack_uncertain(intent_id="a297-intent-1")
    review = gate.review_recovery(plan)
    blocked = gate.attempt_effect(intent_digest="a" * 64)
    reopened = gate.reopen_incident(
        incident_id="incident-a297-ack-2",
        reason="reopened after uncertain effect",
    )
    after = gate.attempt_effect(intent_digest="a" * 64)
    new_host_instance = IsolatedIncidentAuthorityGate()
    fresh = new_host_instance.attempt_effect(intent_digest="a" * 64)
    result.update({
        "unknown_ack_denied": (
            unknown["reason"] == "ACK_OUTCOME_UNKNOWN_ZERO_AUTO_RESEND"
        ),
        "recovery_veto_persists": (
            review["reason"] == "ACK_OUTCOME_UNKNOWN_ZERO_AUTO_RESEND"
        ),
        "effect_blocked_before_reopen": (
            blocked["reason"] == "ACK_OUTCOME_UNKNOWN_ZERO_AUTO_RESEND"
        ),
        "incident_reopening_cannot_clear_uncertainty": (
            reopened["reason"] == "INCIDENT_REOPEN_HARD_VETO"
            and after["reason"] == "ACK_OUTCOME_UNKNOWN_ZERO_AUTO_RESEND"
        ),
        "reset_instance_still_denies_production": (
            fresh["reason"] == "NO_INDEPENDENT_REAL_OWNER_AUTHORITY"
        ),
        "in_memory_journal_is_not_offhost_custody": True,
    })
    return result


__all__ = [
    "SCHEMA", "ROOT_ABSENT", "INCIDENT_OPEN", "ACK_UNCERTAIN",
    "PLAN_FIELDS", "IsolatedIncidentAuthorityGate",
    "probe_incident_reopening_cancels_stale_plan",
    "probe_unknown_ack_and_restart",
]
