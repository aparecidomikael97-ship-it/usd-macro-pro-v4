from __future__ import annotations
from copy import deepcopy
import unittest

from atlasquant_aion_behavioral_eval_gate import SCHEMA as BEHAVIOR_SCHEMA
from atlasquant_aion_finops_metering import SCHEMA as FINOPS_SCHEMA
from atlasquant_aion_incident_control_plane import (
    SCHEMA as INCIDENT_SCHEMA,
    capability_authority_matrix,
)
from atlasquant_aion_operational_resilience import SCHEMA as OPS_SCHEMA
from atlasquant_aion_tenant_crypto import crypto_policy
from atlasquant_aion_post_hardening_readiness import (
    evaluate_post_hardening_readiness,
    post_hardening_review_plan,
    stage_claim_digest,
)
from atlasquant_aion_verification_ledger import (
    default_verification_ledger,
    record_independent_verification,
)

SCOPE = {"owner_id": "owner-a", "tenant_id": "tenant-a", "workspace_id": "ws-a"}


def snapshots():
    return {
        "tenant_crypto": crypto_policy(),
        "durable_cas": {
            "schema": "ATLASQUANT_AION_DURABLE_TASK_REPOSITORY_V1",
            "state": "MATCH",
            "atomic_cas": True,
            "multi_process_boundary": "SQLITE_TRANSACTION",
            "restores_state_only": True,
            "executes_action": False,
            "automatic_resume_executes": False,
        },
        "finops": {
            "schema": FINOPS_SCHEMA,
            "state": "ALLOW",
            "automatic_charge": False,
            "automatic_model_switch": False,
            "grants_authority": False,
            "executes_action": False,
        },
        "behavioral_eval": {
            "schema": BEHAVIOR_SCHEMA,
            "state": "HUMAN_REVIEW_CANDIDATE",
            "automatic_promotion": False,
            "production_change_allowed": False,
            "grants_authority": False,
            "executes_action": False,
        },
        "incident_control": capability_authority_matrix(),
        "operational_resilience": {
            "schema": OPS_SCHEMA,
            "state": "READY_FOR_ADMIN_REVIEW",
            "release_claim_allowed": False,
            "recovery_authorized": False,
            "automatic_restore": False,
            "automatic_deploy": False,
            "executes_action": False,
        },
    }


def verifier(stage, digest, refs):
    verifier_id = f"auditor-{stage}"
    def run(_envelope):
        return {
            "state": "VERIFIED",
            "independent": True,
            "verifier_id": verifier_id,
            "bound_claim_digest": digest,
            "bound_refs": list(refs),
            "reason": "independent staged evidence review",
        }
    return verifier_id, run


def verified_ledger(rows=None, *, trusted_scope=None):
    rows = rows or snapshots()
    scope = trusted_scope or SCOPE
    ledger = default_verification_ledger()
    entry_ids = {}
    for index, (stage, snapshot) in enumerate(rows.items(), start=1):
        digest = stage_claim_digest(stage, snapshot)
        refs = [f"ci:{stage}:15of15"]
        verifier_id, callback = verifier(stage, digest, refs)
        result = record_independent_verification(
            ledger,
            claim_id=f"post-hardening:{stage}",
            claim_kind="HARDENING_GATE",
            claim_digest=digest,
            generator_id=f"stage-generator-{stage}",
            verifier_kind="CODE",
            verifier_id=verifier_id,
            evidence_refs=refs,
            trusted_context=scope,
            verifier=callback,
            created_at=f"2026-10-05T12:{30+index:02d}:00+00:00",
        )
        ledger = result["ledger"]
        entry_ids[stage] = result["entry"]["entry_id"]
    return ledger, entry_ids


