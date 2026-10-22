"""A154 real Checkpoint Mestre writer syntax mutations (offline, no I/O).

Checks the production SOURCE AST, never executes checkpoint product code,
never imports requests, never writes or calls GitHub. Positive means only
that the current DENY-ONLY lexical contract matches; P0 remains HARD NO-GO.
"""
import ast
from pathlib import Path
import unittest

from tools.aion_p0_a154_runtime_writer_deny_ast_lab import (
    GUARD_NAME, REQUIRED_DENIAL_VALUES, REQUIRED_HELPER_VALUES,
    ROOT, RUNTIME_SOURCE, inspect_runtime_writer_source,
)
from tools.aion_p0_checkpoint_write_surface_audit import guard_shape

class A154RuntimeWriterDenyOnlyASTLAB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = RUNTIME_SOURCE.read_text(encoding="utf-8")

    def report(self, source=None):
        return inspect_runtime_writer_source(
            self.source if source is None else source
        )

    def mutated(self, func):
        tree = ast.parse(self.source)
        func(tree)
        ast.fix_missing_locations(tree)
        return ast.unparse(tree)

    def fn(self, tree, name="save_runtime_checkpoint"):
        found = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name == name]
        self.assertEqual(len(found), 1)
        return found[0]

    def target_pair(self, writer):
        for i, st in enumerate(writer.body):
            if (isinstance(st, ast.Assign)
                and len(st.targets) == 1
                and isinstance(st.targets[0], ast.Name)
                and st.targets[0].id == "admission"):
                return i, st, writer.body[i+1]
        self.fail("expected writer witness admission AST assignment")

    def return_dict(self, statement):
        self.assertIsInstance(statement, ast.Return)
        self.assertIsInstance(statement.value, ast.Dict)
        return statement.value

    def set_field(self, node, field, value):
        self.assertIsInstance(node, ast.Dict)
        for k, v in zip(node.keys, node.values):
            if isinstance(k, ast.Constant) and k.value == field:
                v.value = value
                return
        self.fail("field absent: " + field)

    def helper_return(self, tree):
        helper = self.fn(tree, "_require_independent_runtime_write_witness")
        returns = [n for n in helper.body if isinstance(n, ast.Return)]
        self.assertEqual(len(returns), 1)
        return returns[0]

    def deny_return(self, tree):
        writer = self.fn(tree)
        _, _, denial = self.target_pair(writer)
        self.assertIsInstance(denial, ast.If)
        return self.return_dict(denial.body[0])

    def expect(self, source, reason):
        report = self.report(source)
        self.assertFalse(report["writer_deny_shape_intact_lab"], report)
        self.assertTrue(any(reason in x for x in report["findings"]), report)
        self.assertFalse(report["github_checkpoint_write_authorized"])
        self.assertFalse(report["automatic_resend_allowed"])
        self.assertEqual(report["homologated_p0_count"], 0)

    def test_01_actual_writer_guard_shape_is_intact_but_never_authorized(self):
        report = self.report()
        self.assertTrue(report["writer_deny_shape_intact_lab"], report)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["verdict"], "HARD_NO_GO_RUNTIME_WITNESS_UNENROLLED")
        for key in ("independent_runtime_witness_enrolled",
                    "actual_runtime_effects_proven_safe",
                    "github_checkpoint_write_authorized",
                    "worker_allowed", "automatic_resend_allowed"):
            self.assertIs(report[key], False)
        self.assertEqual(report["homologated_p0_count"], 0)

    def test_02_old_A136_line_order_alone_ignores_inverted_denial(self):
        source = self.source.replace(
            'if admission.get("allowed") is not True:',
            'if admission.get("allowed") is True:'
        )
        self.assertNotEqual(source, self.source)
        # Prove A154 closes a gap in the old AST guard's shape-only claim.
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as folder:
            path = Path(folder) / "atlasquant_aion_memory.py"
            path.write_text(source, encoding="utf-8")
            self.assertTrue(guard_shape(Path(folder))["ok"])
        self.expect(source, "NEGATIVE_ADMISSION_CONDITION_ALTERED")

    def test_03_helper_allowed_true_mutation_rejected(self):
        def change(t):
            self.set_field(self.return_dict(self.helper_return(t)), "allowed", True)
        self.expect(self.mutated(change), "INDEPENDENT_WITNESS_HELPER_NOT_UNCONDITIONALLY_DENY_ONLY")

    def test_04_helper_unavailable_status_rejected(self):
        def change(t):
            self.set_field(self.return_dict(self.helper_return(t)), "status", "READY")
        self.expect(self.mutated(change), "INDEPENDENT_WITNESS_HELPER_NOT_UNCONDITIONALLY_DENY_ONLY")

    def test_05_helper_enrolled_true_rejected(self):
        def change(t):
            self.set_field(self.return_dict(self.helper_return(t)), "independent_witness_enrolled", True)
        self.expect(self.mutated(change), "INDEPENDENT_WITNESS_HELPER_NOT_UNCONDITIONALLY_DENY_ONLY")

    def test_06_helper_monotonic_head_true_rejected(self):
        def change(t):
            self.set_field(self.return_dict(self.helper_return(t)), "monotonic_head_proven", True)
        self.expect(self.mutated(change), "INDEPENDENT_WITNESS_HELPER_NOT_UNCONDITIONALLY_DENY_ONLY")

    def test_07_helper_owner_identity_faked_rejected(self):
        def change(t):
            self.set_field(self.return_dict(self.helper_return(t)), "owner_identity_verified", True)
        self.expect(self.mutated(change), "INDEPENDENT_WITNESS_HELPER_NOT_UNCONDITIONALLY_DENY_ONLY")

    def test_08_helper_external_effect_faked_rejected(self):
        def change(t):
            self.set_field(self.return_dict(self.helper_return(t)), "executes_action", True)
        self.expect(self.mutated(change), "INDEPENDENT_WITNESS_HELPER_NOT_UNCONDITIONALLY_DENY_ONLY")

    def test_09_helper_conditionalized_if_true_not_counted_as_unconditional(self):
        def change(t):
            h=self.fn(t,"_require_independent_runtime_write_witness")
            return_stmt=self.helper_return(t)
            h.body[-1]=ast.If(test=ast.Constant(True),body=[return_stmt],orelse=[])
        self.expect(self.mutated(change), "INDEPENDENT_WITNESS_HELPER_NOT_UNCONDITIONALLY_DENY_ONLY")

    def test_10_duplicate_helper_return_rejected(self):
        def change(t):
            h=self.fn(t,"_require_independent_runtime_write_witness")
            h.body.append(ast.Return(value=ast.Constant(False)))
        self.expect(self.mutated(change), "INDEPENDENT_WITNESS_HELPER_NOT_UNCONDITIONALLY_DENY_ONLY")

    def test_11_helper_definition_deleted_rejected(self):
        def change(t):
            h=self.fn(t,"_require_independent_runtime_write_witness")
            t.body.remove(h)
        self.expect(self.mutated(change), "FUNCTION_MISSING_DUPLICATED_OR_ASYNC")

    def test_12_helper_definition_duplicated_rejected(self):
        def change(t):
            h=self.fn(t,"_require_independent_runtime_write_witness")
            import copy
            t.body.append(copy.deepcopy(h))
        self.expect(self.mutated(change), "FUNCTION_MISSING_DUPLICATED_OR_ASYNC")

    def test_13_writer_definition_deleted_rejected(self):
        def change(t):
            t.body.remove(self.fn(t))
        self.expect(self.mutated(change), "FUNCTION_MISSING_DUPLICATED_OR_ASYNC")

    def test_14_writer_definition_duplicated_rejected(self):
        def change(t):
            import copy
            t.body.append(copy.deepcopy(self.fn(t)))
        self.expect(self.mutated(change), "FUNCTION_MISSING_DUPLICATED_OR_ASYNC")

    def test_15_guard_assignment_removed_rejected(self):
        def change(t):
            w=self.fn(t); i,_,_=self.target_pair(w)
            w.body.pop(i)
        self.expect(self.mutated(change), "GUARD_ASSIGNMENT_NOT_DIRECT_TOP_LEVEL")

    def test_16_guard_callable_changed_rejected(self):
        def change(t):
            w=self.fn(t); _,assignment,_=self.target_pair(w)
            assignment.value.func.id="claimed_enrolled_witness"
        self.expect(self.mutated(change), "GUARD_CALL_NOT_UNIQUE")

    def test_17_guard_nested_in_if_true_not_top_level(self):
        def change(t):
            w=self.fn(t); i,assignment,_=self.target_pair(w)
            w.body[i]=ast.If(test=ast.Constant(True),body=[assignment],orelse=[])
        self.expect(self.mutated(change), "GUARD_ASSIGNMENT_NOT_DIRECT_TOP_LEVEL")

    def test_18_guard_nested_in_try_not_top_level(self):
        def change(t):
            w=self.fn(t); i,assignment,_=self.target_pair(w)
            w.body[i]=ast.Try(body=[assignment],handlers=[],orelse=[],
                              finalbody=[ast.Pass()])
        self.expect(self.mutated(change), "GUARD_ASSIGNMENT_NOT_DIRECT_TOP_LEVEL")

    def test_19_guard_digest_binding_to_other_variable_rejected(self):
        def change(t):
            w=self.fn(t); _,assignment,_=self.target_pair(w)
            for kw in assignment.value.keywords:
                if kw.arg=="expected_digest":
                    kw.value=ast.Name(id="attacker_digest",ctx=ast.Load())
        self.expect(self.mutated(change), "GUARD_ASSIGNMENT_NOT_DIRECT_TOP_LEVEL")

    def test_20_guard_positional_config_replaced_rejected(self):
        def change(t):
            w=self.fn(t); _,assignment,_=self.target_pair(w)
            assignment.value.args[0]=ast.Name(id="other_cfg",ctx=ast.Load())
        self.expect(self.mutated(change), "GUARD_ASSIGNMENT_NOT_DIRECT_TOP_LEVEL")

    def test_21_guard_callable_called_twice_rejected(self):
        def change(t):
            import copy
            w=self.fn(t); i,assignment,_=self.target_pair(w)
            w.body.insert(i,copy.deepcopy(assignment))
        self.expect(self.mutated(change), "GUARD_CALL_NOT_UNIQUE")

    def test_22_denial_branch_condition_if_true_rejected(self):
        def change(t):
            w=self.fn(t); _,_,branch=self.target_pair(w)
            branch.test=ast.Constant(True)
        self.expect(self.mutated(change), "NEGATIVE_ADMISSION_CONDITION_ALTERED")

    def test_23_denial_branch_requires_not_true_not_is_true(self):
        def change(t):
            w=self.fn(t); _,_,branch=self.target_pair(w)
            branch.test.ops[0]=ast.Is()
        self.expect(self.mutated(change), "NEGATIVE_ADMISSION_CONDITION_ALTERED")

    def test_24_denial_get_wrong_field_rejected(self):
        def change(t):
            w=self.fn(t); _,_,branch=self.target_pair(w)
            branch.test.left.args[0].value="unblocked"
        self.expect(self.mutated(change), "NEGATIVE_ADMISSION_CONDITION_ALTERED")

    def test_25_denial_get_false_comparator_rejected(self):
        def change(t):
            w=self.fn(t); _,_,branch=self.target_pair(w)
            branch.test.comparators[0].value=False
        self.expect(self.mutated(change), "NEGATIVE_ADMISSION_CONDITION_ALTERED")

    def test_26_denial_status_changed_rejected(self):
        def change(t):
            self.set_field(self.deny_return(t),"status","CONFIRMED")
        self.expect(self.mutated(change), "NEGATIVE_ADMISSION_MUST_RETURN_COMPLETE_DENIAL")

    def test_27_denial_saved_true_rejected(self):
        def change(t):
            self.set_field(self.deny_return(t),"saved",True)
        self.expect(self.mutated(change), "NEGATIVE_ADMISSION_MUST_RETURN_COMPLETE_DENIAL")

    def test_28_denial_verified_true_rejected(self):
        def change(t):
            self.set_field(self.deny_return(t),"verified",True)
        self.expect(self.mutated(change), "NEGATIVE_ADMISSION_MUST_RETURN_COMPLETE_DENIAL")

    def test_29_denial_write_outcome_promoted_rejected(self):
        def change(t):
            self.set_field(self.deny_return(t),"write_outcome","CONFIRMED")
        self.expect(self.mutated(change), "NEGATIVE_ADMISSION_MUST_RETURN_COMPLETE_DENIAL")

    def test_30_denial_reconciliation_flag_true_rejected(self):
        def change(t):
            self.set_field(self.deny_return(t),"reconciliation_required",True)
        self.expect(self.mutated(change), "NEGATIVE_ADMISSION_MUST_RETURN_COMPLETE_DENIAL")

    def test_31_denial_automatic_retry_true_rejected(self):
        def change(t):
            self.set_field(self.deny_return(t),"automatic_retry_allowed",True)
        self.expect(self.mutated(change), "NEGATIVE_ADMISSION_MUST_RETURN_COMPLETE_DENIAL")

    def test_32_denial_witness_enrolled_true_rejected(self):
        def change(t):
            self.set_field(self.deny_return(t),"independent_witness_enrolled",True)
        self.expect(self.mutated(change), "NEGATIVE_ADMISSION_MUST_RETURN_COMPLETE_DENIAL")

    def test_33_denial_monotonic_head_true_rejected(self):
        def change(t):
            self.set_field(self.deny_return(t),"monotonic_head_proven",True)
        self.expect(self.mutated(change), "NEGATIVE_ADMISSION_MUST_RETURN_COMPLETE_DENIAL")

    def test_34_denial_nonreturn_expression_rejected(self):
        def change(t):
            w=self.fn(t); _,_,branch=self.target_pair(w)
            branch.body=[ast.Pass()]
        self.expect(self.mutated(change), "NEGATIVE_ADMISSION_MUST_RETURN_COMPLETE_DENIAL")

    def test_35_denial_else_branch_rejected(self):
        def change(t):
            w=self.fn(t); _,_,branch=self.target_pair(w)
            branch.orelse=[ast.Pass()]
        self.expect(self.mutated(change), "NEGATIVE_ADMISSION_MUST_RETURN_COMPLETE_DENIAL")

    def test_36_intervening_statement_between_guard_and_denial_rejected(self):
        def change(t):
            w=self.fn(t); i,_,_=self.target_pair(w)
            w.body.insert(i+1,ast.Pass())
        self.expect(self.mutated(change), "NEGATIVE_ADMISSION_CONDITION_ALTERED")

    def test_37_guard_after_put_rejected(self):
        def change(t):
            w=self.fn(t); i,_,_=self.target_pair(w)
            w.body.insert(i,ast.parse("requests.put('https://example.invalid')").body[0])
        self.expect(self.mutated(change), "RUNTIME_GITHUB_PUT_NOT_UNIQUE")

    def test_38_second_put_after_original_rejected(self):
        def change(t):
            w=self.fn(t); w.body.append(ast.parse("requests.put('https://example.invalid')").body[0])
        self.expect(self.mutated(change), "RUNTIME_GITHUB_PUT_NOT_UNIQUE")

    def test_39_alias_client_put_rejected_even_if_requests_put_still_present(self):
        def change(t):
            w=self.fn(t); i,_,_=self.target_pair(w)
            w.body.insert(i,ast.parse("client.put('https://example.invalid')").body[0])
        self.expect(self.mutated(change), "UNREVIEWED_MUTATOR_IN_RUNTIME_WRITER")

    def test_40_alias_client_post_rejected_even_if_requests_put_still_present(self):
        def change(t):
            w=self.fn(t); i,_,_=self.target_pair(w)
            w.body.insert(i,ast.parse("httpx.post('https://example.invalid')").body[0])
        self.expect(self.mutated(change), "UNREVIEWED_MUTATOR_IN_RUNTIME_WRITER")

    def test_41_helper_shadowed_by_local_assignment_rejected(self):
        def change(t):
            w=self.fn(t); i,_,_=self.target_pair(w)
            w.body.insert(i,ast.parse("_require_independent_runtime_write_witness=lambda *a,**k: {'allowed':True}").body[0])
        self.expect(self.mutated(change), "GUARD_HELPER_SHADOWED_LOCALLY")

    def test_42_helper_rebound_at_module_scope_rejected(self):
        def change(t):
            t.body.append(ast.parse("_require_independent_runtime_write_witness=lambda *a,**k: {'allowed':True}").body[0])
        self.expect(self.mutated(change), "GUARD_HELPER_REBOUND_AT_MODULE_SCOPE")

    def test_43_unparseable_source_denied(self):
        self.expect("def bad (", "RUNTIME_SOURCE_UNPARSEABLE")

    def test_44_unreviewed_scripted_runtime_scope_never_mints_custodian(self):
        r=self.report()
        self.assertIs(r["independent_runtime_witness_enrolled"],False)
        self.assertIs(r["actual_runtime_effects_proven_safe"],False)
        self.assertIs(r["github_checkpoint_write_authorized"],False)

    def test_45_existing_A136_simple_order_gate_passes_current_source(self):
        self.assertTrue(guard_shape(ROOT)["ok"])
        self.assertTrue(self.report()["writer_deny_shape_intact_lab"])


if __name__ == "__main__":
    unittest.main()
