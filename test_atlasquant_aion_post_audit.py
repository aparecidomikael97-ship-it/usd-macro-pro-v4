"""Regressions for the independent audit of PR #250.

Each test pins one confirmed blocker so the previous behavior cannot return.
"""
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from atlasquant_aion_continuity import (
    MissionTransitionError,
    new_mission,
    prepare_mission_transition,
    transition_mission,
)
from atlasquant_aion_durable_tasks import (
    new_durable_task,
    prepare_resume,
    record_resume,
)
from atlasquant_aion_memory import (
    checkpoint_integrity_report,
    default_checkpoint,
    ensure_operating_checkpoint,
    update_continuity_checkpoint,
    update_durable_tasks_checkpoint,
    update_operating_checkpoint,
)
from atlasquant_aion_memory_layers import recall, remember
from atlasquant_aion_observability import (
    events_digest,
    is_secret_key,
    new_event,
    normalize_event,
    sanitize_metadata,
)
from atlasquant_aion_orchestrator import (
    build_aion_result,
    classify_external_action_claim,
    orchestrate,
    present_validated_answer,
    validate_specialist_result,
    validation_truth_status,
)
from atlasquant_aion_persona_memory import append_persona_entry
from atlasquant_aion_specialist_evidence import read_specialist_evidence
from atlasquant_aion_specialist_session import (
    SCHEMA as SNAPSHOT_SCHEMA,
    build_specialist_session_snapshot,
)
from atlasquant_aion_truth import FUTURE_TOLERANCE_SECONDS, assess_truth
from atlasquant_fx_universe import OFFICIAL_PAIRS


NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
FRESH_AT = NOW.isoformat()
STALE_AT = datetime.fromtimestamp(1_000, tz=timezone.utc).isoformat()
SECRET_VALUES = {
    "cookie": "COOKIE_VALUE_9f3a",
    "token": "TOKEN_VALUE_9f3a",
    "api_key": "APIKEY_VALUE_9f3a",
    "password": "PASSWORD_VALUE_9f3a",
    "authorization": "AUTHORIZATION_VALUE_9f3a",
    "bearer": "BEARER_VALUE_9f3a",
    "access_token": "ACCESS_TOKEN_VALUE_9f3a",
    "refresh_token": "REFRESH_TOKEN_VALUE_9f3a",
    "github_token": "GITHUB_TOKEN_VALUE_9f3a",
}
COMPOUND_SECRET_VALUES = {
    "client_secret": "CLIENT_SECRET_VALUE_9f3a",
    "private_key": "PRIVATE_KEY_VALUE_9f3a",
    "secret_key": "SECRET_KEY_VALUE_9f3a",
    "session_token": "SESSION_TOKEN_VALUE_9f3a",
    "auth_token": "AUTH_TOKEN_VALUE_9f3a",
    "x_api_key": "X_API_KEY_VALUE_9f3a",
    "access_key": "ACCESS_KEY_VALUE_9f3a",
    "client_token": "CLIENT_TOKEN_VALUE_9f3a",
}


def _fresh_claim(claim, value, **extra):
    row = {
        "claim": claim,
        "truth_state": "CONFIRMED",
        "value": value,
        "source": extra.pop("source", "official"),
        "timestamp": FRESH_AT,
        "ttl_seconds": 3600,
        "time_sensitive": True,
    }
    row.update(extra)
    return row


def _complete_result(ts=10_000.0):
    return {
        "processado_em": ts,
        "source": "Twelve Data",
        "tecnico": {
            "disponivel": True,
            "h4": {"status": "BUY"},
            "h1": {"status": "BUY"},
            "m15": {"status": "WAIT"},
        },
    }


def _ranking(observed_at, ttl):
    return {
        "origin": "RADAR",
        "observed_at": observed_at,
        "ttl_seconds": ttl,
        "ranking": [
            {"pair": pair, "data_ready": True, "score": index}
            for index, pair in enumerate(OFFICIAL_PAIRS[:10])
        ],
    }


