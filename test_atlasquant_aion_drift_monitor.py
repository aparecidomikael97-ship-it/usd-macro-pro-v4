from __future__ import annotations

import unittest

from atlasquant_aion_drift_monitor import evaluate_drift, drift_promotion_gate

SCOPE = {"owner_id": "owner-a", "tenant_id": "tenant-a", "workspace_id": "ws-a"}


def policy(**extra):
    row = {
        "state": "VERIFIED",
        "policy_id": "drift-v1",
        "revision": 1,
        **SCOPE,
        "min_sample_size": 100,
        "data_psi_warn": 0.10,
        "data_psi_block": 0.25,
        "decision_tvd_warn": 0.10,
        "decision_tvd_block": 0.20,
        "max_safety_violation_delta_pct_points": 0.5,
        "max_unknown_rate_pct": 5.0,
        "max_override_rate_pct": 10.0,
    }
    row.update(extra)
    return row


def snapshot(
    *,
    version="v1",
    feature_a=None,
    feature_b=None,
    decisions=None,
    safety=0.2,
    unknown=1.0,
    override=2.0,
    sample=1000,
    tenant="tenant-a",
):
    return {
        "owner_id": "owner-a",
        "tenant_id": tenant,
        "workspace_id": "ws-a",
        "version": version,
        "window": "2026-W40",
        "sample_size": sample,
        "features": {
            "country": feature_a or {"BR": 0.7, "US": 0.3},
            "channel": feature_b or {"WEB": 0.6, "APP": 0.4},
        },
        "decisions": decisions or {"ALLOW": 0.8, "BLOCK": 0.2},
        "safety_violation_rate_pct": safety,
        "unknown_rate_pct": unknown,
        "override_rate_pct": override,
        "evidence_refs": [f"metrics:{version}"],
    }


