from __future__ import annotations
import unittest

from atlasquant_aion_finops_metering import (
    build_metering_ledger,
    evaluate_finops_budget,
    normalize_meter_event,
    reconcile_predicted_vs_actual,
)

SCOPE = {"owner_id": "owner-a", "tenant_id": "tenant-a", "workspace_id": "ws-a"}


def event(event_id, *, user="u1", feature="chat", model="model-a", calls=1,
          input_tokens=100, output_tokens=50, predicted=0.10, actual=0.10,
          depth=1, tenant="tenant-a"):
    return {
        "event_id": event_id,
        "owner_id": "owner-a",
        "tenant_id": tenant,
        "workspace_id": "ws-a",
        "user_id": user,
        "feature": feature,
        "model": model,
        "provider": "staging-provider",
        "occurred_at": "2026-10-05T12:00:00+00:00",
        "calls": calls,
        "depth": depth,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "predicted_cost_usd": predicted,
        "actual_cost_usd": actual,
    }


def request(*, user="u1", calls=1, tokens=100, cost=0.1, depth=1):
    return {
        "user_id": user,
        "feature": "chat",
        "model": "model-a",
        "provider": "staging-provider",
        "calls": calls,
        "depth": depth,
        "input_tokens": tokens,
        "output_tokens": 0,
        "predicted_cost_usd": cost,
    }


def policy(**overrides):
    row = {
        "state": "VERIFIED",
        "policy_id": "finops-default",
        "revision": 1,
        **SCOPE,
        "window_budget_usd": 10.0,
        "max_calls": 100,
        "max_tokens": 100000,
        "max_depth": 4,
        "max_user_calls": 50,
        "max_user_tokens": 50000,
        "soft_limit_pct": 80,
        "noisy_neighbor_share_pct": 70,
        "reconciliation_threshold_pct": 20,
        "block_on_cost_divergence": False,
    }
    row.update(overrides)
    return row