class StructuredSnapshotSecretTests(unittest.TestCase):
    def test_structured_snapshot_is_sanitized_at_every_depth(self):
        raw = {
            "schema": SNAPSHOT_SCHEMA,
            "origin": "SESSION",
            "observed_at": FRESH_AT,
            "ttl_seconds": 3600,
            "secrets_included": False,
            "cookie": SECRET_VALUES["cookie"],
            "authorization": SECRET_VALUES["authorization"],
            "slices": {
                "scanner": {
                    "present": True,
                    "origin": "PERSISTED_SCANNER",
                    "observed_at": FRESH_AT,
                    "ttl_seconds": 3600,
                    "token": SECRET_VALUES["token"],
                    "payload": {
                        "pair": "EUR/USD",
                        "api_key": SECRET_VALUES["api_key"],
                        "nested": {
                            "password": SECRET_VALUES["password"],
                            "rows": [
                                {
                                    "bearer": SECRET_VALUES["bearer"],
                                    "note": "token=" + SECRET_VALUES["token"],
                                }
                            ],
                        },
                    },
                },
                "radar": {
                    "present": True,
                    "origin": "RADAR",
                    "observed_at": FRESH_AT,
                    "ttl_seconds": 3600,
                    "access_token": SECRET_VALUES["access_token"],
                    "refresh_token": SECRET_VALUES["refresh_token"],
                    "github_token": SECRET_VALUES["github_token"],
                    "payload": {"ranking": [], "password": SECRET_VALUES["password"]},
                },
            },
        }
        cleaned = build_specialist_session_snapshot(raw, now=NOW)
        blob = json.dumps(cleaned, ensure_ascii=False)
        for value in SECRET_VALUES.values():
            self.assertNotIn(value, blob)
        self.assertEqual(cleaned["schema"], SNAPSHOT_SCHEMA)
        self.assertEqual(cleaned["origin"], "SESSION")
        self.assertEqual(cleaned["observed_at"], FRESH_AT)
        self.assertEqual(cleaned["ttl_seconds"], 3600)
        self.assertFalse(cleaned["secrets_included"])
        self.assertFalse(cleaned["network_called"])
        scanner = cleaned["slices"]["scanner"]
        self.assertEqual(scanner["origin"], "PERSISTED_SCANNER")
        self.assertEqual(scanner["payload"]["pair"], "EUR/USD")
        self.assertNotIn("api_key", scanner["payload"])
        self.assertNotIn("password", scanner["payload"]["nested"])
        self.assertNotIn("cookie", cleaned)
        self.assertNotIn("github_token", cleaned["slices"]["radar"])

    def test_compound_secret_names_are_removed_at_every_depth(self):
        raw = {
            "schema": SNAPSHOT_SCHEMA,
            "origin": "SESSION",
            "observed_at": FRESH_AT,
            "ttl_seconds": 3600,
            "secrets_included": False,
            "primary_key": "EURUSD",
            "session_id": "public-session",
            **COMPOUND_SECRET_VALUES,
            "slices": {
                "scanner": {
                    "present": True,
                    "origin": "PERSISTED_SCANNER",
                    "observed_at": FRESH_AT,
                    "ttl_seconds": 3600,
                    "payload": {
                        "pair": "EUR/USD",
                        "primary_key": "EURUSD",
                        "session_id": "public-session",
                        "nested": {
                            **COMPOUND_SECRET_VALUES,
                            "rows": [{
                                "pair": "GBP/USD",
                                "primary_key": "GBPUSD",
                                **COMPOUND_SECRET_VALUES,
                            }],
                        },
                    },
                },
            },
        }
        cleaned = build_specialist_session_snapshot(raw, now=NOW)
        blob = json.dumps(cleaned, ensure_ascii=False)
        for value in COMPOUND_SECRET_VALUES.values():
            self.assertNotIn(value, blob)
        for key in COMPOUND_SECRET_VALUES:
            self.assertNotIn(key, blob)
            self.assertTrue(is_secret_key(key))
        self.assertEqual(cleaned["primary_key"], "EURUSD")
        self.assertEqual(cleaned["session_id"], "public-session")
        payload = cleaned["slices"]["scanner"]["payload"]
        self.assertEqual(payload["pair"], "EUR/USD")
        self.assertEqual(payload["primary_key"], "EURUSD")
        self.assertEqual(payload["nested"]["rows"][0]["pair"], "GBP/USD")
        self.assertEqual(payload["nested"]["rows"][0]["primary_key"], "GBPUSD")
        redacted = sanitize_metadata({
            "primary_key": "EURUSD",
            "session_id": "public-session",
            "nested": {"rows": [dict(COMPOUND_SECRET_VALUES)]},
            **COMPOUND_SECRET_VALUES,
        })
        redacted_blob = json.dumps(redacted, ensure_ascii=False)
        for value in COMPOUND_SECRET_VALUES.values():
            self.assertNotIn(value, redacted_blob)
        self.assertEqual(redacted["primary_key"], "EURUSD")
        self.assertEqual(redacted["session_id"], "public-session")
        self.assertFalse(is_secret_key("primary_key"))
        self.assertFalse(is_secret_key("session_id"))
        self.assertFalse(is_secret_key("pair"))


