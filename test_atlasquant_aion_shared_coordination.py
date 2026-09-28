import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_runtime_bridge import authenticated_context
from atlasquant_aion_memory import (
    checkpoint_integrity_report,
    checkpoint_source_digest,
    ensure_operating_checkpoint,
)
from atlasquant_aion_shared_coordination import (
    CHECKPOINT_NAMESPACE,
    REQUIRED_CAPABILITIES,
    SharedLeaseManager,
    activation_gate,
    checkpoint_bundle_integrity,
    load_probe_receipt,
    probe_integrity,
    run_coordination_probe,
    shared_coordination_snapshot,
    stage_probe_receipt,
    validate_probe,
    validate_resource_budget,
)


NOW = datetime(2026, 9, 28, 13, 0, tzinfo=timezone.utc)


def _access(username="mikael", fingerprint="shared-coordination-admin"):
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


def _budget(max_probe_writes=5):
    return {
        "max_workers": 2,
        "max_claims_per_minute": 30,
        "max_lease_seconds": 300,
        "max_probe_writes": max_probe_writes,
    }


class FakeAtomicCoordinationStore:
    def __init__(self, *, paid=False, missing=None):
        self.records = {}
        self.versions = {}
        self.fences = {}
        self.mutations = 0
        self.paid = paid
        self.missing = set(missing or [])

    def describe(self):
        caps = {
            name: name not in self.missing
            for name in REQUIRED_CAPABILITIES
        }
        return {
            "configured": True,
            "identity": "fake-atomic-store-v1",
            "backend_kind": "TEST_ONLY_MEMORY",
            "external_paid_service": self.paid,
            "capabilities": caps,
        }

    def read(self, key):
        row = self.records.get(key)
        if row is None:
            return {"exists": False, "version": None, "value": {}}
        return {
            "exists": True,
            "version": row["version"],
            "value": deepcopy(row["value"]),
        }

    def compare_and_swap(self, key, *, expected_version, value, ttl_seconds):
        current = self.records.get(key)
        if current is None:
            if expected_version is not None:
                return {
                    "swapped": False,
                    "version": self.versions.get(key),
                    "reason": "EXPECTED_EXISTING",
                }
        else:
            if expected_version != current["version"]:
                return {
                    "swapped": False,
                    "version": current["version"],
                    "reason": "VERSION_CONFLICT",
                }
        version = int(self.versions.get(key) or 0) + 1
        self.versions[key] = version
        self.records[key] = {
            "version": version,
            "value": deepcopy(dict(value)),
            "ttl_seconds": ttl_seconds,
        }
        self.mutations += 1
        return {"swapped": True, "version": version, "reason": ""}

    def delete(self, key, *, expected_version):
        current = self.records.get(key)
        if current is None:
            return {"deleted": False, "reason": "ABSENT"}
        if expected_version != current["version"]:
            return {"deleted": False, "reason": "VERSION_CONFLICT"}
        del self.records[key]
        self.mutations += 1
        return {"deleted": True, "reason": ""}

    def next_fencing_token(self, key, *, ttl_seconds):
        token = int(self.fences.get(key) or 0) + 1
        self.fences[key] = token
        self.mutations += 1
        return {"token": token}


