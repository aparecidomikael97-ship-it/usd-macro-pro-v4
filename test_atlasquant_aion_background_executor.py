import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from atlasquant_aion_background_executor import (
    EXECUTOR_NAMESPACE,
    MAX_ATTEMPTS,
    execute_due_local_work,
    executor_integrity,
    executor_snapshot,
    load_executor_receipts,
)
from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_runtime_bridge import authenticated_context
from atlasquant_aion_core_voice_automation import (
    SCHEDULER_NAMESPACE,
    stage_schedule,
)
from atlasquant_aion_memory import (
    checkpoint_integrity_report,
    checkpoint_source_digest,
    ensure_operating_checkpoint,
)


CREATED = datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)
DUE_NOW = datetime(2026, 9, 28, 13, 0, tzinfo=timezone.utc)


def _access(username="mikael", role="ADMIN", fingerprint="executor-admin"):
    return {
        "allowed": True,
        "mode": "AUTHENTICATED",
        "role": role,
        "session": {
            "username": username,
            "role": role,
            "credential_fingerprint": fingerprint,
            "permissions": (
                ["app:read", "admin:read", "aion:admin"]
                if role == "ADMIN"
                else ["app:read"]
            ),
            "authenticated_at": 10,
            "last_seen": 10,
        },
    }


def _voice_status(configured=False):
    return {
        "profile_id": "atlasquant_ptbr_fixed_neural_male_v2",
        "configured": configured,
        "provider": "openai",
        "model": "gpt-4o-mini-tts",
        "voice": "cedar",
    }


