"""Synthetic tests: policy correctness is NOT trading accuracy."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_selective_bias_gate_lab import BiasReview, audit_selective_bias_lab

NOW = datetime(2026, 11, 7, 13, 30, tzinfo=timezone.utc)


def candidate(**kwargs):
    basic = BiasReview(
        pair="EUR/USD", horizon="D1", direction="ALTA", score_0_to_10=8,
        scored_at_utc=NOW - timedelta(minutes=10),
        macro_bilateral_evidence_verified=True,
        source_vintages_verified=True, market_regime="TENDENCIA",
        market_regime_verified=True,
        microeconomics_status="DOCUMENTADO_NEUTRO",
        geopolitics_status="DOCUMENTADO_NEUTRO",
        model_oos_calibration_verified=True,
        model_beats_baseline_oos=True,
        forward_paper_validation_verified=True,
        independence_risk_reviewed=True,
        price_reaction_labels_verified=True,
        frozen_model_version="synthetic-v1",
    )
    return replace(basic, **kwargs)


def audit(c=None):
    return audit_selective_bias_lab(candidate() if c is None else c, as_of_utc=NOW)


class SelectiveBiasPolicyTests(unittest.TestCase):
    def assert_never_authorizes(self, r):
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["can_feed_live_radar"])
        self.assertFalse(r["automatic_alert_enabled"])
        self.assertFalse(r["automatic_hold_or_exit"])
        self.assertIsNone(r["broker_command"])
        self.assertIsNone(r["directional_accuracy_pct"])
        self.assertIsNone(r["probability_of_profit_pct"])
        self.assertFalse(r["flags_are_independent_attestation"])
        self.assertFalse(r["real_historical_accuracy_verified"])
        self.assertFalse(r["is_probability"])

    def test_zero_through_five_never_qualifies(self):
        for n in range(6):
            r = audit(candidate(score_0_to_10=n))
            self.assertEqual(r["state"], "AGUARDAR")
            self.assertIn("ABAIXO_DO_LIMIAR_SELETIVO", r["blockers"])
            self.assertIsNone(r["score_label"])
            self.assert_never_authorizes(r)

    def test_six_to_ten_have_explicit_labels_but_no_live_signal(self):
        for score, expected in ((6,"MODERADO"),(7,"FORTE"),(8,"ALTO"),(9,"EXTRA"),(10,"EXTRA")):
            r = audit(candidate(score_0_to_10=score))
            self.assertEqual(r["score_label"], expected)
            self.assertTrue(r["hypothetical_policy_ready_for_human_review"])
            self.assert_never_authorizes(r)

    def test_missing_score_blocks(self):
        self.assertEqual(audit(candidate(score_0_to_10=None))["state"], "AGUARDAR")

    def test_score_not_permitted_if_boolean_float_or_outside_scale(self):
        for invalid in (True, 6.0, 5.5, -1, 11, float("nan"), "8"):
            with self.assertRaises(ValueError):
                audit(candidate(score_0_to_10=invalid))

    def test_score_nine_does_not_override_missing_macro(self):
        r = audit(candidate(score_0_to_10=9, macro_bilateral_evidence_verified=False))
        self.assertEqual(r["state"], "AGUARDAR")
        self.assertIn("MACRO_DAS_DUAS_MOEDAS_SEM_PROVA",r["blockers"])
        self.assert_never_authorizes(r)

    def test_geopolitical_unknown_blocks_and_documented_neutral_does_not(self):
        r = audit(candidate(geopolitics_status="INDETERMINADO"))
        self.assertIn("GEOPOLITICA_SEM_CONTEXTO", r["blockers"])
        self.assertEqual(r["state"], "AGUARDAR")
        self.assert_never_authorizes(r)

    def test_microeconomic_unknown_blocks(self):
        r = audit(candidate(microeconomics_status="INDETERMINADO"))
        self.assertIn("MICROECONOMIA_SEM_CONTEXTO",r["blockers"])
        self.assert_never_authorizes(r)

    def test_high_score_is_not_probabilistic_or_validated_when_calibration_missing(self):
        r=audit(candidate(model_oos_calibration_verified=False,model_beats_baseline_oos=False,score_0_to_10=10))
        self.assertEqual(r["state"],"AGUARDAR")
        self.assertIn("PROBABILIDADES_NAO_CALIBRADAS_OOS",r["blockers"])
        self.assert_never_authorizes(r)

    def test_missing_forward_or_risk_review_blocks(self):
        r = audit(candidate(forward_paper_validation_verified=False,independence_risk_reviewed=False))
        self.assertIn("VALIDACAO_PROSPECTIVA_PENDENTE",r["blockers"])
        self.assertIn("RISCO_INDEPENDENTE_PENDENTE",r["blockers"])

    def test_neutral_or_waiting_direction_never_displays(self):
        for direction in ("NEUTRO","AGUARDAR"):
            r=audit(candidate(direction=direction))
            self.assertIn("SEM_DIRECAO_CANDIDATA",r["blockers"])

    def test_daily_repeat_suppressed_even_with_score_ten(self):
        r=audit(candidate(score_0_to_10=10,last_displayed_at_utc=NOW - timedelta(hours=8)))
        self.assertIn("JANELA_REPETICAO_DO_MESMO_VIES",r["blockers"])
        self.assert_never_authorizes(r)

    def test_weekly_repeat_suppressed(self):
        r=audit(candidate(horizon="W1",last_displayed_at_utc=NOW - timedelta(days=3)))
        self.assertIn("JANELA_REPETICAO_DO_MESMO_VIES",r["blockers"])
        self.assert_never_authorizes(r)

    def test_old_repeat_outside_window_is_not_suppressed(self):
        r=audit(candidate(horizon="W1",last_displayed_at_utc=NOW - timedelta(days=8)))
        self.assertTrue(r["hypothetical_policy_ready_for_human_review"])
        self.assert_never_authorizes(r)

    def test_future_score_is_blocked(self):
        r=audit(candidate(scored_at_utc=NOW+timedelta(seconds=1)))
        self.assertIn("PREVISAO_FUTURA",r["blockers"])
        self.assert_never_authorizes(r)

    def test_temporal_leakage_even_with_full_flags_blocks(self):
        r=audit(candidate(has_future_leakage=True))
        self.assertIn("VAZAMENTO_TEMPORAL",r["blockers"])
        self.assert_never_authorizes(r)

    def test_all_28_pairs_research_only(self):
        self.assertEqual(len(OFFICIAL_PAIRS),28)
        for pair in OFFICIAL_PAIRS:
            r=audit(candidate(pair=pair))
            self.assert_never_authorizes(r)

    def test_unknown_pair_and_horizon_invalid(self):
        for changes in ({"pair":"USD/CHF???"},{"horizon":"M15"},{"direction":"COMPRA"},{"market_regime":"WTF"}):
            with self.assertRaises(ValueError):
                audit(candidate(**changes))

    def test_naive_timestamps_rejected(self):
        with self.assertRaises(ValueError):
            audit(candidate(scored_at_utc=NOW.replace(tzinfo=None)))
        with self.assertRaises(ValueError):
            audit_selective_bias_lab(candidate(),as_of_utc=NOW.replace(tzinfo=None))

    def test_no_frozen_model_version_blocks(self):
        r=audit(candidate(frozen_model_version=""))
        self.assertIn("VERSAO_MODELO_NAO_CONGELADA",r["blockers"])
        self.assert_never_authorizes(r)

    def test_provenance_unverified_blocks(self):
        r=audit(candidate(source_vintages_verified=False))
        self.assertIn("FONTES_E_VINTAGES_NAO_ATESTADOS",r["blockers"])
        self.assert_never_authorizes(r)


if __name__=="__main__":
    unittest.main(verbosity=2)