class AionPostHardeningReadinessTests(unittest.TestCase):
    def test_every_stage_with_independent_ledger_proof_reaches_owner_review_only(self):
        rows = snapshots()
        ledger, ids = verified_ledger(rows)
        out = evaluate_post_hardening_readiness(
            trusted_scope=SCOPE,
            stage_snapshots=rows,
            verification_ledger=ledger,
            verification_entry_ids=ids,
        )
        self.assertEqual(out["state"], "READY_FOR_HUMAN_OWNER_REVIEW")
        self.assertTrue(out["requires_human_owner_review"])
        self.assertFalse(out["production_ready_claim"])
        self.assertFalse(out["activation_authorized"])
        self.assertFalse(out["merge_authorized"])
        self.assertFalse(out["deploy_authorized"])
        self.assertFalse(out["worker_arming_authorized"])
        self.assertFalse(out["executes_action"])

    def test_tenant_crypto_is_mandatory_and_exact(self):
        rows = snapshots()
        ledger, ids = verified_ledger(rows)
        missing = deepcopy(rows)
        missing.pop("tenant_crypto")
        out_missing = evaluate_post_hardening_readiness(
            trusted_scope=SCOPE,
            stage_snapshots=missing,
            verification_ledger=ledger,
            verification_entry_ids=ids,
        )
        self.assertIn("STAGE_MISSING:tenant_crypto", out_missing["blockers"])

        weakened = deepcopy(rows)
        weakened["tenant_crypto"]["production_kms_connected"] = True
        weakened["tenant_crypto"]["homegrown_crypto"] = True
        out_weakened = evaluate_post_hardening_readiness(
            trusted_scope=SCOPE,
            stage_snapshots=weakened,
            verification_ledger=ledger,
            verification_entry_ids=ids,
        )
        joined = " ".join(out_weakened["blockers"])
        self.assertIn("tenant_crypto:STAGE_CONTRACT_MISMATCH:production_kms_connected", joined)
        self.assertIn("tenant_crypto:STAGE_CONTRACT_MISMATCH:homegrown_crypto", joined)

    def test_pass_string_without_independent_ledger_entry_is_not_evidence(self):
        rows = snapshots()
        ledger, ids = verified_ledger(rows)
        ids.pop("finops")
        out = evaluate_post_hardening_readiness(
            trusted_scope=SCOPE,
            stage_snapshots=rows,
            verification_ledger=ledger,
            verification_entry_ids=ids,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "finops:VERIFICATION_ENTRY_ID_REQUIRED",
            out["blockers"],
        )

    def test_snapshot_tamper_after_verification_breaks_claim_binding(self):
        rows = snapshots()
        ledger, ids = verified_ledger(rows)
        tampered = deepcopy(rows)
        tampered["finops"]["state"] = "BLOCK"
        out = evaluate_post_hardening_readiness(
            trusted_scope=SCOPE,
            stage_snapshots=tampered,
            verification_ledger=ledger,
            verification_entry_ids=ids,
        )
        joined = " ".join(out["blockers"])
        self.assertIn("finops:STAGE_CONTRACT_MISMATCH:state", joined)
        self.assertIn("finops:INDEPENDENT_VERIFICATION_REQUIRED", joined)

    def test_ledger_tamper_blocks_every_claim(self):
        rows = snapshots()
        ledger, ids = verified_ledger(rows)
        ledger["entries"][0]["result_reason"] = "rewritten"
        out = evaluate_post_hardening_readiness(
            trusted_scope=SCOPE,
            stage_snapshots=rows,
            verification_ledger=ledger,
            verification_entry_ids=ids,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("VERIFICATION_LEDGER_INTEGRITY_MISMATCH", out["blockers"])

    def test_cross_scope_verified_entry_is_not_reusable(self):
        rows = snapshots()
        foreign_scope = {**SCOPE, "tenant_id": "tenant-b"}
        ledger, ids = verified_ledger(rows, trusted_scope=foreign_scope)
        out = evaluate_post_hardening_readiness(
            trusted_scope=SCOPE,
            stage_snapshots=rows,
            verification_ledger=ledger,
            verification_entry_ids=ids,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertTrue(any("INDEPENDENT_VERIFICATION_REQUIRED" in x for x in out["blockers"]))

    def test_missing_stage_blocks(self):
        rows = snapshots()
        rows.pop("operational_resilience")
        ledger, ids = verified_ledger(rows)
        out = evaluate_post_hardening_readiness(
            trusted_scope=SCOPE,
            stage_snapshots=rows,
            verification_ledger=ledger,
            verification_entry_ids=ids,
        )
        self.assertIn("STAGE_MISSING:operational_resilience", out["blockers"])

    def test_wrong_schema_blocks_even_if_independently_verified(self):
        rows = snapshots()
        rows["behavioral_eval"] = dict(rows["behavioral_eval"], schema="WRONG")
        ledger, ids = verified_ledger(rows)
        out = evaluate_post_hardening_readiness(
            trusted_scope=SCOPE,
            stage_snapshots=rows,
            verification_ledger=ledger,
            verification_entry_ids=ids,
        )
        self.assertIn(
            "behavioral_eval:STAGE_SCHEMA_MISMATCH",
            out["blockers"],
        )

    def test_boolean_contract_cannot_be_spoofed_by_strings_or_ints(self):
        rows = snapshots()
        rows["incident_control"] = dict(
            rows["incident_control"],
            automatic_control_mutation="false",
        )
        ledger, ids = verified_ledger(rows)
        out = evaluate_post_hardening_readiness(
            trusted_scope=SCOPE,
            stage_snapshots=rows,
            verification_ledger=ledger,
            verification_entry_ids=ids,
        )
        self.assertIn(
            "incident_control:STAGE_CONTRACT_MISMATCH:automatic_control_mutation",
            out["blockers"],
        )

    def test_unexpected_stage_input_blocks_instead_of_being_silently_ignored(self):
        rows = snapshots()
        rows["mystery"] = {"schema": "PASS", "state": "PASS"}
        base = snapshots()
        ledger, ids = verified_ledger(base)
        out = evaluate_post_hardening_readiness(
            trusted_scope=SCOPE,
            stage_snapshots=rows,
            verification_ledger=ledger,
            verification_entry_ids=ids,
        )
        self.assertIn("UNEXPECTED_STAGE_INPUT", out["blockers"])

    def test_malformed_top_level_inputs_fail_closed_without_exception(self):
        out = evaluate_post_hardening_readiness(
            trusted_scope=["bad"],
            stage_snapshots="bad",
            verification_ledger={},
            verification_entry_ids="bad",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("TRUSTED_SCOPE_REQUIRED", out["blockers"])
        self.assertIn("STAGE_SNAPSHOTS_MAPPING_REQUIRED", out["blockers"])
        self.assertIn("VERIFICATION_ENTRY_IDS_MAPPING_REQUIRED", out["blockers"])

    def test_unexpected_verification_entry_id_is_not_silently_ignored(self):
        rows = snapshots()
        ledger, ids = verified_ledger(rows)
        ids["mystery"] = "VFY-UNKNOWN"
        out = evaluate_post_hardening_readiness(
            trusted_scope=SCOPE,
            stage_snapshots=rows,
            verification_ledger=ledger,
            verification_entry_ids=ids,
        )
        self.assertIn("UNEXPECTED_VERIFICATION_ENTRY_ID", out["blockers"])

    def test_review_plan_is_non_executing(self):
        rows = snapshots()
        ledger, ids = verified_ledger(rows)
        out = evaluate_post_hardening_readiness(
            trusted_scope=SCOPE,
            stage_snapshots=rows,
            verification_ledger=ledger,
            verification_entry_ids=ids,
        )
        plan = post_hardening_review_plan(out)
        self.assertEqual(plan["state"], "REVIEW_PLAN_READY")
        self.assertFalse(plan["review_is_authority"])
        self.assertFalse(plan["automatic_merge"])
        self.assertFalse(plan["automatic_deploy"])
        self.assertFalse(plan["automatic_activation"])
        self.assertFalse(plan["executes_action"])


if __name__ == "__main__":
    unittest.main()