class AionDriftMonitorTests(unittest.TestCase):
    def test_stable_data_and_decisions_remain_stable(self):
        out = evaluate_drift(
            trusted_scope=SCOPE,
            policy=policy(),
            reference_snapshot=snapshot(version="baseline"),
            current_snapshot=snapshot(version="candidate"),
        )
        self.assertEqual(out["state"], "STABLE")
        self.assertEqual(out["promotion_recommendation"], "REVIEW_OK")
        self.assertFalse(out["automatic_retraining"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["production_mutation"])
        self.assertFalse(out["executes_action"])

    def test_moderate_data_drift_degrades(self):
        out = evaluate_drift(
            trusted_scope=SCOPE,
            policy=policy(),
            reference_snapshot=snapshot(version="baseline"),
            current_snapshot=snapshot(
                version="candidate",
                feature_a={"BR": 0.54, "US": 0.46},
            ),
        )
        self.assertEqual(out["state"], "DEGRADED")
        self.assertTrue(any(x.startswith("DATA_DRIFT_WARN:") for x in out["degrade_reasons"]))
        self.assertEqual(out["promotion_recommendation"], "HOLD_PROMOTION")

    def test_severe_data_drift_blocks(self):
        out = evaluate_drift(
            trusted_scope=SCOPE,
            policy=policy(),
            reference_snapshot=snapshot(version="baseline"),
            current_snapshot=snapshot(
                version="candidate",
                feature_a={"BR": 0.3, "US": 0.7},
            ),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertTrue(any(x.startswith("DATA_DRIFT_BLOCK:") for x in out["blockers"]))

    def test_decision_distribution_drift_degrades_or_blocks_by_threshold(self):
        degraded = evaluate_drift(
            trusted_scope=SCOPE,
            policy=policy(),
            reference_snapshot=snapshot(version="baseline"),
            current_snapshot=snapshot(
                version="candidate",
                decisions={"ALLOW": 0.68, "BLOCK": 0.32},
            ),
        )
        self.assertEqual(degraded["state"], "DEGRADED")
        self.assertIn("DECISION_DRIFT_WARN", degraded["degrade_reasons"])

        blocked = evaluate_drift(
            trusted_scope=SCOPE,
            policy=policy(),
            reference_snapshot=snapshot(version="baseline"),
            current_snapshot=snapshot(
                version="candidate",
                decisions={"ALLOW": 0.55, "BLOCK": 0.45},
            ),
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn("DECISION_DRIFT_BLOCK", blocked["blockers"])

    def test_safety_violation_regression_blocks(self):
        out = evaluate_drift(
            trusted_scope=SCOPE,
            policy=policy(),
            reference_snapshot=snapshot(version="baseline", safety=0.2),
            current_snapshot=snapshot(version="candidate", safety=0.8),
        )
        self.assertIn("SAFETY_VIOLATION_REGRESSION", out["blockers"])

    def test_unknown_and_override_limits_block(self):
        out = evaluate_drift(
            trusted_scope=SCOPE,
            policy=policy(),
            reference_snapshot=snapshot(version="baseline"),
            current_snapshot=snapshot(version="candidate", unknown=6.0, override=11.0),
        )
        self.assertIn("UNKNOWN_RATE_LIMIT", out["blockers"])
        self.assertIn("OVERRIDE_RATE_LIMIT", out["blockers"])

    def test_cross_scope_snapshot_blocks(self):
        out = evaluate_drift(
            trusted_scope=SCOPE,
            policy=policy(),
            reference_snapshot=snapshot(version="baseline"),
            current_snapshot=snapshot(version="candidate", tenant="tenant-b"),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("CURRENT:SNAPSHOT_SCOPE_MISMATCH", out["blockers"])

    def test_small_sample_or_missing_evidence_blocks(self):
        current = snapshot(version="candidate", sample=10)
        current["evidence_refs"] = []
        out = evaluate_drift(
            trusted_scope=SCOPE,
            policy=policy(),
            reference_snapshot=snapshot(version="baseline"),
            current_snapshot=current,
        )
        self.assertIn("CURRENT:SAMPLE_SIZE_INSUFFICIENT", out["blockers"])
        self.assertIn("CURRENT:SNAPSHOT_EVIDENCE_REQUIRED", out["blockers"])

    def test_distribution_must_be_normalized_and_finite(self):
        invalid = snapshot(version="candidate")
        invalid["features"]["country"] = {"BR": 0.9, "US": 0.9}
        invalid["decisions"] = {"ALLOW": True, "BLOCK": 0.0}
        out = evaluate_drift(
            trusted_scope=SCOPE,
            policy=policy(),
            reference_snapshot=snapshot(version="baseline"),
            current_snapshot=invalid,
        )
        joined = " ".join(out["blockers"])
        self.assertIn("DISTRIBUTION_MUST_SUM_TO_ONE", joined)
        self.assertIn("DISTRIBUTION_VALUE_INVALID", joined)

    def test_feature_set_mismatch_blocks(self):
        current = snapshot(version="candidate")
        current["features"].pop("channel")
        out = evaluate_drift(
            trusted_scope=SCOPE,
            policy=policy(),
            reference_snapshot=snapshot(version="baseline"),
            current_snapshot=current,
        )
        self.assertIn("FEATURE_SET_MISMATCH", out["blockers"])

    def test_unverified_or_cross_scope_policy_blocks_before_scoring(self):
        out = evaluate_drift(
            trusted_scope=SCOPE,
            policy=policy(state="DRAFT", tenant_id="tenant-b"),
            reference_snapshot=snapshot(version="baseline"),
            current_snapshot=snapshot(version="candidate"),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("POLICY_NOT_VERIFIED", out["blockers"])
        self.assertIn("POLICY_SCOPE_MISMATCH", out["blockers"])

    def test_threshold_order_must_be_fail_closed(self):
        out = evaluate_drift(
            trusted_scope=SCOPE,
            policy=policy(data_psi_warn=0.3, data_psi_block=0.2),
            reference_snapshot=snapshot(version="baseline"),
            current_snapshot=snapshot(version="candidate"),
        )
        self.assertIn("DATA_PSI_THRESHOLDS_INVALID", out["blockers"])

    def test_promotion_gate_never_promotes_automatically(self):
        report = evaluate_drift(
            trusted_scope=SCOPE,
            policy=policy(),
            reference_snapshot=snapshot(version="baseline"),
            current_snapshot=snapshot(version="candidate"),
        )
        gate = drift_promotion_gate(report)
        self.assertEqual(gate["state"], "HUMAN_REVIEW_CANDIDATE")
        self.assertFalse(gate["promotion_authorized"])
        self.assertFalse(gate["automatic_promotion"])
        self.assertFalse(gate["automatic_retraining"])
        self.assertFalse(gate["executes_action"])

        report["state"] = "DEGRADED"
        blocked = drift_promotion_gate(report)
        self.assertEqual(blocked["state"], "BLOCK_PROMOTION")


if __name__ == "__main__":
    unittest.main()
