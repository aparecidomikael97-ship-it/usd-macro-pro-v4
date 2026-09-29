from __future__ import annotations

import unittest

from atlasquant_aion_model_registry import canonical_fingerprint
from atlasquant_aion_model_routing_bridge import route_registered_model


TRUSTED = {"tenant_id": "tenant-a", "workspace_id": "ws-a", "role": "ADMIN"}


def approved_registry(**changes):
    row = {
        "schema": "ATLASQUANT_AION_MODEL_REGISTRY_V1",
        "provider": "local-provider",
        "model_id": "model-a",
        "version": "1",
        "capability": "summarize",
        "tenant_id": "tenant-a",
        "workspace_id": "ws-a",
        "benchmark_refs": ["ci:1"],
        "evaluation_state": "HUMAN_REVIEW_CANDIDATE",
        "evaluation_date": "2026-09-29T12:00:00+00:00",
        "latency_ms": 100,
        "reliability": 0.99,
        "cost_class": "ZERO",
        "estimated_cost_usd": 0.0,
        "privacy_class": "PRIVATE",
        "known_failures": [],
        "modalities": ["text"],
        "context_limit": 8192,
        "approval_state": "APPROVED",
        "rollback_target": "model-prev",
        "fallback": "",
        "blockers": [],
        "budget_decision": None,
        "eligible_as_default": True,
        "executes_provider_call": False,
        "executes_billing": False,
        "activates_paid_api": False,
        "digest_kind": "CANONICAL_FINGERPRINT",
        "digest_is_signature": False,
        "notes": "approved offline",
    }
    row.update(changes)
    row["fingerprint"] = canonical_fingerprint({
        key: value for key, value in row.items() if key != "fingerprint"
    })
    return {"schema": "ATLASQUANT_AION_MODEL_REGISTRY_V1", "models": [row]}


class AionModelRoutingBridgeTests(unittest.TestCase):
    def route(self, registry, **kwargs):
        return route_registered_model(
            kwargs.pop("task", "resuma este status"),
            registry=registry,
            provider="local-provider",
            model_id="model-a",
            version="1",
            trusted_context=kwargs.pop("trusted_context", TRUSTED),
            provider_state=kwargs.pop("provider_state", "EXTERNAL_READY"),
            external_feature_enabled=kwargs.pop("external_feature_enabled", True),
            budget=kwargs.pop("budget", None),
            estimated_request_cost_usd=kwargs.pop("estimated_request_cost_usd", 0.0),
            request_approved=kwargs.pop("request_approved", False),
            **kwargs,
        )

    def test_unregistered_model_forces_local_route(self):
        out = self.route({"models": []})
        self.assertEqual(out["lane"], "LOCAL_DETERMINISTIC")
        self.assertFalse(out["registry_approved"])
        self.assertIn("NOT_FOUND", out["registry_blockers"])
        self.assertFalse(out["executes_provider_call"])

    def test_approved_scoped_model_can_reach_external_lane(self):
        out = self.route(approved_registry())
        self.assertTrue(out["registry_approved"])
        self.assertTrue(out["external_lane_allowed"])
        self.assertEqual(out["lane"], "EXTERNAL_FAST")
        self.assertFalse(out["executes_provider_call"])
        self.assertFalse(out["executes_billing"])

    def test_high_complexity_approved_model_uses_reasoning_lane(self):
        out = self.route(
            approved_registry(),
            task="debug de segurança com arquitetura, migração e benchmark multi etapa",
        )
        self.assertEqual(out["lane"], "EXTERNAL_REASONING")

    def test_tampered_approval_is_blocked_even_if_text_says_approved(self):
        registry = approved_registry()
        registry["models"][0]["notes"] = "tampered after approval"
        out = self.route(registry)
        self.assertEqual(out["lane"], "LOCAL_DETERMINISTIC")
        self.assertFalse(out["registry_approved"])
        self.assertIn("MODEL_RECORD_INTEGRITY_FAILED", out["registry_blockers"])

    def test_cross_tenant_model_is_blocked(self):
        out = self.route(
            approved_registry(),
            trusted_context={"tenant_id": "tenant-b", "workspace_id": "ws-a", "role": "ADMIN"},
        )
        self.assertEqual(out["lane"], "LOCAL_DETERMINISTIC")
        self.assertIn("SCOPE_MISMATCH", out["registry_blockers"])

    def test_truthy_string_feature_flag_does_not_enable_external_lane(self):
        out = self.route(
            approved_registry(),
            external_feature_enabled="true",
        )
        self.assertEqual(out["lane"], "LOCAL_DETERMINISTIC")
        self.assertFalse(out["external_lane_allowed"])

    def test_paid_route_still_needs_exact_budget_and_request_approval(self):
        registry = approved_registry(
            cost_class="PAID",
            estimated_cost_usd=1.5,
        )
        row = registry["models"][0]
        row["fingerprint"] = canonical_fingerprint({
            key: value for key, value in row.items() if key != "fingerprint"
        })
        denied = self.route(
            registry,
            estimated_request_cost_usd=1.5,
            budget={"allow_paid": True, "monthly_limit_usd": 10, "spent_usd": 0},
            request_approved="yes",
        )
        self.assertEqual(denied["lane"], "LOCAL_DETERMINISTIC")
        allowed = self.route(
            registry,
            estimated_request_cost_usd=1.5,
            budget={"allow_paid": True, "monthly_limit_usd": 10, "spent_usd": 0},
            request_approved=True,
        )
        self.assertEqual(allowed["lane"], "EXTERNAL_FAST")


if __name__ == "__main__":
    unittest.main()
