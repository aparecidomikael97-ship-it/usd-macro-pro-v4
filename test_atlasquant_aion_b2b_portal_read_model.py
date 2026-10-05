from __future__ import annotations

import unittest

from atlasquant_aion_b2b_portal_read_model import build_customer_portal_read_model

SCOPE = {"owner_id": "owner-a", "tenant_id": "tenant-a", "workspace_id": "ws-a"}


def contract(**overrides):
    core = {
        **SCOPE,
        "customer_id": "customer-001",
        "package": "PROFISSIONAL",
        "max_capacity_units": 60,
        "max_calls_per_cycle": 1000,
        "max_tokens_per_cycle": 1000000,
        "max_support_tickets_per_cycle": 40,
        "sla_first_response_hours": 4.0,
        "sla_resolution_hours": 24.0,
    }
    core.update(overrides.pop("contract", {}))
    row = {
        "state": "DRAFT_FOR_OWNER_ACTIVATION",
        "activation_state": "BLOCKED_UNTIL_OWNER_ACTIVATION",
        "blockers": [],
        "contract_digest": "sha256:contract",
        "contract": core,
    }
    row.update(overrides)
    return row


def cycle(**overrides):
    row = {
        **SCOPE,
        "state": "HEALTHY",
        "decision": "RENEWAL_REVIEW_CANDIDATE",
        "customer_id": "customer-001",
        "package": "PROFISSIONAL",
        "actual_service_cost_brl": 2200.0,
        "health_score": 88.0,
        "observed_roi_pct": 60.0,
        "review_reasons": [],
        "incident_reasons": [],
        "blockers": [],
        "evidence_digest": "sha256:cycle",
    }
    row.update(overrides)
    return row


def usage(**overrides):
    row = {
        **SCOPE,
        "customer_id": "customer-001",
        "used_capacity_units": 40,
        "calls": 700,
        "tokens": 700000,
        "support_tickets": 20,
    }
    row.update(overrides)
    return row


def support(**overrides):
    row = {
        **SCOPE,
        "customer_id": "customer-001",
        "avg_first_response_hours": 2.0,
        "avg_resolution_hours": 12.0,
        "critical_open_tickets": 0,
    }
    row.update(overrides)
    return row


