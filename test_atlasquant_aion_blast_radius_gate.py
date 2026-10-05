from __future__ import annotations
from copy import deepcopy
import unittest

from atlasquant_aion_blast_radius_gate import (
    BUDGET_SCHEMA,
    blast_radius_policy_contract,
    candidate_digest,
    evaluate_blast_radius,
)

SCOPE = {"owner_id":"owner-a","tenant_id":"tenant-a","workspace_id":"ws-a"}


def policy(**overrides):
    row = {
        "state":"VERIFIED",
        "policy_id":"blast-v1",
        "revision":1,
        **SCOPE,
        "max_affected_records":100,
        "max_external_targets":5,
        "max_financial_value_minor":10000,
        "max_tenants":1,
        "max_workspaces":1,
        "quorum_by_risk":{"LOW":0,"MEDIUM":1,"HIGH":2,"CRITICAL":2},
        "human_owner_required_for":["HIGH","CRITICAL"],
    }
    row.update(overrides)
    return row


def candidate(**overrides):
    row = {
        **SCOPE,
        "action_id":"action-1",
        "transaction_id":"tx-1",
        "action":"SEND_EMAIL",
        "proposer_id":"prime",
        "risk_level":"MEDIUM",
        "affected_tenant_ids":["tenant-a"],
        "affected_workspace_ids":["ws-a"],
        "affected_records":10,
        "external_targets":1,
        "financial_value_minor":0,
        "external_side_effect":True,
        "reversible":True,
        "rollback_ref":"rollback:1",
        "authority_budget_ref":"budget-1",
        "authority_budget_policy_digest":"budget-policy-digest",
    }
    row.update(overrides)
    return row


def budget(**overrides):
    row = {
        "schema":BUDGET_SCHEMA,
        "allowed":True,
        "transaction_id":"tx-1",
        "authority_budget_ref":"budget-1",
        "policy_digest":"budget-policy-digest",
        "grants_authority":False,
        "executes_action":False,
    }
    row.update(overrides)
    return row


def review(cand, reviewer_id="guardian", reviewer_kind="GUARDIAN", **overrides):
    row = {
        **SCOPE,
        "reviewer_id":reviewer_id,
        "reviewer_kind":reviewer_kind,
        "decision":"SUPPORT",
        "independent":True,
        "candidate_digest":candidate_digest(cand),
    }
    row.update(overrides)
    return row


def owner_approval(cand, **overrides):
    row = {
        **SCOPE,
        "owner_id":"owner-a",
        "action_id":cand["action_id"],
        "candidate_digest":candidate_digest(cand),
        "authority_class":"HUMAN_OWNER",
        "approved":True,
    }
    row.update(overrides)
    return row


