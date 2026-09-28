import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_runtime_bridge import (
    authenticated_context,
    handle_runtime_intent,
)
from atlasquant_aion_core_voice_automation import (
    AtlasQuantVoiceAdapter,
    CheckpointAutomationAdapter,
    SCHEDULER_NAMESPACE,
    load_schedules,
    scheduler_integrity,
    stage_schedule,
)
from atlasquant_aion_memory import (
    checkpoint_integrity_report,
    checkpoint_source_digest,
    ensure_operating_checkpoint,
)


NOW = datetime(2026, 9, 28, 13, 0, tzinfo=timezone.utc)


def _access(username="mikael", fingerprint="voice-scheduler-admin"):
    return {
        "allowed": True,
        "mode": "AUTHENTICATED",
        "role": "ADMIN",
        "session": {
            "username": username,
            "role": "ADMIN",
            "credential_fingerprint": fingerprint,
            "permissions": ["app:read", "admin:read", "aion:admin"],
            "authenticated_at": 10,
            "last_seen": 10,
        },
    }


def _voice_status(configured=True):
    return {
        "profile_id": "atlasquant_ptbr_fixed_neural_male_v2",
        "configured": configured,
        "provider": "openai",
        "model": "gpt-4o-mini-tts",
        "voice": "cedar",
        "automatic_playback": False,
        "trading_side_effects": False,
    }


class VoiceAdapterTests(unittest.TestCase):
    def test_unconfigured_voice_stays_unavailable(self):
        result = handle_runtime_intent(
            _access(),
            "voz",
            legacy_checkpoint={},
            voice_status=_voice_status(False),
            now=NOW,
        )
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["route"]["capability"], "VOICE")
        self.assertFalse(result["provider_called"])
        self.assertFalse(result["execution_authorized"])

    def test_configured_voice_routes_without_calling_provider(self):
        result = handle_runtime_intent(
            _access(),
            "voz",
            legacy_checkpoint={},
            voice_status=_voice_status(True),
            now=NOW,
        )
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["route"]["capability"], "VOICE")
        self.assertEqual(
            result["payload"]["status"],
            "READY_TO_GENERATE_ON_EXPLICIT_CLICK",
        )
        self.assertEqual(result["payload"]["transcript"], "voz")
        self.assertTrue(result["payload"]["cache_digest"])
        self.assertFalse(result["payload"]["provider_called"])
        self.assertFalse(result["provider_called"])

    def test_voice_adapter_status_keeps_manual_generation_boundary(self):
        adapter = AtlasQuantVoiceAdapter(_voice_status(True))
        snapshot = adapter.snapshot()
        self.assertTrue(adapter.available)
        self.assertEqual(snapshot["audio_generation_surface"], "EXPLICIT_UI_BUTTON")
        self.assertFalse(snapshot["automatic_playback"])
        self.assertFalse(snapshot["provider_called"])
        self.assertFalse(snapshot["external_action_executed"])
        self.assertFalse(snapshot["real_trading_enabled"])

    def test_voice_adapter_never_contains_network_call(self):
        source = Path("atlasquant_aion_core_voice_automation.py").read_text(
            encoding="utf-8"
        )
        for banned in (
            "requests.post",
            "requests.get",
            "urlopen(",
            "subprocess.",
            "generate_neural_speech(",
        ):
            self.assertNotIn(banned, source)


