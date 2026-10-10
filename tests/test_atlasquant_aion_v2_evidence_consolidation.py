"""Offline integration regressions: actual deny caller + exact reference bindings."""
import ast
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import importlib
import json
import os
import subprocess
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from atlasquant_aion_core_intelligence.context import Context, Domain
from atlasquant_aion_v2_autopilot_evidence_guard import guarded_autopilot_evidence_write
from atlasquant_aion_v2_evidence_reconciliation_contract import build_reference_intent, review_reference_observation, MAX_CONTENT_BYTES

ROOT = Path(__file__).resolve().parents[1]


def actual_autopilot_function():
    tree = ast.parse((ROOT / "autopilot_v107.py").read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "persist_decision_evidence")
    ns = {"Any": object, "guarded_autopilot_evidence_write": guarded_autopilot_evidence_write}
    for name in ("build_shadow_batch", "persist_shadow_samples", "record_from_pack", "persist_records"):
        ns[name] = Mock(side_effect=AssertionError("BUILDER_OR_WRITER_CALLED_AFTER_DENIAL"))
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "actual-autopilot", "exec"), ns)
    return ns


class ConsolidatedAutopilotTests(unittest.TestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection", "requests.sessions.Session.request"):
            p = patch(target, side_effect=AssertionError("NETWORK_FORBIDDEN")); p.start(); self.addCleanup(p.stop)

    def run_caller(self, ns):
        result = ns["persist_decision_evidence"]([{"private": "CONTENT_MUST_NOT_LEAK"}],
             engine_version="fixture", repo="fixture/repo", branch="atlasquant-runtime", token="SECRET_MUST_NOT_LEAK")
        for status, sink in zip(result[:2], ("shadow", "flight")):
            self.assertEqual(status["state"], "HARD_DENY")
            self.assertEqual(status["sink"], sink)
            self.assertFalse(status["external_writer_called"])
            self.assertFalse(status["execution_authorized"])
        text = json.dumps(result)
        self.assertNotIn("SECRET_MUST_NOT_LEAK", text)
        self.assertNotIn("CONTENT_MUST_NOT_LEAK", text)
        for name in ("build_shadow_batch", "persist_shadow_samples", "record_from_pack", "persist_records"):
            ns[name].assert_not_called()
        return result

    def test_actual_caller_denies_both_sinks_without_build_or_write(self):
        self.run_caller(actual_autopilot_function())

    def test_reexecution_and_reloaded_guard_still_deny(self):
        ns = actual_autopilot_function()
        self.run_caller(ns); self.run_caller(ns)
        import atlasquant_aion_v2_autopilot_evidence_guard as guard
        ns["guarded_autopilot_evidence_write"] = importlib.reload(guard).guarded_autopilot_evidence_write
        self.run_caller(ns)

    def test_two_concurrent_callers_do_not_write(self):
        ns = actual_autopilot_function()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.run_caller(ns), range(2)))
        self.assertEqual(len(results), 2)

    def test_exception_details_are_redacted_separately_for_both_sinks(self):
        ns = actual_autopilot_function()
        ns["guarded_autopilot_evidence_write"] = Mock(side_effect=RuntimeError("SECRET_MUST_NOT_LEAK CONTENT_MUST_NOT_LEAK"))
        shadow, flight, errors = ns["persist_decision_evidence"]([], engine_version="fixture", repo="fixture/repo", branch="atlasquant-runtime", token="fake")
        self.assertEqual((shadow["reason"], flight["reason"]), ("SHADOW_EXCEPTION", "FLIGHT_EXCEPTION"))
        self.assertEqual((shadow["error"], flight["error"]), ("RuntimeError", "RuntimeError"))
        self.assertNotIn("MUST_NOT_LEAK", json.dumps([shadow, flight, errors]))

    def test_source_has_no_other_shadow_or_flight_write_path(self):
        tree = ast.parse((ROOT / "autopilot_v107.py").read_text(encoding="utf-8"))
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id in {"persist_shadow_samples", "persist_records"}]
        self.assertEqual(len(calls), 2)
        guards = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id == "guarded_autopilot_evidence_write"]
        self.assertEqual(len(guards), 2)
        for call in calls:
            self.assertTrue(any(call in list(ast.walk(k.value)) for g in guards for k in g.keywords
                                if k.arg == "write" and isinstance(k.value, ast.Lambda)))