class AionB2BPortalReadModelTests(unittest.TestCase):
    def test_valid_evidence_builds_ready_read_only_snapshot(self):
        out = build_customer_portal_read_model(
            trusted_scope=SCOPE,
            contract_result=contract(),
            cycle_result=cycle(),
            usage_evidence=usage(),
            support_evidence=support(),
            generated_at="2026-10-05T12:00:00-04:00",
            evidence_refs=["cycle:v1", "finops:v1", "quota:v1", "support:v1"],
        )
        self.assertEqual(out["state"], "READY")
        self.assertEqual(out["health_label"], "SAUDÁVEL")
        self.assertEqual(out["health_score"], 88.0)
        self.assertEqual(out["observed_roi_pct"], 60.0)
        self.assertEqual(out["usage"]["capacity"]["utilization_pct"], 66.67)
        self.assertEqual(out["usage"]["calls"]["utilization_pct"], 70.0)
        self.assertTrue(out["support"]["first_response_sla_met"])
        self.assertTrue(out["support"]["resolution_sla_met"])
        self.assertTrue(out["read_only"])
        self.assertFalse(out["grants_authority"])

    def test_scope_mismatch_blocks(self):
        out = build_customer_portal_read_model(
            trusted_scope=SCOPE,
            contract_result=contract(),
            cycle_result=cycle(),
            usage_evidence=usage(tenant_id="tenant-b"),
            support_evidence=support(),
            generated_at="2026-10-05T12:00:00-04:00",
            evidence_refs=["a", "b", "c", "d"],
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("USAGE_SCOPE_MISMATCH", out["blockers"])

    def test_cross_tenant_cycle_evidence_is_rejected(self):
        out = build_customer_portal_read_model(
            trusted_scope=SCOPE,
            contract_result=contract(),
            cycle_result=cycle(tenant_id="tenant-b"),
            usage_evidence=usage(),
            support_evidence=support(),
            generated_at="2026-10-05T12:00:00-04:00",
            evidence_refs=["a", "b", "c", "d"],
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("SERVICE_CYCLE_SCOPE_MISMATCH", out["blockers"])

    def test_blocked_service_cycle_is_not_presentable(self):
        out = build_customer_portal_read_model(
            trusted_scope=SCOPE,
            contract_result=contract(),
            cycle_result=cycle(state="BLOCKED", decision="BLOCKED"),
            usage_evidence=usage(),
            support_evidence=support(),
            generated_at="2026-10-05T12:00:00-04:00",
            evidence_refs=["a", "b", "c", "d"],
        )
        self.assertIn("SERVICE_CYCLE_STATE_NOT_PRESENTABLE", out["blockers"])
        self.assertIn("SERVICE_CYCLE_DECISION_NOT_PRESENTABLE", out["blockers"])

    def test_usage_limits_come_from_contract_not_caller_claims(self):
        out = build_customer_portal_read_model(
            trusted_scope=SCOPE,
            contract_result=contract(),
            cycle_result=cycle(),
            usage_evidence=usage(used_capacity_units=30),
            support_evidence=support(),
            generated_at="2026-10-05T12:00:00-04:00",
            evidence_refs=["a", "b", "c", "d"],
        )
        self.assertEqual(out["usage"]["capacity"]["limit"], 60)
        self.assertEqual(out["usage"]["capacity"]["utilization_pct"], 50.0)

    def test_support_sla_miss_is_displayed_not_reinterpreted_as_authority(self):
        out = build_customer_portal_read_model(
            trusted_scope=SCOPE,
            contract_result=contract(),
            cycle_result=cycle(state="REMEDIATION", decision="REMEDIATE_REVIEW", health_score=68.0),
            usage_evidence=usage(),
            support_evidence=support(avg_first_response_hours=6.0),
            generated_at="2026-10-05T12:00:00-04:00",
            evidence_refs=["a", "b", "c", "d"],
        )
        self.assertEqual(out["state"], "READY")
        self.assertEqual(out["health_label"], "ATENÇÃO")
        self.assertFalse(out["support"]["first_response_sla_met"])
        self.assertFalse(out["automatic_renewal"])

    def test_incident_review_is_visible_but_never_auto_terminates(self):
        out = build_customer_portal_read_model(
            trusted_scope=SCOPE,
            contract_result=contract(),
            cycle_result=cycle(
                state="INCIDENT_REVIEW",
                decision="INCIDENT_REVIEW",
                incident_reasons=["TENANT_PRIVACY_INCIDENT"],
            ),
            usage_evidence=usage(),
            support_evidence=support(),
            generated_at="2026-10-05T12:00:00-04:00",
            evidence_refs=["a", "b", "c", "d"],
        )
        self.assertEqual(out["health_label"], "INCIDENTE")
        self.assertIn("TENANT_PRIVACY_INCIDENT", out["incident_reasons"])
        self.assertFalse(out["automatic_customer_contact"])
        self.assertFalse(out["production_mutation"])

    def test_evidence_refs_are_required(self):
        out = build_customer_portal_read_model(
            trusted_scope=SCOPE,
            contract_result=contract(),
            cycle_result=cycle(),
            usage_evidence=usage(),
            support_evidence=support(),
            generated_at="2026-10-05T12:00:00-04:00",
            evidence_refs=["one"],
        )
        self.assertIn("PORTAL_EVIDENCE_INSUFFICIENT", out["blockers"])

    def test_no_external_authority_is_granted(self):
        out = build_customer_portal_read_model(
            trusted_scope=SCOPE,
            contract_result=contract(),
            cycle_result=cycle(),
            usage_evidence=usage(),
            support_evidence=support(),
            generated_at="2026-10-05T12:00:00-04:00",
            evidence_refs=["a", "b", "c", "d"],
        )
        for key in (
            "grants_authority",
            "automatic_renewal",
            "automatic_billing",
            "automatic_quota_change",
            "automatic_role_change",
            "automatic_customer_contact",
            "automatic_deploy",
            "production_mutation",
            "executes_action",
        ):
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