class AionBackgroundExecutorTests(unittest.TestCase):
    def setUp(self):
        self.access = _access()
        self.context = authenticated_context(self.access, Domain.ADMIN)

    def schedule(
        self,
        *,
        capability="ADMINISTRATION",
        prompt="estado do sistema",
        title="Estado do sistema",
        checkpoint=None,
        created=CREATED,
    ):
        result = stage_schedule(
            checkpoint or {},
            self.context,
            title=title,
            prompt=prompt,
            capability=capability,
            cadence="DAILY",
            timezone_name="America/Cuiaba",
            hour=8,
            minute=0,
            confirmation=True,
            now=created,
        )
        return result["checkpoint"]

    def execute(self, checkpoint, *, now=DUE_NOW, confirmation=True, max_jobs=5):
        return execute_due_local_work(
            self.access,
            checkpoint,
            system_context={},
            voice_status=_voice_status(False),
            confirmation=confirmation,
            max_jobs=max_jobs,
            now=now,
        )

    def test_explicit_confirmation_is_required(self):
        checkpoint = self.schedule()
        result = self.execute(checkpoint, confirmation=False)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["processed"], 0)
        self.assertNotIn(EXECUTOR_NAMESPACE, result["checkpoint"])
        self.assertFalse(result["autonomous_worker_started"])
        self.assertFalse(result["external_action_executed"])

    def test_safe_local_due_work_succeeds_and_receipt_is_staged(self):
        checkpoint = self.schedule()
        result = self.execute(checkpoint)
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["blocked"], 0)
        self.assertTrue(result["requires_checkpoint_save"])
        self.assertFalse(result["external_persisted"])
        self.assertFalse(result["background_worker_connected"])
        self.assertFalse(result["provider_called"])
        self.assertFalse(result["external_action_executed"])
        self.assertFalse(result["real_trading_enabled"])
        receipts, state = load_executor_receipts(
            self.context,
            result["checkpoint"],
        )
        self.assertEqual(state["state"], "CONNECTED")
        self.assertEqual(len(receipts), 1)
        receipt = receipts[0]
        self.assertEqual(receipt["state"], "SUCCEEDED")
        self.assertEqual(receipt["capability"], "ADMINISTRATION")
        self.assertTrue(receipt["guardian_allowed"])
        self.assertEqual(receipt["guardian_risk"], "READ")
        self.assertFalse(receipt["provider_called"])
        self.assertFalse(receipt["external_action_executed"])
        self.assertFalse(receipt["real_trading_enabled"])
        self.assertFalse(receipt["execution_authorized"])

    def test_same_occurrence_is_idempotent(self):
        first = self.execute(self.schedule())
        second = self.execute(first["checkpoint"])
        self.assertEqual(second["processed"], 0)
        self.assertEqual(second["outcomes"][0]["state"], "SKIPPED")
        self.assertEqual(
            second["outcomes"][0]["reason"],
            "IDEMPOTENT_TERMINAL_RECEIPT_EXISTS",
        )
        receipts, _ = load_executor_receipts(
            self.context,
            second["checkpoint"],
        )
        self.assertEqual(len(receipts), 1)

    def test_next_daily_occurrence_has_new_idempotency_key(self):
        first = self.execute(self.schedule())
        tomorrow = DUE_NOW + timedelta(days=1)
        second = self.execute(first["checkpoint"], now=tomorrow)
        self.assertEqual(second["processed"], 1)
        self.assertEqual(second["succeeded"], 1)
        receipts, _ = load_executor_receipts(
            self.context,
            second["checkpoint"],
        )
        self.assertEqual(len(receipts), 2)
        self.assertNotEqual(
            receipts[0]["occurrence_key"],
            receipts[1]["occurrence_key"],
        )

    def test_sensitive_publication_prompt_is_blocked_before_core_handler(self):
        checkpoint = self.schedule(
            capability="CONTENT",
            prompt="publique este conteúdo agora",
            title="Publicação proibida",
        )
        with patch(
            "atlasquant_aion_background_executor.handle_runtime_intent"
        ) as handler:
            result = self.execute(checkpoint)
        handler.assert_not_called()
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["blocked"], 1)
        receipt = load_executor_receipts(
            self.context,
            result["checkpoint"],
        )[0][0]
        self.assertEqual(receipt["state"], "BLOCKED")
        self.assertIn("SENSITIVE_INTENT_REQUIRES_INTERACTIVE_APPROVAL", receipt["reason"])
        self.assertFalse(receipt["external_action_executed"])

    def test_unbound_legacy_schedule_is_blocked_not_guessed(self):
        checkpoint = self.schedule()
        legacy = deepcopy(checkpoint)
        row = legacy[SCHEDULER_NAMESPACE]["schedules"][0]
        row["capability"] = ""
        raw = dict(legacy[SCHEDULER_NAMESPACE])
        raw.pop("digest", None)
        from atlasquant_aion_core_intelligence.evidence import digest
        legacy[SCHEDULER_NAMESPACE]["digest"] = digest(raw)
        with patch(
            "atlasquant_aion_background_executor.handle_runtime_intent"
        ) as handler:
            result = self.execute(legacy)
        handler.assert_not_called()
        self.assertEqual(result["blocked"], 1)
        receipt = load_executor_receipts(
            self.context,
            result["checkpoint"],
        )[0][0]
        self.assertEqual(
            receipt["reason"],
            "CAPABILITY_NOT_BACKGROUND_ALLOWLISTED",
        )

    def test_exception_creates_failed_receipt_and_retry_backoff(self):
        checkpoint = self.schedule()
        with patch(
            "atlasquant_aion_background_executor.handle_runtime_intent",
            side_effect=RuntimeError("secret detail must not persist"),
        ):
            first = self.execute(checkpoint)
        self.assertEqual(first["failed"], 1)
        receipts, _ = load_executor_receipts(
            self.context,
            first["checkpoint"],
        )
        self.assertEqual(receipts[-1]["state"], "FAILED")
        self.assertEqual(receipts[-1]["attempt"], 1)
        self.assertIn("RuntimeError", receipts[-1]["reason"])
        self.assertNotIn("secret detail", str(receipts[-1]))
        retry_at = datetime.fromisoformat(receipts[-1]["retry_after"])
        self.assertEqual(retry_at, DUE_NOW + timedelta(seconds=60))

        with patch(
            "atlasquant_aion_background_executor.handle_runtime_intent",
            side_effect=RuntimeError("still failing"),
        ) as handler:
            blocked_by_backoff = self.execute(
                first["checkpoint"],
                now=DUE_NOW + timedelta(seconds=30),
            )
        handler.assert_not_called()
        self.assertEqual(blocked_by_backoff["processed"], 0)
        self.assertEqual(
            blocked_by_backoff["outcomes"][0]["reason"],
            "RETRY_BACKOFF_ACTIVE",
        )

    def test_retry_limit_is_fail_closed(self):
        checkpoint = self.schedule()
        moments = [
            DUE_NOW,
            DUE_NOW + timedelta(seconds=61),
            DUE_NOW + timedelta(seconds=362),
        ]
        current = checkpoint
        for expected_attempt, moment in enumerate(moments, start=1):
            with patch(
                "atlasquant_aion_background_executor.handle_runtime_intent",
                side_effect=RuntimeError("boom"),
            ):
                result = self.execute(current, now=moment)
            current = result["checkpoint"]
            receipts, _ = load_executor_receipts(self.context, current)
            self.assertEqual(receipts[-1]["attempt"], expected_attempt)
            self.assertEqual(receipts[-1]["state"], "FAILED")

        with patch(
            "atlasquant_aion_background_executor.handle_runtime_intent"
        ) as handler:
            exhausted = self.execute(
                current,
                now=DUE_NOW + timedelta(seconds=2000),
            )
        handler.assert_not_called()
        self.assertEqual(exhausted["processed"], 0)
        self.assertEqual(exhausted["outcomes"][0]["reason"], "RETRY_EXHAUSTED")
        receipts, _ = load_executor_receipts(self.context, current)
        self.assertEqual(len(receipts), MAX_ATTEMPTS)

    def test_result_preview_redacts_secret_material(self):
        checkpoint = self.schedule(capability="CONTENT", prompt="conteudo")
        fake = {
            "status": "COMPLETED",
            "payload": {
                "draft": "api_key=super-sensitive-value",
                "url": "https://user:pass@example.test/path",
            },
            "provider_called": False,
            "external_action_executed": False,
            "real_trading_enabled": False,
            "execution_authorized": False,
        }
        with patch(
            "atlasquant_aion_background_executor.handle_runtime_intent",
            return_value=fake,
        ):
            result = self.execute(checkpoint)
        receipt = load_executor_receipts(
            self.context,
            result["checkpoint"],
        )[0][0]
        self.assertNotIn("super-sensitive-value", receipt["result_preview"])
        self.assertNotIn("user:pass", receipt["result_preview"])
        self.assertIn("[REDACTED]", receipt["result_preview"])

    def test_executor_integrity_tamper_blocks_master_integrity(self):
        result = self.execute(self.schedule())
        raw = result["checkpoint"][EXECUTOR_NAMESPACE]
        self.assertEqual(executor_integrity(raw)["state"], "MATCH")
        tampered = deepcopy(result["checkpoint"])
        tampered[EXECUTOR_NAMESPACE]["receipts"][0]["state"] = "FAILED"
        self.assertEqual(
            executor_integrity(tampered[EXECUTOR_NAMESPACE])["state"],
            "MISMATCH",
        )
        report = checkpoint_integrity_report(tampered)
        self.assertEqual(report["state"], "MISMATCH")
        self.assertIn("aion_core_executor", report["mismatches"])

    def test_executor_namespace_survives_normalization_and_conflict_digest(self):
        base = ensure_operating_checkpoint(self.schedule())
        before = checkpoint_source_digest(base)
        result = self.execute(base)
        normalized = ensure_operating_checkpoint(result["checkpoint"])
        self.assertIn(EXECUTOR_NAMESPACE, normalized)
        self.assertNotEqual(before, checkpoint_source_digest(normalized))

    def test_cross_actor_executor_receipts_are_isolated(self):
        result = self.execute(self.schedule())
        other_access = _access(username="outro", fingerprint="other-executor")
        other_context = authenticated_context(other_access, Domain.ADMIN)
        rows, state = load_executor_receipts(
            other_context,
            result["checkpoint"],
        )
        self.assertEqual(rows, [])
        self.assertEqual(state["state"], "CONTEXT_ISOLATED")

    def test_snapshot_never_claims_autonomous_or_physical_execution(self):
        checkpoint = self.schedule()
        snapshot = executor_snapshot(self.access, checkpoint, now=DUE_NOW)
        self.assertEqual(snapshot["due_count"], 1)
        self.assertTrue(snapshot["manual_invocation_only"])
        self.assertTrue(snapshot["manual_run_available"])
        self.assertFalse(snapshot["autonomous_worker_connected"])
        self.assertEqual(snapshot["physical_action_adapter"], "UNAVAILABLE")
        self.assertFalse(snapshot["external_action_executed"])
        self.assertFalse(snapshot["real_trading_enabled"])

    def test_admin_ui_requires_explicit_executor_confirmation(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Executor Local V1 · trabalhos devidos", source)
        self.assertIn("Capability local autorizada para esta agenda", source)
        self.assertIn("Executar trabalhos locais devidos agora", source)
        self.assertIn("Isto NÃO autoriza provider", source)
        self.assertIn("confirmation=True", source)
        self.assertIn("executor_snapshot(access, checkpoint)", source)

    def test_executor_module_has_no_network_subprocess_or_physical_provider(self):
        source = Path("atlasquant_aion_background_executor.py").read_text(
            encoding="utf-8"
        )
        for banned in (
            "import requests",
            "requests.",
            "subprocess",
            "urlopen(",
            "generate_neural_speech(",
            "save_runtime_checkpoint(",
            "publish_social(",
            "real_trade(",
        ):
            self.assertNotIn(banned, source)


    def test_executor_emits_action_envelope_referencing_child_receipt(self):
        result = self.execute(self.schedule())
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(len(result["action_receipts"]), 1)
        envelope = result["action_receipts"][0]
        child = load_executor_receipts(
            self.context,
            result["checkpoint"],
        )[0][0]
        self.assertEqual(envelope["child_receipt_id"], child["receipt_id"])
        self.assertEqual(
            envelope["receipt"]["child_receipts"][0]["receipt_id"],
            child["receipt_id"],
        )
        self.assertTrue(envelope["child_fingerprint"])
        self.assertEqual(envelope["authorization"], "NONE")
        self.assertFalse(envelope["executes_action"])
        self.assertFalse(result["action_receipts_are_authority"])

    def test_malformed_runtime_safety_flags_fail_closed(self):
        checkpoint = self.schedule(capability="CONTENT", prompt="conteudo")
        fake = {
            "status": "COMPLETED",
            "payload": {"draft": "safe"},
            "provider_called": "false",
            "external_action_executed": False,
            "real_trading_enabled": False,
            "execution_authorized": False,
        }
        with patch(
            "atlasquant_aion_background_executor.handle_runtime_intent",
            return_value=fake,
        ):
            result = self.execute(checkpoint)
        self.assertEqual(result["blocked"], 1)
        receipt = load_executor_receipts(
            self.context,
            result["checkpoint"],
        )[0][0]
        self.assertEqual(receipt["state"], "BLOCKED")
        self.assertEqual(receipt["reason"], "RUNTIME_SAFETY_FLAG_VIOLATION")

    def test_truthy_string_guardian_allow_does_not_authorize(self):
        checkpoint = self.schedule()
        with patch(
            "atlasquant_aion_background_executor.guardian_decision",
            return_value={"allowed": "yes", "risk": "READ", "reason": "malformed"},
        ), patch(
            "atlasquant_aion_background_executor.handle_runtime_intent"
        ) as handler:
            result = self.execute(checkpoint)
        handler.assert_not_called()
        self.assertEqual(result["blocked"], 1)
        receipt = load_executor_receipts(
            self.context,
            result["checkpoint"],
        )[0][0]
        self.assertFalse(receipt["guardian_allowed"])
        self.assertIn("GUARDIAN_BLOCKED", receipt["reason"])


if __name__ == "__main__":
    unittest.main()