class EvidenceBindingReferenceTests(unittest.TestCase):
    def setUp(self):
        self.context = Context("tenant-a", "workspace-a", "actor-a", "task-a", Domain.RESEARCH)
        self.raw = b'{"sample_id":"synthetic","value":1}\n'
        self.intent = self.build()

    def build(self, **changes):
        args = dict(context=self.context, repo="fixture/repo", branch="atlasquant-runtime", sink="shadow",
                    exact_content=self.raw, nonce_hex="a" * 64, policy_generation=7)
        args.update(changes)
        return build_reference_intent(**args)

    def review(self, **changes):
        args = dict(expected_intent=self.intent, observed_intent=deepcopy(self.intent), observed_content=self.raw,
                    journal_state="UNKNOWN_OUTCOME", current_generation=7)
        args.update(changes)
        result = review_reference_observation(**args)
        self.assertFalse(result["safe_to_retry"]); self.assertFalse(result["safe_to_resume"])
        self.assertFalse(result["execution_authorized"]); self.assertFalse(result["writer_called"])
        self.assertTrue(result["reconciliation_required"])
        return result

    def test_exact_bytes_match_is_still_pending_without_independent_witness(self):
        result = self.review()
        self.assertEqual(result["state"], "PENDING_RECONCILIATION")
        self.assertTrue(result["content_match_reference_only"])
        self.assertFalse(result["independent_evidence_verified"])
        self.assertFalse(result["human_approval_verified"])

    def test_newline_change_changes_exact_binding(self):
        changed = self.build(exact_content=self.raw.rstrip())
        self.assertNotEqual(changed["content_sha256"], self.intent["content_sha256"])
        self.assertEqual(self.review(observed_intent=changed)["reason"], "OPERATION_OR_SCOPE_MISMATCH")

    def test_new_nonce_does_not_change_semantic_identity(self):
        changed = self.build(nonce_hex="b" * 64)
        self.assertEqual(changed["semantic_id"], self.intent["semantic_id"])
        self.assertNotEqual(changed["operation_id"], self.intent["operation_id"])
        self.assertEqual(self.review(observed_intent=changed)["reason"], "OPERATION_OR_SCOPE_MISMATCH")

    def test_tenant_workspace_actor_task_and_domain_are_separate(self):
        for context in (Context("tenant-b", "workspace-a", "actor-a", "task-a", Domain.RESEARCH),
                        Context("tenant-a", "workspace-b", "actor-a", "task-a", Domain.RESEARCH),
                        Context("tenant-a", "workspace-a", "actor-b", "task-a", Domain.RESEARCH),
                        Context("tenant-a", "workspace-a", "actor-a", "task-b", Domain.RESEARCH),
                        Context("tenant-a", "workspace-a", "actor-a", "task-a", Domain.ADMIN)):
            with self.subTest(context=context.key):
                changed = self.build(context=context)
                self.assertNotEqual(changed["scope_digest"], self.intent["scope_digest"])
                self.assertEqual(self.review(observed_intent=changed)["state"], "HARD_DENY")

    def test_repo_branch_and_sink_swap_blocked(self):
        for changes in ({"repo": "fixture/other"}, {"branch": "other-runtime"}, {"sink": "flight"}):
            with self.subTest(changes=changes):
                self.assertEqual(self.review(observed_intent=self.build(**changes))["state"], "HARD_DENY")

    def test_unknown_read_and_not_found_never_prove_absence(self):
        self.assertEqual(self.review(observed_content=None)["state"], "PENDING_RECONCILIATION")
        self.assertEqual(self.review(observed_content=b'')["state"], "HARD_DENY")

    def test_wrong_sha_or_content_cannot_match(self):
        wrong = deepcopy(self.intent); wrong["blob_sha"] = "b" * 40
        self.assertEqual(self.review(observed_intent=wrong)["reason"], "INVALID_CLOSED_BINDING")
        self.assertEqual(self.review(observed_content=self.raw.replace(b'1', b'2'))["reason"], "CONTENT_MISMATCH")

    def test_closed_schema_rejects_implicit_approval_flag(self):
        extra = deepcopy(self.intent); extra["approved"] = True
        self.assertEqual(self.review(observed_intent=extra)["state"], "HARD_DENY")

    def test_rollback_generation_and_bool_generation_rejected(self):
        for generation in (6, 8, True, None):
            with self.subTest(generation=generation):
                self.assertEqual(self.review(current_generation=generation)["reason"], "GENERATION_MISMATCH")

    def test_stale_generation_matching_both_sides_still_has_no_authority(self):
        old = self.build(policy_generation=1)
        result = self.review(expected_intent=old, observed_intent=old, current_generation=1)
        self.assertTrue(result["content_match_reference_only"])
        self.assertFalse(result["durable_admission_verified"])

    def test_saved_already_present_or_prepared_not_reconciliation(self):
        for state in ("SAVED", "ALREADY_PRESENT", "PREPARED", "LOADED"):
            with self.subTest(state=state):
                self.assertEqual(self.review(journal_state=state)["reason"], "UNCERTAIN_JOURNAL_STATE_REQUIRED")

    def test_no_unbounded_iterable_accepted_as_content(self):
        for content in (iter([self.raw]), "text", b"", b"x" * (MAX_CONTENT_BYTES + 1)):
            with self.subTest(kind=type(content).__name__):
                with self.assertRaises(ValueError): self.build(exact_content=content)

    def test_changed_bound_digest_or_scope_corruption_blocks(self):
        for key in ("scope_digest", "content_sha256", "operation_id", "semantic_id"):
            with self.subTest(key=key):
                wrong = deepcopy(self.intent); wrong[key] = "0" * 64
                self.assertEqual(self.review(observed_intent=wrong)["state"], "HARD_DENY")


