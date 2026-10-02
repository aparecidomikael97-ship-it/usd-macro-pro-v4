import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_intelligence.evidence import assess
from atlasquant_aion_core_runtime_bridge import (
    SAFETY_GATES,
    authenticated_context,
    handle_runtime_intent,
    persistence_contract,
    scoped_runtime_evidence,
)


NOW = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)


def _access(role="ADMIN"):
    return {
        "allowed": True,
        "mode": "AUTHENTICATED",
        "role": role,
        "session": {
            "username": "mikael" if role == "ADMIN" else "cliente",
            "role": role,
            "credential_fingerprint": "a1b2c3d4e5f60718293a4b5c",
            "permissions": (
                ["app:read", "admin:read", "aion:admin"]
                if role == "ADMIN"
                else ["app:read"]
            ),
            "authenticated_at": 10,
            "last_seen": 10,
        },
    }


def _record(**overrides):
    row = {
        "claim": "build",
        "value": "abc123",
        "truth_state": "CONFIRMED",
        "source": "AtlasQuant runtime identity",
        "source_ref": "runtime-build:abc123",
        "time_sensitive": False,
    }
    row.update(overrides)
    return row


class AionCoreRuntimeBridgeTests(unittest.TestCase):
    def test_authenticated_admin_context_uses_only_authenticated_identity(self):
        access = _access()
        access["query_params"] = {"role": "USER", "actor": "forged"}
        ctx = authenticated_context(access, Domain.ADMIN)
        self.assertEqual(ctx.role, "ADMIN")
        self.assertEqual(ctx.actor_id, "mikael")
        self.assertTrue(ctx.tenant_id.startswith("tenant:"))
        self.assertTrue(ctx.workspace_id.startswith("workspace:"))

    def test_forged_access_role_cannot_override_session_authority(self):
        access = _access("USER")
        access["role"] = "ADMIN"
        with self.assertRaisesRegex(ValueError, "AUTHORITY_MISMATCH"):
            authenticated_context(access, Domain.ADMIN)

    def test_non_admin_runtime_bridge_is_denied_without_private_payload(self):
        result = handle_runtime_intent(
            _access("USER"),
            "estado do sistema",
            system_context={"core_evidence": [_record()]},
            now=NOW,
        )
        self.assertEqual(result["status"], "DENIED")
        self.assertIsNone(result["payload"])
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["external_action_executed"])

    def test_cross_context_evidence_is_rejected(self):
        admin = _access()
        admin_ctx = authenticated_context(admin, Domain.ADMIN)
        developer_ctx = authenticated_context(admin, Domain.DEVELOPER)
        scoped, _ = scoped_runtime_evidence(
            admin_ctx,
            {"core_evidence": [_record()]},
        )
        with self.assertRaisesRegex(ValueError, "EVIDENCE_CONTEXT_MISMATCH"):
            scoped.for_context(developer_ctx)

    def test_complete_stable_build_evidence_can_be_confirmed(self):
        ctx = authenticated_context(_access(), Domain.ADMIN)
        scoped, ingress = scoped_runtime_evidence(
            ctx,
            {"core_evidence": [_record()]},
        )
        truth = assess(scoped.records, NOW)
        self.assertEqual(truth["status"], "CONFIRMED")
        self.assertEqual(ingress["accepted_records"], 1)

    def test_missing_source_reference_never_becomes_confirmed(self):
        ctx = authenticated_context(_access(), Domain.ADMIN)
        scoped, _ = scoped_runtime_evidence(
            ctx,
            {"core_evidence": [_record(source_ref="")]},
        )
        truth = assess(scoped.records, NOW)
        self.assertEqual(truth["status"], "UNKNOWN")

    def test_stale_temporal_evidence_never_becomes_confirmed(self):
        old = (NOW - timedelta(hours=2)).isoformat()
        ctx = authenticated_context(_access(), Domain.ADMIN)
        scoped, _ = scoped_runtime_evidence(
            ctx,
            {"core_evidence": [_record(
                observed_at=old,
                ttl_seconds=60,
                time_sensitive=True,
            )]},
        )
        truth = assess(scoped.records, NOW)
        self.assertEqual(truth["status"], "UNKNOWN")
        self.assertEqual(truth["freshness"], "STALE")

    def test_conflicting_confirmed_records_never_choose_a_winner(self):
        ctx = authenticated_context(_access(), Domain.ADMIN)
        scoped, _ = scoped_runtime_evidence(
            ctx,
            {"core_evidence": [
                _record(value="abc123"),
                _record(value="def456", source_ref="runtime-build:def456"),
            ]},
        )
        truth = assess(scoped.records, NOW)
        self.assertEqual(truth["status"], "UNKNOWN")
        self.assertEqual(truth["conflict_state"], "CONFLICT")

    def test_administration_receives_typed_build_evidence(self):
        result = handle_runtime_intent(
            _access(),
            "qual é o estado do sistema e do build",
            system_context={"core_evidence": [_record()]},
            now=NOW,
        )
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["route"]["capability"], "ADMINISTRATION")
        self.assertEqual(
            result["payload"]["system"]["build"]["state"],
            "SYSTEM_OBSERVED",
        )
        self.assertEqual(result["truth_state"], "CONFIRMED")

    def test_memory_has_no_automatic_store_or_write(self):
        result = handle_runtime_intent(
            _access(),
            "memoria e checkpoint",
            system_context={"core_evidence": [_record()]},
            now=NOW,
        )
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertFalse(result["memory_auto_written"])
        self.assertEqual(result["persistence"]["state"], "LOCAL_DURABLE_AVAILABLE")
        self.assertEqual(
            result["persistence"]["storage"],
            "LOCAL_TENANT_WORKSPACE_FILESYSTEM",
        )
        self.assertTrue(result["persistence"]["tenant_code_ready"])
        self.assertFalse(result["persistence"]["tenant_evidence_ready"])
        self.assertFalse(result["persistence"]["automatic_database_creation"])
        self.assertFalse(result["persistence"]["memory_auto_write"])
        self.assertFalse(result["persistence"]["production_persistence_activated"])

    def test_sensitive_action_is_never_executed(self):
        result = handle_runtime_intent(
            _access(),
            "publique este conteúdo",
            system_context={"core_evidence": [_record()]},
            now=NOW,
        )
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["reason"], "APPROVAL_STORE_UNAVAILABLE")
        for key, value in SAFETY_GATES.items():
            self.assertFalse(result[key], key)

    def test_voice_and_automation_stay_unavailable_without_adapters(self):
        for prompt in ("use voz para transcrever", "agende esta automacao"):
            with self.subTest(prompt=prompt):
                result = handle_runtime_intent(
                    _access(),
                    prompt,
                    system_context={},
                    now=NOW,
                )
                self.assertEqual(result["status"], "UNAVAILABLE")
                self.assertFalse(result["provider_called"])
                self.assertFalse(result["execution_authorized"])

    def test_persistence_contract_exposes_local_capability_without_activation(self):
        contract = persistence_contract()
        self.assertEqual(contract["state"], "LOCAL_DURABLE_AVAILABLE")
        self.assertEqual(contract["storage"], "LOCAL_TENANT_WORKSPACE_FILESYSTEM")
        self.assertEqual(contract["identity_acl"], "LOCAL_READY")
        self.assertTrue(contract["explicit_write_approval_required"])
        self.assertTrue(contract["tenant_code_ready"])
        self.assertFalse(contract["tenant_evidence_ready"])
        self.assertEqual(
            contract["tenant_evidence_source"],
            "NOT_INJECTED_REVIEW_ARTIFACT",
        )
        self.assertFalse(contract["tenant_evidence_auto_loaded"])
        self.assertFalse(contract["runtime_bridge_connected"])
        self.assertFalse(contract["automatic_directory_creation"])
        self.assertFalse(contract["automatic_database_creation"])
        self.assertFalse(contract["memory_auto_write"])
        self.assertFalse(contract["production_persistence_activated"])
        self.assertFalse(contract["automatic_activation"])

    def test_checkpoint_bridge_and_local_durable_capability_stay_separate(self):
        contract = persistence_contract(True)
        self.assertEqual(
            contract["state"],
            "STAGED_CHECKPOINT_AND_LOCAL_DURABLE_AVAILABLE",
        )
        self.assertTrue(contract["runtime_bridge_connected"])
        self.assertIn("CHECKPOINT_MASTER_STAGED", contract["storage"])
        self.assertFalse(contract["memory_auto_write"])
        self.assertFalse(contract["production_persistence_activated"])

    def test_bridge_has_no_network_subprocess_or_store_constructor(self):
        source = Path("atlasquant_aion_core_runtime_bridge.py").read_text(encoding="utf-8")
        for banned in (
            "import requests",
            "import subprocess",
            "from subprocess",
            "urllib.request",
            "socket.",
            "CoreStore(",
        ):
            self.assertNotIn(banned, source)

    def test_runtime_and_ui_integration_reuse_the_same_system_context(self):
        cloud = Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
        self.assertEqual(cloud.count("= _build_aion_source_runtime_context()"), 1)
        self.assertIn('"core_evidence":', cloud)
        self.assertIn("system_context=_aion_system_context", cloud)
        admin = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("handle_runtime_intent(", admin)
        self.assertIn("system_context=system_context", admin)
        self.assertIn("AION Core Intelligence · leitura local", admin)


if __name__ == "__main__":
    unittest.main()
