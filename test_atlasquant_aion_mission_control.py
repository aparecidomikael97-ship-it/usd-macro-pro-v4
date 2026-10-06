from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore
from atlasquant_aion_durable_task_repository import DurableTaskRepository
from atlasquant_aion_durable_tasks import new_durable_task
from atlasquant_aion_mission_control import build_mission_control, mission_control_contract
from atlasquant_aion_system_health_center import build_system_health_center
from atlasquant_aion_incident_center import collect_incidents
from atlasquant_aion_release_confidence import release_confidence

SCOPE = {"owner_id": "owner-a", "tenant_id": "tenant-a", "workspace_id": "ws-a"}


def health(state="HEALTHY"):
    if state == "HEALTHY":
        source = {
            key: {
                "state": "HEALTHY",
                "confirmed": True,
                "freshness_attested": True,
                "freshness_source": "test",
                "unresolved": 0,
            }
            for key in ("sources", "runtime", "notifications", "workers", "queues", "screens")
        }
    else:
        source = {
            key: {
                "state": "HEALTHY",
                "confirmed": True,
                "freshness_attested": True,
                "freshness_source": "test",
                "unresolved": 0,
            }
            for key in ("sources", "runtime", "notifications", "workers", "queues", "screens")
        }
        source["runtime"] = {
            "state": state,
            "confirmed": state == "HEALTHY",
            "freshness_attested": True,
            "freshness_source": "test",
            "unresolved": 1,
        }
    return build_system_health_center(source)


def finops(state="ALLOW", **extra):
    row = {
        "schema": "ATLASQUANT_AION_FINOPS_METERING_V1",
        "state": state,
        "mode": "NORMAL" if state == "ALLOW" else "LOW_COST_MODE" if state == "DEGRADE" else "BLOCK_NEW_WORK",
        "scope": dict(SCOPE),
        "projected": {"calls": 2, "tokens": 100, "predicted_cost_usd": 0.01},
        "reconciliation": {"state": "MATCH"},
        "automatic_provider_call": False,
        "automatic_model_switch": False,
        "automatic_charge": False,
        "grants_authority": False,
        "executes_action": False,
    }
    row.update(extra)
    return row


def confidence(state="HUMAN_REVIEW_READY"):
    if state == "HUMAN_REVIEW_READY":
        rows = [
            {
                "dimension": name,
                "confirmed": True,
                "evidence_refs": [f"e:{name}"],
                "blocker": False,
            }
            for name in ("DIGITAL_TWIN", "DEV_FUSION", "EVALUATION", "QUALITY", "RELEASE_GATE", "ROLLBACK")
        ]
        verifier = lambda dim, refs: {"state": "VERIFIED", "bound_refs": list(refs)}
    elif state == "BLOCKED":
        rows = [
            {
                "dimension": "QUALITY",
                "confirmed": True,
                "evidence_refs": ["e:QUALITY"],
                "blocker": True,
            }
        ]
        verifier = lambda dim, refs: {"state": "VERIFIED", "bound_refs": list(refs)}
    else:
        rows = []
        verifier = None
    return release_confidence(
        candidate_ref="head-1",
        dimensions=rows,
        evidence_verifier=verifier,
    )


def readiness(state="READY_FOR_HUMAN_OWNER_REVIEW", **extra):
    row = {
        "schema": "ATLASQUANT_AION_POST_HARDENING_READINESS_V2",
        "state": state,
        "scope": dict(SCOPE),
        "required_stages": ["durable_cas", "finops", "behavioral_eval", "incident_control", "operational_resilience", "tenant_crypto"],
        "stages": {
            key: {"state": "VERIFIED"}
            for key in ("durable_cas", "finops", "behavioral_eval", "incident_control", "operational_resilience", "tenant_crypto")
        },
        "readiness_digest": "sha256:" + "1" * 64,
        "production_ready_claim": False,
        "activation_authorized": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "core_freeze_authorized": False,
        "worker_arming_authorized": False,
        "provider_activation_authorized": False,
        "recovery_authorized": False,
        "real_trading_authorized": False,
        "payment_authorized": False,
        "executes_action": False,
    }
    row.update(extra)
    return row


