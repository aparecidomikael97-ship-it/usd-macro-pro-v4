import unittest
import pandas as pd

from atlasquant_validation_readiness import build_validation_readiness, validation_visual_state
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
            {"performance_reviewable","calibration_consistent","stability_consistent","shadow_reviewable"},
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



if __name__=="__main__":
    unittest.main()