class AionBlastRadiusQuorumTests(unittest.TestCase):
    def test_medium_side_effect_requires_budget_and_independent_quorum(self):
        cand = candidate()
        out = evaluate_blast_radius(
            trusted_scope=SCOPE,
            policy=policy(),
            candidate=cand,
            authority_budget_guard=budget(),
            reviews=[review(cand)],
        )
        self.assertEqual(out["state"], "READY_FOR_DOWNSTREAM_EXECUTION_GATE")
        self.assertEqual(out["valid_reviewer_count"], 1)
        self.assertFalse(out["execution_authorized"])
        self.assertFalse(out["executes_action"])

    def test_quorum_never_replaces_human_owner_for_high_risk(self):
        cand = candidate(risk_level="HIGH")
        reviews = [
            review(cand, "guardian", "GUARDIAN"),
            review(cand, "shadow", "SHADOW"),
            review(cand, "sentinel", "SENTINEL"),
        ]
        out = evaluate_blast_radius(
            trusted_scope=SCOPE,
            policy=policy(),
            candidate=cand,
            authority_budget_guard=budget(),
            reviews=reviews,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("HUMAN_OWNER_APPROVAL_REQUIRED", out["blockers"])
        self.assertTrue(out["quorum_never_replaces_human_owner"])

    def test_exact_owner_approval_allows_review_readiness_but_not_execution(self):
        cand = candidate(risk_level="HIGH")
        out = evaluate_blast_radius(
            trusted_scope=SCOPE,
            policy=policy(),
            candidate=cand,
            authority_budget_guard=budget(),
            reviews=[
                review(cand, "guardian", "GUARDIAN"),
                review(cand, "shadow", "SHADOW"),
            ],
            human_owner_approval=owner_approval(cand),
        )
        self.assertEqual(out["state"], "READY_FOR_DOWNSTREAM_EXECUTION_GATE")
        self.assertTrue(out["human_owner_approval_valid"])
        self.assertFalse(out["execution_authorized"])
        self.assertFalse(out["automatic_execution"])

    def test_sensitive_action_requires_owner_even_when_risk_is_medium(self):
        cand = candidate(action="DEPLOY_PRODUCTION")
        out = evaluate_blast_radius(
            trusted_scope=SCOPE,
            policy=policy(),
            candidate=cand,
            authority_budget_guard=budget(),
            reviews=[review(cand)],
        )
        self.assertIn("HUMAN_OWNER_APPROVAL_REQUIRED", out["blockers"])
        self.assertTrue(out["requires_specialized_execution_gate"])

    def test_agent_cannot_forge_human_owner_approval(self):
        cand = candidate(risk_level="HIGH")
        fake = owner_approval(cand, authority_class="GUARDIAN", owner_id="guardian")
        out = evaluate_blast_radius(
            trusted_scope=SCOPE,
            policy=policy(),
            candidate=cand,
            authority_budget_guard=budget(),
            reviews=[
                review(cand, "guardian", "GUARDIAN"),
                review(cand, "shadow", "SHADOW"),
            ],
            human_owner_approval=fake,
        )
        joined = " ".join(out["blockers"])
        self.assertIn("HUMAN_OWNER_AUTHORITY_CLASS_REQUIRED", joined)
        self.assertIn("HUMAN_OWNER_ID_MISMATCH", joined)

    def test_duplicate_and_self_reviews_do_not_count(self):
        cand = candidate(risk_level="HIGH")
        rows = [
            review(cand, "guardian", "GUARDIAN"),
            review(cand, "guardian", "GUARDIAN"),
            review(cand, "prime", "SHADOW"),
        ]
        out = evaluate_blast_radius(
            trusted_scope=SCOPE,
            policy=policy(),
            candidate=cand,
            authority_budget_guard=budget(),
            reviews=rows,
            human_owner_approval=owner_approval(cand),
        )
        self.assertEqual(out["valid_reviewer_count"], 1)
        self.assertIn("INDEPENDENT_REVIEW_QUORUM_INSUFFICIENT", out["blockers"])

    def test_review_is_bound_to_exact_candidate_digest_and_scope(self):
        cand = candidate()
        bad = review(cand, candidate_digest="sha256:other", tenant_id="tenant-b")
        out = evaluate_blast_radius(
            trusted_scope=SCOPE,
            policy=policy(),
            candidate=cand,
            authority_budget_guard=budget(),
            reviews=[bad],
        )
        self.assertEqual(out["valid_reviewer_count"], 0)
        self.assertIn("INDEPENDENT_REVIEW_QUORUM_INSUFFICIENT", out["blockers"])

    def test_authority_budget_must_be_allow_and_exactly_bound(self):
        cand = candidate()
        out = evaluate_blast_radius(
            trusted_scope=SCOPE,
            policy=policy(),
            candidate=cand,
            authority_budget_guard=budget(
                allowed=False,
                transaction_id="tx-other",
                policy_digest="other",
            ),
            reviews=[review(cand)],
        )
        joined = " ".join(out["blockers"])
        self.assertIn("AUTHORITY_BUDGET_BLOCKED", joined)
        self.assertIn("AUTHORITY_BUDGET_TRANSACTION_MISMATCH", joined)
        self.assertIn("AUTHORITY_BUDGET_POLICY_MISMATCH", joined)

    def test_budget_cannot_claim_authority_or_execution(self):
        cand = candidate()
        out = evaluate_blast_radius(
            trusted_scope=SCOPE,
            policy=policy(),
            candidate=cand,
            authority_budget_guard=budget(grants_authority=True, executes_action=True),
            reviews=[review(cand)],
        )
        joined = " ".join(out["blockers"])
        self.assertIn("AUTHORITY_BUDGET_MUST_NOT_GRANT_AUTHORITY", joined)
        self.assertIn("AUTHORITY_BUDGET_MUST_NOT_EXECUTE", joined)

    def test_cross_tenant_or_workspace_blast_is_blocked(self):
        cand = candidate(
            affected_tenant_ids=["tenant-a","tenant-b"],
            affected_workspace_ids=["ws-a","ws-b"],
        )
        out = evaluate_blast_radius(
            trusted_scope=SCOPE,
            policy=policy(max_tenants=2,max_workspaces=2),
            candidate=cand,
            authority_budget_guard=budget(),
            reviews=[review(cand)],
        )
        joined = " ".join(out["blockers"])
        self.assertIn("CROSS_TENANT_BLAST_RADIUS_FORBIDDEN", joined)
        self.assertIn("CROSS_WORKSPACE_BLAST_RADIUS_FORBIDDEN", joined)

    def test_record_external_and_financial_limits_fail_closed(self):
        cand = candidate(affected_records=101, external_targets=6, financial_value_minor=10001)
        out = evaluate_blast_radius(
            trusted_scope=SCOPE,
            policy=policy(),
            candidate=cand,
            authority_budget_guard=budget(),
            reviews=[review(cand)],
        )
        joined = " ".join(out["blockers"])
        self.assertIn("RECORD_BLAST_RADIUS_LIMIT", joined)
        self.assertIn("EXTERNAL_TARGET_BLAST_RADIUS_LIMIT", joined)
        self.assertIn("FINANCIAL_BLAST_RADIUS_LIMIT", joined)

    def test_high_risk_must_be_reversible_and_have_rollback_ref(self):
        cand = candidate(risk_level="HIGH", reversible=False, rollback_ref="")
        out = evaluate_blast_radius(
            trusted_scope=SCOPE,
            policy=policy(),
            candidate=cand,
            authority_budget_guard=budget(),
            reviews=[
                review(cand, "guardian", "GUARDIAN"),
                review(cand, "shadow", "SHADOW"),
            ],
            human_owner_approval=owner_approval(cand),
        )
        self.assertIn("HIGH_RISK_MUST_BE_REVERSIBLE", out["blockers"])

    def test_string_booleans_do_not_pass(self):
        cand = candidate(external_side_effect="true", reversible="true")
        out = evaluate_blast_radius(
            trusted_scope=SCOPE,
            policy=policy(),
            candidate=cand,
            authority_budget_guard=budget(),
            reviews=[review(cand)],
        )
        joined = " ".join(out["blockers"])
        self.assertIn("EXTERNAL_SIDE_EFFECT_BOOL_REQUIRED", joined)
        self.assertIn("REVERSIBLE_BOOL_REQUIRED", joined)

    def test_candidate_tamper_after_review_breaks_binding(self):
        original = candidate()
        signed_review = review(original)
        changed = deepcopy(original)
        changed["affected_records"] = 11
        out = evaluate_blast_radius(
            trusted_scope=SCOPE,
            policy=policy(),
            candidate=changed,
            authority_budget_guard=budget(),
            reviews=[signed_review],
        )
        self.assertIn("INDEPENDENT_REVIEW_QUORUM_INSUFFICIENT", out["blockers"])

    def test_policy_requires_critical_human_owner(self):
        broken = policy(human_owner_required_for=["HIGH"])
        cand = candidate()
        out = evaluate_blast_radius(
            trusted_scope=SCOPE,
            policy=broken,
            candidate=cand,
            authority_budget_guard=budget(),
            reviews=[review(cand)],
        )
        self.assertIn("CRITICAL_MUST_REQUIRE_HUMAN_OWNER", out["blockers"])

    def test_contract_is_non_authoritative(self):
        contract = blast_radius_policy_contract()
        self.assertTrue(contract["quorum_never_replaces_human_owner"])
        self.assertFalse(contract["automatic_execution"])
        self.assertFalse(contract["executes_action"])


if __name__ == "__main__":
    unittest.main()
