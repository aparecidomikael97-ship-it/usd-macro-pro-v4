import unittest

from atlasquant_release_gate import release_gate, release_gate_rows


def publication(**overrides):
    base = {
        "source_build": "build-a",
        "runtime_commit": "a" * 40,
        "expected_main_commit": "a" * 40,
        "main_match": "MATCH",
        "production_verification": "UNKNOWN",
        "can_claim_latest_main_live": False,
        "next_action": "Validar produção.",
    }
    base.update(overrides)
    return base


def validation(**overrides):
    base = {
        "state": "COMPLETE",
        "confirmed": 3,
        "total": 3,
        "failed": 0,
        "all_confirmed_current_build": True,
    }
    base.update(overrides)
    return base


class AtlasQuantReleaseGateTests(unittest.TestCase):
    def test_no_source_evidence_fails_closed(self):
        out = release_gate()
        self.assertEqual(out["state"], "UNKNOWN")
        self.assertEqual(out["confirmed_stages"], 0)
        self.assertFalse(out["release_claim_allowed"])
        self.assertFalse(out["deployment_action_allowed"])

    def test_incomplete_interface_becomes_validate_build(self):
        out = release_gate(
            publication_truth=publication(),
            interface_validation=validation(
                state="IN_PROGRESS",
                confirmed=2,
                failed=0,
                all_confirmed_current_build=False,
                next_action="Validar Radar avançado.",
            ),
        )
        self.assertEqual(out["state"], "VALIDATE_BUILD")
        self.assertEqual(out["next_stage"], "critical_interface")
        self.assertEqual(out["confirmed_stages"], 2)
        self.assertFalse(out["release_claim_allowed"])

    def test_interface_failure_blocks_release_gate(self):
        out = release_gate(
            publication_truth=publication(),
            interface_validation=validation(
                state="ATTENTION",
                confirmed=1,
                failed=1,
                all_confirmed_current_build=False,
                next_action="Revisar Painel Mestre.",
            ),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertEqual(out["next_stage"], "critical_interface")
        self.assertTrue(out["has_blocker"])

    def test_runtime_main_mismatch_blocks_even_if_interface_is_good(self):
        out = release_gate(
            publication_truth=publication(
                main_match="MISMATCH",
                runtime_commit="a" * 40,
                expected_main_commit="b" * 40,
            ),
            interface_validation=validation(),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertEqual(out["next_stage"], "main_alignment")
        self.assertFalse(out["latest_main_live_claim_allowed"])

    def test_matching_main_without_production_proof_requires_verification(self):
        out = release_gate(
            publication_truth=publication(),
            interface_validation=validation(),
        )
        self.assertEqual(out["state"], "VERIFY_PRODUCTION")
        self.assertEqual(out["confirmed_stages"], 3)
        self.assertEqual(out["progress_pct"], 75.0)
        self.assertEqual(out["next_stage"], "production")
        self.assertFalse(out["release_claim_allowed"])

    def test_complete_requires_all_four_evidence_stages(self):
        out = release_gate(
            publication_truth=publication(
                production_verification="VERIFIED",
                can_claim_latest_main_live=True,
            ),
            interface_validation=validation(),
        )
        self.assertEqual(out["state"], "COMPLETE")
        self.assertEqual(out["confirmed_stages"], 4)
        self.assertEqual(out["progress_pct"], 100.0)
        self.assertTrue(out["release_claim_allowed"])
        self.assertTrue(out["latest_main_live_claim_allowed"])
        self.assertFalse(out["automatic_deploy"])
        self.assertFalse(out["real_orders_enabled"])

    def test_rows_are_presentation_only(self):
        out = release_gate(
            publication_truth=publication(),
            interface_validation=validation(),
        )
        rows = release_gate_rows(out)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["Etapa"], "Código / bundle")
        self.assertIn("Próxima ação", rows[0])


if __name__ == "__main__":
    unittest.main()
