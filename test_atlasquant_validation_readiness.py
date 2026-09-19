import unittest
import pandas as pd

from atlasquant_validation_readiness import build_validation_readiness, validation_visual_state, render_validation_readiness, balanced_pair_coverage
from atlasquant_shadow_mode import compare_shadow_sample


class AtlasQuantValidationReadinessTests(unittest.TestCase):
    def history(self, n_per_band=40, months=4):
        rows=[]
        bands=[(75,24),(85,28),(95,32)]
        for b,(score,hits) in enumerate(bands):
            for i in range(n_per_band):
                rows.append({
                    "par":"EUR/USD" if i%2==0 else "GBP/USD",
                    "direcao":"BUY",
                    "score_mestre":score,
                    "qualidade":85,
                    "registrado_em":f"2026-{1+(i%months):02d}-{1+(i%20):02d}T12:00:00Z",
                    "retorno_24h_pct":1.0 if i < min(hits,n_per_band) else -1.0,
                })
        return pd.DataFrame(rows)

    def shadow_samples(self,n=100,critical=False):
        out=[]
        for i in range(n):
            champion={
                "pair":"EUR/USD","side":"BUY","state":"WAIT","score":80,
                "data_quality":90,"executable":False,"version":"champ",
                "timestamp":f"2026-01-{1+(i%20):02d}T12:{i%60:02d}:00Z",
            }
            challenger=dict(champion)
            challenger["version"]="challenger"
            if critical and i==0:
                challenger["side"]="SELL"
            out.append(compare_shadow_sample(champion,challenger))
        return out

    def test_empty_history_is_building(self):
        r=build_validation_readiness(pd.DataFrame(),[])
        self.assertIn(r["status"],("BUILDING","PARTIAL"))
        self.assertFalse(r["automatic_promotion_allowed"])

    def test_shadow_critical_mismatch_blocks(self):
        r=build_validation_readiness(
            self.history(),
            self.shadow_samples(100,critical=True),
            min_total_samples=50,
            min_group_samples=10,
            min_band_samples=10,
            min_fold_samples=10,
            min_shadow_samples=100,
        )
        self.assertEqual(r["status"],"BLOCKED")
        self.assertTrue(r["blockers"])

    def test_no_automatic_actions_are_ever_allowed(self):
        r=build_validation_readiness(pd.DataFrame(),[])
        self.assertFalse(r["automatic_promotion_allowed"])
        self.assertFalse(r["automatic_weight_change_allowed"])
        self.assertFalse(r["automatic_merge_allowed"])
        self.assertTrue(r["manual_review_required"])

    def test_shadow_minimum_is_pending_not_blocker(self):
        r=build_validation_readiness(
            self.history(),
            self.shadow_samples(10),
            min_total_samples=50,
            min_group_samples=10,
            min_band_samples=10,
            min_fold_samples=10,
            min_shadow_samples=100,
        )
        self.assertFalse(r["shadow"]["minimum_met"])
        self.assertFalse(r["blockers"])
        self.assertTrue(any("Shadow Mode" in x for x in r["pending"]))

    def test_target_expansion_is_planning_only(self):
        r=build_validation_readiness(
            self.history(),
            self.shadow_samples(100),
            min_total_samples=50,
            min_group_samples=10,
            min_band_samples=10,
            min_fold_samples=10,
            min_shadow_samples=100,
            current_pairs=7,
            target_pairs=28,
            daily_cap=480,
        )
        self.assertIn("target_requires_change",r["expansion"])
        self.assertNotIn("expansão", " ".join(r["blockers"]).lower())

    def test_checks_are_explicit(self):
        r=build_validation_readiness(pd.DataFrame(),[])
        self.assertEqual(
            set(r["checks"]),
            {"performance_reviewable","calibration_consistent","stability_consistent","shadow_reviewable","quota_shadow_reviewable"},
        )

    def test_shadow_total_can_pass_while_pair_coverage_remains_pending(self):
        r=build_validation_readiness(
            self.history(),
            self.shadow_samples(100),
            min_total_samples=50,
            min_group_samples=10,
            min_band_samples=10,
            min_fold_samples=10,
            min_shadow_samples=100,
            min_shadow_pair_samples=1,
            expected_shadow_pairs=("EUR/USD","GBP/USD"),
        )
        self.assertTrue(r["shadow"]["minimum_met"])
        self.assertFalse(r["shadow"]["coverage_balanced"])
        self.assertFalse(r["checks"]["shadow_reviewable"])
        self.assertTrue(any("cobertura por par" in x.lower() for x in r["pending"]))

    def test_balanced_shadow_coverage_can_pass_shadow_check(self):
        samples=[]
        for pair in ("EUR/USD","GBP/USD"):
            for i in range(2):
                champion={
                    "pair":pair,"side":"BUY","state":"WAIT","score":80,
                    "data_quality":90,"executable":False,"version":"champ",
                    "timestamp":f"2026-01-01T12:0{i}:00Z",
                }
                challenger=dict(champion); challenger["version"]="challenger"
                samples.append(compare_shadow_sample(champion,challenger))
        r=build_validation_readiness(
            self.history(),
            samples,
            min_total_samples=50,
            min_group_samples=10,
            min_band_samples=10,
            min_fold_samples=10,
            min_shadow_samples=4,
            min_shadow_pair_samples=2,
            expected_shadow_pairs=("EUR/USD","GBP/USD"),
        )
        self.assertTrue(r["shadow"]["coverage_balanced"])
        self.assertTrue(r["checks"]["shadow_reviewable"])


    def test_invalid_review_thresholds_never_enable_automatic_actions(self):
        bad=float("nan")
        r=build_validation_readiness(
            self.history(),
            self.shadow_samples(10),
            min_total_samples=bad,
            min_group_samples=bad,
            min_band_samples=bad,
            min_fold_samples=bad,
            min_shadow_samples=bad,
            min_shadow_pair_samples=bad,
            current_pairs=7,
            target_pairs=28,
            daily_cap=bad,
        )
        self.assertNotEqual(r["status"],"REVIEWABLE")
        self.assertFalse(r["automatic_promotion_allowed"])
        self.assertFalse(r["automatic_weight_change_allowed"])
        self.assertFalse(r["automatic_merge_allowed"])
        self.assertTrue(r["manual_review_required"])


    def test_validation_visual_state_is_conservative(self):
        self.assertEqual(validation_visual_state({"status":"BLOCKED"})["label"],"BLOQUEADA")
        self.assertEqual(validation_visual_state({"status":"REVIEWABLE"})["label"],"PRONTA PARA REVISÃO")
        self.assertEqual(validation_visual_state({"status":"PARTIAL"})["label"],"PARCIAL")
        self.assertEqual(validation_visual_state({"status":"BUILDING"})["label"],"EM FORMAÇÃO")
        self.assertEqual(validation_visual_state({"status":"UNKNOWN"})["label"],"REVISAR")



    def test_quota_shadow_is_explicit_readiness_gate(self):
        quota=[]
        for i in range(20):
            quota.append({
                "market_open":True,"provider_blocked":False,"app_headless_ok":True,
                "adaptive_within_usable_cap":True,"actual_http_calls":4,
            })
        r=build_validation_readiness(
            self.history(), self.shadow_samples(100), quota,
            min_total_samples=50, min_group_samples=10, min_band_samples=10,
            min_fold_samples=10, min_shadow_samples=100,
            min_shadow_pair_samples=1, expected_shadow_pairs=("EUR/USD",),
            min_quota_market_runs=20,
        )
        self.assertTrue(r["checks"]["quota_shadow_reviewable"])
        self.assertTrue(r["quota_shadow"]["eligible_for_manual_review"])
        self.assertFalse(r["automatic_promotion_allowed"])

    def test_closed_market_quota_samples_remain_pending(self):
        quota=[{
            "market_open":False,"provider_blocked":False,"app_headless_ok":True,
            "adaptive_within_usable_cap":True,"actual_http_calls":0,
        } for _ in range(44)]
        r=build_validation_readiness(pd.DataFrame(), [], quota, min_quota_market_runs=20)
        self.assertFalse(r["checks"]["quota_shadow_reviewable"])
        self.assertTrue(any("Quota Shadow" in x for x in r["pending"]))


    def test_renderer_signature_accepts_quota_shadow_samples(self):
        import inspect
        sig=inspect.signature(render_validation_readiness)
        self.assertIn("quota_shadow_samples",sig.parameters)


    def test_validation_panel_exposes_progress_and_pair_coverage(self):
        import inspect
        source=inspect.getsource(render_validation_readiness)
        self.assertIn("Progresso da evidência",source)
        self.assertIn("Shadow Mode ·",source)
        self.assertIn("Quota com mercado aberto ·",source)
        self.assertIn("Cobertura de validação por par",source)
        self.assertIn("Críticas",source)


    def test_validation_panel_protects_balanced_pair_progress_semantics(self):
        import inspect
        source=inspect.getsource(render_validation_readiness)
        self.assertIn("Cobertura balanceada por par",source)
        self.assertIn("pair_covered_total",source)
        self.assertIn("balanced_pair_coverage(",source)


    def test_closed_market_history_does_not_dilute_open_market_quota_gate(self):
        quota=[{
            "market_open":False,"provider_blocked":False,"app_headless_ok":True,
            "adaptive_within_usable_cap":True,"actual_http_calls":0,
        } for _ in range(44)]
        quota += [{
            "market_open":True,"provider_blocked":False,"app_headless_ok":True,
            "adaptive_within_usable_cap":True,"actual_http_calls":4,
        } for _ in range(20)]
        r=build_validation_readiness(
            pd.DataFrame(), [], quota, min_quota_market_runs=20
        )
        self.assertEqual(r["quota_shadow"]["samples"],64)
        self.assertEqual(r["quota_shadow"]["market_open_runs"],20)
        self.assertTrue(r["quota_shadow"]["minimum_met"])
        self.assertTrue(r["checks"]["quota_shadow_reviewable"])

    def test_unhealthy_open_market_quota_reaches_minimum_but_blocks(self):
        quota=[{
            "market_open":True,"provider_blocked":False,"app_headless_ok":True,
            "adaptive_within_usable_cap":True,"actual_http_calls":4,
        } for _ in range(20)]
        quota[-1]["provider_blocked"]=True
        r=build_validation_readiness(
            pd.DataFrame(), [], quota, min_quota_market_runs=20
        )
        self.assertTrue(r["quota_shadow"]["minimum_met"])
        self.assertFalse(r["checks"]["quota_shadow_reviewable"])
        self.assertTrue(any("Quota Shadow" in x for x in r["blockers"]))
        self.assertEqual(r["status"],"BLOCKED")


    def test_balanced_pair_coverage_caps_surplus_and_counts_missing_as_zero(self):
        r=balanced_pair_coverage(
            ("EUR/USD","GBP/USD","USD/JPY"),
            ({"pair":"EUR/USD","samples":30},{"pair":"GBP/USD","samples":4}),
            10,
        )
        self.assertEqual(r["required"],30)
        self.assertEqual(r["covered"],14)
        self.assertAlmostEqual(r["progress_pct"],46.6666666667)
        self.assertFalse(r["complete"])
        self.assertEqual(r["counts"]["USD/JPY"],0)

    def test_balanced_pair_coverage_is_conservative_with_duplicates_and_invalid_rows(self):
        r=balanced_pair_coverage(
            ("EUR/USD","EUR/USD","GBP/USD"),
            (
                {"pair":"EUR/USD","samples":3},
                {"pair":"EUR/USD","samples":8},
                {"pair":"GBP/USD","samples":-5},
                {"pair":"GBP/USD","samples":"bad"},
                {"pair":"AUD/USD","samples":999},
                "invalid",
            ),
            10,
        )
        self.assertEqual(r["required"],20)
        self.assertEqual(r["covered"],8)
        self.assertEqual(r["counts"],{"EUR/USD":8,"GBP/USD":0})
        self.assertFalse(r["complete"])


    def test_balanced_pair_coverage_complete_and_overfilled_stays_at_100(self):
        exact=balanced_pair_coverage(
            ("EUR/USD","GBP/USD"),
            ({"pair":"EUR/USD","samples":10},{"pair":"GBP/USD","samples":10}),
            10,
        )
        over=balanced_pair_coverage(
            ("EUR/USD","GBP/USD"),
            ({"pair":"EUR/USD","samples":100},{"pair":"GBP/USD","samples":20}),
            10,
        )
        self.assertEqual(exact["covered"],20)
        self.assertEqual(exact["progress_pct"],100.0)
        self.assertTrue(exact["complete"])
        self.assertEqual(over["covered"],20)
        self.assertEqual(over["progress_pct"],100.0)
        self.assertTrue(over["complete"])

    def test_balanced_pair_coverage_empty_expected_pairs_is_safe_not_complete(self):
        r=balanced_pair_coverage((),({"pair":"EUR/USD","samples":999},),10)
        self.assertEqual(r["required"],0)
        self.assertEqual(r["covered"],0)
        self.assertEqual(r["progress_pct"],0.0)
        self.assertFalse(r["complete"])


if __name__=="__main__":
    unittest.main()
