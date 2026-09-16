import unittest

from atlasquant_next_event import normalize_next_event


class AtlasQuantNextEventTests(unittest.TestCase):
    NOW="2026-09-16T12:00:00Z"

    def test_missing_event(self):
        r=normalize_next_event({},now_utc=self.NOW)
        self.assertFalse(r["available"])
        self.assertIsNone(r["safety_minutes"])

    def test_date_only_never_invents_countdown(self):
        r=normalize_next_event({
            "disponivel":True,
            "evento":"FOMC",
            "data":"2026-09-16 00:00:00",
            "impacto":"MÁXIMO",
            "fonte":"Federal Reserve",
        },now_utc=self.NOW)
        self.assertTrue(r["available"])
        self.assertFalse(r["exact_time"])
        self.assertIsNone(r["countdown"])
        self.assertIsNone(r["safety_minutes"])
        self.assertEqual(r["state"],"DATE_ONLY_TODAY")

    def test_exact_timestamp_produces_minutes(self):
        r=normalize_next_event({
            "disponivel":True,
            "evento":"CPI",
            "scheduled_at":"2026-09-16T12:10:00Z",
            "impacto":"ALTO",
        },now_utc=self.NOW)
        self.assertTrue(r["exact_time"])
        self.assertEqual(r["minutes_to_event"],10.0)
        self.assertEqual(r["safety_minutes"],10.0)
        self.assertEqual(r["state"],"CRITICAL")

    def test_exact_low_impact_not_sent_to_safety(self):
        r=normalize_next_event({
            "disponivel":True,
            "evento":"Dado menor",
            "scheduled_at":"2026-09-16T12:10:00Z",
            "impacto":"MÉDIO",
        },now_utc=self.NOW)
        self.assertIsNone(r["safety_minutes"])

    def test_exact_four_hours_is_near(self):
        r=normalize_next_event({
            "disponivel":True,
            "evento":"Payroll",
            "scheduled_at":"2026-09-16T15:00:00Z",
            "impacto":"ALTO",
        },now_utc=self.NOW)
        self.assertEqual(r["state"],"NEAR")
        self.assertEqual(r["countdown"],"3.0 h")

    def test_past_exact_event_requires_refresh(self):
        r=normalize_next_event({
            "disponivel":True,
            "evento":"CPI",
            "scheduled_at":"2026-09-16T11:00:00Z",
            "impacto":"ALTO",
        },now_utc=self.NOW)
        self.assertEqual(r["state"],"PASSED")
        self.assertIsNone(r["safety_minutes"])

    def test_date_only_tomorrow(self):
        r=normalize_next_event({
            "disponivel":True,
            "evento":"PCE",
            "data_txt":"17/09/2026",
            "impacto":"ALTO",
        },now_utc=self.NOW)
        self.assertEqual(r["state"],"DATE_ONLY_TOMORROW")
        self.assertIsNone(r["countdown"])

    def test_source_and_type_preserved(self):
        r=normalize_next_event({
            "disponivel":True,
            "evento":"FOMC",
            "data_txt":"18/09/2026",
            "impacto":"MÁXIMO",
            "fonte":"Federal Reserve",
            "tipo":"Banco Central",
        },now_utc=self.NOW)
        self.assertEqual(r["source"],"Federal Reserve")
        self.assertEqual(r["type"],"Banco Central")


if __name__=="__main__":
    unittest.main()