class TemporalValidityTests(unittest.TestCase):
    def test_expired_valid_until_is_not_recalled_as_current_confirmed(self):
        past = (NOW - timedelta(days=1)).isoformat()
        future = (NOW + timedelta(days=1)).isoformat()
        memory = remember(
            None,
            layer="project",
            content="Fato que já expirou",
            origin="audit",
            category="temporal",
            truth_state="CONFIRMED",
            valid_until=past,
            memory_key="audit:expired",
        )
        memory = remember(
            memory,
            layer="project",
            content="Fato ainda vigente",
            origin="audit",
            category="temporal",
            truth_state="CONFIRMED",
            valid_until=future,
            memory_key="audit:current",
        )
        stored = [dict(row) for row in memory["entries"]]
        active = recall(memory, now=NOW)
        self.assertEqual([row["content"] for row in active], ["Fato ainda vigente"])
        self.assertEqual(active[0]["status"], "ACTIVE")
        self.assertEqual(active[0]["truth_state"], "CONFIRMED")
        expired = recall(memory, now=NOW, include_expired=True)
        old = next(row for row in expired if row["content"] == "Fato que já expirou")
        self.assertEqual(old["status"], "EXPIRED")
        self.assertEqual(old["truth_state"], "UNKNOWN")
        self.assertEqual(memory["entries"], stored)
        self.assertEqual(memory["entries"][0]["status"], "ACTIVE")
        self.assertEqual(memory["entries"][0]["truth_state"], "CONFIRMED")

    def test_truth_does_not_confirm_unproven_or_future_temporal_evidence(self):
        future = assess_truth([_fresh_claim(
            "cpi", 2, timestamp=(NOW + timedelta(minutes=10)).isoformat(),
        )], now=NOW)
        self.assertNotEqual(future["status"], "CONFIRMED")
        self.assertNotEqual(future["freshness"], "FRESH")
        self.assertIn("TIMESTAMP_IN_FUTURE", future["records"][0]["issues"])

        skew = assess_truth([_fresh_claim(
            "cpi", 2, timestamp=(NOW + timedelta(seconds=FUTURE_TOLERANCE_SECONDS - 5)).isoformat(),
        )], now=NOW)
        self.assertEqual(skew["status"], "CONFIRMED")
        self.assertEqual(skew["freshness"], "FRESH")

        missing_ttl = assess_truth([{
            "claim": "cpi",
            "truth_state": "CONFIRMED",
            "value": 2,
            "source": "official",
            "timestamp": FRESH_AT,
            "time_sensitive": True,
        }], now=NOW)
        self.assertEqual(missing_ttl["status"], "UNKNOWN")
        self.assertIn("TTL_MISSING", missing_ttl["records"][0]["issues"])
        self.assertNotEqual(missing_ttl["freshness"], "FRESH")

        unknown_clock = assess_truth([{
            "claim": "cpi",
            "truth_state": "CONFIRMED",
            "value": 2,
            "source": "official",
            "timestamp": FRESH_AT,
        }], now=NOW)
        self.assertEqual(unknown_clock["status"], "UNKNOWN")
        self.assertIn("FRESHNESS_UNPROVEN", unknown_clock["records"][0]["issues"])

        fresh = assess_truth([_fresh_claim("cpi", 2)], now=NOW)
        self.assertEqual(fresh["status"], "CONFIRMED")
        self.assertEqual(fresh["freshness"], "FRESH")

        expired = assess_truth([_fresh_claim(
            "cpi", 2, timestamp=(NOW - timedelta(hours=3)).isoformat(), ttl_seconds=60,
        )], now=NOW)
        self.assertEqual(expired["freshness"], "STALE")
        self.assertEqual(expired["status"], "UNKNOWN")
        self.assertIn("DATA_STALE", expired["records"][0]["issues"])

        canonical = assess_truth([{
            "claim": "architecture",
            "truth_state": "CONFIRMED",
            "value": "documented",
            "source": "docs/aion/ARCHITECTURE.md",
            "time_sensitive": False,
        }], now=NOW)
        self.assertEqual(canonical["status"], "CONFIRMED")
        self.assertEqual(canonical["records"][0]["freshness"], "NOT_APPLICABLE")
        self.assertNotIn("TTL_MISSING", canonical["records"][0]["issues"])


