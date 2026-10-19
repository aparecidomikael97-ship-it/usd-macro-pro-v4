"""Mutation tests proving critical staging source changes trigger CI failure.

This is strictly a STATIC REGRESSION SENTINEL, never source authenticity,
runtime witness enrollment, formal proof, independent ownership or GO.
The mutations are in-memory AST only; never modify the checkout.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

import atlasquant_aion_p0_h0_boundary_drift_sentinel_lab as sentinel

ROOT = Path(__file__).resolve().parent


def sources() -> dict[str, str]:
    return {name: (ROOT / name).read_text(encoding="utf-8") for name in sentinel.WATCHED}


def direct_return(fn: ast.FunctionDef, reason: str) -> ast.Return:
    return next(
        n for n in fn.body if isinstance(n, ast.Return)
        and isinstance(n.value, ast.Dict)
        and any(
            isinstance(k, ast.Constant) and k.value == "reason"
            and isinstance(v, ast.Constant) and v.value == reason
            for k, v in zip(n.value.keys, n.value.values)
        )
    )


def mutation(file: str, edit) -> dict[str, str]:
    data = sources()
    tree = ast.parse(data[file])
    edit(tree)
    ast.fix_missing_locations(tree)
    data[file] = ast.unparse(tree)
    return data


class P0BoundarySourceMutationTests(unittest.TestCase):
    def expect(self, file, edit, code):
        data = mutation(file, edit)
        issues = sentinel.verify_p0_staging_boundaries(data)
        self.assertIn(code, issues, issues)
        self.assertNotIn("SOURCE_NOT_PARSEABLE:" + file, issues)

    def test_01_unmodified_checkout_structural_contracts_observed(self):
        self.assertEqual(sentinel.verify_p0_staging_boundaries(sources()), ())
        self.assertEqual(sentinel.verify_checkout(ROOT), ())

    def test_02_worker_writer_first_return_removed_is_detected(self):
        file = "atlasquant_aion_global_worker.py"
        def edit(t):
            fn = sentinel._function(t, "_persist_runtime_checkpoint_cas")
            fn.body.remove(direct_return(fn, sentinel.BLOCK_SOURCE))
        self.expect(file, edit, "WORKER_WRITER_NOT_UNCONDITIONALLY_BLOCKED")

    def test_03_worker_entrypoint_cas_denial_removed_is_detected(self):
        file = "atlasquant_aion_global_worker.py"
        def edit(t):
            fn = sentinel._function(t, "run_global_worker_once")
            fn.body.remove(direct_return(fn, sentinel.BLOCK_SOURCE))
        self.expect(file, edit, "WORKER_NO_WITNESS_GATE_MISSING_OR_AFTER_EFFECT_BOUNDARY")

    def test_04_worker_entrypoint_gate_moved_after_first_cas_is_detected(self):
        file = "atlasquant_aion_global_worker.py"
        def edit(t):
            fn = sentinel._function(t, "run_global_worker_once")
            guard = direct_return(fn, sentinel.BLOCK_SOURCE)
            fn.body.remove(guard)
            cas_index = next(i for i, node in enumerate(fn.body)
                             if sentinel._calls(node, "_persist_runtime_checkpoint_cas"))
            fn.body.insert(cas_index + 1, guard)
        self.expect(file, edit, "WORKER_NO_WITNESS_GATE_MISSING_OR_AFTER_EFFECT_BOUNDARY")

    def test_05_outbox_send_gate_removed_is_detected(self):
        file = "atlasquant_aion_execution_outbox.py"
        def edit(t):
            fn = sentinel._function(t, "dispatch_claimed", "ExecutionOutbox")
            for n in sentinel._direct_raise(fn, sentinel.BLOCK_PRODUCER):
                fn.body.remove(n)
        self.expect(file, edit, "OUTBOX_DISPATCH_NO_PRODUCER_HARDSTOP_MISSING")

    def test_06_outbox_reconcile_gate_removed_is_detected(self):
        file = "atlasquant_aion_execution_outbox.py"
        def edit(t):
            fn = sentinel._function(t, "reconcile", "ExecutionOutbox")
            for n in sentinel._direct_raise(fn, sentinel.BLOCK_PRODUCER):
                fn.body.remove(n)
        self.expect(file, edit, "OUTBOX_RECONCILE_NO_PRODUCER_HARDSTOP_MISSING")

    def test_07_restore_checks_of_source_removed_are_detected(self):
        file = "aion_chat/store.py"
        def edit(t):
            fn = sentinel._function(t, "restore_from_backup", "SQLiteChatStore")
            fn.body[:] = [
                n for n in fn.body
                if not (isinstance(n, ast.Expr)
                        and sentinel._calls(n, "_require_chat_only_restore_file"))
            ]
            # The inner temporary-file check remains; source preflight is gone.
        self.expect(file, edit, "SQLITE_RESTORE_MISSING_SOURCE_TARGET_RECHECK_BEFORE_REPLACE")

    def test_08_restore_checks_of_target_removed_are_detected(self):
        file = "aion_chat/store.py"
        def edit(t):
            fn = sentinel._function(t, "restore_from_backup", "SQLiteChatStore")
            fn.body[:] = [
                n for n in fn.body
                if not (isinstance(n, ast.Expr)
                        and sentinel._calls(n, "_require_restore_target_safe"))
            ]
        self.expect(file, edit, "SQLITE_RESTORE_MISSING_SOURCE_TARGET_RECHECK_BEFORE_REPLACE")

    def test_09_restore_independent_witness_denial_removed_is_detected(self):
        file = "aion_chat/store.py"
        def edit(t):
            fn = sentinel._function(t, "_require_chat_only_restore_file")
            for n in ast.walk(fn):
                if isinstance(n, ast.Constant) and n.value == sentinel.BLOCK_RESTORE:
                    n.value = "ALLOWED_UNSAFE"
        self.expect(file, edit, "SQLITE_RESTORE_EXECUTION_LEDGER_REFUSAL_MISSING")

    def test_10_readiness_witness_denial_removed_is_detected(self):
        file = "atlasquant_aion_global_worker_readiness.py"
        def edit(t):
            fn = sentinel._function(t, "activation_readiness_snapshot")
            for n in fn.body:
                if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == "blockers":
                    n.value = ast.List(elts=[], ctx=ast.Load())
        self.expect(file, edit, "READINESS_INDEPENDENT_SOURCE_BLOCKER_MISSING")

    def test_11_h0_local_signature_flip_to_verified_is_detected(self):
        file = "atlasquant_aion_p0_h0_sqlite_startup_observer_lab.py"
        def edit(t):
            fn = sentinel._function(t, "observe_h0_sqlite_first_effect_lab")
            for n in fn.body:
                if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == "report":
                    d = n.value
                    for key, value in zip(d.keys, d.values):
                        if isinstance(key, ast.Constant) and key.value == "independent_witness_authenticated":
                            value.value = True
        self.expect(file, edit, "H0_FALSE_AUTHORITY_CONTRACT_CHANGED:independent_witness_authenticated")

    def test_12_h0_local_ready_state_is_detected(self):
        file = "atlasquant_aion_p0_h0_sqlite_startup_observer_lab.py"
        def edit(t):
            fn = sentinel._function(t, "observe_h0_sqlite_first_effect_lab")
            for n in fn.body:
                if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == "report":
                    d = n.value
                    for key, value in zip(d.keys, d.values):
                        if isinstance(key, ast.Constant) and key.value == "state":
                            value.value = "READY"
        self.expect(file, edit, "H0_OBSERVER_NOT_BLOCKED_BY_DEFAULT")

    def test_13_h0_cli_returning_success_is_detected(self):
        file = "atlasquant_aion_p0_h0_sqlite_startup_observer_lab.py"
        def edit(t):
            fn = sentinel._function(t, "main")
            for n in fn.body:
                if isinstance(n, ast.Return) and isinstance(n.value, ast.Constant) and n.value.value == 2:
                    n.value.value = 0
        self.expect(file, edit, "H0_CLI_NO_GO_EXIT_CODE_MISSING")

    def test_14_missing_source_never_silently_passes(self):
        data = sources()
        del data["atlasquant_aion_execution_outbox.py"]
        result = sentinel.verify_p0_staging_boundaries(data)
        self.assertIn("SOURCE_MISSING:atlasquant_aion_execution_outbox.py", result)

    def test_15_comment_claiming_enrollment_cannot_replace_actual_gate(self):
        file = "atlasquant_aion_global_worker.py"
        def edit(t):
            fn = sentinel._function(t, "_persist_runtime_checkpoint_cas")
            fn.body.remove(direct_return(fn, sentinel.BLOCK_SOURCE))
            # A constant with the right string does NOT restore the gate.
            fn.body.insert(1, ast.Expr(value=ast.Constant(value=sentinel.BLOCK_SOURCE)))
        self.expect(file, edit, "WORKER_WRITER_NOT_UNCONDITIONALLY_BLOCKED")


if __name__ == "__main__":
    unittest.main()