class AionFinOpsMeteringTests(unittest.TestCase):
    def test_scope_mismatch_is_rejected_and_not_counted(self):
        ledger = build_metering_ledger(
            [event("good"), event("foreign", tenant="tenant-b")],
            trusted_scope=SCOPE,
        )
        self.assertEqual(ledger["accepted_count"], 1)
        self.assertEqual(ledger["rejected_count"], 1)
        self.assertEqual(ledger["totals"]["calls"], 1)
        self.assertIn("SCOPE_MISMATCH", ledger["rejected_events"][0]["blockers"])
        self.assertFalse(ledger["executes_action"])

    def test_exact_replay_is_idempotent_but_event_id_conflict_is_rejected(self):
        first = event("same", predicted=0.2, actual=0.2)
        exact = dict(first)
        conflict = event("same", predicted=0.9, actual=0.9)
        ledger = build_metering_ledger([first, exact, conflict], trusted_scope=SCOPE)
        self.assertEqual(ledger["accepted_count"], 1)
        self.assertEqual(ledger["duplicate_exact_count"], 1)
        self.assertEqual(ledger["rejected_count"], 1)
        self.assertIn("EVENT_ID_CONFLICT", ledger["rejected_events"][0]["blockers"])

    def test_predicted_vs_actual_divergence_above_twenty_percent_is_flagged(self):
        ledger = build_metering_ledger(
            [event("a", predicted=1.0, actual=1.25)],
            trusted_scope=SCOPE,
        )
        result = reconcile_predicted_vs_actual(ledger, divergence_threshold_pct=20)
        self.assertEqual(result["state"], "DIVERGENT")
        self.assertEqual(result["divergence_pct"], 25.0)
        self.assertTrue(result["requires_reconciliation"])

    def test_missing_actual_cost_stays_unknown_instead_of_being_invented(self):
        row = event("a")
        row.pop("actual_cost_usd")
        ledger = build_metering_ledger([row], trusted_scope=SCOPE)
        result = reconcile_predicted_vs_actual(ledger)
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertEqual(result["actual_cost_events"], 0)

    def test_hard_cost_cap_blocks_prospective_work(self):
        ledger = build_metering_ledger(
            [event("a", predicted=0.8, actual=0.8)],
            trusted_scope=SCOPE,
        )
        decision = evaluate_finops_budget(
            ledger,
            policy=policy(window_budget_usd=1.0, soft_limit_pct=80),
            prospective_request=request(cost=0.25),
        )
        self.assertEqual(decision["state"], "BLOCK")
        self.assertIn("COST_LIMIT", decision["blockers"])
        self.assertFalse(decision["automatic_charge"])
        self.assertFalse(decision["executes_action"])

    def test_soft_budget_degrades_without_automatic_model_switch(self):
        ledger = build_metering_ledger(
            [event("a", predicted=0.70, actual=0.70)],
            trusted_scope=SCOPE,
        )
        decision = evaluate_finops_budget(
            ledger,
            policy=policy(window_budget_usd=1.0, soft_limit_pct=80),
            prospective_request=request(cost=0.12),
        )
        self.assertEqual(decision["state"], "DEGRADE")
        self.assertEqual(decision["mode"], "LOW_COST_MODE")
        self.assertIn("COST_SOFT_LIMIT", decision["degrade_reasons"])
        self.assertFalse(decision["automatic_model_switch"])

    def test_calls_tokens_and_recursive_depth_are_hard_gates(self):
        ledger = build_metering_ledger([], trusted_scope=SCOPE)
        decision = evaluate_finops_budget(
            ledger,
            policy=policy(
                max_calls=3,
                max_tokens=200,
                max_depth=2,
                window_budget_usd=10,
            ),
            prospective_request=request(calls=4, tokens=250, cost=0.1, depth=3),
        )
        self.assertEqual(decision["state"], "BLOCK")
        self.assertIn("CALL_LIMIT", decision["blockers"])
        self.assertIn("TOKEN_LIMIT", decision["blockers"])
        self.assertIn("DEPTH_LIMIT", decision["blockers"])

    def test_noisy_neighbor_is_scoped_to_offending_user(self):
        ledger = build_metering_ledger(
            [
                event("u1-a", user="u1", predicted=0.70, actual=0.70),
                event("u2-a", user="u2", predicted=0.30, actual=0.30),
            ],
            trusted_scope=SCOPE,
        )
        offender = evaluate_finops_budget(
            ledger,
            policy=policy(
                window_budget_usd=10,
                noisy_neighbor_share_pct=70,
                max_user_calls=100,
                max_user_tokens=100000,
            ),
            prospective_request=request(user="u1", cost=0.20),
        )
        other = evaluate_finops_budget(
            ledger,
            policy=policy(
                window_budget_usd=10,
                noisy_neighbor_share_pct=70,
                max_user_calls=100,
                max_user_tokens=100000,
            ),
            prospective_request=request(user="u2", cost=0.20),
        )
        self.assertEqual(offender["state"], "BLOCK")
        self.assertIn("NOISY_NEIGHBOR_SHARE", offender["blockers"])
        self.assertEqual(other["state"], "ALLOW")

    def test_user_specific_caps_do_not_require_global_exhaustion(self):
        ledger = build_metering_ledger(
            [
                event("u1-a", user="u1", calls=4, input_tokens=400, output_tokens=0),
                event("u2-a", user="u2", calls=1, input_tokens=50, output_tokens=0),
            ],
            trusted_scope=SCOPE,
        )
        offender = evaluate_finops_budget(
            ledger,
            policy=policy(
                window_budget_usd=100,
                max_calls=100,
                max_tokens=100000,
                max_user_calls=4,
                max_user_tokens=100000,
                noisy_neighbor_share_pct=100,
            ),
            prospective_request=request(user="u1", calls=1, cost=0.01),
        )
        self.assertIn("USER_CALL_LIMIT", offender["blockers"])
        self.assertNotIn("CALL_LIMIT", offender["blockers"])

    def test_dimension_totals_exist_for_user_feature_model_and_provider(self):
        ledger = build_metering_ledger(
            [event("a", user="u1", feature="research", model="model-x")],
            trusted_scope=SCOPE,
        )
        for dimension in ("user_id", "feature", "model", "provider"):
            self.assertTrue(ledger["by_dimension"][dimension])
        self.assertEqual(ledger["by_dimension"]["feature"]["research"]["calls"], 1)

    def test_token_total_mismatch_fails_closed(self):
        raw = event("bad-total")
        raw["total_tokens"] = 999
        row = normalize_meter_event(raw, trusted_scope=SCOPE)
        self.assertEqual(row["state"], "REJECTED")
        self.assertIn("TOKEN_TOTAL_MISMATCH", row["blockers"])

    def test_cost_reconciliation_can_degrade_or_block_by_policy(self):
        ledger = build_metering_ledger(
            [event("a", predicted=1.0, actual=1.4)],
            trusted_scope=SCOPE,
        )
        degraded = evaluate_finops_budget(
            ledger,
            policy=policy(
                window_budget_usd=10,
                reconciliation_threshold_pct=20,
                block_on_cost_divergence=False,
            ),
            prospective_request=request(cost=0.1),
        )
        blocked = evaluate_finops_budget(
            ledger,
            policy=policy(
                window_budget_usd=10,
                reconciliation_threshold_pct=20,
                block_on_cost_divergence=True,
            ),
            prospective_request=request(cost=0.1),
        )
        self.assertEqual(degraded["state"], "DEGRADE")
        self.assertIn("COST_RECONCILIATION_REQUIRED", degraded["degrade_reasons"])
        self.assertEqual(blocked["state"], "BLOCK")
        self.assertIn("COST_RECONCILIATION_REQUIRED", blocked["blockers"])

    def test_missing_or_invalid_required_limit_fails_closed(self):
        ledger = build_metering_ledger([], trusted_scope=SCOPE)
        missing = policy()
        missing.pop("max_depth")
        invalid = policy(max_tokens="unlimited")
        out_missing = evaluate_finops_budget(
            ledger,
            policy=missing,
            prospective_request=request(cost=0.1),
        )
        out_invalid = evaluate_finops_budget(
            ledger,
            policy=invalid,
            prospective_request=request(cost=0.1),
        )
        self.assertIn("POLICY_MAX_DEPTH_INVALID", out_missing["blockers"])
        self.assertIn("POLICY_MAX_TOKENS_INVALID", out_invalid["blockers"])
        self.assertEqual(out_missing["state"], "BLOCK")
        self.assertEqual(out_invalid["state"], "BLOCK")

    def test_policy_scope_and_verified_state_are_mandatory(self):
        ledger = build_metering_ledger([], trusted_scope=SCOPE)
        unverified = policy(state="DRAFT")
        crossed = policy(tenant_id="tenant-b")
        out_unverified = evaluate_finops_budget(
            ledger,
            policy=unverified,
            prospective_request=request(cost=0.1),
        )
        out_crossed = evaluate_finops_budget(
            ledger,
            policy=crossed,
            prospective_request=request(cost=0.1),
        )
        self.assertIn("POLICY_NOT_VERIFIED", out_unverified["blockers"])
        self.assertIn("POLICY_SCOPE_MISMATCH", out_crossed["blockers"])

    def test_request_never_grants_authority_or_executes(self):
        ledger = build_metering_ledger([], trusted_scope=SCOPE)
        decision = evaluate_finops_budget(
            ledger,
            policy=policy(window_budget_usd=10),
            prospective_request=request(cost=0.1),
        )
        self.assertFalse(decision["grants_authority"])
        self.assertFalse(decision["automatic_provider_call"])
        self.assertFalse(decision["automatic_model_switch"])
        self.assertFalse(decision["executes_action"])


if __name__ == "__main__":
    unittest.main()
