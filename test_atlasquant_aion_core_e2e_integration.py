import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timezone

from atlasquant_aion_core_runtime_bridge import (
    handle_runtime_intent,
    persistence_contract,
)
from atlasquant_aion_entitlements import (
    approve_entitlement_request,
    mark_entitlement_from_provider_evidence,
    new_entitlement_request,
)
from atlasquant_aion_local_executor import execute_local_tool
from atlasquant_aion_local_synthesis import synthesize_local_tool_results
from atlasquant_aion_local_traceability import build_local_traceability
from atlasquant_aion_memory import (
    checkpoint_integrity_report,
    checkpoint_source_digest,
    default_checkpoint,
)
from atlasquant_aion_recovery_traceability_gate import (
    recovery_traceability_readiness,
)
from atlasquant_aion_tenant import PERSONAL_SCOPE
from atlasquant_aion_tenant_durable_store import DurableTenantStore

NOW = datetime(2026, 10, 2, 11, 0, tzinfo=timezone.utc)

def _admin_access():
    return {
        "allowed": True,
        "mode": "AUTHENTICATED",
        "role": "ADMIN",
        "session": {
            "username": "mikael",
            "role": "ADMIN",
            "credential_fingerprint": "a" * 32,
            "permissions": ["app:read", "admin:read", "aion:admin"],
            "authenticated_at": 10,
            "last_seen": 10,
        },
    }


def _tenant_access(username="cliente.01", fingerprint="b"):
    return {
        "session": {
            "username": username,
            "role": "USER",
            "credential_fingerprint": fingerprint * 32,
        }
    }


def _active_entitlement(subject, external_id):
    admin = {"role": "ADMIN", "username": "admin.01"}
    row = new_entitlement_request(
        subject,
        scope=PERSONAL_SCOPE,
        source_kind="MANUAL_GRANT",
        created_at="2026-10-02T10:00:00Z",
    )
    row = approve_entitlement_request(row, admin)
    return mark_entitlement_from_provider_evidence(
        row,
        {
            "confirmed": True,
            "provider": "e2e_registry",
            "external_id": external_id,
        },
    )

def _checkpoint_execution():
    checkpoint = default_checkpoint()
    execution = execute_local_tool(
        "aion.checkpoint.inspect",
        access=_admin_access(),
        authenticated_admin=True,
        source_kind="ADMIN",
        runtime_context={"checkpoint": checkpoint},
        request_id="core-e2e:checkpoint",
    )
    synthesis = synthesize_local_tool_results([execution])
    trace = build_local_traceability([execution], synthesis=synthesis)
    return checkpoint, execution, synthesis, trace


