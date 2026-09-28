"""Independent application-core regressions; no network, model or physical probe."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import ast
import json
import tempfile
import unittest
from unittest.mock import patch

from atlasquant_aion_core_intelligence.adapters import attach_checkpoint, propose_legacy_memory
from atlasquant_aion_core_intelligence.administration import observed_status
from atlasquant_aion_core_intelligence.approval import Action, ApprovalGate
from atlasquant_aion_core_intelligence.context import Context, Domain
from atlasquant_aion_core_intelligence.developer import analyze, compare
from atlasquant_aion_core_intelligence.evidence import Evidence, Origin, digest, safe_text
from atlasquant_aion_core_intelligence.registry import Registry, SPECS
from atlasquant_aion_core_intelligence.research import synthesize
from atlasquant_aion_core_intelligence.router import route
from atlasquant_aion_core_intelligence.service import AionCore, ScopedEvidence
from atlasquant_aion_core_intelligence.store import CoreStore, ConflictError, memory_subject


NOW = datetime(2026, 9, 28, 0, 0, tzinfo=timezone.utc)


def ctx(domain=Domain.ADMIN, **overrides):
    return replace(Context("tenant-a", "workspace-a", "human-a", "task-a", domain, "ADMIN"), **overrides)


def observed(claim="health", value="HEALTHY", **overrides):
    return replace(Evidence(claim, value, Origin.SYSTEM_OBSERVED, "test-observer",
                   "evidence:fixture:1", NOW.isoformat(), 60), **overrides)


class BoundHumanAdapter:
    """Test-only host session verifier, not included in production modules."""
    def __init__(self):
        self.receipts = {}

    def issue(self, context, request, decision="APPROVED"):
        receipt = "receipt-" + request["approval_id"]
        self.receipts[receipt] = (context.key, request["approval_id"], request["subject_digest"], request["action"], decision)
        return receipt

    def verify(self, *, context, approval_id, subject_digest, action, decision, receipt):
        expected = (context.key, approval_id, subject_digest, action, decision)
        return context.actor_id if self.receipts.get(receipt) == expected else None


class CoreCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "checkpoint.sqlite"
        self.store = CoreStore(self.path)
        self.humans = BoundHumanAdapter()
        self.core = AionCore(self.store, human_adapter=self.humans, clock=lambda: NOW)
        self.context = ctx()

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def remember(self, **overrides):
        values = dict(kind="DECISION", text="Manter Central Principal", origin=Origin.INFERRED,
                      source="analysis", evidence_refs=("evidence:analysis:1",),
                      expected_revision=self.store.revision(self.context))
        values.update(overrides)
        return self.core.remember(self.context, **values)

    def approve_memory(self, subject):
        request = self.core.approvals.request(self.context, Action.MEMORY_DECISION, subject, NOW)
        receipt = self.humans.issue(self.context, request)
        return self.core.approvals.decide(self.context, request["approval_id"], "APPROVED", receipt, NOW)


class RoutingTests(CoreCase):
    def test_requested_examples_route_correctly(self):
        cases = [("AION, qual o estado do sistema?", Domain.ADMIN, "ADMINISTRATION"),
                 ("O que decidimos sobre a Central Principal?", Domain.ADMIN, "MEMORY"),
                 ("Analise este código", Domain.DEVELOPER, "DEVELOPER"),
                 ("Pesquise este assunto", Domain.RESEARCH, "RESEARCH"),
                 ("Crie um roteiro", Domain.CONTENT, "CONTENT")]
        for intent, domain, capability in cases:
            with self.subTest(intent=intent):
                result = self.core.handle(intent, ctx(domain))
                self.assertEqual(result["route"]["capability"], capability)
                self.assertEqual(result["status"], "COMPLETED")
                self.assertFalse(result["execution_authorized"])

    def test_registry_contains_all_capabilities_and_reasons(self):
        rows = self.core.registry.snapshot()
        self.assertEqual(len(rows), 11)
        self.assertEqual({r["name"] for r in rows}, {x.name for x in SPECS})
        self.assertTrue(all(r["reason"] and "dependencies" in r for r in rows))
        self.assertTrue(all(not r["external_integration_active"] for r in rows))

    def test_missing_voice_adapter_does_not_claim_active(self):
        result = self.core.handle("Transcrever áudio", self.context)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["route"]["reason"], "ADAPTER_NOT_CONNECTED")

    def test_scheduler_not_connected(self):
        self.assertFalse(self.core.registry.get("AUTOMATION")["available"])

    def test_no_checkpoint_never_falls_back_to_persisted_claim(self):
        core = AionCore(clock=lambda: NOW)
        self.assertEqual(core.handle("O que decidimos?", self.context)["status"], "UNAVAILABLE")
        with self.assertRaises(ValueError):
            core.remember(self.context, kind="DECISION", text="x", origin=Origin.UNKNOWN,
                          source="UNKNOWN", expected_revision=0)

    def test_future_domains_are_disabled(self):
        for domain, name in [(Domain.BUSINESS, "BUSINESS_FUTURE"), (Domain.TRADER, "TRADER_FUTURE"),
                             (Domain.INVESTMENTS, "INVESTMENTS_FUTURE")]:
            with self.subTest(domain=domain):
                self.assertFalse(self.core.registry.get(name)["available"])
                self.assertEqual(self.core.handle("estado do sistema", ctx(domain))["status"], "UNAVAILABLE")
                self.assertEqual(self.core.handle("AION", self.context, capability=name)["status"], "UNAVAILABLE")

    def test_unknown_intent_is_not_arbitrary_fallback(self):
        result = self.core.handle("xyzzy", self.context)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertIsNone(result["route"]["capability"])

    def test_unknown_explicit_capability_fails_closed(self):
        self.assertEqual(self.core.handle("codigo", self.context, capability="NOT_REAL")["status"], "UNAVAILABLE")

    def test_ambiguous_intent_requires_clarification(self):
        result = self.core.handle("codigo roteiro", self.context)
        self.assertEqual(result["status"], "CLARIFICATION_REQUIRED")
        self.assertIsNone(result["payload"])

    def test_cross_domain_requires_explicit_context_switch(self):
        result = self.core.handle("Analise este código", self.context)
        self.assertEqual(result["status"], "CONTEXT_SWITCH_REQUIRED")
        self.assertEqual(result["route"]["required_context"], "DEVELOPER")
        self.assertIsNone(result["payload"])

    def test_admin_developer_content_roles_are_enforced(self):
        for name, domain in [("ADMINISTRATION", Domain.ADMIN), ("DEVELOPER", Domain.DEVELOPER), ("CONTENT", Domain.CONTENT)]:
            with self.subTest(capability=name):
                result = self.core.handle("AION", ctx(domain, role="USER"), capability=name)
                self.assertEqual(result["status"], "DENIED")

    def test_context_validation_does_not_default_unknown_domain(self):
        with self.assertRaises(ValueError):
            ctx(domain="TRADER")
        with self.assertRaises(ValueError):
            ctx(task_id="../other")

    def test_legacy_registry_and_flags_are_not_mutated(self):
        from atlasquant_aion_capabilities import default_registry, capability_feature_flags
        before = [x.as_dict() for x in default_registry().list()]
        self.core.handle("estado do sistema", self.context)
        self.assertEqual(before, [x.as_dict() for x in default_registry().list()])
        self.assertFalse(capability_feature_flags()["REAL_TRADING_ENABLED"])


class EvidenceTests(unittest.TestCase):
    def test_unknown_never_becomes_confirmed(self):
        report = synthesize("Pesquise", (observed(origin=Origin.UNKNOWN),), NOW)
        self.assertEqual(report["facts"], [])
        self.assertEqual(report["unknown"][0]["truth_state"], "UNKNOWN")

    def test_inference_remains_inference(self):
        report = synthesize("Pesquise", (observed(origin=Origin.INFERRED),), NOW)
        self.assertEqual(len(report["inferences"]), 1)
        self.assertEqual(report["facts"], [])

    def test_missing_source_or_reference_cannot_confirm(self):
        for change in ({"source": "UNKNOWN"}, {"source_ref": "UNKNOWN"}, {"source_ref": "token=abc"}):
            with self.subTest(change=change):
                self.assertEqual(synthesize("Pesquise", (observed(**change),), NOW)["facts"], [])

    def test_stale_temporal_evidence_is_not_current_fact(self):
        report = synthesize("Estado atual", (observed(observed_at=(NOW - timedelta(seconds=61)).isoformat()),), NOW)
        self.assertEqual(report["facts"], [])
        self.assertEqual(report["freshness"], "STALE")

    def test_temporal_timestamp_and_ttl_are_required(self):
        for changes in ({"observed_at": None}, {"ttl_seconds": None}):
            self.assertEqual(synthesize("Agora", (observed(**changes),), NOW)["facts"], [])

    def test_future_timestamp_even_for_stable_claim_is_unknown(self):
        e = observed(observed_at=(NOW + timedelta(seconds=1)).isoformat(), time_sensitive=False)
        self.assertEqual(synthesize("Pesquise", (e,), NOW)["facts"], [])

    def test_conflicting_sources_are_preserved_not_selected(self):
        report = synthesize("Saude", (observed(), observed(value="FAILED", source="other")), NOW)
        self.assertEqual(report["status"], "CONFLICT")
        self.assertEqual(report["facts"], [])
        self.assertEqual(len(report["unknown"]), 2)

    def test_fact_has_source_timestamp_freshness_and_uncertainty(self):
        row = synthesize("Saude", (observed(),), NOW)["facts"][0]
        for key in ("source", "source_ref", "timestamp", "freshness", "uncertainty"):
            self.assertTrue(row[key])

    def test_evidence_inventory_does_not_claim_answered_question(self):
        self.assertFalse(synthesize("Pergunta diferente", (observed(),), NOW)["answers_user_question"])

    def test_user_approval_is_not_factual_observation(self):
        with self.assertRaises(ValueError):
            observed(origin=Origin.USER_APPROVED)

    def test_invalid_timestamp_and_numeric_types_fail_closed(self):
        for overrides in ({"observed_at": "2026-09-28T00:00:00"}, {"ttl_seconds": True},
                          {"ttl_seconds": -1}, {"time_sensitive": "false"}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                observed(**overrides)

    def test_unrelated_status_evidence_is_not_reused(self):
        self.assertEqual(observed_status("tests", (observed(),), NOW)["state"], "UNKNOWN")


class MemoryTests(CoreCase):
    def test_inference_cannot_appear_in_approved_decisions(self):
        row = self.remember()
        report = self.core.handle("O que decidimos?", self.context)["payload"]
        self.assertEqual(report["approved_decisions"], [])
        self.assertEqual(row["origin"], "INFERRED")

    def test_direct_user_approved_write_without_receipt_is_rejected(self):
        with self.assertRaises(ValueError):
            self.remember(origin=Origin.USER_APPROVED)
        self.assertEqual(self.store.revision(self.context), 0)

    def test_unknown_record_preserves_unknown(self):
        row = self.remember(origin=Origin.UNKNOWN, source="UNKNOWN", evidence_refs=())
        self.assertEqual(row["origin"], "UNKNOWN")
        self.assertFalse(row["is_approved_decision"])

    def test_nonunknown_requires_provenance(self):
        with self.assertRaises(ValueError):
            self.remember(evidence_refs=())

    def test_human_approval_bound_to_content_and_consumed_once(self):
        subject = memory_subject("DECISION", "Manter Central Principal", ("evidence:analysis:1",))
        approval = self.approve_memory(subject)
        row = self.remember(origin=Origin.USER_APPROVED, approval_id=approval["approval_id"])
        self.assertTrue(row["is_approved_decision"])
        with self.assertRaises(ValueError):
            self.remember(origin=Origin.USER_APPROVED, approval_id=approval["approval_id"])

    def test_approval_for_other_content_is_rejected(self):
        approval = self.approve_memory(memory_subject("DECISION", "Outro texto", ("evidence:analysis:1",)))
        with self.assertRaises(ValueError):
            self.remember(origin=Origin.USER_APPROVED, approval_id=approval["approval_id"])

    def test_approved_revision_does_not_auto_approve_update(self):
        approval = self.approve_memory(memory_subject("DECISION", "Manter Central Principal", ("evidence:analysis:1",)))
        row = self.remember(origin=Origin.USER_APPROVED, approval_id=approval["approval_id"])
        changed = self.remember(record_id=row["record_id"], text="Nova hipótese")
        self.assertEqual(changed["origin"], "INFERRED")
        self.assertEqual(changed["version"], 2)
        self.assertEqual(self.core.handle("decidimos", self.context)["payload"]["approved_decisions"], [])
        self.assertEqual(self.store.history(self.context)[0]["origin"], "USER_APPROVED")

    def test_every_context_dimension_is_isolated(self):
        row = self.remember()
        variants = [ctx(tenant_id="tenant-b"), ctx(workspace_id="workspace-b"), ctx(actor_id="human-b"),
                    ctx(task_id="task-b"), ctx(Domain.DEVELOPER)]
        for other in variants:
            with self.subTest(scope=other.key):
                self.assertEqual(self.store.read(other, NOW), [])
                with self.assertRaises(ValueError):
                    self.store.append(other, kind="DECISION", text="x", origin=Origin.UNKNOWN,
                                      source="UNKNOWN", now=NOW, expected_revision=0, record_id=row["record_id"])

    def test_persistence_survives_reopening_and_preserves_version(self):
        self.remember()
        with CoreStore(self.path) as reopened:
            self.assertEqual(reopened.revision(self.context), 1)
            self.assertEqual(reopened.read(self.context, NOW)[0]["text"], "Manter Central Principal")

    def test_concurrent_writer_cannot_overwrite_checkpoint(self):
        with CoreStore(self.path) as second:
            revision = second.revision(self.context)
            self.remember()
            with self.assertRaises(ConflictError):
                second.append(self.context, kind="PRIORITY", text="Outra prioridade", origin=Origin.UNKNOWN,
                              source="UNKNOWN", now=NOW, expected_revision=revision)
        self.assertEqual(len(self.store.history(self.context)), 1)

    def test_checkpoint_export_is_scoped_versioned_and_not_remote_persistence(self):
        self.remember()
        export = self.store.checkpoint(self.context, NOW)
        self.assertEqual(export["version"], 1)
        supplied_digest = export.pop("digest")
        self.assertEqual(digest(export), supplied_digest)
        self.assertEqual(export["storage"], "LOCAL_SQLITE")

    def test_legacy_checkpoint_adapter_preserves_other_fields_without_writing(self):
        legacy = {"memory_layers": {"entries": ["old"]}, "security": {"x": 1}}
        out = attach_checkpoint(legacy, self.store.checkpoint(self.context, NOW), self.context)
        self.assertEqual(out["memory_layers"], legacy["memory_layers"])
        self.assertNotIn("aion_core_intelligence_v1", legacy)
        with self.assertRaises(ValueError):
            attach_checkpoint(out, self.store.checkpoint(ctx(task_id="other"), NOW), ctx(task_id="other"))

    def test_legacy_approved_label_does_not_mint_approval(self):
        self.assertEqual(propose_legacy_memory("Aprovado anteriormente", "legacy:1")["origin"], "UNKNOWN")

    def test_future_context_memory_is_disabled(self):
        with self.assertRaises(ValueError):
            self.core.remember(ctx(Domain.BUSINESS), kind="PRIORITY", text="x", origin=Origin.UNKNOWN,
                               source="UNKNOWN", expected_revision=0)


class ApprovalTests(CoreCase):
    def test_sensitive_intent_requires_approval(self):
        result = self.core.handle("Publique este roteiro", ctx(Domain.CONTENT))
        self.assertEqual(result["status"], "APPROVAL_REQUIRED")
        self.assertFalse(result["payload"]["execution_authorized"])

    def test_all_sensitive_action_contracts_stay_nonexecuting(self):
        for action in Action:
            with self.subTest(action=action):
                row = self.core.approvals.request(self.context, action, {"proposal": "x"}, NOW)
                self.assertEqual(row["state"], "PENDING")
                self.assertFalse(row["execution_authorized"])

    def test_approval_has_no_permissive_default_human_adapter(self):
        gate = ApprovalGate(self.store)
        row = gate.request(self.context, Action.DEPLOY, {"revision": "abc"}, NOW)
        with self.assertRaises(ValueError):
            gate.decide(self.context, row["approval_id"], "APPROVED", "yes", NOW)

    def test_wrong_human_receipt_is_rejected(self):
        row = self.core.approvals.request(self.context, Action.DEPLOY, {}, NOW)
        with self.assertRaises(ValueError):
            self.core.approvals.decide(self.context, row["approval_id"], "APPROVED", "fake", NOW)

    def test_receipt_cannot_replay_for_other_action_or_decision(self):
        one = self.core.approvals.request(self.context, Action.DEPLOY, {}, NOW)
        two = self.core.approvals.request(self.context, Action.PUBLICATION, {}, NOW)
        receipt = self.humans.issue(self.context, one)
        for request_id, decision in [(two["approval_id"], "APPROVED"), (one["approval_id"], "REJECTED")]:
            with self.assertRaises(ValueError):
                self.core.approvals.decide(self.context, request_id, decision, receipt, NOW)

    def test_approved_is_still_not_execution_authority(self):
        row = self.core.approvals.request(self.context, Action.DEPLOY, {}, NOW)
        receipt = self.humans.issue(self.context, row)
        approved = self.core.approvals.decide(self.context, row["approval_id"], "APPROVED", receipt, NOW)
        self.assertEqual(approved["state"], "APPROVED")
        self.assertFalse(approved["execution_authorized"])
        self.assertFalse(approved["external_action_executed"])

    def test_expired_approval_cannot_be_approved(self):
        row = self.core.approvals.request(self.context, Action.DEPLOY, {}, NOW, ttl_seconds=1)
        receipt = self.humans.issue(self.context, row)
        with self.assertRaises(ValueError):
            self.core.approvals.decide(self.context, row["approval_id"], "APPROVED", receipt, NOW + timedelta(seconds=1))

    def test_approval_context_isolation(self):
        row = self.core.approvals.request(self.context, Action.DEPLOY, {}, NOW)
        self.assertIsNone(self.core.approvals.get(ctx(task_id="other"), row["approval_id"], NOW))

    def test_duplicate_human_decision_rejected(self):
        row = self.core.approvals.request(self.context, Action.DEPLOY, {}, NOW)
        receipt = self.humans.issue(self.context, row)
        self.core.approvals.decide(self.context, row["approval_id"], "APPROVED", receipt, NOW)
        with self.assertRaises(ValueError):
            self.core.approvals.decide(self.context, row["approval_id"], "APPROVED", receipt, NOW)

    def test_ambiguous_sensitive_action_not_silently_chosen(self):
        self.assertEqual(self.core.handle("publique e pague", self.context)["status"], "CLARIFICATION_REQUIRED")

    def test_missing_approval_store_is_explicit(self):
        core = AionCore(clock=lambda: NOW)
        self.assertEqual(core.handle("deploy", self.context)["status"], "UNAVAILABLE")


class AdministrationDeveloperTests(CoreCase):
    def test_missing_system_sources_stay_unknown(self):
        result = self.core.handle("estado do sistema", self.context)["payload"]
        self.assertTrue(all(v["state"] == "UNKNOWN" for v in result["system"].values()))
        self.assertEqual(result["checkpoint"]["remote_persistence"], "UNAVAILABLE")

    def test_supplied_pr_build_test_statuses_are_not_invented(self):
        records = tuple(observed(claim=name, value=value) for name, value in [("pr", "DRAFT"), ("build", "FAIL"), ("tests", "PASS")])
        system = self.core.handle("estado do sistema", self.context, evidence=ScopedEvidence(self.context, records))["payload"]["system"]
        self.assertEqual(system["build"]["value"], "FAIL")
        self.assertEqual(system["pr"]["value"], "DRAFT")
        self.assertEqual(system["health"]["state"], "UNKNOWN")

    def test_wrong_evidence_context_is_rejected(self):
        with self.assertRaises(ValueError):
            self.core.handle("estado do sistema", self.context, evidence=ScopedEvidence(ctx(task_id="other"), (observed(),)))

    def test_system_inference_is_never_observed_status(self):
        result = self.core.handle("estado do sistema", self.context,
                                 evidence=ScopedEvidence(self.context, (observed(origin=Origin.INFERRED),)))
        self.assertEqual(result["payload"]["system"]["health"]["state"], "UNKNOWN")

    def test_static_analysis_never_executes_supplied_code(self):
        code = "raise RuntimeError('would execute')\ndef add(a, b):\n    return a+b\n"
        result = self.core.handle("Analise codigo", ctx(Domain.DEVELOPER), source_code=code)
        self.assertIn("add", result["payload"]["analysis"]["symbols"])
        self.assertFalse(result["payload"]["tests_executed"])

    def test_syntax_regression_is_detected(self):
        result = compare("x = 1", "def broken(", (), NOW)
        self.assertEqual(result["regression"], "SYNTAX_REGRESSION")

    def test_missing_test_evidence_never_means_pass(self):
        result = compare("x=1", "x=2", (), NOW)
        self.assertEqual(result["regression"], "UNKNOWN")
        self.assertEqual(result["after_test_evidence"]["state"], "UNKNOWN")

    def test_recorded_test_regression_requires_exact_source_digests(self):
        before, after = "x=1", "x=2"
        records = (observed(claim="tests@" + analyze(before)["source_sha256"], value="PASS"),
                   observed(claim="tests@" + analyze(after)["source_sha256"], value="FAIL"))
        self.assertEqual(compare(before, after, records, NOW)["regression"], "OBSERVED_TEST_REGRESSION")
        self.assertEqual(compare(before, "x=3", records, NOW)["regression"], "UNKNOWN")

    def test_developer_plan_reuses_engine_and_keeps_adapter_unavailable(self):
        result = self.core.handle("Analise codigo", ctx(Domain.DEVELOPER), branch="work/example", baseline_ref="abc123")
        plan = result["payload"]["plan"]
        self.assertEqual(plan["workflow"]["schema"], "ATLASQUANT_AION_DEVELOPER_ENGINE_V1")
        self.assertEqual(plan["security_chain_adapter"], "UNAVAILABLE")

    def test_content_is_unpublished_outline(self):
        result = self.core.handle("Crie um roteiro", ctx(Domain.CONTENT))["payload"]
        self.assertEqual(result["status"], "DRAFT")
        self.assertFalse(result["published"])
        self.assertFalse(result["facts_verified"])


class ObservabilityTests(CoreCase):
    def test_lifecycle_events_and_no_raw_prompt_or_credential(self):
        secret = "api_key=super-sensitive-value"
        self.core.handle("estado do sistema " + secret, self.context)
        events = self.store.events(self.context)
        self.assertTrue({"intent_received", "module_selected", "memory_read", "completed"}.issubset({x["event_type"] for x in events}))
        self.assertNotIn("super-sensitive-value", json.dumps(events))
        self.assertNotIn("estado do sistema", json.dumps(events))

    def test_error_event_contains_no_exception_payload(self):
        with self.assertRaises(ValueError):
            self.core.handle("estado do sistema", self.context, evidence=ScopedEvidence(ctx(task_id="other"), (observed(),)))
        self.assertEqual(self.store.events(self.context)[-1]["event_type"], "error")

    def test_memory_writes_redact_credentials(self):
        row = self.remember(text="password=abc", source="https://user:pass@example.test/path")
        encoded = json.dumps(row)
        self.assertEqual(row["text"], "[REDACTED]")
        self.assertEqual(row["source"], "https://[REDACTED]@example.test/path")
        self.assertNotIn("password=abc", encoded)
        self.assertNotIn("user:pass", encoded)

    def test_multiline_private_key_redacted(self):
        secret = "-----BEGIN " + "PRIVATE KEY-----\nvery-sensitive-key\n-----END " + "PRIVATE KEY-----"
        self.assertNotIn("very-sensitive-key", safe_text(secret))

    def test_event_contexts_do_not_leak(self):
        self.core.handle("estado do sistema", self.context)
        self.assertEqual(self.store.events(ctx(actor_id="other")), [])

    def test_external_network_functions_are_never_called(self):
        with patch("socket.socket", side_effect=AssertionError("network prohibited")), \
             patch("subprocess.Popen", side_effect=AssertionError("process prohibited")):
            for domain, intent in [(Domain.ADMIN, "estado do sistema"), (Domain.RESEARCH, "pesquise assunto"),
                                   (Domain.DEVELOPER, "analise codigo"), (Domain.CONTENT, "crie roteiro")]:
                self.core.handle(intent, ctx(domain))

    def test_security_chain_modules_are_not_imported_by_new_package(self):
        forbidden = ("builder_sandbox", "sandbox_preflight", "patch_validation", "runner_contract",
                     "command_policy", "os_sandbox", "probe_result")
        package = Path(__file__).parent / "atlasquant_aion_core_intelligence"
        for file in package.glob("*.py"):
            tree = ast.parse(file.read_text(encoding="utf-8"))
            imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
            self.assertFalse(any(any(term in name for term in forbidden) for name in imports), file.name)


if __name__ == "__main__":
    unittest.main()