def incidents(*, critical=False, high=False):
    system = {}
    if critical:
        system["critical_engine_error"] = True
    elif high:
        system["production_identity_state"] = "MISMATCH"
    return collect_incidents(system_context=system)


class AionMissionControlTests(unittest.TestCase):
    def _tasks(self, raw, *, scope=None, add_task=True):
        trusted = scope or Scope("owner-a", "tenant-a", "ws-a")
        store = SQLiteChatStore(Path(raw) / "chat.sqlite3")
        repo = DurableTaskRepository(store, trusted)
        if add_task:
            repo.create(new_durable_task(
                "Mission Control task",
                objective="read-only projection",
                created_at="2026-10-05T13:00:00+00:00",
                source="TEST",
            ))
        return store, repo.integrity_report(), repo.checkpoint_projection()

    def _build(self, raw, **overrides):
        store, integrity, projection = self._tasks(raw)
        args = {
            "trusted_scope": SCOPE,
            "health_snapshot": health(),
            "finops_snapshot": finops(),
            "confidence_snapshot": confidence(),
            "readiness_snapshot": readiness(),
            "incident_snapshot": incidents(),
            "task_integrity": integrity,
            "task_projection": projection,
        }
        args.update(overrides)
        return store, build_mission_control(**args)

    def test_all_green_sources_reach_human_review_only(self):
        with tempfile.TemporaryDirectory() as raw:
            store, out = self._build(raw)
            self.assertEqual(out["state"], "READY_FOR_HUMAN_REVIEW")
            self.assertTrue(out["projection_only"])
            self.assertFalse(out["source_of_truth"])
            self.assertFalse(out["raw_payloads_exposed"])
            self.assertFalse(out["merge_authorized"])
            self.assertFalse(out["deploy_authorized"])
            self.assertFalse(out["worker_arming_authorized"])
            self.assertFalse(out["provider_activation_authorized"])
            self.assertFalse(out["real_trading_authorized"])
            self.assertFalse(out["payment_authorized"])
            self.assertFalse(out["executes_action"])
            store.close()

    def test_finops_cross_scope_blocks_entire_projection(self):
        with tempfile.TemporaryDirectory() as raw:
            row = finops()
            row["scope"] = {**SCOPE, "tenant_id": "tenant-b"}
            store, out = self._build(raw, finops_snapshot=row)
            self.assertEqual(out["state"], "BLOCKED")
            self.assertIn("FINOPS_SCOPE_MISMATCH", out["blockers"])
            store.close()

    def test_readiness_cross_scope_blocks(self):
        with tempfile.TemporaryDirectory() as raw:
            row = readiness()
            row["scope"] = {**SCOPE, "workspace_id": "ws-b"}
            store, out = self._build(raw, readiness_snapshot=row)
            self.assertIn("READINESS_SCOPE_MISMATCH", out["blockers"])
            store.close()

    def test_task_repository_cross_scope_blocks(self):
        with tempfile.TemporaryDirectory() as raw:
            store = SQLiteChatStore(Path(raw) / "chat.sqlite3")
            foreign_scope = Scope("owner-a", "tenant-b", "ws-a")
            repo = DurableTaskRepository(store, foreign_scope)
            integrity = repo.integrity_report()
            projection = repo.checkpoint_projection()
            out = build_mission_control(
                trusted_scope=SCOPE,
                health_snapshot=health(),
                finops_snapshot=finops(),
                confidence_snapshot=confidence(),
                readiness_snapshot=readiness(),
                incident_snapshot=incidents(),
                task_integrity=integrity,
                task_projection=projection,
            )
            self.assertEqual(out["state"], "BLOCKED")
            self.assertIn("TASK_SCOPE_MISMATCH", out["blockers"])
            store.close()

    def test_task_projection_digest_mismatch_blocks(self):
        with tempfile.TemporaryDirectory() as raw:
            store, integrity, projection = self._tasks(raw)
            projection = deepcopy(projection)
            projection["repository_digest"] = "0" * 64
            out = build_mission_control(
                trusted_scope=SCOPE,
                health_snapshot=health(),
                finops_snapshot=finops(),
                confidence_snapshot=confidence(),
                readiness_snapshot=readiness(),
                incident_snapshot=incidents(),
                task_integrity=integrity,
                task_projection=projection,
            )
            self.assertIn("TASK_REPOSITORY_DIGEST_MISMATCH", out["blockers"])
            store.close()

    def test_critical_incident_blocks_but_noncritical_incident_only_degrades(self):
        with tempfile.TemporaryDirectory() as raw:
            store, blocked = self._build(raw, incident_snapshot=incidents(critical=True))
            self.assertEqual(blocked["state"], "BLOCKED")
            self.assertIn("CRITICAL_INCIDENT_OPEN", blocked["blockers"])
            store.close()
        with tempfile.TemporaryDirectory() as raw:
            store, degraded = self._build(raw, incident_snapshot=incidents(high=True))
            self.assertEqual(degraded["state"], "DEGRADED")
            self.assertIn("INCIDENTS_OPEN", degraded["degrade_reasons"])
            store.close()

    def test_degraded_health_finops_or_missing_confidence_evidence_degrades(self):
        for field, value in (
            ("health_snapshot", health("DEGRADED")),
            ("finops_snapshot", finops("DEGRADE")),
            ("confidence_snapshot", confidence("NEEDS_EVIDENCE")),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as raw:
                store, out = self._build(raw, **{field: value})
                self.assertEqual(out["state"], "DEGRADED")
                store.close()

    def test_blocked_health_finops_confidence_or_readiness_blocks(self):
        cases = (
            ("health_snapshot", health("BLOCKED")),
            ("finops_snapshot", finops("BLOCK")),
            ("confidence_snapshot", confidence("BLOCKED")),
            ("readiness_snapshot", readiness("BLOCKED")),
        )
        for field, value in cases:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as raw:
                store, out = self._build(raw, **{field: value})
                self.assertEqual(out["state"], "BLOCKED")
                store.close()

    def test_unsafe_upstream_action_claim_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            row = finops(executes_action=True)
            store, out = self._build(raw, finops_snapshot=row)
            self.assertIn("FINOPS_UNSAFE_FIELD:executes_action", out["blockers"])
            self.assertFalse(out["executes_action"])
            store.close()

    def test_raw_task_payload_is_not_exposed_in_mission_control_view(self):
        with tempfile.TemporaryDirectory() as raw:
            store, out = self._build(raw)
            rendered = repr(out)
            self.assertNotIn("Mission Control task", rendered)
            self.assertNotIn("read-only projection", rendered)
            self.assertIn("repository_digest", rendered)
            store.close()

    def test_malformed_sources_fail_closed_without_exception(self):
        out = build_mission_control(
            trusted_scope=["bad"],
            health_snapshot="bad",
            finops_snapshot="bad",
            confidence_snapshot="bad",
            readiness_snapshot="bad",
            incident_snapshot="bad",
            task_integrity="bad",
            task_projection="bad",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("TRUSTED_SCOPE_REQUIRED", out["blockers"])

    def test_contract_is_projection_only(self):
        contract = mission_control_contract()
        self.assertFalse(contract["source_of_truth"])
        self.assertTrue(contract["projection_only"])
        self.assertFalse(contract["raw_payloads_exposed"])
        self.assertFalse(contract["automatic_repair"])
        self.assertFalse(contract["automatic_incident_control"])
        self.assertFalse(contract["automatic_task_transition"])
        self.assertFalse(contract["executes_action"])


if __name__ == "__main__":
    unittest.main()