class AionCoreE2EIntegrationTests(unittest.TestCase):
    def test_checkpoint_tool_hub_traceability_chain_is_clean_and_non_authoritative(self):
        checkpoint, execution, synthesis, trace = _checkpoint_execution()
        self.assertEqual(checkpoint_integrity_report(checkpoint)["state"], "CONFIRMED")
        self.assertEqual(execution["state"], "SUCCESS")
        self.assertEqual(execution["preflight"]["state"], "READY_FOR_EXECUTOR")
        self.assertEqual(execution["result"]["integrity"]["state"], "CONFIRMED")
        self.assertEqual(synthesis["conflicts"], [])
        self.assertEqual(trace["state"], "TRACED")
        self.assertEqual(trace["security"]["state"], "SAFE_LOCAL")
        self.assertEqual(trace["source_keys"], ["checkpoint_master"])
        self.assertTrue(trace["execution_refs"])
        self.assertFalse(execution["tool_output_is_authority"])
        self.assertFalse(trace["tool_output_is_authority"])
        self.assertFalse(execution["external_action_executed"])

    def test_core_consumes_trace_bound_observation_without_promoting_tool_output(self):
        _, execution, _, trace = _checkpoint_execution()
        trace_id = trace["execution_refs"][0]
        result = handle_runtime_intent(
            _admin_access(),
            "qual é o estado do sistema e do build",
            system_context={
                "core_evidence": [{
                    "claim": "checkpoint-integrity",
                    "value": execution["result"]["integrity"]["state"],
                    "truth_state": "UNKNOWN",
                    "source": "AION local checkpoint trace",
                    "source_ref": trace_id,
                    "time_sensitive": False,
                }]
            },
            now=NOW,
        )
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["truth_state"], "UNKNOWN")
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["external_action_executed"])
        self.assertFalse(result["memory_auto_written"])
        self.assertEqual(
            result["persistence"]["state"],
            "LOCAL_DURABLE_AVAILABLE",
        )
        self.assertFalse(result["persistence"]["production_persistence_activated"])

    def test_explicit_local_tenant_roundtrip_is_isolated_and_not_production(self):
        user = _tenant_access()
        entitlement = _active_entitlement("cliente.01", "e2e-ent-1")
        with tempfile.TemporaryDirectory() as tmp:
            store = DurableTenantStore(tmp)
            denied = store.write(
                user,
                [entitlement],
                {"profile": {"display_name": "E2E"}},
                approved=False,
                now=NOW,
            )
            self.assertFalse(denied["stored"])
            written = store.write(
                user,
                [entitlement],
                {"profile": {"display_name": "E2E"}},
                workspace_id="core-e2e",
                approved=True,
                now=NOW,
            )
            self.assertTrue(written["stored"])
            self.assertFalse(written["production_activated"])
            self.assertFalse(written["network_io"])
            loaded = store.read(
                user,
                [entitlement],
                workspace_id="core-e2e",
                now=NOW,
            )
            self.assertTrue(loaded["loaded"])
            self.assertEqual(loaded["memory"]["profile"]["display_name"], "E2E")
            self.assertFalse(loaded["network_io"])

            other = _tenant_access("cliente.02", "c")
            other_entitlement = _active_entitlement("cliente.02", "e2e-ent-2")
            foreign = store.read(
                other,
                [other_entitlement],
                workspace_id="core-e2e",
                now=NOW,
            )
            self.assertFalse(foreign["loaded"])
            self.assertEqual(foreign["reason"], "NOT_FOUND")

    def test_recovery_uses_real_checkpoint_trace_but_stays_review_only(self):
        checkpoint, _, _, trace = _checkpoint_execution()
        candidate_checkpoint = deepcopy(checkpoint)
        candidate_checkpoint["aion"]["priority"] = "e2e recovery candidate"
        current = {
            "status": "CONFIRMED",
            "sha": "b" * 40,
            "checkpoint": checkpoint,
            "integrity": checkpoint_integrity_report(checkpoint),
        }
        candidate = {
            "status": "CONFIRMED",
            "revision": "c" * 40,
            "checkpoint": candidate_checkpoint,
            "integrity": checkpoint_integrity_report(candidate_checkpoint),
            "digest": checkpoint_source_digest(candidate_checkpoint),
        }
        result = recovery_traceability_readiness(current, candidate, trace)
        self.assertEqual(result["state"], "READY_FOR_ADMIN_REVIEW")
        self.assertEqual(result["blockers"], [])
        self.assertTrue(result["receipt"]["requires_explicit_admin_approval"])
        self.assertFalse(result["recovery_authorized"])
        self.assertFalse(result["automatic_restore"])
        self.assertFalse(result["automatic_retry"])
        self.assertFalse(result["checkpoint_saved"])
        self.assertFalse(result["external_action_executed"])
        self.assertFalse(result["network_called"])

    def test_write_tool_remains_blocked_even_when_approved_flag_is_true(self):
        result = execute_local_tool(
            "aion.checkpoint.prepare_save",
            access=_admin_access(),
            authenticated_admin=True,
            approved=True,
            source_kind="ADMIN",
            runtime_context={"checkpoint": default_checkpoint()},
            request_id="core-e2e:blocked-write",
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertFalse(result["executes_action"])
        self.assertFalse(result["external_action_executed"])
        self.assertFalse(result["real_orders_enabled"])

    def test_runtime_persistence_snapshot_is_capability_not_activation(self):
        contract = persistence_contract()
        self.assertEqual(contract["state"], "LOCAL_DURABLE_AVAILABLE")
        self.assertTrue(contract["tenant_code_ready"])
        self.assertFalse(contract["tenant_evidence_ready"])
        self.assertEqual(
            contract["tenant_evidence_source"],
            "NOT_INJECTED_REVIEW_ARTIFACT",
        )
        self.assertFalse(contract["tenant_evidence_auto_loaded"])
        self.assertTrue(contract["explicit_write_approval_required"])
        self.assertFalse(contract["runtime_bridge_connected"])
        self.assertFalse(contract["memory_auto_write"])
        self.assertFalse(contract["production_persistence_activated"])
        self.assertFalse(contract["automatic_activation"])


if __name__ == "__main__":
    unittest.main()