class TruthConflictIdentityTests(unittest.TestCase):
    def test_different_claims_are_not_a_conflict(self):
        out = assess_truth([
            _fresh_claim("cpi", 2, source="official-a"),
            _fresh_claim("rate", 5, source="official-b"),
        ], now=NOW)
        self.assertEqual(out["conflict_state"], "NONE")
        self.assertEqual(out["status"], "CONFIRMED")
        self.assertEqual(out["conflict_claims"], [])

    def test_same_claim_with_divergent_values_stays_conflict(self):
        out = assess_truth([
            _fresh_claim("cpi", 2, source="official-a"),
            _fresh_claim("cpi", 3, source="official-b"),
        ], now=NOW)
        self.assertEqual(out["conflict_state"], "CONFLICT")
        self.assertEqual(out["status"], "UNKNOWN")
        self.assertEqual(out["conflict_claims"], ["cpi"])

    def test_same_claim_and_same_value_from_two_sources_is_not_conflict(self):
        out = assess_truth([
            _fresh_claim("cpi", 2, source="official-a"),
            _fresh_claim("cpi", 2, source="official-b"),
        ], now=NOW)
        self.assertEqual(out["conflict_state"], "NONE")
        self.assertEqual(out["status"], "CONFIRMED")

    def test_three_sources_and_two_values_keep_the_conflict(self):
        out = assess_truth([
            _fresh_claim("cpi", 2, source="official-a"),
            _fresh_claim("cpi", 2, source="official-b"),
            _fresh_claim("cpi", 3, source="official-c"),
        ], now=NOW)
        self.assertEqual(out["conflict_state"], "CONFLICT")
        self.assertEqual(out["conflict_claims"], ["cpi"])
        self.assertEqual(out["status"], "UNKNOWN")
        self.assertNotIn("chosen", out)


MARKET_NOW = datetime.fromtimestamp(10_000, tz=timezone.utc)
MARKET_FRESH = MARKET_NOW.isoformat()


class IndependentMarketClockTests(unittest.TestCase):
    def test_fresh_scanner_does_not_revive_stale_radar_ranking(self):
        reading = read_specialist_evidence(
            "market",
            session={
                "origin": "PERSISTED_SCANNER",
                "observed_at": MARKET_FRESH,
                "ttl_seconds": 3600,
                "scanner": {"persisted_results": {"EUR/USD": _complete_result()}},
                "radar": _ranking(STALE_AT, 60),
            },
            now=MARKET_NOW,
        )
        self.assertEqual(reading["input_state"], "VALID")
        self.assertEqual(reading["freshness"], "FRESH")
        self.assertEqual(reading["answer_truth"], "CONFIRMED")
        self.assertTrue(reading["observations"]["scanner_clock_current"])
        self.assertFalse(reading["observations"]["radar_clock_current"])
        self.assertEqual(reading["observations"]["observed_pairs"][0]["pair"], "EUR/USD")
        self.assertFalse(reading["observations"]["ranking_valid"])
        self.assertNotIn("top_10", reading["observations"])
        self.assertNotIn("observed_ranking", reading["observations"])

    def test_fresh_radar_does_not_revive_stale_scanner(self):
        reading = read_specialist_evidence(
            "market",
            session={
                "origin": "PERSISTED_SCANNER",
                "observed_at": STALE_AT,
                "ttl_seconds": 60,
                "scanner": {
                    "observed_at": STALE_AT,
                    "ttl_seconds": 60,
                    "persisted_results": {"EUR/USD": _complete_result(ts=1_000)},
                },
                "radar": _ranking(MARKET_FRESH, 3600),
            },
            now=MARKET_NOW,
        )
        self.assertEqual(reading["input_state"], "VALID")
        self.assertEqual(reading["freshness"], "FRESH")
        self.assertFalse(reading["observations"]["scanner_clock_current"])
        self.assertTrue(reading["observations"]["radar_clock_current"])
        self.assertEqual(reading["observations"]["observed_pairs"], [])
        self.assertEqual(reading["observations"]["top_10"], list(OFFICIAL_PAIRS[:10]))
        self.assertTrue(reading["observations"]["ranking_valid"])
        self.assertNotIn("BUY", reading["summary"])


