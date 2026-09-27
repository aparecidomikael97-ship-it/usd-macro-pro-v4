import json
import os
import unittest

from atlasquant_aion_specialist_evidence import SCHEMA, read_specialist_evidence
from atlasquant_aion_specialists import SPECIALIST_MODULES
from atlasquant_aion_truth import assess_truth


class AionSpecialistEvidenceTests(unittest.TestCase):
    def test_every_registered_specialist_stays_local_and_fail_closed(self):
        for specialist in SPECIALIST_MODULES:
            snapshot = read_specialist_evidence(specialist)
            self.assertEqual(snapshot["schema"], SCHEMA)
            self.assertEqual(snapshot["specialist"], specialist)
            self.assertEqual(snapshot["module"], SPECIALIST_MODULES[specialist])
            self.assertEqual(snapshot["answer_truth"], "UNKNOWN")
            self.assertFalse(snapshot["answers_user_question"])
            self.assertFalse(snapshot["provider_called"])
            self.assertFalse(snapshot["network_called"])
            self.assertFalse(snapshot["tool_called"])
            self.assertFalse(snapshot["executes_action"])
            self.assertFalse(snapshot["real_orders_enabled"])
            self.assertFalse(snapshot["invented_values"])
            self.assertFalse(snapshot["secrets_included"])
            self.assertTrue(snapshot["summary"])
            self.assertTrue(snapshot["claims"])

    def test_unknown_specialist_invents_nothing(self):
        snapshot = read_specialist_evidence("missing")
        self.assertEqual(snapshot["state"], "UNKNOWN_SPECIALIST")
        self.assertEqual(snapshot["claims"], [])
        self.assertIn("não registrado", snapshot["summary"])

    def test_market_contract_is_not_a_live_quote(self):
        snapshot = read_specialist_evidence("market")
        self.assertEqual(snapshot["observations"]["pair_count"], 28)
        self.assertTrue(snapshot["observations"]["universe_valid"])
        self.assertEqual(snapshot["observations"]["missing_without_persisted_input"], 28)
        self.assertEqual(snapshot["observations"]["fresh_readings"], 0)
        self.assertFalse(snapshot["observations"]["live_feed_consulted"])
        self.assertFalse(snapshot["observations"]["continuous_worker_configured"])
        blob = json.dumps(snapshot, ensure_ascii=False)
        self.assertNotIn("EURUSD", blob)
        self.assertNotIn("price", snapshot["observations"])
        self.assertNotIn("top_10", snapshot["observations"])

    def test_macro_and_invest_do_not_estimate(self):
        macro = read_specialist_evidence("macro")
        self.assertEqual(macro["observations"]["state"], "DADOS INSUFICIENTES")
        self.assertFalse(macro["observations"]["data_sufficient"])
        invest = read_specialist_evidence("invest")
        self.assertEqual(invest["observations"]["state"], "NÃO CONFIRMADO")
        self.assertEqual(invest["observations"]["rows"], 0)
        self.assertFalse(invest["observations"]["personalized_recommendation"])

    def test_ict_blocks_undefined_setup_without_running_backtest(self):
        snapshot = read_specialist_evidence("ict")
        self.assertIn("ppr", snapshot["observations"]["blocked_setups"])
        self.assertGreater(snapshot["observations"]["counts"]["SEM_EVIDENCIA"], 0)
        self.assertFalse(snapshot["observations"]["runs_backtest"])
        self.assertFalse(snapshot["observations"]["fabricated_values"])

    def test_risk_posture_is_not_a_confirmed_incident(self):
        snapshot = read_specialist_evidence("risk")
        self.assertEqual(snapshot["observations"]["posture"], "SAFE_MODE_RECOMMENDED")
        self.assertFalse(snapshot["observations"]["incident_confirmed"])
        self.assertFalse(snapshot["observations"]["automatic_cutoff"])

    def test_lab_never_reads_or_records_credentials(self):
        key = "GITHUB_TOKEN_HISTORICO"
        previous = os.environ.get(key)
        os.environ[key] = "super-secret-token-value"
        try:
            snapshot = read_specialist_evidence("lab")
            blob = json.dumps(snapshot)
            self.assertNotIn("super-secret-token-value", blob)
            self.assertTrue(snapshot["observations"]["credential_present"])
            self.assertFalse(snapshot["observations"]["remote_store_consulted"])
            self.assertEqual(snapshot["observations"]["records_loaded"], 0)
        finally:
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous

    def test_dev_business_studio_research_and_admin_do_not_act(self):
        dev = read_specialist_evidence("dev")
        self.assertEqual(dev["observations"]["status"], "INCOMPLETE")
        self.assertFalse(dev["observations"]["automatic_merge"])
        self.assertFalse(dev["observations"]["automatic_deploy"])
        self.assertFalse(dev["observations"]["repository_mutated"])
        business = read_specialist_evidence("business")
        self.assertEqual(business["observations"]["total"], 0)
        self.assertFalse(business["observations"]["publication_executed"])
        studio = read_specialist_evidence("studio")
        self.assertFalse(studio["observations"]["publishing_configured"])
        self.assertTrue(all(state == "NOT_CONFIGURED" for state in studio["observations"]["providers"].values()))
        research = read_specialist_evidence("research")
        self.assertFalse(research["observations"]["web_research_executed"])
        self.assertFalse(research["observations"]["external_model_executed"])
        admin = read_specialist_evidence("admin")
        self.assertEqual(admin["observations"]["pending_in_this_call"], 0)
        self.assertFalse(admin["observations"]["checkpoint_supplied"])
        self.assertFalse(admin["observations"]["automatic_approval"])

    def test_core_denies_real_trade_even_when_approved(self):
        snapshot = read_specialist_evidence("core")
        self.assertFalse(snapshot["observations"]["real_trade_allowed"])
        self.assertEqual(snapshot["observations"]["risk"], "REAL_TRADING")

    def test_contract_claim_and_live_gap_keep_separate_truth(self):
        market = read_specialist_evidence("market")
        by_claim = {row["claim"]: row for row in market["claims"]}
        contract = assess_truth([by_claim["forex_universe_contract"]])
        live = assess_truth([by_claim["live_market_reading"]])
        self.assertEqual(contract["status"], "CONFIRMED")
        self.assertEqual(live["status"], "UNKNOWN")
        self.assertEqual(market["answer_truth"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
