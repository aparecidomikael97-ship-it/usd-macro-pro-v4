import json
import unittest

from atlasquant_aion_system_health_center import (
    BLOCKED,
    DEGRADED,
    DOMAINS,
    HEALTHY,
    UNKNOWN,
    build_system_health_center,
    normalize_health_domain,
    system_health_rows,
)


class AionSystemHealthCenterTests(unittest.TestCase):
    def healthy(self, **overrides):
        value = {
            "state": "HEALTHY",
            "confirmed": True,
            "detail": "Evidência atual confirmada.",
            "observed_at": "2026-09-28T23:55:00+00:00",
            "total": 3,
            "unresolved": 0,
            "affected": 0,
            "freshness_attested": True,
            "freshness_source": "test.fixture",
        }
        value.update(overrides)
        return value

    def full(self, **overrides):
        data = {domain: self.healthy() for domain in DOMAINS}
        data.update(overrides)
        return data

    def test_empty_center_is_unknown_and_never_authorizes_action(self):
        out = build_system_health_center({})
        self.assertEqual(out["state"], UNKNOWN)
        self.assertEqual(out["counts"][UNKNOWN], len(DOMAINS))
        self.assertFalse(out["all_confirmed_healthy"])
        self.assertFalse(out["automatic_repair"])
        self.assertFalse(out["automatic_restart"])
        self.assertFalse(out["automatic_notification"])
        self.assertFalse(out["execution_authorized"])
        self.assertFalse(out["real_trading_enabled"])

    def test_all_six_domains_must_be_confirmed_for_healthy(self):
        out = build_system_health_center(self.full())
        self.assertEqual(out["state"], HEALTHY)
        self.assertEqual(out["healthy_domains"], 6)
        self.assertTrue(out["all_confirmed_healthy"])
        self.assertEqual(out["unresolved_domains"], [])


    def test_confirmed_healthy_without_freshness_proof_stays_unknown(self):
        item = normalize_health_domain(
            "runtime",
            {"state": "HEALTHY", "confirmed": True, "detail": "Runtime ok"},
        )
        self.assertEqual(item["state"], UNKNOWN)
        self.assertFalse(item["confirmed"])
        self.assertIn("FRESHNESS_NOT_CONFIRMED", item["reasons"])

    def test_secret_like_value_inside_detail_is_redacted(self):
        item = normalize_health_domain(
            "notifications",
            self.healthy(detail="token=abc123 bearer ZXhhbXBsZQ== sk-abcdefghijk"),
        )
        blob = json.dumps(item)
        self.assertNotIn("abc123", blob)
        self.assertNotIn("ZXhhbXBsZQ==", blob)
        self.assertNotIn("sk-abcdefghijk", blob)
        self.assertIn("[REDACTED]", blob)

    def test_consistency_warning_surfaces_worker_queue_mismatch(self):
        out = build_system_health_center(
            self.full(
                workers=self.healthy(),
                queues={"state": "DEGRADED", "confirmed": False, "unresolved": 3},
            )
        )
        self.assertIn("WORKER_HEALTHY_WITH_QUEUE_ISSUES", out["consistency_warnings"])

    def test_healthy_label_without_confirmation_stays_unknown(self):
        item = normalize_health_domain(
            "runtime",
            {"state": "OK", "confirmed": False, "detail": "looks fine"},
        )
        self.assertEqual(item["state"], UNKNOWN)
        self.assertFalse(item["confirmed"])
        self.assertIn("HEALTH_NOT_CONFIRMED", item["reasons"])

    def test_negative_states_do_not_need_confirmation_to_remain_visible(self):
        degraded = normalize_health_domain(
            "sources",
            {"state": "DEGRADED", "confirmed": False},
        )
        blocked = normalize_health_domain(
            "workers",
            {"state": "FAILED", "confirmed": False},
        )
        self.assertEqual(degraded["state"], DEGRADED)
        self.assertEqual(blocked["state"], BLOCKED)

    def test_blocked_dominates_center(self):
        out = build_system_health_center(
            self.full(workers={"state": "BLOCKED", "confirmed": False})
        )
        self.assertEqual(out["state"], BLOCKED)
        self.assertIn("workers", out["unresolved_domains"])

    def test_unknown_precedes_degraded_when_coverage_is_incomplete(self):
        data = self.full(
            queues={"state": "DEGRADED", "confirmed": False},
            notifications=None,
        )
        out = build_system_health_center(data)
        self.assertEqual(out["state"], UNKNOWN)
        self.assertEqual(out["counts"][DEGRADED], 1)
        self.assertEqual(out["counts"][UNKNOWN], 1)

    def test_degraded_is_used_when_all_domains_are_known(self):
        out = build_system_health_center(
            self.full(queues={"state": "WARNING", "confirmed": False})
        )
        self.assertEqual(out["state"], DEGRADED)
        self.assertEqual(out["counts"][DEGRADED], 1)

    def test_unresolved_items_downgrade_a_claimed_healthy_domain(self):
        item = normalize_health_domain(
            "screens",
            self.healthy(unresolved=2),
        )
        self.assertEqual(item["state"], DEGRADED)
        self.assertIn("UNRESOLVED_ITEMS_PRESENT", item["reasons"])
        self.assertFalse(item["confirmed"])

    def test_secret_like_fields_are_rejected_and_never_echoed(self):
        item = normalize_health_domain(
            "notifications",
            {
                "state": "HEALTHY",
                "confirmed": True,
                "api_key": "super-secret-value",
                "detail": "provider ready",
            },
        )
        self.assertEqual(item["state"], BLOCKED)
        self.assertIn("SECRET_FIELD_REJECTED", item["reasons"])
        blob = json.dumps(item)
        self.assertNotIn("super-secret-value", blob)

    def test_invalid_counts_are_not_trusted(self):
        item = normalize_health_domain(
            "queues",
            self.healthy(total=True, unresolved=-1, affected="nan"),
        )
        self.assertIsNone(item["total"])
        self.assertIsNone(item["unresolved"])
        self.assertIsNone(item["affected"])

    def test_rows_are_compact_and_do_not_include_raw_payload(self):
        center = build_system_health_center(
            self.full(runtime=self.healthy(detail="Runtime confirmado."))
        )
        rows = system_health_rows(center)
        self.assertEqual(len(rows), 6)
        self.assertEqual(
            set(rows[0]),
            {"Área", "Estado", "Confirmado", "Pendências", "Detalhe"},
        )
        self.assertNotIn("execution_authorized", rows[0])

    def test_unknown_domain_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_health_domain("billing", self.healthy())


if __name__ == "__main__":
    unittest.main()