class MissionCallerContractTests(unittest.TestCase):
    def _mission(self, *statuses):
        mission = new_mission("Auditoria", created_at=FRESH_AT)
        rows = [mission]
        for status in statuses:
            rows = transition_mission(rows, mission["mission_id"], status, changed_at=FRESH_AT)
        return rows

    def test_waiting_approval_requires_explicit_approval(self):
        rows = self._mission("WAITING_APPROVAL")
        with self.assertRaises(MissionTransitionError) as caught:
            prepare_mission_transition("WAITING_APPROVAL", "IN_PROGRESS", approved=False)
        self.assertEqual(str(caught.exception), "MISSION_APPROVAL_REQUIRED")
        self.assertEqual(rows[0]["status"], "WAITING_APPROVAL")

        prepared = prepare_mission_transition(
            "WAITING_APPROVAL",
            "IN_PROGRESS",
            approved=True,
            actor="admin.test",
            changed_at=FRESH_AT,
            evidence_refs=["doc-1"],
            mission_id=rows[0]["mission_id"],
        )
        self.assertTrue(prepared["approved"])
        self.assertEqual(prepared["unblock_reason"], "")
        self.assertEqual(prepared["audit_refs"], [f"aprovacao:admin.test@{FRESH_AT}"])
        self.assertFalse(prepared["executes_action"])
        updated = transition_mission(
            rows,
            rows[0]["mission_id"],
            "IN_PROGRESS",
            approved=prepared["approved"],
            unblock_reason=prepared["unblock_reason"],
            evidence_refs=prepared["evidence_refs"],
            changed_at=prepared["changed_at"],
        )
        self.assertEqual(updated[0]["status"], "IN_PROGRESS")
        self.assertIn(f"aprovacao:admin.test@{FRESH_AT}", updated[0]["evidence_refs"])

    def test_blocked_requires_explicit_unblock_reason(self):
        rows = self._mission("BLOCKED")
        with self.assertRaises(MissionTransitionError) as caught:
            prepare_mission_transition("BLOCKED", "IN_PROGRESS", unblock_reason="   ")
        self.assertEqual(str(caught.exception), "MISSION_UNBLOCK_REQUIRED")
        prepared = prepare_mission_transition(
            "BLOCKED",
            "IN_PROGRESS",
            unblock_reason="revisão humana concluída",
            actor="admin.test",
            changed_at=FRESH_AT,
            mission_id=rows[0]["mission_id"],
        )
        self.assertFalse(prepared["approved"])
        self.assertEqual(prepared["unblock_reason"], "revisão humana concluída")
        updated = transition_mission(
            rows,
            rows[0]["mission_id"],
            "IN_PROGRESS",
            approved=prepared["approved"],
            unblock_reason=prepared["unblock_reason"],
            evidence_refs=prepared["evidence_refs"],
            changed_at=prepared["changed_at"],
        )
        self.assertEqual(updated[0]["status"], "IN_PROGRESS")
        self.assertIn("desbloqueio:admin.test:revisão humana concluída", updated[0]["evidence_refs"])

    def test_terminal_mission_does_not_reopen(self):
        rows = self._mission("IN_PROGRESS", "DONE")
        with self.assertRaises(MissionTransitionError) as caught:
            prepare_mission_transition(
                "DONE",
                "IN_PROGRESS",
                approved=True,
                unblock_reason="reabrir",
            )
        self.assertEqual(str(caught.exception), "INVALID_MISSION_TRANSITION")
        self.assertEqual(rows[0]["status"], "DONE")

    def test_admin_form_wires_explicit_approval_without_hardcoding_it(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        form = source.split("Missões persistentes", 1)[1].split("Tool Hub / MCP", 1)[0]
        self.assertIn("prepare_mission_transition(", form)
        self.assertIn("Aprovo explicitamente a retomada desta missão", form)
        self.assertIn("Motivo do desbloqueio", form)
        self.assertIn('approved=prepared["approved"]', form)
        self.assertIn('unblock_reason=prepared["unblock_reason"]', form)
        self.assertNotIn("approved=True", form)
        self.assertIn('"actor":prepared["actor"]', form)
        self.assertIn('"changed_at":prepared["changed_at"]', form)


class ResultValidationPresentationTests(unittest.TestCase):
    def test_pass_revise_and_block_follow_the_truth_contract(self):
        preflight = orchestrate("Explique a arquitetura", context={"role": "ADMIN"})
        passed = build_aion_result(
            preflight,
            answer="A arquitetura está documentada.",
            evidence=[{
                "claim": "architecture",
                "value": "documented",
                "truth_state": "CONFIRMED",
                "source": "docs/aion/ARCHITECTURE.md",
                "time_sensitive": False,
            }],
        )
        self.assertEqual(passed["status"], "PASS")
        self.assertEqual(validation_truth_status(passed["validation"]), "CONFIRMED")
        self.assertNotIn("truth_state", passed["validation"])
        self.assertEqual(passed["validation"]["truth"]["status"], "CONFIRMED")
        self.assertEqual(passed["external_action_claim_state"], "NOT_ASSERTED")
        self.assertIs(passed["claims_external_action"], False)
        shown = present_validated_answer(passed["validation"])
        self.assertEqual(shown["display"], "ANSWER")
        self.assertIn("documentada", shown["text"])
        self.assertTrue(shown["validated"])

        revised = validate_specialist_result(preflight, {"response": "Sem fonte"})
        self.assertEqual(revised["state"], "REVISE")
        hidden = present_validated_answer(revised, answer="Sem fonte")
        self.assertEqual(hidden["text"], "")
        self.assertFalse(hidden["validated"])
        self.assertIn("Revisão necessária", hidden["notice"])

        blocked = build_aion_result(
            preflight,
            answer="A ordem real executada foi enviada ao broker.",
            evidence=[{
                "claim": "architecture",
                "value": "documented",
                "truth_state": "CONFIRMED",
                "source": "docs/aion/ARCHITECTURE.md",
                "time_sensitive": False,
            }],
        )
        self.assertEqual(blocked["status"], "BLOCK")
        self.assertEqual(blocked["external_action_claim_state"], "ASSERTED")
        self.assertIs(blocked["claims_external_action"], True)
        self.assertIn("ACTION_CLAIM_WITHOUT_EVIDENCE", blocked["validation"]["issues"])
        presentation = blocked["answer_presentation"]
        self.assertEqual(presentation["display"], "BLOCK")
        self.assertEqual(presentation["text"], "")
        self.assertNotIn("broker", presentation["text"])
        self.assertFalse(presentation["validated"])
        self.assertFalse(presentation["executes_action"])
        self.assertFalse(blocked["external_action_executed"])
        self.assertFalse(blocked["real_orders_enabled"])

    def test_external_action_claim_is_not_asserted_without_a_scan(self):
        self.assertEqual(classify_external_action_claim({"opaque": True}), "UNKNOWN")
        unknown = validate_specialist_result(
            {"task": {"task_id": "t"}},
            {"response": {"opaque": True}, "evidence": []},
        )
        self.assertEqual(unknown["external_action_claim_state"], "UNKNOWN")
        self.assertIsNone(unknown["claims_external_action"])
        self.assertEqual(unknown["state"], "REVISE")
        self.assertIn("EXTERNAL_ACTION_CLAIM_UNVERIFIED", unknown["issues"])
        self.assertNotIn("ACTION_CLAIM_WITHOUT_EVIDENCE", unknown["issues"])

        denied = validate_specialist_result(
            {"task": {"task_id": "t"}},
            {
                "response": "Nenhuma ação externa foi confirmada.",
                "evidence": [{"claim": "real_trade", "value": False, "truth_state": "CONFIRMED", "source": "guardian"}],
            },
        )
        self.assertEqual(denied["external_action_claim_state"], "NOT_ASSERTED")
        self.assertFalse(denied["executes_action"])

    def test_admin_reads_truth_status_and_hides_unvalidated_answers(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        block = source.split("#### Resposta AION", 1)[1].split("#### Secretaria", 1)[0]
        self.assertIn("present_validated_answer(", block)
        self.assertLess(block.index("present_validated_answer("), block.index("st.write("))
        self.assertNotIn("st.write(str(answer.get(\"answer\"", block)
        self.assertNotIn("validation.get('truth_state'", block)
        self.assertNotIn('validation.get("truth_state"', block)
        self.assertIn("presentation['truth_status']", block)


class HistoricalCheckpointMigrationTests(unittest.TestCase):
    def test_v17_checkpoint_migrates_without_loss_or_false_mismatch(self):
        mission = new_mission("Missão histórica", created_at=FRESH_AT)
        checkpoint = update_continuity_checkpoint(default_checkpoint(), missions=[mission])
        task = new_durable_task(
            "Tarefa histórica",
            mission_id=mission["mission_id"],
            steps=[{
                "step_id": "s1",
                "title": "Inspecionar",
                "evidence_refs": ["evidence://legacy-step"],
                "artifact_refs": ["artifact://legacy-step"],
            }],
            checkpoint_digest="cp-v17",
            created_at=FRESH_AT,
        )
        task["artifacts"] = ["artifact://legacy-task"]
        task["evidence_refs"] = ["evidence://legacy-task"]
        correlation = task["correlation_id"]
        checkpoint = update_durable_tasks_checkpoint(checkpoint, records=[task])
        legacy_event = new_event(
            "legacy_note",
            "evento histórico não vazio",
            evidence={"note": "preservado"},
            created_at=FRESH_AT,
        )
        self.assertEqual(normalize_event(legacy_event), legacy_event)
        checkpoint = update_operating_checkpoint(checkpoint, events=[legacy_event])
        checkpoint["persona_memory"] = append_persona_entry(
            checkpoint["persona_memory"],
            "developer",
            kind="checkpoint",
            message="nota histórica da persona",
            truth_state="UNKNOWN",
            source="v17",
        )
        legacy = json.loads(json.dumps(checkpoint))
        legacy["checkpoint_version"] = 17
        legacy.pop("memory_layers")
        before_events = events_digest(legacy["operating"]["events"])
        report = checkpoint_integrity_report(legacy)
        self.assertEqual(report["state"], "MIGRATION_REQUIRED")
        self.assertEqual(report["mismatches"], [])
        self.assertIn("memory_layers ausente", report["migration_items"])
        self.assertTrue(any("checkpoint_version 17 < 18" in item for item in report["migration_items"]))

        upgraded = ensure_operating_checkpoint(legacy)
        self.assertEqual(legacy["checkpoint_version"], 17)
        self.assertEqual(upgraded["checkpoint_version"], 18)
        self.assertEqual(upgraded["memory_layers"]["schema"], "ATLASQUANT_AION_MEMORY_LAYERS_V1")
        self.assertEqual(events_digest(upgraded["operating"]["events"]), before_events)
        self.assertEqual(upgraded["operating"]["events"][0]["event_id"], legacy_event["event_id"])
        self.assertEqual(normalize_event(upgraded["operating"]["events"][0]), legacy_event)
        restored = upgraded["durable_tasks"]["records"][0]
        self.assertEqual(restored["durable_task_id"], task["durable_task_id"])
        self.assertEqual(restored["state"], "PLANNED")
        self.assertEqual(restored["steps"][0]["step_id"], "s1")
        self.assertEqual(restored["steps"][0]["evidence_refs"], ["evidence://legacy-step"])
        self.assertEqual(restored["steps"][0]["artifact_refs"], ["artifact://legacy-step"])
        self.assertEqual(restored["artifacts"], ["artifact://legacy-task"])
        self.assertEqual(restored["evidence_refs"], ["evidence://legacy-task"])
        self.assertEqual(restored["correlation_id"], correlation)
        self.assertEqual(upgraded["continuity"]["missions"][0]["mission_id"], mission["mission_id"])
        self.assertEqual(
            upgraded["persona_memory"]["personas"]["developer"]["entries"][0]["message"],
            "nota histórica da persona",
        )
        self.assertFalse(upgraded["aion"]["real_trading"])
        self.assertFalse(restored["real_trading_enabled"])
        self.assertFalse(restored["automatic_resume_executes"])
        view = prepare_resume(restored, checkpoint_digest="cp-v17")
        self.assertFalse(view["executes_action"])
        self.assertTrue(view["restores_state_only"])
        resumed = record_resume(
            restored,
            checkpoint_digest="cp-v17",
            expected_revision=restored["revision"],
            changed_at=FRESH_AT,
        )
        self.assertNotEqual(resumed["state"], "RUNNING")
        self.assertFalse(resumed["automatic_resume_executes"])
        self.assertEqual(resumed["steps"][0]["state"], restored["steps"][0]["state"])
        self.assertFalse(resumed["real_trading_enabled"])


class MissionFormUiTests(unittest.TestCase):
    def _script(self, statuses):
        status_list = ", ".join(repr(item) for item in statuses)
        return f'''
import os
os.environ["GITHUB_TOKEN_HISTORICO"] = ""
os.environ["GITHUB_REPO_HISTORICO"] = ""
os.environ["GITHUB_DATA_BRANCH"] = "atlasquant-runtime"
os.environ["AION_MODEL_PROVIDER"] = "offline"
import atlasquant_aion_admin as admin
from atlasquant_aion_continuity import new_mission, transition_mission
from atlasquant_aion_memory import default_checkpoint, update_continuity_checkpoint

mission = new_mission("Gate", created_at="2026-09-27T12:00:00+00:00")
rows = [mission]
for status in ({status_list},):
    rows = transition_mission(rows, mission["mission_id"], status, changed_at="2026-09-27T12:00:00+00:00")
checkpoint = update_continuity_checkpoint(default_checkpoint(), missions=rows)

def _load(cfg, timeout=6.0):
    return {{"status": "CONFIRMED", "checkpoint": checkpoint, "source": "post-audit"}}

admin.load_runtime_checkpoint = _load
admin.render_aion_admin_console(
    {{"role": "ADMIN", "username": "admin.test"}},
    market_context={{"fresh_confirmed": False, "summary": ""}},
    system_context={{
        "truth_state": "CONFIRMED",
        "source_build": "test-build",
        "environment": "LOCAL",
        "app_version": "test",
        "market_status": "não confirmado nesta tela",
    }},
)
'''

    def _open(self, statuses):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_string(self._script(statuses))
        app.run(timeout=60)
        self.assertEqual(list(app.exception), [])
        app.selectbox[0].set_value("🛠️ Desenvolvimento").run(timeout=60)
        self.assertEqual(list(app.exception), [])
        return app

    def _widget(self, widgets, label):
        found = [item for item in widgets if getattr(item, "label", "") == label]
        self.assertEqual(len(found), 1, msg=label)
        return found[0]

    def _mission_table(self, app) -> str:
        return " ".join(str(frame.value) for frame in app.dataframe)

    def test_form_blocks_resume_until_approval_is_explicit(self):
        app = self._open(("WAITING_APPROVAL",))
        self._widget(app.selectbox, "Novo estado da missão").set_value("IN_PROGRESS").run(timeout=60)
        checkbox = self._widget(app.checkbox, "Aprovo explicitamente a retomada desta missão")
        self.assertFalse(checkbox.value)
        self._widget(app.button, "Atualizar missão persistente").click().run(timeout=60)
        self.assertEqual(list(app.exception), [])
        self.assertTrue(any("MISSION_APPROVAL_REQUIRED" in str(item.value) for item in app.error))
        self.assertIn("WAITING_APPROVAL", self._mission_table(app))
        checkbox.set_value(True).run(timeout=60)
        self._widget(app.button, "Atualizar missão persistente").click().run(timeout=60)
        self.assertEqual(list(app.exception), [])
        self.assertEqual(list(app.error), [])
        labels = [getattr(item, "label", "") for item in app.checkbox]
        self.assertNotIn("Aprovo explicitamente a retomada desta missão", labels)
        self.assertIn("IN_PROGRESS", self._mission_table(app))

    def test_form_blocks_unblock_until_reason_is_explicit(self):
        app = self._open(("BLOCKED",))
        self._widget(app.selectbox, "Novo estado da missão").set_value("IN_PROGRESS").run(timeout=60)
        reason = self._widget(app.text_input, "Motivo do desbloqueio")
        self.assertEqual(reason.value, "")
        self._widget(app.button, "Atualizar missão persistente").click().run(timeout=60)
        self.assertTrue(any("MISSION_UNBLOCK_REQUIRED" in str(item.value) for item in app.error))
        self.assertIn("BLOCKED", self._mission_table(app))
        reason.set_value("bloqueio revisado").run(timeout=60)
        self._widget(app.button, "Atualizar missão persistente").click().run(timeout=60)
        self.assertEqual(list(app.exception), [])
        self.assertEqual(list(app.error), [])
        labels = [getattr(item, "label", "") for item in app.text_input]
        self.assertNotIn("Motivo do desbloqueio", labels)
        self.assertIn("IN_PROGRESS", self._mission_table(app))

    def test_form_does_not_reopen_a_terminal_mission(self):
        app = self._open(("IN_PROGRESS", "DONE"))
        self._widget(app.selectbox, "Novo estado da missão").set_value("IN_PROGRESS").run(timeout=60)
        labels = [getattr(item, "label", "") for item in app.checkbox]
        self.assertNotIn("Aprovo explicitamente a retomada desta missão", labels)
        self._widget(app.button, "Atualizar missão persistente").click().run(timeout=60)
        self.assertTrue(any("INVALID_MISSION_TRANSITION" in str(item.value) for item in app.error))
        self.assertIn("DONE", self._mission_table(app))
        self.assertNotIn("IN_PROGRESS", self._mission_table(app))


if __name__ == "__main__":
    unittest.main()
