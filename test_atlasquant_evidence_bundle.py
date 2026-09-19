import json
import unittest

from atlasquant_evidence_bundle import (
    build_validation_evidence,
    serialize_validation_evidence,
    verify_validation_evidence,
    evidence_visual_state,
)


class AtlasQuantEvidenceBundleTests(unittest.TestCase):
    def readiness(self):
        return {
            "status":"PARTIAL",
            "label":"VALIDAÇÃO PARCIAL",
            "checks":{
                "performance_reviewable":True,
                "calibration_consistent":False,
                "stability_consistent":True,
                "shadow_reviewable":False,
                "quota_shadow_reviewable":False,
            },
            "passed_checks":2,
            "total_checks":5,
            "blockers":[],
            "pending":["Shadow Mode: cobertura por par insuficiente"],
            "performance":{"status":"REVIEWABLE","label":"REVIEWABLE","samples":120},
            "calibration":{"status":"BUILDING","label":"EM FORMAÇÃO","total_samples":80},
            "stability":{"status":"STABLE","label":"ESTÁVEL","folds":3},
            "shadow":{
                "samples":100,
                "min_samples":100,
                "critical_mismatches":0,
                "coverage_balanced":False,
                "pairs_meeting_minimum":3,
                "expected_pair_count":7,
                "missing_pairs":["AUD/USD"],
                "under_sampled_pairs":["USD/CAD"],
                "eligible_for_manual_review":False,
            },
            "quota_shadow":{
                "samples":44,
                "market_open_runs":0,
                "min_market_runs":20,
                "provider_blocked_runs":0,
                "headless_failed_runs":0,
                "adaptive_plan_fit_all_samples":True,
                "eligible_for_manual_review":False,
            },
            "expansion":{
                "target_requires_change":True,
                "max_pairs_same_cadence":8,
            },
        }

    def test_bundle_is_integrity_verifiable(self):
        b=build_validation_evidence(
            self.readiness(),
            engine_version="dev",
            generated_at="2026-09-16T00:00:00+00:00",
        )
        self.assertTrue(verify_validation_evidence(b))

    def test_tampering_breaks_digest(self):
        b=build_validation_evidence(
            self.readiness(),
            engine_version="dev",
            generated_at="2026-09-16T00:00:00+00:00",
        )
        b["validation"]["status"]="REVIEWABLE"
        self.assertFalse(verify_validation_evidence(b))

    def test_automatic_actions_are_always_disabled(self):
        b=build_validation_evidence(self.readiness(),engine_version="dev")
        self.assertTrue(b["controls"]["manual_review_required"])
        self.assertFalse(b["controls"]["automatic_promotion_allowed"])
        self.assertFalse(b["controls"]["automatic_weight_change_allowed"])
        self.assertFalse(b["controls"]["automatic_merge_allowed"])

    def test_shadow_pair_coverage_is_exported(self):
        b=build_validation_evidence(self.readiness(),engine_version="dev")
        s=b["evidence"]["shadow"]
        self.assertEqual(s["pairs_meeting_minimum"],3)
        self.assertEqual(s["expected_pair_count"],7)
        self.assertFalse(s["coverage_balanced"])

    def test_serialized_bundle_is_valid_json(self):
        b=build_validation_evidence(self.readiness(),engine_version="dev")
        parsed=json.loads(serialize_validation_evidence(b))
        self.assertEqual(parsed["schema_version"],"atlasquant.validation-evidence.v1")
        self.assertIn("integrity_sha256",parsed)


    def test_evidence_provenance_metadata_must_be_identifiable(self):
        good=build_validation_evidence(self.readiness(),engine_version="V11",generated_at="2026-09-16T00:00:00+00:00")
        self.assertTrue(good["source_metadata_valid"])
        for engine,stamp in (("","2026-09-16T00:00:00+00:00"),("V11","bad"),("V11","2026-09-16T00:00:00")):
            with self.subTest(engine=engine,stamp=stamp):
                b=build_validation_evidence(self.readiness(),engine_version=engine,generated_at=stamp)
                self.assertFalse(b["source_metadata_valid"])
                self.assertTrue(verify_validation_evidence(b))



    def test_evidence_visual_state_separates_integrity_from_provenance(self):
        good=build_validation_evidence(self.readiness(),engine_version="V11",generated_at="2026-09-16T00:00:00+00:00")
        self.assertEqual(evidence_visual_state(good)["label"],"EVIDÊNCIA PARCIAL")
        bad_meta=build_validation_evidence(self.readiness(),engine_version="",generated_at="2026-09-16T00:00:00+00:00")
        self.assertEqual(evidence_visual_state(bad_meta)["label"],"PROVENIÊNCIA A REVISAR")
        tampered=dict(good)
        tampered["validation"]=dict(good["validation"])
        tampered["validation"]["status"]="REVIEWABLE"
        self.assertEqual(evidence_visual_state(tampered)["label"],"INTEGRIDADE INVÁLIDA")



    def test_quota_shadow_evidence_is_exported_and_integrity_protected(self):
        b=build_validation_evidence(self.readiness(),engine_version="dev")
        q=b["evidence"]["quota_shadow"]
        self.assertEqual(q["samples"],44)
        self.assertEqual(q["market_open_runs"],0)
        self.assertEqual(q["min_market_runs"],20)
        self.assertFalse(q["eligible_for_manual_review"])
        self.assertTrue(verify_validation_evidence(b))
        b["evidence"]["quota_shadow"]["market_open_runs"]=20
        self.assertFalse(verify_validation_evidence(b))


if __name__=="__main__":
    unittest.main()
