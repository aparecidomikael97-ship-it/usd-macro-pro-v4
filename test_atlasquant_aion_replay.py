from datetime import datetime, timezone
import unittest

from atlasquant_aion_replay import (
    build_replay_frame,
    compact_replay_rows,
    reveal_replay_outcome,
    start_replay_session,
    submit_replay_decision,
)


CUT = "2026-09-20T14:00:00+00:00"


def record(
    record_id,
    key,
    available_at,
    *,
    label="Evidence",
    payload=None,
    observed_at="2026-09-20T13:00:00+00:00",
    source="historical_fixture",
    truth_state="CONFIRMED",
    kind="MACRO",
):
    return {
        "record_id": record_id,
        "knowledge_key": key,
        "kind": kind,
        "label": label,
        "source": source,
        "truth_state": truth_state,
        "observed_at": observed_at,
        "available_at": available_at,
        "payload": payload if payload is not None else {"value": record_id},
    }


class AionReplayModeTests(unittest.TestCase):
    def test_future_evidence_is_masked_without_content_leak(self):
        future = record(
            "R2",
            "cpi",
            "2026-09-20T14:01:00+00:00",
            label="SECRET FUTURE CPI",
            payload={"value": 99, "surprise": "future-only"},
        )
        frame = build_replay_frame([future], replay_at=CUT)
        self.assertEqual(frame["state"], "EMPTY")
        self.assertEqual(frame["visible_records"], [])
        self.assertEqual(frame["counts"]["future_masked"], 1)
        blob = str(frame)
        self.assertNotIn("SECRET FUTURE CPI", blob)
        self.assertNotIn("future-only", blob)
        self.assertFalse(frame["future_evidence_exposed"])

    def test_available_at_equal_cutoff_is_visible(self):
        frame = build_replay_frame(
            [record("R1", "cpi", CUT)],
            replay_at=CUT,
        )
        self.assertEqual(frame["state"], "VERIFIED")
        self.assertEqual(frame["counts"]["visible"], 1)
        self.assertTrue(frame["point_in_time_verified"])

    def test_missing_availability_never_becomes_visible(self):
        raw = record("R1", "cpi", CUT)
        raw.pop("available_at")
        frame = build_replay_frame([raw], replay_at=CUT)
        self.assertEqual(frame["visible_records"], [])
        self.assertEqual(frame["counts"]["unknown_availability"], 1)
        self.assertFalse(frame["point_in_time_verified"])

    def test_invalid_availability_is_invalid_not_visible(self):
        frame = build_replay_frame(
            [record("R1", "cpi", "not-a-date")],
            replay_at=CUT,
        )
        self.assertEqual(frame["visible_records"], [])
        self.assertEqual(frame["counts"]["invalid"], 1)
        self.assertEqual(frame["invalid_records"][0]["reason"], "AVAILABLE_AT_INVALID")

    def test_naive_cutoff_is_blocked(self):
        frame = build_replay_frame([], replay_at="2026-09-20T14:00:00")
        self.assertEqual(frame["state"], "BLOCKED")
        self.assertEqual(frame["reason"], "REPLAY_AT_INVALID")

    def test_revision_after_cutoff_does_not_overwrite_known_value(self):
        initial = record(
            "R1",
            "payroll",
            "2026-09-20T13:30:00+00:00",
            payload={"value": 100},
        )
        revision = record(
            "R2",
            "payroll",
            "2026-09-20T16:00:00+00:00",
            payload={"value": 125},
            label="later revision",
        )
        frame = build_replay_frame([initial, revision], replay_at=CUT)
        self.assertEqual(frame["visible_records"][0]["payload"]["value"], 100)
        self.assertEqual(frame["counts"]["future_masked"], 1)
        self.assertNotIn("later revision", str(frame))

    def test_latest_revision_known_before_cutoff_wins(self):
        first = record("R1", "gdp", "2026-09-20T12:00:00+00:00", payload={"value": 1})
        second = record("R2", "gdp", "2026-09-20T13:30:00+00:00", payload={"value": 2})
        frame = build_replay_frame([first, second], replay_at=CUT)
        self.assertEqual(frame["visible_records"][0]["record_id"], "R2")
        self.assertEqual(frame["counts"]["superseded"], 1)

    def test_frame_digest_is_deterministic_and_input_order_independent(self):
        a = record("R1", "a", "2026-09-20T12:00:00+00:00")
        b = record("R2", "b", "2026-09-20T13:00:00+00:00")
        one = build_replay_frame([a, b], replay_at=CUT)
        two = build_replay_frame([b, a], replay_at=CUT)
        self.assertEqual(one["frame_digest"], two["frame_digest"])
        self.assertEqual(one["visible_records"], two["visible_records"])

    def test_duplicate_record_id_is_fail_closed_for_duplicate_row(self):
        a = record("R1", "a", "2026-09-20T12:00:00+00:00")
        b = record("R1", "b", "2026-09-20T13:00:00+00:00")
        frame = build_replay_frame([a, b], replay_at=CUT)
        self.assertEqual(frame["counts"]["visible"], 1)
        self.assertEqual(frame["counts"]["invalid"], 1)
        self.assertEqual(frame["invalid_records"][0]["reason"], "DUPLICATE_RECORD_ID")
        self.assertEqual(frame["state"], "PARTIAL")

    def test_secret_key_blocks_entire_frame_without_echo(self):
        raw = record("R1", "x", "2026-09-20T12:00:00+00:00")
        raw["payload"] = {"api_key": "do-not-echo"}
        frame = build_replay_frame([raw], replay_at=CUT)
        self.assertEqual(frame["state"], "BLOCKED")
        self.assertEqual(frame["reason"], "SECRET_MATERIAL_REJECTED")
        self.assertNotIn("do-not-echo", str(frame))

    def test_secret_value_inside_normal_field_blocks_frame(self):
        raw = record(
            "R1",
            "x",
            "2026-09-20T12:00:00+00:00",
            label="token=abc123",
        )
        frame = build_replay_frame([raw], replay_at=CUT)
        self.assertEqual(frame["state"], "BLOCKED")
        self.assertNotIn("abc123", str(frame))

    def test_too_many_records_is_blocked(self):
        rows = [
            record(
                f"R{i}",
                f"k{i}",
                "2026-09-20T12:00:00+00:00",
            )
            for i in range(1001)
        ]
        frame = build_replay_frame(rows, replay_at=CUT)
        self.assertEqual(frame["state"], "BLOCKED")
        self.assertEqual(frame["reason"], "TOO_MANY_RECORDS")

    def test_start_session_is_training_only_and_no_live_actions(self):
        session = start_replay_session(
            scenario_id="S1",
            title="Historical decision",
            domain="admin",
            mode="DECISION_REVIEW",
            replay_at=CUT,
            records=[record("R1", "x", "2026-09-20T12:00:00+00:00")],
        )
        self.assertEqual(session["state"], "ACTIVE")
        self.assertTrue(session["training_only"])
        self.assertFalse(session["live_data_used"])
        self.assertFalse(session["execution_authorized"])
        self.assertFalse(session["executes_action"])
        self.assertFalse(session["real_trading_enabled"])
        self.assertFalse(session["automatic_promotion"])

    def test_missing_scenario_identity_blocks_session(self):
        session = start_replay_session(
            scenario_id="",
            title="Replay",
            domain="admin",
            mode="GENERAL",
            replay_at=CUT,
            records=[],
        )
        self.assertEqual(session["state"], "BLOCKED")

    def test_tampered_session_cannot_preserve_execution_flags_on_error(self):
        session = {
            "state": "REVEALED",
            "training_only": False,
            "live_data_used": True,
            "future_evidence_exposed": True,
            "automatic_promotion": True,
            "execution_authorized": True,
            "executes_action": True,
            "real_trading_enabled": True,
        }
        out = submit_replay_decision(
            session,
            choice="WAIT",
            submitted_at="2026-09-20T14:05:00+00:00",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertFalse(out["live_data_used"])
        self.assertFalse(out["future_evidence_exposed"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["execution_authorized"])
        self.assertFalse(out["executes_action"])
        self.assertFalse(out["real_trading_enabled"])
        self.assertTrue(out["training_only"])

    def test_decision_requires_active_session(self):
        session = start_replay_session(
            scenario_id="S1",
            title="Replay",
            domain="admin",
            mode="GENERAL",
            replay_at=CUT,
            records=[],
        )
        session["state"] = "REVEALED"
        out = submit_replay_decision(
            session,
            choice="A",
            submitted_at="2026-09-20T14:05:00+00:00",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertEqual(out["reason"], "SESSION_NOT_ACTIVE")

    def test_decision_before_replay_cutoff_is_blocked(self):
        session = start_replay_session(
            scenario_id="S1",
            title="Replay",
            domain="admin",
            mode="GENERAL",
            replay_at=CUT,
            records=[],
        )
        out = submit_replay_decision(
            session,
            choice="WAIT",
            submitted_at="2026-09-20T13:59:00+00:00",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertEqual(out["reason"], "DECISION_BEFORE_REPLAY_CUTOFF")

    def test_decision_confidence_is_descriptive_not_profit_probability(self):
        session = start_replay_session(
            scenario_id="S1",
            title="Replay",
            domain="admin",
            mode="GENERAL",
            replay_at=CUT,
            records=[],
        )
        out = submit_replay_decision(
            session,
            choice="WAIT",
            rationale="Evidence incomplete",
            confidence_pct=70,
            submitted_at="2026-09-20T14:05:00+00:00",
        )
        self.assertEqual(out["state"], "DECISION_RECORDED")
        self.assertEqual(out["decision"]["confidence_pct"], 70.0)
        self.assertEqual(
            out["decision"]["confidence_meaning"],
            "TRAINEE_SELF_CONFIDENCE_NOT_PROFIT_PROBABILITY",
        )
        self.assertFalse(out["real_trading_enabled"])

    def test_invalid_confidence_fails_closed(self):
        session = start_replay_session(
            scenario_id="S1",
            title="Replay",
            domain="admin",
            mode="GENERAL",
            replay_at=CUT,
            records=[],
        )
        out = submit_replay_decision(
            session,
            choice="WAIT",
            confidence_pct=101,
            submitted_at="2026-09-20T14:05:00+00:00",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertEqual(out["reason"], "CONFIDENCE_INVALID")

    def test_tampered_session_cannot_preserve_execution_flags_on_reveal_error(self):
        session = {
            "state": "ACTIVE",
            "training_only": False,
            "live_data_used": True,
            "future_evidence_exposed": True,
            "automatic_promotion": True,
            "execution_authorized": True,
            "executes_action": True,
            "real_trading_enabled": True,
        }
        out = reveal_replay_outcome(
            session,
            outcome={"expected_decision": "WAIT"},
            available_at="2026-09-20T15:00:00+00:00",
            revealed_at="2026-09-20T15:00:00+00:00",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertFalse(out["execution_authorized"])
        self.assertFalse(out["executes_action"])
        self.assertFalse(out["real_trading_enabled"])
        self.assertTrue(out["training_only"])

    def test_outcome_cannot_be_revealed_before_decision(self):
        session = start_replay_session(
            scenario_id="S1",
            title="Replay",
            domain="admin",
            mode="GENERAL",
            replay_at=CUT,
            records=[],
        )
        out = reveal_replay_outcome(
            session,
            outcome={"expected_decision": "WAIT"},
            available_at="2026-09-20T15:00:00+00:00",
            revealed_at="2026-09-20T15:00:00+00:00",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertEqual(out["reason"], "DECISION_REQUIRED_BEFORE_REVEAL")

    def test_outcome_already_available_at_replay_invalidates_scenario(self):
        session = start_replay_session(
            scenario_id="S1",
            title="Replay",
            domain="admin",
            mode="GENERAL",
            replay_at=CUT,
            records=[],
        )
        decided = submit_replay_decision(
            session,
            choice="WAIT",
            submitted_at="2026-09-20T14:05:00+00:00",
        )
        out = reveal_replay_outcome(
            decided,
            outcome={"expected_decision": "WAIT"},
            available_at="2026-09-20T13:59:00+00:00",
            revealed_at="2026-09-20T15:00:00+00:00",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertEqual(out["reason"], "OUTCOME_WAS_AVAILABLE_AT_REPLAY")

    def test_outcome_cannot_be_revealed_before_it_becomes_available(self):
        session = start_replay_session(
            scenario_id="S1",
            title="Replay",
            domain="admin",
            mode="GENERAL",
            replay_at=CUT,
            records=[],
        )
        decided = submit_replay_decision(
            session,
            choice="WAIT",
            submitted_at="2026-09-20T14:05:00+00:00",
        )
        out = reveal_replay_outcome(
            decided,
            outcome={"expected_decision": "WAIT"},
            available_at="2026-09-20T16:00:00+00:00",
            revealed_at="2026-09-20T15:00:00+00:00",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertEqual(out["reason"], "OUTCOME_NOT_YET_AVAILABLE")

    def test_revealed_match_does_not_infer_decision_quality(self):
        session = start_replay_session(
            scenario_id="S1",
            title="Replay",
            domain="admin",
            mode="GENERAL",
            replay_at=CUT,
            records=[],
        )
        decided = submit_replay_decision(
            session,
            choice="WAIT",
            confidence_pct=80,
            submitted_at="2026-09-20T14:05:00+00:00",
        )
        out = reveal_replay_outcome(
            decided,
            outcome={
                "expected_decision": "WAIT",
                "actual_result": "later observation",
            },
            available_at="2026-09-20T15:00:00+00:00",
            revealed_at="2026-09-20T15:01:00+00:00",
        )
        self.assertEqual(out["state"], "REVEALED")
        self.assertEqual(out["evaluation"], "MATCH")
        self.assertFalse(out["decision_quality_inferred"])
        self.assertEqual(
            out["evaluation_meaning"],
            "DESCRIPTIVE_TRAINING_COMPARISON_NOT_PROFIT_PROBABILITY",
        )
        self.assertFalse(out["automatic_promotion"])

    def test_revealed_mismatch_also_does_not_infer_bad_decision(self):
        session = start_replay_session(
            scenario_id="S1",
            title="Replay",
            domain="admin",
            mode="GENERAL",
            replay_at=CUT,
            records=[],
        )
        decided = submit_replay_decision(
            session,
            choice="BUY",
            submitted_at="2026-09-20T14:05:00+00:00",
        )
        out = reveal_replay_outcome(
            decided,
            outcome={"expected_decision": "SELL"},
            available_at="2026-09-20T15:00:00+00:00",
            revealed_at="2026-09-20T15:01:00+00:00",
        )
        self.assertEqual(out["evaluation"], "MISMATCH")
        self.assertFalse(out["decision_quality_inferred"])
        self.assertFalse(out["real_trading_enabled"])

    def test_compact_rows_only_contain_visible_evidence(self):
        visible = record("R1", "x", "2026-09-20T12:00:00+00:00", label="known")
        future = record("R2", "y", "2026-09-20T15:00:00+00:00", label="future")
        frame = build_replay_frame([visible, future], replay_at=CUT)
        rows = compact_replay_rows(frame)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Evidência"], "known")
        self.assertNotIn("future", str(rows))


if __name__ == "__main__":
    unittest.main()
