"""The coordination adapter diagnostic is data only. It does not run a probe."""
from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from atlasquant_aion_coordination_adapter_readiness import (
    BLOCKED,
    DESCRIPTOR_INVALID,
    DESCRIPTOR_READY,
    NOT_CONFIGURED,
    PROBE_EVIDENCE_READY,
    PROBE_REQUIRED,
    build_probe_receipt_fixture,
    coordination_adapter_readiness,
    format_coordination_adapter_caption,
    seal_probe_receipt,
)


NOW = datetime(2026, 9, 28, 22, 0, tzinfo=timezone.utc)
SCOPE = "scope-admin-context"


def _descriptor(**overrides):
    document = {
        "adapter_id": "future-shared",
        "adapter_version": "0",
        "provider": "unconnected",
        "backend_kind": "contract-only",
        "paid_service": False,
        "shared_across_instances": True,
        "atomic_compare_and_swap": True,
        "monotonic_versions": True,
        "atomic_monotonic_fencing_token": True,
        "ttl_expiry": True,
        "atomic_delete": True,
        "durable_outside_browser": True,
    }
    document.update(overrides)
    return document


def _flags_closed(report):
    return (
        report["global_worker_started"] is False
        and report["execution_authorized"] is False
        and report["real_trading_enabled"] is False
        and report["paid_service_approved"] is False
        and report["feature_flag_changed"] is False
        and report["worker_changed"] is False
        and report["probe_executed"] is False
    )


