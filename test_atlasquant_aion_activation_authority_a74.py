"""A74 adversarial lab: no local readiness, self-hash plan or ticket is authority.

These fixtures are synthetic. This suite does not invoke the Worker, writer,
real issuer, external witness, Windows TPM or a network client.
"""
import unittest
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

import test_atlasquant_aion_global_worker_activation as prior
from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_intelligence.evidence import digest
from atlasquant_aion_core_runtime_bridge import authenticated_context
from atlasquant_aion_global_worker_activation import (
    APPROVAL_SCHEMA, CONFIRMATION_PHRASE, PLAN_SCHEMA,
    _payload_digest, _readiness_contract, _runtime_armed_contract,
    _scope_payload, approve_global_worker_activation_plan,
    prepare_global_worker_activation_plan,
    validate_global_worker_activation_approval,
    write_repository_feature_flag_enabled,
)


class A74PlanTicketDenialTests(unittest.TestCase):
    def setUp(self):
        self.fixture = prior.GlobalWorkerActivationCeremonyTests()
        self.fixture.setUp()
        self.now = prior.NOW
        self.ctx = authenticated_context(self.fixture.access, Domain.ADMIN)
        self.runtime_contract = _runtime_armed_contract(self.fixture.runtime)
        self.assertEqual(self.runtime_contract["state"], "READY")

    def legacy_plan(self):
        r = self.runtime_contract
        plan = {
            "schema": PLAN_SCHEMA,
            "actor_id": self.ctx.actor_id,
            "scope": _scope_payload(self.ctx),
            "runtime_sha": r["runtime_sha"],
            "runtime_checkpoint_digest": r["runtime_checkpoint_digest"],
            "arm_digest": r["arm_digest"],
            "arming_plan_digest": r["arming_plan_digest"],
            "arming_approval_digest": r["arming_approval_digest"],
            "feature_flag_state": "UNSET",
            "feature_flag_target_state": "ENABLED",
            "created_at": self.now.isoformat(),
            "expires_at": (self.now + timedelta(seconds=600)).isoformat(),
        }
        plan["plan_digest"] = _payload_digest(plan, "plan_digest")
        return plan

    def legacy_ticket(self):
        plan = self.legacy_plan()
        ticket = {
            "schema": APPROVAL_SCHEMA,
            "plan_digest": plan["plan_digest"],
            "actor_id": self.ctx.actor_id,
            "scope": _scope_payload(self.ctx),
            "runtime_sha": plan["runtime_sha"],
            "runtime_checkpoint_digest": plan["runtime_checkpoint_digest"],
            "arm_digest": plan["arm_digest"],
            "arming_plan_digest": plan["arming_plan_digest"],
            "arming_approval_digest": plan["arming_approval_digest"],
            "feature_flag_state_at_plan": "UNSET",
            "feature_flag_target_state": "ENABLED",
            "issued_at": self.now.isoformat(),
            "expires_at": plan["expires_at"],
            "confirmation_phrase_digest": digest(CONFIRMATION_PHRASE),
        }
        ticket["approval_digest"] = _payload_digest(ticket, "approval_digest")
        return ticket

    def test_01_local_pass_and_forged_true_witness_cannot_pass_readiness_contract(self):
        for mode in ("missing", "false", "true", "future", "stale"):
            with self.subTest(mode=mode):
                readiness = deepcopy(self.fixture.readiness)
                if mode in ("false", "true"):
                    claimed = mode == "true"
                    for name in (
                        "source_authenticity_verified",
                        "independent_witness_verified",
                        "source_resource_owner_bound",
                        "external_activation_allowed",
                    ):
                        readiness[name] = claimed
                if mode == "future":
                    readiness["checked_at"] = (self.now + timedelta(days=365)).isoformat()
                if mode == "stale":
                    readiness["checked_at"] = (self.now - timedelta(days=365)).isoformat()
                r = _readiness_contract(readiness)
                self.assertEqual(r["state"], "BLOCKED")
                self.assertEqual(r["reason"], "INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED")

    def test_02_fake_readiness_cannot_make_plan_even_with_armed_runtime(self):
        for claimed in (None, False, True):
            with self.subTest(witness_claim=claimed):
                readiness = deepcopy(self.fixture.readiness)
                if claimed is not None:
                    for name in (
                        "source_authenticity_verified", "independent_witness_verified",
                        "source_resource_owner_bound", "external_activation_allowed",
                    ):
                        readiness[name] = claimed
                before = deepcopy(self.fixture.runtime)
                result = prepare_global_worker_activation_plan(
                    self.fixture.access, self.fixture.runtime, readiness,
                    prior._safe_flag("UNSET"), now=self.now,
                )
                self.assertEqual(result["status"], "BLOCKED")
                self.assertEqual(result["reason"], "INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED")
                self.assertNotIn("plan", result)
                self.assertIs(result["feature_flag_modified"], False)
                self.assertIs(result["global_worker_executed"], False)
                self.assertEqual(self.fixture.runtime, before)

    def test_03_legacy_self_hashed_plan_cannot_emit_activation_ticket(self):
        plan = self.legacy_plan()
        result = approve_global_worker_activation_plan(
            self.fixture.access, plan,
            confirmation=True, confirmation_phrase=CONFIRMATION_PHRASE,
            now=self.now,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED")
        self.assertNotIn("approval", result)

    def test_04_legacy_ticket_cannot_validate_or_replay_with_matching_runtime(self):
        ticket = self.legacy_ticket()
        for attempt in range(2):
            with self.subTest(attempt=attempt):
                r = validate_global_worker_activation_approval(
                    self.fixture.access, self.fixture.runtime, ticket, now=self.now,
                )
                self.assertEqual(r["state"], "BLOCKED")
                self.assertEqual(r["reason"], "INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED")

    def test_05_tenant_crossing_and_runtime_mismatch_remain_blocked(self):
        ticket = self.legacy_ticket()
        wrong_owner = prior._access(username="other-owner", fingerprint="other-fingerprint-1234567890")
        wrong_tenant = validate_global_worker_activation_approval(
            wrong_owner, self.fixture.runtime, ticket, now=self.now,
        )
        self.assertEqual(wrong_tenant["state"], "BLOCKED")
        modified = deepcopy(self.fixture.runtime)
        modified["sha"] = "changed-sha"
        mismatch = validate_global_worker_activation_approval(
            self.fixture.access, modified, ticket, now=self.now,
        )
        self.assertEqual(mismatch["state"], "BLOCKED")

    def test_06_direct_real_writer_stays_denied_without_transport(self):
        with patch("atlasquant_aion_global_worker_activation.requests.post") as post, patch(
            "atlasquant_aion_global_worker_activation.requests.patch"
        ) as patcher:
            out = write_repository_feature_flag_enabled(prior._config(), "UNSET")
        self.assertEqual(out["status"], "BLOCKED")
        self.assertEqual(out["reason"], "INDEPENDENT_ACTIVATION_AUTHORITY_NOT_ENROLLED")
        post.assert_not_called()
        patcher.assert_not_called()


if __name__ == "__main__":
    unittest.main()
