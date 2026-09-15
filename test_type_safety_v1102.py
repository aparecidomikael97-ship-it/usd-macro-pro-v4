import unittest
from decision_integrity_v110 import (
    _is_missing, _bool_or_none, _event_level, evaluate_decision_integrity
)

class FakeNA:
    def __str__(self):
        return "<NA>"
    def __bool__(self):
        raise TypeError("boolean value of NA is ambiguous")
    def __eq__(self, other):
        return self
    def __ne__(self, other):
        return self

class TypeSafetyV1102Tests(unittest.TestCase):
    def test_fake_na_is_missing(self):
        self.assertTrue(_is_missing(FakeNA()))

    def test_event_na_defaults_normal(self):
        self.assertEqual(_event_level(FakeNA()), "NORMAL")

    def test_bool_na_is_none(self):
        self.assertIsNone(_bool_or_none(FakeNA()))

    def test_evaluator_does_not_crash_with_na_like_scalars(self):
        out = evaluate_decision_integrity(
            side="BUY", score=90, quality=84, rank_index=78,
            h4="🟢 CONFIRMA", h1="🟢 PULLBACK OK", m15="🟢 GATILHO",
            ict_readiness=70, institutional_readiness=70,
            gate="B", gate_score=75,
            adr_used_pct=FakeNA(), event_risk=FakeNA(),
            technical_age_min=FakeNA(), news_alignment="CONFIRMA",
            data_sufficient=FakeNA(), data_readiness_score=FakeNA(),
        )
        self.assertIn("state", out)
        self.assertIn("priority_score", out)
        self.assertIsNone(out["data_sufficient"])

if __name__ == "__main__":
    unittest.main()