class SharedCoordinationGateTests(unittest.TestCase):
    def setUp(self):
        self.access = _access()
        self.context = authenticated_context(self.access, Domain.ADMIN)

    def probe(self, adapter=None, **kwargs):
        return run_coordination_probe(
            self.access,
            adapter or FakeAtomicCoordinationStore(),
            confirmation=True,
            now=NOW,
            **kwargs,
        )

    def test_no_backend_is_fail_closed_and_never_claims_24x7(self):
        snap = shared_coordination_snapshot(
            self.access,
            {},
            adapter=None,
            now=NOW,
        )
        self.assertEqual(snap["status"], "UNAVAILABLE")
        self.assertEqual(
            snap["reason"],
            "NO_SHARED_ATOMIC_STORE_CONFIGURED",
        )
        self.assertFalse(snap["coordination_ready"])
        self.assertFalse(snap["global_worker_started"])
        self.assertFalse(snap["global_24x7_confirmed"])
        self.assertFalse(snap["multi_instance_safe_confirmed"])
        self.assertFalse(snap["external_paid_service_activated"])
        self.assertFalse(snap["real_trading_enabled"])

    def test_probe_requires_explicit_admin_confirmation_without_writes(self):
        adapter = FakeAtomicCoordinationStore()
        result = run_coordination_probe(
            self.access,
            adapter,
            confirmation=False,
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(adapter.mutations, 0)
        self.assertFalse(result["external_write_executed"])

    def test_paid_backend_probe_requires_explicit_paid_service_approval(self):
        adapter = FakeAtomicCoordinationStore(paid=True)
        result = run_coordination_probe(
            self.access,
            adapter,
            confirmation=True,
            paid_service_approved=False,
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["reason"],
            "PAID_SERVICE_REQUIRES_EXPLICIT_APPROVAL",
        )
        self.assertEqual(adapter.mutations, 0)

    def test_missing_atomic_capability_blocks_before_probe_writes(self):
        adapter = FakeAtomicCoordinationStore(
            missing={"atomic_monotonic_fencing_token"}
        )
        result = run_coordination_probe(
            self.access,
            adapter,
            confirmation=True,
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(
            "atomic_monotonic_fencing_token",
            result["reason"],
        )
        self.assertEqual(adapter.mutations, 0)

    def test_probe_confirms_real_cas_fencing_and_cleanup_semantics(self):
        adapter = FakeAtomicCoordinationStore()
        result = self.probe(adapter)
        self.assertEqual(result["status"], "CONFIRMED")
        receipt = result["probe_receipt"]
        self.assertEqual(probe_integrity(receipt)["state"], "MATCH")
        self.assertEqual(receipt["status"], "PASS")
        self.assertTrue(receipt["tests"]["create_cas"])
        self.assertTrue(receipt["tests"]["stale_cas_rejected"])
        self.assertTrue(receipt["tests"]["live_cas"])
        self.assertTrue(receipt["tests"]["read_after_cas"])
        self.assertTrue(receipt["tests"]["version_monotonic"])
        self.assertTrue(receipt["tests"]["fencing_token_monotonic"])
        self.assertTrue(receipt["tests"]["cleanup"])
        self.assertEqual(receipt["probe_writes"], 5)
        self.assertEqual(adapter.mutations, 5)
        self.assertTrue(result["external_write_executed"])
        self.assertFalse(result["real_trading_enabled"])

    def test_probe_receipt_expires_and_cannot_support_current_claim(self):
        adapter = FakeAtomicCoordinationStore()
        receipt = self.probe(adapter)["probe_receipt"]
        fresh = validate_probe(
            receipt,
            adapter_identity="fake-atomic-store-v1",
            now=NOW,
        )
        stale = validate_probe(
            receipt,
            adapter_identity="fake-atomic-store-v1",
            now=NOW + timedelta(seconds=901),
        )
        self.assertEqual(fresh["state"], "CONFIRMED")
        self.assertEqual(stale["state"], "STALE")

    def test_probe_is_bound_to_exact_adapter_identity(self):
        adapter = FakeAtomicCoordinationStore()
        receipt = self.probe(adapter)["probe_receipt"]
        result = validate_probe(
            receipt,
            adapter_identity="different-store",
            now=NOW,
        )
        self.assertEqual(result["state"], "UNVERIFIED")
        self.assertEqual(
            result["reason"],
            "PROBE_ADAPTER_IDENTITY_MISMATCH",
        )

    def test_resource_budget_requires_exact_ints_not_bool_or_string(self):
        self.assertEqual(
            validate_resource_budget(_budget())["state"],
            "CONFIRMED",
        )
        bad_bool = _budget()
        bad_bool["max_workers"] = True
        self.assertEqual(
            validate_resource_budget(bad_bool)["state"],
            "INVALID",
        )
        bad_string = _budget()
        bad_string["max_workers"] = "2"
        self.assertEqual(
            validate_resource_budget(bad_string)["state"],
            "INVALID",
        )

    def test_activation_gate_requires_probe_budget_and_confirmation_but_never_starts(self):
        adapter = FakeAtomicCoordinationStore()
        receipt = self.probe(adapter)["probe_receipt"]
        no_confirm = activation_gate(
            self.access,
            adapter,
            probe_receipt=receipt,
            resource_budget=_budget(),
            confirmation=False,
            now=NOW,
        )
        self.assertEqual(no_confirm["status"], "BLOCKED")
        self.assertEqual(
            no_confirm["reason"],
            "EXPLICIT_GLOBAL_ACTIVATION_CONFIRMATION_REQUIRED",
        )
        ready = activation_gate(
            self.access,
            adapter,
            probe_receipt=receipt,
            resource_budget=_budget(),
            confirmation=True,
            now=NOW,
        )
        self.assertEqual(ready["status"], "READY")
        self.assertTrue(ready["coordination_ready"])
        self.assertFalse(ready["global_worker_started"])
        self.assertFalse(ready["execution_authorized"])
        self.assertFalse(ready["external_action_executed"])
        self.assertFalse(ready["real_trading_enabled"])

    def test_probe_write_budget_blocks_when_lower_than_observed_mutations(self):
        adapter = FakeAtomicCoordinationStore()
        receipt = self.probe(adapter)["probe_receipt"]
        result = activation_gate(
            self.access,
            adapter,
            probe_receipt=receipt,
            resource_budget=_budget(max_probe_writes=4),
            confirmation=True,
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "PROBE_WRITE_BUDGET_EXCEEDED")

    def test_probe_receipt_can_be_staged_and_tamper_breaks_master_integrity(self):
        adapter = FakeAtomicCoordinationStore()
        receipt = self.probe(adapter)["probe_receipt"]
        staged = stage_probe_receipt({}, self.context, receipt)
        self.assertEqual(
            checkpoint_bundle_integrity(
                staged[CHECKPOINT_NAMESPACE]
            )["state"],
            "MATCH",
        )
        loaded, state = load_probe_receipt(self.context, staged)
        self.assertEqual(state["state"], "CONNECTED")
        self.assertEqual(loaded["digest"], receipt["digest"])

        tampered = deepcopy(staged)
        tampered[CHECKPOINT_NAMESPACE]["probe_receipt"]["status"] = "FAIL"
        self.assertEqual(
            checkpoint_bundle_integrity(
                tampered[CHECKPOINT_NAMESPACE]
            )["state"],
            "MISMATCH",
        )
        report = checkpoint_integrity_report(tampered)
        self.assertEqual(report["state"], "MISMATCH")
        self.assertIn("aion_shared_coordination", report["mismatches"])

    def test_coordination_namespace_survives_checkpoint_normalization_and_digest(self):
        adapter = FakeAtomicCoordinationStore()
        receipt = self.probe(adapter)["probe_receipt"]
        base = ensure_operating_checkpoint({})
        before = checkpoint_source_digest(base)
        staged = stage_probe_receipt(base, self.context, receipt)
        normalized = ensure_operating_checkpoint(staged)
        self.assertIn(CHECKPOINT_NAMESPACE, normalized)
        self.assertNotEqual(before, checkpoint_source_digest(normalized))

    def test_cross_actor_probe_receipt_is_isolated(self):
        adapter = FakeAtomicCoordinationStore()
        receipt = self.probe(adapter)["probe_receipt"]
        staged = stage_probe_receipt({}, self.context, receipt)
        other = authenticated_context(
            _access(username="outro", fingerprint="other-shared"),
            Domain.ADMIN,
        )
        loaded, state = load_probe_receipt(other, staged)
        self.assertIsNone(loaded)
        self.assertEqual(state["state"], "CONTEXT_ISOLATED")

    def test_shared_lease_blocks_competitor_and_reclaims_with_higher_fence(self):
        adapter = FakeAtomicCoordinationStore()
        manager = SharedLeaseManager(
            adapter,
            namespace="atlasquant/aion/test",
        )
        first = manager.claim(
            owner="runtime-a",
            ttl_seconds=120,
            now=NOW,
        )
        self.assertEqual(first["status"], "CLAIMED")
        self.assertEqual(first["fencing_token"], 1)

        blocked = manager.claim(
            owner="runtime-b",
            ttl_seconds=120,
            now=NOW + timedelta(seconds=30),
        )
        self.assertEqual(blocked["status"], "LEASE_HELD")
        self.assertEqual(blocked["fencing_token"], 1)

        reclaimed = manager.claim(
            owner="runtime-b",
            ttl_seconds=120,
            now=NOW + timedelta(seconds=121),
        )
        self.assertEqual(reclaimed["status"], "CLAIMED")
        self.assertEqual(reclaimed["fencing_token"], 2)

        stale_heartbeat = manager.heartbeat(
            owner="runtime-a",
            lease_token=first["lease_token"],
            fencing_token=first["fencing_token"],
            ttl_seconds=120,
            now=NOW + timedelta(seconds=122),
        )
        self.assertEqual(stale_heartbeat["status"], "LOST")
        self.assertEqual(
            stale_heartbeat["reason"],
            "FENCING_OR_OWNER_MISMATCH",
        )

    def test_same_owner_heartbeat_preserves_fence(self):
        adapter = FakeAtomicCoordinationStore()
        manager = SharedLeaseManager(adapter, namespace="atlasquant/aion/test")
        claim = manager.claim(
            owner="runtime-a",
            ttl_seconds=120,
            now=NOW,
        )
        beat = manager.heartbeat(
            owner="runtime-a",
            lease_token=claim["lease_token"],
            fencing_token=claim["fencing_token"],
            ttl_seconds=120,
            now=NOW + timedelta(seconds=30),
        )
        self.assertEqual(beat["status"], "HEARTBEAT")
        self.assertEqual(beat["fencing_token"], claim["fencing_token"])

    def test_release_does_not_reset_future_fencing_token(self):
        adapter = FakeAtomicCoordinationStore()
        manager = SharedLeaseManager(adapter, namespace="atlasquant/aion/test")
        first = manager.claim(
            owner="runtime-a",
            ttl_seconds=120,
            now=NOW,
        )
        released = manager.release(
            owner="runtime-a",
            lease_token=first["lease_token"],
            fencing_token=first["fencing_token"],
        )
        self.assertEqual(released["status"], "RELEASED")
        second = manager.claim(
            owner="runtime-b",
            ttl_seconds=120,
            now=NOW + timedelta(seconds=1),
        )
        self.assertEqual(second["status"], "CLAIMED")
        self.assertGreater(
            second["fencing_token"],
            first["fencing_token"],
        )

    def test_global_kill_switch_blocks_claim_and_epoch_changes(self):
        adapter = FakeAtomicCoordinationStore()
        manager = SharedLeaseManager(adapter, namespace="atlasquant/aion/test")
        on = manager.set_kill_switch(
            active=True,
            reason="operator stop",
        )
        self.assertEqual(on["status"], "UPDATED")
        self.assertTrue(on["active"])
        blocked = manager.claim(
            owner="runtime-a",
            ttl_seconds=120,
            now=NOW,
        )
        self.assertEqual(blocked["status"], "KILLED")

        off = manager.set_kill_switch(
            active=False,
            reason="operator re-enabled",
        )
        self.assertEqual(off["status"], "UPDATED")
        self.assertFalse(off["active"])
        self.assertGreater(off["epoch"], on["epoch"])
        claimed = manager.claim(
            owner="runtime-a",
            ttl_seconds=120,
            now=NOW,
        )
        self.assertEqual(claimed["status"], "CLAIMED")
        self.assertEqual(claimed["kill_epoch"], off["epoch"])

    def test_admin_ui_states_global_gate_is_unavailable_without_backend(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn(
            "Shared Coordination Gate V1 · autonomia global",
            source,
        )
        self.assertIn("Multi-instância", source)
        self.assertIn("24/7 global", source)
        self.assertIn("Nenhum serviço pago foi ativado", source)
        self.assertIn("adapter=None", source)

    def test_module_has_no_network_database_driver_or_implicit_backend(self):
        source = Path("atlasquant_aion_shared_coordination.py").read_text(
            encoding="utf-8"
        )
        for banned in (
            "import requests",
            "requests.",
            "redis.",
            "import redis",
            "psycopg",
            "supabase",
            "sqlite3",
            "urlopen(",
            "subprocess",
        ):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
