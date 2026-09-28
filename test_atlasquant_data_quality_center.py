import unittest
from datetime import datetime, timedelta, timezone

from atlasquant_data_quality_center import build_data_confidence, data_confidence_visual_state


NOW = datetime(2026, 9, 28, 23, 45, tzinfo=timezone.utc)


class AtlasQuantDataConfidenceTests(unittest.TestCase):
    def pack(
        self,
        ready=True,
        score=90,
        quality=85,
        age=20,
        stale=False,
        event="NORMAL",
        *,
        freshness=True,
        freshness_minutes=20,
        freshness_ttl=60,
        source="technical-cache",
    ):
        out = {
            "quality": quality,
            "technical_age": age,
            "stale_technical": stale,
            "event": event,
            "data_ready": {"sufficient": ready, "score": score},
        }
        if freshness:
            out["freshness"] = {
                "source": source,
                "observed_at": (NOW - timedelta(minutes=freshness_minutes)).isoformat(),
                "ttl_minutes": freshness_ttl,
            }
        return out

    def build(self, packs, autopilot=None):
        return build_data_confidence(packs, autopilot or {}, evaluated_at=NOW)

    def test_green_requires_strong_readiness_healthy_process_and_current_freshness(self):
        packs = [self.pack() for _ in range(5)]
        s = self.build(packs, {"app_headless_ok": True, "twelve_daily_blocked": False})
        self.assertEqual(s["status"], "GREEN")
        self.assertEqual(s["ready_pairs"], 5)
        self.assertEqual(s["freshness_state"], "CURRENT")
        self.assertEqual(s["freshness_current_pairs"], 5)
        self.assertFalse(s["freshness_execution_authorized"])

    def test_missing_temporal_evidence_blocks_green_with_legible_reason(self):
        packs = [self.pack(freshness=False) for _ in range(5)]
        s = self.build(packs, {"app_headless_ok": True, "twelve_daily_blocked": False})
        self.assertEqual(s["status"], "YELLOW")
        self.assertEqual(s["freshness_state"], "UNKNOWN")
        self.assertEqual(s["freshness_unknown_pairs"], 5)
        self.assertIn("SOURCE_UNKNOWN", s["freshness_reasons"])
        self.assertIn("OBSERVED_AT_UNKNOWN", s["freshness_reasons"])
        self.assertIn("TTL_UNKNOWN", s["freshness_reasons"])

    def test_zero_ready_is_red(self):
        packs = [self.pack(ready=False, score=40) for _ in range(3)]
        s = self.build(packs, {"app_headless_ok": True})
        self.assertEqual(s["status"], "RED")

    def test_source_block_prevents_green(self):
        packs = [self.pack() for _ in range(5)]
        s = self.build(packs, {"app_headless_ok": True, "twelve_daily_blocked": True})
        self.assertEqual(s["status"], "YELLOW")
        self.assertTrue(s["source_blocked"])

    def test_stale_pair_prevents_green(self):
        packs = [self.pack() for _ in range(4)] + [self.pack(stale=True, freshness_minutes=90)]
        s = self.build(packs, {"app_headless_ok": True})
        self.assertEqual(s["status"], "YELLOW")
        self.assertEqual(s["stale_pairs"], 1)
        self.assertEqual(s["freshness_stale_pairs"], 1)
        self.assertEqual(s["freshness_conflict_pairs"], 0)

    def test_freshness_stale_conflicts_with_legacy_not_stale_flag(self):
        packs = [self.pack() for _ in range(4)] + [self.pack(stale=False, freshness_minutes=60)]
        s = self.build(packs, {"app_headless_ok": True})
        self.assertEqual(s["status"], "YELLOW")
        self.assertEqual(s["freshness_state"], "STALE")
        self.assertEqual(s["freshness_conflict_pairs"], 1)

    def test_legacy_stale_conflicts_with_current_explicit_freshness(self):
        packs = [self.pack() for _ in range(4)] + [self.pack(stale=True, freshness_minutes=10)]
        s = self.build(packs, {"app_headless_ok": True})
        self.assertEqual(s["status"], "YELLOW")
        self.assertEqual(s["freshness_state"], "CURRENT")
        self.assertEqual(s["freshness_conflict_pairs"], 1)

    def test_missing_ages_are_counted_without_replacing_explicit_freshness(self):
        packs = [self.pack(age=None), self.pack(age=30)]
        s = self.build(packs, {"app_headless_ok": True})
        self.assertEqual(s["missing_age_pairs"], 1)
        self.assertEqual(s["oldest_age_min"], 30.0)
        self.assertEqual(s["freshness_state"], "CURRENT")

    def test_nowcast_auth_issue_is_visible_without_changing_core_data_status(self):
        packs = [self.pack() for _ in range(5)]
        auto = {
            "app_headless_ok": True,
            "twelve_daily_blocked": False,
            "news_nowcast_v1": {
                "runtime_state": "AUTH_COOLDOWN",
                "provider_retry_reason": "AUTH_ERROR",
                "provider_retry_after_min": 210,
                "provider_status": {"reason": "AUTH_ERROR", "http_status": 401},
            },
        }
        s = self.build(packs, auto)
        self.assertEqual(s["status"], "GREEN")
        self.assertTrue(s["news_auth_issue"])
        self.assertEqual(s["news_provider_reason"], "AUTH_ERROR")
        self.assertEqual(s["news_retry_after_min"], 210)

    def test_nowcast_rate_limit_is_diagnostic_only(self):
        packs = [self.pack() for _ in range(5)]
        auto = {
            "app_headless_ok": True,
            "twelve_daily_blocked": False,
            "news_nowcast_v1": {
                "runtime_state": "RATE_LIMIT_COOLDOWN",
                "provider_retry_reason": "RATE_LIMITED",
                "provider_retry_after_min": 40,
            },
        }
        s = self.build(packs, auto)
        self.assertEqual(s["status"], "GREEN")
        self.assertFalse(s["news_auth_issue"])
        self.assertEqual(s["news_provider_reason"], "RATE_LIMITED")

    def test_event_risk_is_visible_but_not_signal(self):
        packs = [self.pack(event="ALTO FOMC"), self.pack(event="NORMAL")]
        s = self.build(packs, {"app_headless_ok": True})
        self.assertEqual(s["event_risk_pairs"], 1)
        self.assertFalse(s["freshness_execution_authorized"])

    def test_presentation_contract_keeps_existing_keys_and_adds_temporal_state(self):
        s = self.build([self.pack()], {"app_headless_ok": True})
        for key in (
            "status",
            "label",
            "total_pairs",
            "ready_pairs",
            "average_data_score",
            "average_model_quality",
            "stale_pairs",
            "process_ok",
            "source_blocked",
        ):
            self.assertIn(key, s)
        self.assertIn("freshness_state", s)
        self.assertIn("freshness_reports", s)

    def test_data_confidence_visual_state_never_implies_trade_permission(self):
        self.assertEqual(data_confidence_visual_state({"status": "GREEN"})["label"], "DADOS OPERACIONAIS")
        self.assertEqual(data_confidence_visual_state({"status": "YELLOW"})["label"], "ATENÇÃO NOS DADOS")
        self.assertEqual(data_confidence_visual_state({"status": "RED"})["label"], "DADOS INSUFICIENTES")
        self.assertEqual(data_confidence_visual_state({"status": "UNKNOWN"})["label"], "REVISAR")
        self.assertIn(
            "não é autorização de trade",
            data_confidence_visual_state({"status": "GREEN"})["detail"],
        )


if __name__ == "__main__":
    unittest.main()
