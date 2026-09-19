import json
import unittest

from atlasquant_evidence_bundle import (
    build_validation_evidence,
    serialize_validation_evidence,
    verify_validation_evidence,
    evidence_visual_state,
    render_validation_evidence,
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


    def test_evidence_panel_source_exposes_quota_market_progress(self):
        import inspect, atlasquant_evidence_bundle as module
        source=inspect.getsource(module.render_validation_evidence)
        self.assertIn('"Quota mercado"',source)
        self.assertIn("market_open_runs",source)
        self.assertIn("min_market_runs",source)


    def test_prospective_paper_and_setup_state_are_integrity_protected(self):
        paper={"trades_total":3,"pending_entries":1,"open_positions":1,"closed_trades":1,
               "net_r_after_friction":0.94,"safety":{"real_orders":False}}
        setup={"audited_trades":3,"closed_trades":1,"component_state_rows":4,
               "sample_state":"AMOSTRA PEQUENA","safety":{"real_orders":False}}
        b=build_validation_evidence(self.readiness(),engine_version="dev",
                                    paper_summary=paper,setup_summary=setup)
        self.assertEqual(b["evidence"]["paper_forward_test"]["closed_trades"],1)
        self.assertEqual(b["evidence"]["setup_audit"]["audited_trades"],3)
        self.assertFalse(b["evidence"]["paper_forward_test"]["real_orders"])
        self.assertTrue(verify_validation_evidence(b))
        b["evidence"]["paper_forward_test"]["closed_trades"]=99
        self.assertFalse(verify_validation_evidence(b))


    def test_evidence_panel_exposes_prospective_maturity_without_live_claims(self):
        import inspect, atlasquant_evidence_bundle as module
        source=inspect.getsource(module.render_validation_evidence)
        self.assertIn("Evidência prospectiva",source)
        self.assertIn("Paper fechados",source)
        self.assertIn("Setups auditados",source)
        self.assertIn("Maturidade setup",source)
        self.assertIn("não liberam operação real",source)


    def test_balanced_pair_coverage_is_integrity_protected(self):
        r=self.readiness()
        r["shadow"]["min_pair_samples"]=10
        r["shadow"]["expected_pairs"]=["EUR/USD","GBP/USD"]
        r["shadow"]["pair_breakdown"]=[
            {"pair":"EUR/USD","samples":15,"critical_mismatches":0},
            {"pair":"GBP/USD","samples":4,"critical_mismatches":0},
        ]
        b=build_validation_evidence(r,engine_version="dev")
        shadow=b["evidence"]["shadow"]
        self.assertEqual(shadow["balanced_pair_covered"],14)
        self.assertEqual(shadow["balanced_pair_required"],20)
        self.assertFalse(shadow["balanced_pair_complete"])
        self.assertTrue(verify_validation_evidence(b))
        b["evidence"]["shadow"]["balanced_pair_complete"]=True
        self.assertFalse(verify_validation_evidence(b))


    def test_evidence_panel_exposes_protected_balanced_coverage(self):
        import inspect
        source=inspect.getsource(render_validation_evidence)
        self.assertIn("Cobertura balanceada protegida no manifesto",source)
        self.assertIn("balanced_pair_covered",source)
        self.assertIn("balanced_pair_required",source)


    def test_evidence_and_validation_share_canonical_balanced_coverage(self):
        from atlasquant_validation_readiness import balanced_pair_coverage
        r=self.readiness()
        r["shadow"]["min_pair_samples"]=10
        r["shadow"]["expected_pairs"]=["EUR/USD","GBP/USD","USD/JPY"]
        r["shadow"]["pair_breakdown"]=[
            {"pair":"EUR/USD","samples":30},
            {"pair":"EUR/USD","samples":8},
            {"pair":"GBP/USD","samples":4},
            {"pair":"AUD/USD","samples":999},
        ]
        expected=balanced_pair_coverage(
            r["shadow"]["expected_pairs"],r["shadow"]["pair_breakdown"],10
        )
        b=build_validation_evidence(r,engine_version="dev")
        shadow=b["evidence"]["shadow"]
        self.assertEqual(shadow["balanced_pair_covered"],expected["covered"])
        self.assertEqual(shadow["balanced_pair_required"],expected["required"])
        self.assertEqual(shadow["balanced_pair_complete"],expected["complete"])


    def test_renderer_accepts_and_forwards_prospective_summaries(self):
        import inspect
        sig=inspect.signature(render_validation_evidence)
        self.assertIn("paper_summary",sig.parameters)
        self.assertIn("setup_summary",sig.parameters)
        source=inspect.getsource(render_validation_evidence)
        self.assertIn("paper_summary=paper_summary",source)
        self.assertIn("setup_summary=setup_summary",source)


    def test_balanced_pair_diagnostics_are_integrity_protected(self):
        r=self.readiness()
        r["shadow"]["min_pair_samples"]=10
        r["shadow"]["expected_pairs"]=["EUR/USD","GBP/USD","USD/JPY"]
        r["shadow"]["pair_breakdown"]=[
            {"pair":"EUR/USD","samples":12},
            {"pair":"GBP/USD","samples":4},
        ]
        b=build_validation_evidence(r,engine_version="dev")
        s=b["evidence"]["shadow"]
        self.assertEqual(s["balanced_pairs_complete"],1)
        self.assertEqual(s["balanced_pairs_total"],3)
        self.assertEqual(s["balanced_pairs_missing"],["USD/JPY"])
        self.assertEqual(s["balanced_pairs_under_target"],["GBP/USD"])
        self.assertTrue(verify_validation_evidence(b))
        b["evidence"]["shadow"]["balanced_pairs_complete"]=3
        self.assertFalse(verify_validation_evidence(b))


if __name__=="__main__":
    unittest.main()
