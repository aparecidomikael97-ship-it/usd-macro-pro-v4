import unittest

from atlasquant_adaptive_execution_gate import (
    adaptive_pair_permission,
    active_set_integrity,
)


GOOD_HEALTH={
    "h1_ready":True,
    "h4_ready":True,
    "strict_complete_groups":True,
}


class AtlasQuantAdaptiveExecutionGateTests(unittest.TestCase):
    def test_background_pair_is_never_executable(self):
        r=adaptive_pair_permission(
            "EUR/GBP",
            active_pairs=["EUR/USD","GBP/USD","USD/JPY"],
            m15_age_minutes=10,
            derived_health=GOOD_HEALTH,
            data_sufficient=True,
        )
        self.assertFalse(r["executable"])
        self.assertEqual(r["tier"],"BACKGROUND")

    def test_active_pair_can_be_eligible_only_with_all_gates(self):
        r=adaptive_pair_permission(
            "EUR/USD",
            active_pairs=["EUR/USD"],
            m15_age_minutes=20,
            derived_health=GOOD_HEALTH,
            data_sufficient=True,
        )
        self.assertTrue(r["executable"])
        self.assertEqual(r["state"],"SEARCH_ENTRY_ELIGIBLE")

    def test_stale_active_m15_blocks(self):
        r=adaptive_pair_permission(
            "EUR/USD",
            active_pairs=["EUR/USD"],
            m15_age_minutes=61,
            derived_health=GOOD_HEALTH,
            data_sufficient=True,
        )
        self.assertFalse(r["executable"])
        self.assertTrue(any("M15 acima" in x for x in r["blockers"]))

    def test_missing_derived_h1_blocks(self):
        health=dict(GOOD_HEALTH); health["h1_ready"]=False
        r=adaptive_pair_permission(
            "EUR/USD",
            active_pairs=["EUR/USD"],
            m15_age_minutes=20,
            derived_health=health,
            data_sufficient=True,
        )
        self.assertFalse(r["executable"])

    def test_existing_hard_block_is_preserved(self):
        r=adaptive_pair_permission(
            "EUR/USD",
            active_pairs=["EUR/USD"],
            m15_age_minutes=20,
            derived_health=GOOD_HEALTH,
            data_sufficient=True,
            hard_blocks=["Evento crítico"],
        )
        self.assertFalse(r["executable"])
        self.assertIn("Evento crítico",r["blockers"])

    def test_future_timestamp_fails_closed(self):
        r=adaptive_pair_permission(
            "EUR/USD",
            active_pairs=["EUR/USD"],
            m15_age_minutes=-5,
            derived_health=GOOD_HEALTH,
            data_sufficient=True,
        )
        self.assertFalse(r["executable"])

    def test_integrity_detects_background_execution_violation(self):
        rows=[
            {"pair":"EUR/USD","tier":"ACTIVE","executable":True},
            {"pair":"EUR/GBP","tier":"BACKGROUND","executable":True},
        ]
        r=active_set_integrity(rows,expected_active_pairs=["EUR/USD"])
        self.assertTrue(r["background_execution_violation"])
        self.assertFalse(r["integrity_ok"])

    def test_integrity_accepts_clean_active_set(self):
        rows=[
            {"pair":"EUR/USD","tier":"ACTIVE","executable":True},
            {"pair":"EUR/GBP","tier":"BACKGROUND","executable":False},
        ]
        r=active_set_integrity(rows,expected_active_pairs=["EUR/USD"])
        self.assertTrue(r["integrity_ok"])
        self.assertFalse(r["automatic_live_wiring_allowed"])


    def test_exact_freshness_boundary_and_invalid_limit_fail_closed(self):
        r=adaptive_pair_permission(
            "EUR/USD",active_pairs=["EUR/USD"],m15_age_minutes=60,
            derived_health=GOOD_HEALTH,data_sufficient=True,max_active_m15_age_min=60,
        )
        self.assertFalse(r["executable"])
        for bad in (0,-1,float("nan"),float("inf"),float("-inf")):
            with self.subTest(limit=bad):
                r=adaptive_pair_permission(
                    "EUR/USD",active_pairs=["EUR/USD"],m15_age_minutes=20,
                    derived_health=GOOD_HEALTH,data_sufficient=True,max_active_m15_age_min=bad,
                )
                self.assertFalse(r["executable"])


if __name__=="__main__":
    unittest.main()
