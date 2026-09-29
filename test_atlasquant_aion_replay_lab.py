import unittest

from atlasquant_aion_replay_lab import (
    build_news_replay_package,
    news_replay_catalog,
    reveal_news_replay_outcome,
    submit_news_replay_decision,
)


def event(
    event_id,
    headline,
    first_seen_at,
    *,
    last_seen_at=None,
    kind="MACRO",
    reported_at="2026-09-20T12:00:00+00:00",
):
    return {
        "event_id": event_id,
        "headline": headline,
        "kind": kind,
        "reported_at": reported_at,
        "truth_state": "CONFIRMED",
        "truth_note": "later enriched truth",
        "sources": ["later-source.example"],
        "source_count": 1,
        "currencies": ["USD"],
        "urgency_score": 99,
        "peak_urgency_score": 100,
        "alert_level": "URGENT_REVIEW",
        "peak_alert_level": "URGENT_REVIEW",
        "impact_truth_state": "CONFIRMED",
        "first_seen_at": first_seen_at,
        "last_seen_at": last_seen_at or first_seen_at,
        "seen_count": 7,
    }


class AionReplayLabTests(unittest.TestCase):
    def journal(self):
        return {
            "live_event_journal": {
                "events": [
                    event(
                        "E1",
                        "Primeiro evento",
                        "2026-09-20T12:00:00+00:00",
                    ),
                    event(
                        "E2",
                        "Evento alvo",
                        "2026-09-20T13:00:00+00:00",
                    ),
                    event(
                        "E3",
                        "Evento posterior",
                        "2026-09-20T14:00:00+00:00",
                    ),
                    event(
                        "E4",
                        "Evento muito posterior",
                        "2026-09-21T20:00:00+00:00",
                    ),
                ]
            }
        }

    def test_catalog_only_uses_events_with_valid_first_seen(self):
        data = self.journal()
        data["live_event_journal"]["events"].append(
            event("BAD", "Sem relógio", "")
        )
        catalog = news_replay_catalog(data)
        self.assertEqual(catalog["state"], "READY")
        ids = [row["event_id"] for row in catalog["scenarios"]]
        self.assertNotIn("BAD", ids)
        self.assertFalse(catalog["fabricated_scenarios"])
        self.assertFalse(catalog["real_trading_enabled"])

    def test_catalog_does_not_claim_full_historical_snapshots(self):
        catalog = news_replay_catalog(self.journal())
        self.assertTrue(catalog["scenarios"])
        self.assertTrue(
            all(
                row["full_historical_snapshot_available"] is False
                for row in catalog["scenarios"]
            )
        )
        self.assertIn("not a versioned field-by-field snapshot", catalog["limitations"])

    def test_package_exposes_only_stable_historical_fields(self):
        package = build_news_replay_package(
            self.journal(),
            event_id="E2",
            outcome_window_minutes=180,
        )
        self.assertEqual(package["state"], "READY")
        session = package["session"]
        self.assertEqual(session["state"], "ACTIVE")
        self.assertEqual(session["scenario_id"], "NEWS-E2")

        blob = str(session)
        self.assertIn("Primeiro evento", blob)
        self.assertIn("Evento alvo", blob)
        self.assertNotIn("Evento posterior", blob)

        for forbidden in (
            "later enriched truth",
            "later-source.example",
            "URGENT_REVIEW",
            "peak_urgency_score",
            "seen_count",
            "currencies",
        ):
            self.assertNotIn(forbidden, blob)

        self.assertFalse(package["mutable_journal_enrichment_exposed"])
        self.assertFalse(package["full_historical_snapshot_available"])

    def test_future_event_is_kept_for_outcome_not_initial_frame(self):
        package = build_news_replay_package(
            self.journal(),
            event_id="E2",
            outcome_window_minutes=180,
        )
        self.assertTrue(package["outcome_available"])
        self.assertEqual(package["later_event_count"], 1)
        self.assertNotIn("Evento posterior", str(package["session"]))
        self.assertIn("Evento posterior", str(package["outcome"]))
        self.assertNotIn("Evento muito posterior", str(package["outcome"]))

    def test_previous_events_are_visible_at_target_cutoff(self):
        package = build_news_replay_package(
            self.journal(),
            event_id="E2",
        )
        rows = package["visible_rows"]
        labels = [row["Evidência"] for row in rows]
        self.assertEqual(labels, ["Primeiro evento", "Evento alvo"])

    def test_unknown_scenario_fails_closed(self):
        package = build_news_replay_package(
            self.journal(),
            event_id="missing",
        )
        self.assertEqual(package["state"], "BLOCKED")
        self.assertEqual(package["reason"], "SCENARIO_NOT_FOUND")
        self.assertFalse(package["executes_action"])
        self.assertFalse(package["real_trading_enabled"])

    def test_decision_and_reveal_flow_is_training_only(self):
        package = build_news_replay_package(
            self.journal(),
            event_id="E2",
            outcome_window_minutes=180,
        )
        decided = submit_news_replay_decision(
            package["session"],
            choice="AGUARDAR",
            rationale="Informação ainda incompleta",
            confidence_pct=65,
            submitted_at="2026-09-20T13:01:00+00:00",
        )
        self.assertEqual(decided["state"], "DECISION_RECORDED")
        self.assertFalse(decided["executes_action"])
        self.assertFalse(decided["real_trading_enabled"])

        revealed = reveal_news_replay_outcome(
            decided,
            package["outcome"],
            revealed_at="2026-09-20T14:01:00+00:00",
        )
        self.assertEqual(revealed["state"], "REVEALED")
        self.assertEqual(revealed["evaluation"], "UNSCORED")
        self.assertFalse(revealed["decision_quality_inferred"])
        self.assertFalse(revealed["automatic_promotion"])
        self.assertFalse(revealed["execution_authorized"])
        self.assertFalse(revealed["real_trading_enabled"])

    def test_no_later_event_evidence_blocks_reveal(self):
        package = build_news_replay_package(
            self.journal(),
            event_id="E4",
            outcome_window_minutes=180,
        )
        self.assertFalse(package["outcome_available"])
        decided = submit_news_replay_decision(
            package["session"],
            choice="INDEFINIDO",
            rationale="Sem evento posterior no recorte",
            confidence_pct=20,
            submitted_at="2026-09-21T20:01:00+00:00",
        )
        revealed = reveal_news_replay_outcome(
            decided,
            package["outcome"],
            revealed_at="2026-09-21T21:00:00+00:00",
        )
        self.assertEqual(revealed["state"], "BLOCKED")
        self.assertEqual(revealed["reason"], "NO_LATER_EVENT_EVIDENCE")
        self.assertTrue(revealed["training_only"])
        self.assertFalse(revealed["executes_action"])
        self.assertFalse(revealed["real_trading_enabled"])

    def test_outcome_window_is_bounded(self):
        package = build_news_replay_package(
            self.journal(),
            event_id="E2",
            outcome_window_minutes=999999,
        )
        self.assertLessEqual(
            package["outcome"]["payload"]["window_minutes"],
            24 * 60,
        )

    def test_bool_window_does_not_become_one_minute(self):
        package = build_news_replay_package(
            self.journal(),
            event_id="E2",
            outcome_window_minutes=True,
        )
        self.assertEqual(
            package["outcome"]["payload"]["window_minutes"],
            240,
        )

    def test_empty_journal_does_not_fabricate_scenario(self):
        catalog = news_replay_catalog({"live_event_journal": {"events": []}})
        self.assertEqual(catalog["state"], "NO_ELIGIBLE_SCENARIOS")
        self.assertEqual(catalog["scenarios"], [])
        self.assertFalse(catalog["fabricated_scenarios"])


if __name__ == "__main__":
    unittest.main()