class JournalProcessReferenceTests(unittest.TestCase):
    CHILD = """
import json, socket, sys
from atlasquant_aion_v2_one_shot_unknown_outcome_journal_reference import ReferenceOneShotUnknownOutcomeJournal
socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError('NETWORK_FORBIDDEN'))
data=json.loads(sys.stdin.read())
journal=ReferenceOneShotUnknownOutcomeJournal(data['path'],config=data['config'])
try:
 result=journal.claim_reference_only(intent=data['intent'])
 assert not result['network_invocation_authorized'] and not result['paid_dispatch_authorized']
 print(json.dumps({'state':result['state'],'safe_to_resume':result['safe_to_resume']}))
finally:
 journal.close()
"""

    def setUp(self):
        # Reuse the existing disposable fixture and existing reference journal.
        from test_atlasquant_aion_v2_one_shot_unknown_outcome_journal_reference import OneShotUnknownOutcomeTests
        self.fixture = OneShotUnknownOutcomeTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.fixture.prepare()

    def child_claim(self):
        data = dict(path=str(self.fixture.path), config=self.fixture.config, intent=self.fixture.intent)
        env = {k: v for k, v in os.environ.items()
               if not any(word in k.upper() for word in ('TOKEN','SECRET','API_KEY','PASSWORD'))}
        process = subprocess.run([sys.executable, '-B', '-c', self.CHILD], input=json.dumps(data),
                                 cwd=ROOT, env=env, text=True, capture_output=True, timeout=20)
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertFalse(result['safe_to_resume'])
        return result['state']

    def test_actual_new_python_process_does_not_reclaim_uncertain_intent(self):
        self.fixture.claim()
        self.fixture.journal.mark_unknown_reference_only(nonce_hex=self.fixture.intent['nonce_hex'])
        self.assertEqual(self.child_claim(), 'REPLAY_BLOCKED_NO_SECOND_DISPATCH')

    def test_two_actual_python_processes_only_one_reference_claim(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.child_claim(), range(2)))
        self.assertEqual(sorted(results), sorted(['LOCAL_REFERENCE_CLAIM_RECORDED_UNTRUSTED',
                                                  'REPLAY_BLOCKED_NO_SECOND_DISPATCH']))


if __name__ == "__main__":
    unittest.main()