class SchedulerAdapterTests(unittest.TestCase):
    def setUp(self):
        self.access = _access()
        self.context = authenticated_context(self.access, Domain.ADMIN)

    def stage(self, checkpoint=None, **overrides):
        values = {
            "title": "Briefing macro da manhã",
            "prompt": "Preparar briefing com fatos confirmados e pendências.",
            "cadence": "DAILY",
            "timezone_name": "America/Cuiaba",
            "hour": 8,
            "minute": 0,
            "weekday": None,
            "run_at": None,
            "confirmation": True,
            "now": NOW,
        }
        values.update(overrides)
        return stage_schedule(checkpoint or {}, self.context, **values)

    def test_schedule_requires_explicit_human_confirmation(self):
        result = self.stage(confirmation=False)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertNotIn(SCHEDULER_NAMESPACE, result["checkpoint"])
        self.assertFalse(result["automatic_execution"])

    def test_daily_schedule_is_staged_but_not_executed(self):
        result = self.stage()
        self.assertEqual(result["status"], "STAGED")
        self.assertTrue(result["requires_checkpoint_save"])
        self.assertFalse(result["external_persisted"])
        self.assertFalse(result["automatic_execution"])
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["external_action_executed"])
        self.assertEqual(result["execution_adapter"], "UNAVAILABLE")
        self.assertTrue(result["next_run_at"])

    def test_new_schedule_after_today_slot_is_not_immediately_due(self):
        staged = self.stage()
        snapshot = CheckpointAutomationAdapter(
            self.context, staged["checkpoint"]
        ).snapshot(NOW)
        self.assertEqual(snapshot["count"], 1)
        self.assertEqual(snapshot["due_count"], 0)
        self.assertFalse(snapshot["schedules"][0]["due"])

    def test_daily_schedule_becomes_due_on_next_occurrence_without_execution(self):
        staged = self.stage()
        later = datetime(2026, 9, 29, 12, 30, tzinfo=timezone.utc)
        snapshot = CheckpointAutomationAdapter(
            self.context, staged["checkpoint"]
        ).snapshot(later)
        self.assertEqual(snapshot["due_count"], 1)
        self.assertTrue(snapshot["schedules"][0]["due"])
        self.assertFalse(snapshot["automatic_execution"])
        self.assertEqual(snapshot["execution_adapter"], "UNAVAILABLE")

    def test_hourly_schedule_has_deterministic_next_run(self):
        staged = self.stage(
            cadence="HOURLY",
            hour=0,
            minute=15,
        )
        self.assertEqual(
            staged["next_run_at"],
            "2026-09-28T14:15:00+00:00",
        )

    def test_weekly_schedule_respects_timezone_and_weekday(self):
        staged = self.stage(
            cadence="WEEKLY",
            hour=8,
            minute=30,
            weekday=0,
        )
        self.assertEqual(
            staged["next_run_at"],
            "2026-10-05T12:30:00+00:00",
        )

    def test_once_schedule_requires_future_aware_time(self):
        with self.assertRaises(ValueError):
            self.stage(
                cadence="ONCE",
                run_at=datetime(2026, 9, 28, 14, 0),
            )
        with self.assertRaisesRegex(ValueError, "future run_at"):
            self.stage(
                cadence="ONCE",
                run_at=NOW - timedelta(minutes=1),
            )
        future = NOW + timedelta(hours=2)
        staged = self.stage(cadence="ONCE", run_at=future)
        self.assertEqual(staged["next_run_at"], future.isoformat())

    def test_cross_actor_schedule_is_isolated(self):
        staged = self.stage()
        other = authenticated_context(
            _access(username="outro", fingerprint="different-principal"),
            Domain.ADMIN,
        )
        rows, state = load_schedules(other, staged["checkpoint"])
        self.assertEqual(rows, [])
        self.assertEqual(state["state"], "CONTEXT_ISOLATED")
        with self.assertRaisesRegex(ValueError, "SCHEDULER_CONTEXT_MISMATCH"):
            stage_schedule(
                staged["checkpoint"],
                other,
                title="Não sobrescrever",
                prompt="Não sobrescrever agenda de outro contexto.",
                cadence="DAILY",
                timezone_name="America/Cuiaba",
                hour=9,
                minute=0,
                confirmation=True,
                now=NOW,
            )

    def test_scheduler_tamper_fails_its_digest_and_master_integrity(self):
        staged = self.stage()
        self.assertEqual(
            scheduler_integrity(staged["checkpoint"][SCHEDULER_NAMESPACE])["state"],
            "MATCH",
        )
        tampered = deepcopy(staged["checkpoint"])
        tampered[SCHEDULER_NAMESPACE]["schedules"][0]["prompt"] = "adulterado"
        self.assertEqual(
            scheduler_integrity(tampered[SCHEDULER_NAMESPACE])["state"],
            "MISMATCH",
        )
        report = checkpoint_integrity_report(tampered)
        self.assertEqual(report["state"], "MISMATCH")
        self.assertIn("aion_core_scheduler", report["mismatches"])

    def test_scheduler_namespace_survives_checkpoint_normalization_and_conflict_digest(self):
        base = ensure_operating_checkpoint({})
        before = checkpoint_source_digest(base)
        staged = self.stage(base)
        normalized = ensure_operating_checkpoint(staged["checkpoint"])
        self.assertIn(SCHEDULER_NAMESPACE, normalized)
        self.assertNotEqual(before, checkpoint_source_digest(normalized))

    def test_runtime_automation_reads_persisted_schedule_without_executing(self):
        staged = self.stage()
        result = handle_runtime_intent(
            self.access,
            "agenda automacao",
            legacy_checkpoint=staged["checkpoint"],
            voice_status=_voice_status(False),
            now=NOW,
        )
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["route"]["capability"], "AUTOMATION")
        self.assertEqual(result["payload"]["count"], 1)
        self.assertEqual(result["payload"]["execution_adapter"], "UNAVAILABLE")
        self.assertFalse(result["payload"]["automatic_execution"])
        self.assertFalse(result["external_action_executed"])

    def test_automation_without_checkpoint_stays_unavailable(self):
        result = handle_runtime_intent(
            self.access,
            "agenda automacao",
            legacy_checkpoint=None,
            voice_status=_voice_status(False),
            now=NOW,
        )
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["route"]["capability"], "AUTOMATION")

    def test_admin_ui_exposes_scheduler_without_claiming_executor(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Voz & ⏱️ Automação do AION Core", source)
        self.assertIn("Executor background", source)
        self.assertIn("Registrar agenda no Checkpoint de trabalho", source)
        self.assertIn("NÃO será executada automaticamente", source)
        self.assertIn("voice_status=core_voice_status", source)

    def test_master_save_gate_contains_scheduler_integrity_check(self):
        source = Path("atlasquant_aion_memory.py").read_text(encoding="utf-8")
        self.assertIn("_aion_core_scheduler_integrity(payload)", source)
        self.assertIn("AION Core scheduler integrity mismatch.", source)


if __name__ == "__main__":
    unittest.main()