class CoordinationAdapterReadinessTests(unittest.TestCase):
    def test_missing_descriptor_stays_unconfigured(self):
        report = coordination_adapter_readiness(None, now=NOW)
        self.assertEqual(report["state"], NOT_CONFIGURED)
        self.assertEqual(report["descriptor_state"], NOT_CONFIGURED)
        self.assertFalse(report["backend_configured"])
        self.assertFalse(report["adapter_configured"])
        self.assertTrue(_flags_closed(report))
        caption = format_coordination_adapter_caption(report)
        self.assertIn("Backend compartilhado: NÃO CONFIGURADO", caption)
        self.assertIn("Adapter: NÃO CONFIGURADO", caption)
        self.assertIn("Probe: NÃO EXECUTADO", caption)
        self.assertIn("Worker alterado: NÃO", caption)
        self.assertIn("Feature flag alterada: NÃO", caption)

    def test_incomplete_descriptor_is_blocked(self):
        report = coordination_adapter_readiness({"adapter_id": "future-shared"}, now=NOW)
        self.assertEqual(report["state"], BLOCKED)
        self.assertEqual(report["descriptor_state"], DESCRIPTOR_INVALID)
        self.assertTrue(report["blockers"])
        self.assertTrue(_flags_closed(report))

    def test_false_capabilities_and_absent_backend_are_blocked(self):
        false_cap = coordination_adapter_readiness(
            _descriptor(atomic_compare_and_swap=False),
            now=NOW,
        )
        self.assertEqual(false_cap["state"], BLOCKED)
        self.assertIn("CAPABILITY_NOT_SATISFIED:atomic_compare_and_swap", false_cap["blockers"])
        absent = coordination_adapter_readiness(_descriptor(backend_kind="memory"), now=NOW)
        self.assertEqual(absent["state"], BLOCKED)
        self.assertIn("BACKEND_NOT_CONFIGURED", absent["blockers"])
        self.assertNotEqual(false_cap["state"], PROBE_REQUIRED)
        self.assertNotEqual(absent["state"], PROBE_EVIDENCE_READY)

    def test_valid_descriptor_requires_probe_and_does_not_activate(self):
        report = coordination_adapter_readiness(_descriptor(), now=NOW)
        self.assertEqual(report["state"], PROBE_REQUIRED)
        self.assertEqual(report["descriptor_state"], DESCRIPTOR_READY)
        self.assertTrue(report["backend_configured"])
        self.assertTrue(report["adapter_configured"])
        self.assertFalse(report["probe_evidence_accepted"])
        self.assertTrue(_flags_closed(report))

    def test_declared_paid_service_does_not_approve_anything(self):
        report = coordination_adapter_readiness(_descriptor(paid_service=True), now=NOW)
        self.assertEqual(report["state"], PROBE_REQUIRED)
        self.assertTrue(report["paid_service_declared"])
        self.assertFalse(report["paid_service_approved"])
        self.assertTrue(_flags_closed(report))

    def test_valid_receipt_is_evidence_only(self):
        receipt = build_probe_receipt_fixture(_descriptor(), scope_digest=SCOPE, now=NOW)
        report = coordination_adapter_readiness(
            _descriptor(),
            probe_receipt=receipt,
            expected_scope_digest=SCOPE,
            now=NOW,
        )
        self.assertEqual(report["state"], PROBE_EVIDENCE_READY)
        self.assertTrue(report["probe_evidence_accepted"])
        self.assertFalse(report["probe_executed"])
        self.assertFalse(report["global_worker_started"])
        self.assertFalse(report["execution_authorized"])
        self.assertFalse(report["real_trading_enabled"])

    def test_expired_receipt_is_blocked(self):
        receipt = build_probe_receipt_fixture(
            _descriptor(), scope_digest=SCOPE, now=NOW, ttl_seconds=60,
        )
        report = coordination_adapter_readiness(
            _descriptor(),
            probe_receipt=receipt,
            expected_scope_digest=SCOPE,
            now=NOW + timedelta(seconds=120),
        )
        self.assertEqual(report["state"], BLOCKED)
        self.assertIn("PROBE_EXPIRED", report["blockers"])

    def test_empty_or_different_scope_is_rejected(self):
        empty = build_probe_receipt_fixture(_descriptor(), scope_digest=SCOPE, now=NOW)
        empty["scope_digest"] = ""
        empty = seal_probe_receipt(empty)
        empty_report = coordination_adapter_readiness(
            _descriptor(),
            probe_receipt=empty,
            expected_scope_digest=SCOPE,
            now=NOW,
        )
        self.assertEqual(empty_report["state"], BLOCKED)
        self.assertIn("PROBE_SCOPE_DIGEST_MISSING", empty_report["blockers"])

        swapped = build_probe_receipt_fixture(_descriptor(), scope_digest="other-scope", now=NOW)
        swapped_report = coordination_adapter_readiness(
            _descriptor(),
            probe_receipt=swapped,
            expected_scope_digest=SCOPE,
            now=NOW,
        )
        self.assertEqual(swapped_report["state"], BLOCKED)
        self.assertIn("PROBE_SCOPE_MISMATCH", swapped_report["blockers"])
        missing_expected = coordination_adapter_readiness(
            _descriptor(),
            probe_receipt=build_probe_receipt_fixture(_descriptor(), scope_digest=SCOPE, now=NOW),
            expected_scope_digest="",
            now=NOW,
        )
        self.assertEqual(missing_expected["state"], BLOCKED)
        self.assertIn("PROBE_SCOPE_MISMATCH", missing_expected["blockers"])

    def test_adapter_mismatch_and_tampered_digest_are_rejected(self):
        receipt = build_probe_receipt_fixture(_descriptor(), scope_digest=SCOPE, now=NOW)
        mismatched = seal_probe_receipt({**receipt, "adapter_identity_digest": "f" * 64})
        mismatch = coordination_adapter_readiness(
            _descriptor(),
            probe_receipt=mismatched,
            expected_scope_digest=SCOPE,
            now=NOW,
        )
        self.assertEqual(mismatch["state"], BLOCKED)
        self.assertIn("PROBE_ADAPTER_MISMATCH", mismatch["blockers"])

        tampered = dict(receipt)
        tampered["evidence_digest"] = "cd" * 32
        forged = coordination_adapter_readiness(
            _descriptor(),
            probe_receipt=tampered,
            expected_scope_digest=SCOPE,
            now=NOW,
        )
        self.assertEqual(forged["state"], BLOCKED)
        self.assertIn("PROBE_DIGEST_MISMATCH", forged["blockers"])

    def test_excessive_ttl_and_invalid_timestamp_are_rejected(self):
        receipt = build_probe_receipt_fixture(_descriptor(), scope_digest=SCOPE, now=NOW)
        issued = datetime.fromisoformat(receipt["issued_at"])
        long_window = seal_probe_receipt({
            **receipt,
            "expires_at": (issued + timedelta(seconds=901)).isoformat(),
        })
        ttl = coordination_adapter_readiness(
            _descriptor(),
            probe_receipt=long_window,
            expected_scope_digest=SCOPE,
            now=NOW,
        )
        self.assertEqual(ttl["state"], BLOCKED)
        self.assertIn("PROBE_TTL_EXCEEDED", ttl["blockers"])
        with self.assertRaises(ValueError):
            build_probe_receipt_fixture(
                _descriptor(), scope_digest=SCOPE, now=NOW, ttl_seconds=1800,
            )

        bad_time = seal_probe_receipt({**receipt, "issued_at": "yesterday"})
        invalid = coordination_adapter_readiness(
            _descriptor(),
            probe_receipt=bad_time,
            expected_scope_digest=SCOPE,
            now=NOW,
        )
        self.assertEqual(invalid["state"], BLOCKED)
        self.assertIn("PROBE_TIMESTAMP_INVALID", invalid["blockers"])

    def test_secret_field_and_kill_switch_namespace_are_rejected(self):
        secret = _descriptor()
        secret["api_token"] = "not-stored"
        report = coordination_adapter_readiness(secret, now=NOW)
        self.assertEqual(report["state"], BLOCKED)
        self.assertTrue(any(item.startswith("DESCRIPTOR_SECRET_FIELD:") for item in report["blockers"]))
        kill = _descriptor(global_kill_switch_namespace="old-286")
        blocked = coordination_adapter_readiness(kill, now=NOW)
        self.assertEqual(blocked["state"], BLOCKED)
        self.assertTrue(any("UNKNOWN_FIELD" in item for item in blocked["blockers"]))

    def test_module_does_not_port_lease_manager_kill_switch_or_io(self):
        source = Path("atlasquant_aion_coordination_adapter_readiness.py").read_text(encoding="utf-8")
        self.assertNotIn("SharedLeaseManager", source)
        self.assertNotIn("set_kill_switch", source)
        self.assertNotIn("ATLASQUANT_AION_GLOBAL_WORKER_ENABLED", source)
        tree = ast.parse(source)
        imported = set()
        calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                calls.add(node.func.id)
        forbidden = {
            "requests", "socket", "subprocess", "urllib", "http", "sqlite3",
            "redis", "boto3", "pymongo", "psycopg", "importlib",
        }
        self.assertFalse(imported & forbidden)
        self.assertNotIn("open", calls)
        self.assertNotIn("system", calls)
        for path in (
            "atlasquant_aion_global_worker.py",
            "atlasquant_aion_global_worker_activation.py",
            "atlasquant_aion_global_worker_reactivation_gate.py",
        ):
            text = Path(path).read_text(encoding="utf-8")
            self.assertNotIn("coordination_adapter_readiness", text)

    def test_admin_section_is_read_only_and_unconfigured(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("Shared Coordination Adapter · readiness futuro", source)
        self.assertIn("coordination_adapter_readiness(None)", source)
        self.assertNotIn("Executar probe", source)
        self.assertNotIn("SharedLeaseManager", source)
        self.assertNotIn("set_kill_switch", source)
        caption = format_coordination_adapter_caption(coordination_adapter_readiness(None))
        self.assertEqual(
            caption,
            "Backend compartilhado: NÃO CONFIGURADO\n"
            "Adapter: NÃO CONFIGURADO\n"
            "Probe: NÃO EXECUTADO\n"
            "Worker alterado: NÃO\n"
            "Feature flag alterada: NÃO",
        )
