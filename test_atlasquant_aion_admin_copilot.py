import unittest

from atlasquant_aion_admin_copilot import (
    build_admin_copilot,
    compact_admin_copilot_rows,
)


class AionAdminCopilotTests(unittest.TestCase):
    def test_empty_evidence_stays_unknown(self):
        out = build_admin_copilot()
        self.assertEqual(out["state"], "UNKNOWN")
        self.assertEqual(out["items"], [])
        self.assertFalse(out["executes_action"])
        self.assertFalse(out["real_trading_enabled"])

    def test_critical_incident_becomes_primary_p0(self):
        out = build_admin_copilot(
            incident_snapshot={
                "incidents": [{
                    "incident_id": "INC-1",
                    "severity": "CRITICAL",
                    "title": "Checkpoint corrompido",
                    "detail": "Digest divergente",
                    "source": "runtime_result.integrity",
                    "evidence_state": "CONFIRMED",
                }]
            }
        )
        self.assertEqual(out["state"], "CRITICAL")
        self.assertEqual(out["primary"]["priority"], "P0")
        self.assertEqual(out["primary"]["truth_state"], "CONFIRMED")
        self.assertIn("Checkpoint", out["primary"]["title"])

    def test_health_blocked_becomes_p1_blocked(self):
        out = build_admin_copilot(
            system_health_center={
                "items": [{
                    "id": "runtime",
                    "label": "Runtime",
                    "state": "BLOCKED",
                    "detail": "Runtime bloqueado",
                }]
            }
        )
        row = out["items"][0]
        self.assertEqual(row["priority"], "P1")
        self.assertEqual(row["truth_state"], "BLOCKED")
        self.assertEqual(out["state"], "ATTENTION")

    def test_degraded_or_unknown_health_is_not_promoted_to_confirmed(self):
        out = build_admin_copilot(
            system_health_center={
                "items": [{
                    "id": "workers",
                    "label": "Workers",
                    "state": "UNKNOWN",
                    "detail": "Sem evidência",
                }]
            }
        )
        row = out["items"][0]
        self.assertEqual(row["truth_state"], "UNKNOWN")
        self.assertEqual(row["priority"], "P2")

    def test_cost_estimate_never_becomes_confirmed_spend(self):
        out = build_admin_copilot(
            cost_center={
                "state": "PARTIAL",
                "confirmed_monthly_usd": 10,
                "estimated_monthly_usd": 5,
            }
        )
        row = out["items"][0]
        self.assertEqual(row["truth_state"], "UNKNOWN")
        self.assertIn("estimado US$ 5.00", row["detail"])
        self.assertIn("Estimativa", row["next_action"])

    def test_confirmed_cost_center_adds_no_attention_item(self):
        out = build_admin_copilot(
            cost_center={
                "state": "CONFIRMED",
                "confirmed_monthly_usd": 10,
                "estimated_monthly_usd": 0,
            },
            reliability_snapshot={"posture": "CONTROLLED"},
        )
        self.assertEqual(out["items"], [])
        self.assertEqual(out["state"], "CONTROLLED")

    def test_release_blocked_is_attention_and_never_changes_flag(self):
        out = build_admin_copilot(
            release_matrix={
                "items": [{
                    "feature": "social_publish",
                    "requested_layer": "PILOT",
                    "state": "BLOCKED",
                    "missing_evidence": ["health_confirmed"],
                }]
            }
        )
        row = out["items"][0]
        self.assertEqual(row["priority"], "P1")
        self.assertEqual(row["truth_state"], "BLOCKED")
        self.assertFalse(row["automatic_feature_change"])
        self.assertFalse(out["automatic_feature_change"])

    def test_human_review_ready_is_advisory_only(self):
        out = build_admin_copilot(
            release_matrix={
                "items": [{
                    "feature": "external_llm",
                    "requested_layer": "PILOT",
                    "state": "HUMAN_REVIEW_READY",
                    "missing_evidence": [],
                }]
            }
        )
        row = out["items"][0]
        self.assertEqual(row["priority"], "P2")
        self.assertEqual(row["truth_state"], "CONFIRMED")
        self.assertIn("não altera a feature flag", row["next_action"])

    def test_status_unknown_stays_unknown(self):
        out = build_admin_copilot(
            status_board={
                "attention": [{
                    "id": "worker",
                    "label": "Worker",
                    "state": "UNKNOWN",
                    "detail": "Não confirmado",
                    "next_action": "Revisar",
                    "source": "status",
                    "area": "system",
                }]
            }
        )
        row = out["items"][0]
        self.assertEqual(row["truth_state"], "UNKNOWN")
        self.assertEqual(row["priority"], "P3")

    def test_executive_primary_is_preserved_as_advisory(self):
        out = build_admin_copilot(
            executive_snapshot={
                "posture": "ATTENTION",
                "primary": {
                    "priority": "P1",
                    "title": "Aprovação pendente",
                    "detail": "Revisar aprovação",
                    "next_action": "Abrir inbox",
                    "source": "approval_inbox",
                    "area": "studio",
                },
            }
        )
        row = out["items"][0]
        self.assertEqual(row["title"], "Aprovação pendente")
        self.assertEqual(row["truth_state"], "CONFIRMED")
        self.assertFalse(row["automatic_approval"])

    def test_secret_like_values_are_redacted(self):
        out = build_admin_copilot(
            incident_snapshot={
                "incidents": [{
                    "incident_id": "INC-2",
                    "severity": "HIGH",
                    "title": "Segredo exposto token=abc123",
                    "detail": "Authorization bearer ZXhhbXBsZQ== api_key=xyz",
                    "source": "log secret=supervalue",
                    "evidence_state": "CONFIRMED",
                }]
            }
        )
        blob = str(out)
        self.assertNotIn("abc123", blob)
        self.assertNotIn("ZXhhbXBsZQ==", blob)
        self.assertNotIn("xyz", blob)
        self.assertNotIn("supervalue", blob)
        self.assertIn("[REDACTED]", blob)

    def test_limit_is_bounded_and_bool_does_not_become_one(self):
        health = {
            "items": [
                {
                    "id": f"d{i}",
                    "label": f"Domain {i}",
                    "state": "UNKNOWN",
                    "detail": "unknown",
                }
                for i in range(20)
            ]
        }
        out = build_admin_copilot(
            system_health_center=health,
            max_items=True,
        )
        self.assertEqual(len(out["items"]), 8)

        out = build_admin_copilot(
            system_health_center=health,
            max_items=1000,
        )
        self.assertEqual(len(out["items"]), 12)

    def test_deduplicates_same_title_and_source(self):
        out = build_admin_copilot(
            executive_snapshot={
                "posture": "ATTENTION",
                "primary": {
                    "priority": "P1",
                    "title": "Mesmo item",
                    "detail": "a",
                    "next_action": "x",
                    "source": "same-source",
                },
            },
            status_board={
                "attention": [{
                    "id": "same",
                    "label": "Mesmo item",
                    "state": "BLOCKED",
                    "detail": "b",
                    "next_action": "y",
                    "source": "same-source",
                }]
            },
        )
        self.assertEqual(len(out["items"]), 1)

    def test_compact_rows_do_not_expose_control_flags(self):
        out = build_admin_copilot(
            system_health_center={
                "items": [{
                    "id": "sources",
                    "label": "Fontes",
                    "state": "UNKNOWN",
                    "detail": "Sem prova",
                }]
            }
        )
        rows = compact_admin_copilot_rows(out)
        self.assertEqual(
            set(rows[0]),
            {"Prioridade", "Área", "Item", "Evidência", "Próxima ação"},
        )
        self.assertNotIn("automatic_feature_change", rows[0])

    def test_never_promotes_setup_or_enables_trading(self):
        out = build_admin_copilot(
            reliability_snapshot={"posture": "CONTROLLED"}
        )
        self.assertFalse(out["promotes_setup"])
        self.assertFalse(out["automatic_setup_promotion"])
        self.assertFalse(out["real_trading_enabled"])
        self.assertFalse(out["executes_action"])


if __name__ == "__main__":
    unittest.main()
