"""A156 52 read-only mutations against real Checkpoint Mestre recovery source.

No product module import, no runtime restore, no HTTP, no GitHub write.
Tests edit ephemeral Python AST in memory, never the tracked source.
"""
import ast
import copy
import unittest

from tools.aion_p0_a156_recovery_restore_deny_ast_lab import (
    ROOT, RECOVERY, RESTORE, HELPER, inspect_recovery_source,
)


class A156RealRecoveryDenyASTLAB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = RECOVERY.read_text(encoding="utf-8")

    def fn(self, tree, name=RESTORE):
        matches = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                   and n.name == name]
        self.assertEqual(len(matches), 1, name)
        return matches[0]

    def at(self, tree):
        body = self.fn(tree).body
        found = [i for i, s in enumerate(body) if isinstance(s, ast.Assign)
                 and len(s.targets) == 1
                 and isinstance(s.targets[0], ast.Name)
                 and s.targets[0].id == "witness_admission"]
        self.assertEqual(len(found), 1)
        return body, found[0]

    def helper_return_dict(self, tree):
        fn = self.fn(tree, HELPER)
        return next(n.value for n in fn.body if isinstance(n, ast.Return))

    def denial_dict(self, tree):
        body, ix = self.at(tree)
        self.assertIsInstance(body[ix + 1], ast.If)
        return body[ix + 1].body[0].value

    def change_value(self, obj, key, value):
        self.assertIsInstance(obj, ast.Dict)
        for k, v in zip(obj.keys, obj.values):
            if isinstance(k, ast.Constant) and k.value == key:
                self.assertIsInstance(v, ast.Constant)
                v.value = value
                return
        self.fail("key missing " + key)

    def mutated(self, f):
        tree = ast.parse(self.source)
        f(tree)
        ast.fix_missing_locations(tree)
        return ast.unparse(tree)

    def expect(self, f, reason):
        result = inspect_recovery_source(self.mutated(f))
        self.assertFalse(result["recovery_static_deny_contract_intact_lab"], result)
        self.assertTrue(any(reason in item for item in result["findings"]), result)
        self.assertIs(result["checkpoint_restoration_authorized"], False)
        self.assertIs(result["automatic_resend_allowed"], False)
        self.assertEqual(result["homologated_p0_count"], 0)

    def inject(self, tree, before=True, statement="requests.put('https://invalid.example')"):
        body, ix = self.at(tree)
        body.insert(ix if before else ix + 2, ast.parse(statement).body[0])

    def test_01_current_real_recovery_is_statically_deny_only(self):
        result = inspect_recovery_source(self.source)
        self.assertTrue(result["recovery_static_deny_contract_intact_lab"], result)
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["verdict"], "HARD_NO_GO_RECOVERY_WITNESS_NOT_ENROLLED")
        for key in ("real_independent_witness_verified",
                    "human_owner_critical_consent_verified",
                    "checkpoint_restoration_authorized",
                    "real_provider_effect_proven", "worker_allowed",
                    "automatic_resend_allowed"):
            self.assertIs(result[key], False)
        self.assertEqual(result["homologated_p0_count"], 0)

    def test_02_inverted_witness_denial_condition_rejected(self):
        def f(t):
            b,i=self.at(t)
            b[i+1].test.ops[0]=ast.Is()
        self.expect(f,"RECOVERY_NEGATIVE_ADMISSION_CONDITION_ALTERED")

    def test_03_helper_allowed_true_rejected(self):
        self.expect(lambda t:self.change_value(self.helper_return_dict(t),"allowed",True),
                    "INDEPENDENT_RECOVERY_WITNESS_NOT_UNCONDITIONALLY_DENY_ONLY")

    def test_04_helper_status_ready_rejected(self):
        self.expect(lambda t:self.change_value(self.helper_return_dict(t),"status","READY"),
                    "INDEPENDENT_RECOVERY_WITNESS_NOT_UNCONDITIONALLY_DENY_ONLY")

    def test_05_helper_enrolled_true_rejected(self):
        self.expect(lambda t:self.change_value(self.helper_return_dict(t),"independent_witness_enrolled",True),
                    "INDEPENDENT_RECOVERY_WITNESS_NOT_UNCONDITIONALLY_DENY_ONLY")

    def test_06_helper_head_verified_true_rejected(self):
        self.expect(lambda t:self.change_value(self.helper_return_dict(t),"monotonic_head_proven",True),
                    "INDEPENDENT_RECOVERY_WITNESS_NOT_UNCONDITIONALLY_DENY_ONLY")

    def test_07_helper_owner_true_rejected(self):
        self.expect(lambda t:self.change_value(self.helper_return_dict(t),"human_owner_verified",True),
                    "INDEPENDENT_RECOVERY_WITNESS_NOT_UNCONDITIONALLY_DENY_ONLY")

    def test_08_helper_restore_authorized_true_rejected(self):
        self.expect(lambda t:self.change_value(self.helper_return_dict(t),"restoration_authorized",True),
                    "INDEPENDENT_RECOVERY_WITNESS_NOT_UNCONDITIONALLY_DENY_ONLY")

    def test_09_helper_executes_action_true_rejected(self):
        self.expect(lambda t:self.change_value(self.helper_return_dict(t),"executes_action",True),
                    "INDEPENDENT_RECOVERY_WITNESS_NOT_UNCONDITIONALLY_DENY_ONLY")

    def test_10_helper_conditionalized_rejected(self):
        def f(t):
            h=self.fn(t,HELPER)
            old=h.body[-1]
            h.body[-1]=ast.If(test=ast.Constant(True),body=[old],orelse=[])
        self.expect(f,"INDEPENDENT_RECOVERY_WITNESS_NOT_UNCONDITIONALLY_DENY_ONLY")

    def test_11_deleted_helper_rejected(self):
        self.expect(lambda t:t.body.remove(self.fn(t,HELPER)),
                    "FUNCTION_MISSING_DUPLICATED_OR_ASYNC")

    def test_12_duplicate_helper_rejected(self):
        self.expect(lambda t:t.body.append(copy.deepcopy(self.fn(t,HELPER))),
                    "FUNCTION_MISSING_DUPLICATED_OR_ASYNC")

    def test_13_decorated_helper_rejected(self):
        def f(t):
            self.fn(t,HELPER).decorator_list=[ast.Name(id="fake_authority",ctx=ast.Load())]
        self.expect(f,"UNREVIEWED_FUNCTION_DECORATOR")

    def test_14_async_helper_rejected(self):
        def f(t):
            h=self.fn(t,HELPER)
            index=t.body.index(h)
            t.body[index]=ast.AsyncFunctionDef(
                name=h.name,args=h.args,body=h.body,decorator_list=[],returns=h.returns,
                type_comment=None,
            )
        self.expect(f,"FUNCTION_MISSING_DUPLICATED_OR_ASYNC")

    def test_15_missing_restore_rejected(self):
        self.expect(lambda t:t.body.remove(self.fn(t)), "FUNCTION_MISSING_DUPLICATED_OR_ASYNC")

    def test_16_duplicate_restore_rejected(self):
        self.expect(lambda t:t.body.append(copy.deepcopy(self.fn(t))),
                    "FUNCTION_MISSING_DUPLICATED_OR_ASYNC")

    def test_17_decorated_restore_rejected(self):
        def f(t):
            self.fn(t).decorator_list=[ast.Name(id="fake_enrollment",ctx=ast.Load())]
        self.expect(f,"UNREVIEWED_FUNCTION_DECORATOR")

    def test_18_approval_condition_inverted_rejected(self):
        def f(t):
            self.fn(t).body[1].test.ops[0]=ast.Is()
        self.expect(f,"EXPLICIT_APPROVAL_MUST_DENY_BEFORE_NETWORK")

    def test_19_approval_branch_removed_rejected(self):
        def f(t):
            self.fn(t).body.pop(1)
        self.expect(f,"EXPLICIT_APPROVAL_MUST_DENY_BEFORE_NETWORK")

    def test_20_approval_branch_delayed_rejected(self):
        def f(t):
            self.fn(t).body.insert(1,ast.parse("recovery_preflight(current_runtime,candidate)").body[0])
        self.expect(f,"EXPLICIT_APPROVAL_MUST_DENY_BEFORE_NETWORK")

    def test_21_witness_assignment_removed_rejected(self):
        def f(t):
            b,i=self.at(t);b.pop(i)
        self.expect(f,"RECOVERY_WITNESS_ASSIGNMENT_NOT_TOP_LEVEL_OR_BINDING_DRIFT")

    def test_22_duplicate_witness_call_rejected(self):
        def f(t):
            b,i=self.at(t);b.insert(i,copy.deepcopy(b[i]))
        self.expect(f,"INDEPENDENT_WITNESS_CALL_NOT_UNIQUE")

    def test_23_witness_call_nested_if_true_rejected(self):
        def f(t):
            b,i=self.at(t)
            old=b[i]
            b[i]=ast.If(test=ast.Constant(True),body=[old],orelse=[])
        self.expect(f,"RECOVERY_WITNESS_ASSIGNMENT_NOT_TOP_LEVEL_OR_BINDING_DRIFT")

    def test_24_witness_config_argument_mutation_rejected(self):
        def f(t):
            b,i=self.at(t)
            b[i].value.args[0].id="attacker_config"
        self.expect(f,"RECOVERY_WITNESS_ASSIGNMENT_NOT_TOP_LEVEL_OR_BINDING_DRIFT")

    def test_25_witness_wrong_ancestry_rejected(self):
        def f(t):
            b,i=self.at(t)
            next(k for k in b[i].value.keywords if k.arg=="ancestry").value.id="unverified"
        self.expect(f,"RECOVERY_WITNESS_ASSIGNMENT_NOT_TOP_LEVEL_OR_BINDING_DRIFT")

    def test_26_witness_wrong_revision_rejected(self):
        def f(t):
            b,i=self.at(t)
            next(k for k in b[i].value.keywords if k.arg=="candidate_revision").value.id="attacker_revision"
        self.expect(f,"RECOVERY_WITNESS_ASSIGNMENT_NOT_TOP_LEVEL_OR_BINDING_DRIFT")

    def test_27_witness_wrong_blob_sha_rejected(self):
        def f(t):
            b,i=self.at(t)
            next(k for k in b[i].value.keywords if k.arg=="current_blob_sha").value.args[0].value="fake_sha"
        self.expect(f,"RECOVERY_WITNESS_ASSIGNMENT_NOT_TOP_LEVEL_OR_BINDING_DRIFT")

    def test_28_witness_denial_condition_missing_get_rejected(self):
        def f(t):
            b,i=self.at(t);b[i+1].test=ast.Constant(True)
        self.expect(f,"RECOVERY_NEGATIVE_ADMISSION_CONDITION_ALTERED")

    def test_29_witness_denial_get_wrong_key_rejected(self):
        def f(t):
            b,i=self.at(t);b[i+1].test.left.args[0].value="approved"
        self.expect(f,"RECOVERY_NEGATIVE_ADMISSION_CONDITION_ALTERED")

    def test_30_witness_denial_comparison_false_rejected(self):
        def f(t):
            b,i=self.at(t);b[i+1].test.comparators[0].value=False
        self.expect(f,"RECOVERY_NEGATIVE_ADMISSION_CONDITION_ALTERED")

    def test_31_denial_status_confirmed_rejected(self):
        self.expect(lambda t:self.change_value(self.denial_dict(t),"status","CONFIRMED"),
                    "RECOVERY_NEGATIVE_ADMISSION_NOT_COMPLETE_RETURN")

    def test_32_denial_saved_true_rejected(self):
        self.expect(lambda t:self.change_value(self.denial_dict(t),"saved",True),
                    "RECOVERY_NEGATIVE_ADMISSION_NOT_COMPLETE_RETURN")

    def test_33_denial_verified_true_rejected(self):
        self.expect(lambda t:self.change_value(self.denial_dict(t),"verified",True),
                    "RECOVERY_NEGATIVE_ADMISSION_NOT_COMPLETE_RETURN")

    def test_34_denial_restore_confirmed_true_rejected(self):
        self.expect(lambda t:self.change_value(self.denial_dict(t),"restore_confirmed",True),
                    "RECOVERY_NEGATIVE_ADMISSION_NOT_COMPLETE_RETURN")

    def test_35_denial_reconciliation_true_rejected(self):
        self.expect(lambda t:self.change_value(self.denial_dict(t),"reconciliation_required",True),
                    "RECOVERY_NEGATIVE_ADMISSION_NOT_COMPLETE_RETURN")

    def test_36_denial_automatic_retry_true_rejected(self):
        self.expect(lambda t:self.change_value(self.denial_dict(t),"automatic_retry_allowed",True),
                    "RECOVERY_NEGATIVE_ADMISSION_NOT_COMPLETE_RETURN")

    def test_37_denial_automatic_restore_true_rejected(self):
        self.expect(lambda t:self.change_value(self.denial_dict(t),"automatic_restore",True),
                    "RECOVERY_NEGATIVE_ADMISSION_NOT_COMPLETE_RETURN")

    def test_38_denial_witness_enrolled_true_rejected(self):
        self.expect(lambda t:self.change_value(self.denial_dict(t),"independent_witness_enrolled",True),
                    "RECOVERY_NEGATIVE_ADMISSION_NOT_COMPLETE_RETURN")

    def test_39_denial_head_proven_true_rejected(self):
        self.expect(lambda t:self.change_value(self.denial_dict(t),"monotonic_head_proven",True),
                    "RECOVERY_NEGATIVE_ADMISSION_NOT_COMPLETE_RETURN")

    def test_40_denial_owner_verified_true_rejected(self):
        self.expect(lambda t:self.change_value(self.denial_dict(t),"human_owner_verified",True),
                    "RECOVERY_NEGATIVE_ADMISSION_NOT_COMPLETE_RETURN")

    def test_41_denial_restored_revision_nonempty_rejected(self):
        self.expect(lambda t:self.change_value(self.denial_dict(t),"restored_revision","claimed"),
                    "RECOVERY_NEGATIVE_ADMISSION_NOT_COMPLETE_RETURN")

    def test_42_denial_return_removed_rejected(self):
        def f(t):
            b,i=self.at(t);b[i+1].body=[ast.Pass()]
        self.expect(f,"RECOVERY_NEGATIVE_ADMISSION_NOT_COMPLETE_RETURN")

    def test_43_denial_else_branch_rejected(self):
        def f(t):
            b,i=self.at(t);b[i+1].orelse=[ast.Pass()]
        self.expect(f,"RECOVERY_NEGATIVE_ADMISSION_NOT_COMPLETE_RETURN")

    def test_44_save_before_witness_rejected(self):
        def f(t):
            self.inject(t,statement="save_runtime_checkpoint(checkpoint, config, approved=True)")
        self.expect(f,"SHARED_CHECKPOINT_SAVE_CALL_NOT_UNIQUE")

    def test_45_second_save_after_witness_rejected(self):
        def f(t):
            self.inject(t,before=False,statement="save_runtime_checkpoint(checkpoint, config, approved=True)")
        self.expect(f,"SHARED_CHECKPOINT_SAVE_CALL_NOT_UNIQUE")

    def test_46_save_function_target_changed_rejected(self):
        def f(t):
            w=self.fn(t)
            for st in w.body:
                if (isinstance(st,ast.Assign)
                    and isinstance(st.value,ast.Call)
                    and isinstance(st.value.func,ast.Name)
                    and st.value.func.id=="save_runtime_checkpoint"):
                    st.value.func.id="alternate_restore_writer"
                    return
            self.fail("save call absent")
        self.expect(f,"SHARED_CHECKPOINT_SAVE_CALL_NOT_UNIQUE")

    def test_47_save_approved_keyword_changed_rejected(self):
        def f(t):
            w=self.fn(t)
            for st in w.body:
                if isinstance(st,ast.Assign) and isinstance(st.value,ast.Call) \
                   and isinstance(st.value.func,ast.Name) \
                   and st.value.func.id=="save_runtime_checkpoint":
                    next(k for k in st.value.keywords if k.arg=="approved").value.value=False
                    return
            self.fail("no save")
        self.expect(f,"SHARED_CHECKPOINT_SAVE_BINDING_DRIFT")

    def test_48_local_helper_shadow_rejected(self):
        def f(t):
            self.inject(t,statement="_require_independent_recovery_head_witness=lambda *a,**k: {'allowed':True}")
        self.expect(f,"RECOVERY_WITNESS_SHADOWED_LOCALLY")

    def test_49_module_scope_helper_rebinding_rejected(self):
        def f(t):
            t.body.append(ast.parse("_require_independent_recovery_head_witness=lambda *a,**k: {'allowed':True}").body[0])
        self.expect(f,"RECOVERY_WITNESS_REBOUND_AT_MODULE_SCOPE")

    def test_50_direct_requests_put_in_restore_rejected(self):
        def f(t):
            self.inject(t,statement="requests.put('https://example.invalid')")
        self.expect(f,"UNREVIEWED_ALTERNATE_RECOVERY_MUTATOR")

    def test_51_alias_client_delete_in_restore_rejected(self):
        def f(t):
            self.inject(t,statement="client.delete('https://example.invalid')")
        self.expect(f,"UNREVIEWED_ALTERNATE_RECOVERY_MUTATOR")

    def test_52_bad_python_parse_always_no_go(self):
        r=inspect_recovery_source("def bad (")
        self.assertFalse(r["recovery_static_deny_contract_intact_lab"])
        self.assertIn("RECOVERY_SOURCE_UNPARSEABLE",r["findings"])
        self.assertFalse(r["checkpoint_restoration_authorized"])
        self.assertFalse(r["automatic_resend_allowed"])


    def save_call(self, tree):
        w=self.fn(tree)
        for st in w.body:
            if (isinstance(st, ast.Assign) and isinstance(st.value, ast.Call)
                    and isinstance(st.value.func, ast.Name)
                    and st.value.func.id=="save_runtime_checkpoint"):
                return st.value
        self.fail("save function call not found")

    def replace_save_keyword(self, tree, name, text):
        call=self.save_call(tree)
        kw=next(k for k in call.keywords if k.arg==name)
        kw.value=ast.parse(text,mode="eval").body

    def test_53_cas_sha_literal_instead_of_preflight_rejected(self):
        self.expect(lambda t:self.replace_save_keyword(t,"expected_sha","str('a'*40)"),
                    "SHARED_CHECKPOINT_SAVE_BINDING_DRIFT")

    def test_54_cas_sha_from_candidate_revision_rejected(self):
        self.expect(lambda t:self.replace_save_keyword(t,"expected_sha","str(revision)"),
                    "SHARED_CHECKPOINT_SAVE_BINDING_DRIFT")

    def test_55_cas_sha_wrong_preflight_field_rejected(self):
        self.expect(lambda t:self.replace_save_keyword(t,"expected_sha",
                                  "str(preflight.get('candidate_digest') or '')"),
                    "SHARED_CHECKPOINT_SAVE_BINDING_DRIFT")

    def test_56_cas_sha_without_explicit_string_fallback_rejected(self):
        self.expect(lambda t:self.replace_save_keyword(t,"expected_sha",
                                  "str(preflight.get('expected_sha'))"),
                    "SHARED_CHECKPOINT_SAVE_BINDING_DRIFT")

    def test_57_cas_sha_unreviewed_default_keyword_rejected(self):
        self.expect(lambda t:self.replace_save_keyword(t,"expected_sha",
                                  "str(preflight.get('expected_sha', 'fake') or '')"),
                    "SHARED_CHECKPOINT_SAVE_BINDING_DRIFT")

    def test_58_cas_sha_unsafe_nonempty_fallback_rejected(self):
        self.expect(lambda t:self.replace_save_keyword(t,"expected_sha",
                                  "str(preflight.get('expected_sha') or 'f'*40)"),
                    "SHARED_CHECKPOINT_SAVE_BINDING_DRIFT")

    def test_59_save_timeout_hardcoded_instead_of_forwarded_rejected(self):
        self.expect(lambda t:self.replace_save_keyword(t,"timeout","999"),
                    "SHARED_CHECKPOINT_SAVE_BINDING_DRIFT")

    def test_60_save_approved_numeric_true_instead_of_boolean_rejected(self):
        self.expect(lambda t:self.replace_save_keyword(t,"approved","1"),
                    "SHARED_CHECKPOINT_SAVE_BINDING_DRIFT")

if __name__ == "__main__":
    unittest.main()
