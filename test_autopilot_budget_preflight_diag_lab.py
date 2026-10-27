"""Safe introspection tests for budget preflight stage observability.

Load only _td_initialize AST: never import operational Autopilot or execute
provider, requests, GitHub, Streamlit, market data or budget reservations.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

from atlasquant_twelve_preflight_diagnostic import preflight_diagnostic


def _source():
    override = globals().get("_AUTOPILOT_SOURCE_FOR_IN_MEMORY_TEST")
    if type(override) is str:
        return override
    return Path(__file__).with_name("autopilot_v107.py").read_text(encoding="utf-8")


def _init_ast():
    tree = ast.parse(_source())
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_td_initialize")


def harness(*, errors=None, missing_paths=None, invalid_payloads=None,
            bootstrap_error=None, summary_error=None,
            budget_init_error=None, blocked=None):
    errors = dict(errors or {})
    missing_paths=set(missing_paths or ())
    invalid_payloads=dict(invalid_payloads or {})
    calls = []
    state = {}
    class BudgetUnavailable(RuntimeError):
        pass
    class Clock:
        def to_pydatetime(self):
            return object()
    class FakeBudget:
        def bootstrap(self, previous, scanner, now):
            calls.append("budget.bootstrap")
            if bootstrap_error:
                raise bootstrap_error
        def summary(self, now):
            calls.append("budget.summary")
            if summary_error:
                raise summary_error
            return blocked or {}
    fake_budget=FakeBudget()
    def construct_budget(store):
        calls.append("budget.construct")
        if budget_init_error:
            raise budget_init_error
        return fake_budget
    def read(path, default):
        calls.append("read."+path)
        values={
            "status":({"last_run":"test"},""),
            "scanner":({"autopilot_v107":{}},""),
            "series":({"series":{}},""),
        }
        val,err=values[path]
        if path in missing_paths:
            return default,errors.get(path,err)
        return invalid_payloads.get(path,val),errors.get(path,err)
    env={
        "__builtins__":__builtins__,
        "preflight_diagnostic":preflight_diagnostic,
        "BudgetUnavailable":BudgetUnavailable,
        "Budget":construct_budget,
        "GitHubStore":lambda *args:object(),
        "TOKEN":"secret-never-used", "REPO":"sample/repo",
        "BRANCH":"not-real",
        "gh_get_json":read,
        "utcnow":lambda:Clock(),
        "STATUS_PATH":"status","SCANNER_PATH":"scanner","SERIES_PATH":"series",
        "_TD_BUDGET":None,
        "_TD_SERIES":{"series":{"preexisting":"must-preserve-on-failure"}},
        "_TD_DAILY_BLOCKED":True,
        "_TD_BLOCK_TYPE":"old",
        "_TD_DAILY_BLOCK_REASON":"old",
        "_TD_STOP_UNTIL":"old",
        "_TD_HTTP_CALLS":15,
        "_TD_CACHE_HITS":10,
        "_TD_CALL_TIMES":[123],
        "_TD_PREFLIGHT_DIAGNOSTIC":{},
    }
    node=_init_ast()
    code=compile(ast.Module(body=[node],type_ignores=[]),"<isolated-budget-preflight>","exec")
    exec(code,env)
    env["_td_initialize"]()
    return env,calls


class DiagnosticAllowlistTests(unittest.TestCase):
    def test_01_secret_bearing_exception_message_never_leaked(self):
        err=ValueError("sk-secret https://api.twelvedata.com?apikey=leak")
        result=preflight_diagnostic("READ_CACHE",failed=True,error=err)
        self.assertEqual(result["error_category"],"ValueError")
        self.assertNotIn("sk-secret",str(result))
        self.assertNotIn("apikey",str(result))

    def test_02_unknown_stage_and_exception_are_classified_not_echoed(self):
        d=preflight_diagnostic("read /private/secret",failed=True,error=OSError("token secret"))
        self.assertEqual(d["stage"],"UNKNOWN")
        self.assertEqual(d["error_category"],"UNCLASSIFIED")

    def test_03_even_success_diagnostic_never_grants_spend_retry_or_provider(self):
        d=preflight_diagnostic("COMPLETE",failed=False)
        self.assertEqual(d["state"],"COMPLETED_NON_AUTHORIZING")
        for name in ("authorizes_provider_call","automatic_retry_allowed","spend_authorized"):
            self.assertIs(d[name],False)

    def test_04_helper_rejects_bogus_stage_type(self):
        self.assertEqual(preflight_diagnostic(7,failed=True)["stage"],"UNKNOWN")

    def test_05_success_reads_exact_three_states_and_preserves_no_calls(self):
        env,calls=harness()
        self.assertFalse(env["_TD_DAILY_BLOCKED"])
        self.assertEqual(env["_TD_PREFLIGHT_DIAGNOSTIC"]["stage"],"COMPLETE")
        self.assertEqual(calls,["budget.construct","read.status","read.scanner",
                                "read.series","budget.bootstrap","budget.summary"])
        self.assertEqual(env["_TD_HTTP_CALLS"],0)
        self.assertEqual(env["_TD_CACHE_HITS"],0)

    def test_06_status_read_failure_identified_but_stays_blocked(self):
        env,calls=harness(errors={"status":"token=secret"})
        self.assertTrue(env["_TD_DAILY_BLOCKED"])
        self.assertEqual(env["_TD_PREFLIGHT_DIAGNOSTIC"]["stage"],"READ_PREVIOUS_STATUS")
        self.assertNotIn("secret",str(env["_TD_PREFLIGHT_DIAGNOSTIC"]))
        self.assertNotIn("budget.bootstrap",calls)

    def test_07_scanner_read_failure_identified(self):
        env,_=harness(errors={"scanner":"HTTP 403 token=secret"})
        self.assertEqual(env["_TD_PREFLIGHT_DIAGNOSTIC"]["stage"],"READ_SCANNER")
        self.assertTrue(env["_TD_DAILY_BLOCKED"])

    def test_08_series_read_failure_identified(self):
        env,_=harness(errors={"series":"HTTP 429"})
        self.assertEqual(env["_TD_PREFLIGHT_DIAGNOSTIC"]["stage"],"READ_CACHE")
        self.assertEqual(env["_TD_BLOCK_TYPE"],"CONTROLE_INDISPONIVEL")

    def test_09_budget_bootstrap_error_remains_fail_closed(self):
        env,calls=harness(bootstrap_error=ValueError("secret"))
        self.assertEqual(env["_TD_PREFLIGHT_DIAGNOSTIC"]["stage"],"BOOTSTRAP")
        self.assertEqual(env["_TD_PREFLIGHT_DIAGNOSTIC"]["error_category"],"ValueError")
        self.assertTrue(env["_TD_DAILY_BLOCKED"])
        self.assertNotIn("budget.summary",calls)

    def test_10_summary_exception_remains_fail_closed(self):
        env,_=harness(summary_error=ValueError("secret"))
        self.assertEqual(env["_TD_PREFLIGHT_DIAGNOSTIC"]["stage"],"SUMMARY")
        self.assertTrue(env["_TD_DAILY_BLOCKED"])

    def test_11_constructor_exception_is_captured_fail_closed(self):
        env,calls=harness(budget_init_error=RuntimeError("secret"))
        self.assertEqual(env["_TD_PREFLIGHT_DIAGNOSTIC"]["stage"],"BOOTSTRAP")
        self.assertTrue(env["_TD_DAILY_BLOCKED"])
        self.assertEqual(calls,["budget.construct"])

    def test_12_legitimate_persisted_budget_block_not_bypassed(self):
        env,_=harness(blocked={"blocked_until":"tomorrow","block_type":"COTA_DIARIA",
                               "block_reason":"provider reported daily cap"})
        self.assertTrue(env["_TD_DAILY_BLOCKED"])
        self.assertEqual(env["_TD_BLOCK_TYPE"],"COTA_DIARIA")
        self.assertEqual(env["_TD_STOP_UNTIL"],"tomorrow")
        self.assertEqual(env["_TD_PREFLIGHT_DIAGNOSTIC"]["stage"],"COMPLETE")

    def test_13_failure_never_creates_provider_call_in_function_ast(self):
        code=ast.unparse(_init_ast())
        self.assertNotIn("requests.get",code)
        self.assertNotIn("td_fetch(",code)
        self.assertNotIn("reserve(",code)
        self.assertNotIn("sleep(",code)

    def test_14_status_summary_exposes_only_sanitized_preflight_snapshot(self):
        self.assertIn('"twelve_budget_preflight":dict(_TD_PREFLIGHT_DIAGNOSTIC)',_source())
        self.assertIn('from atlasquant_twelve_preflight_diagnostic import preflight_diagnostic',_source())

    def test_15_repeat_failed_boot_does_not_reuse_old_credits_or_auto_retry(self):
        for _ in range(2):
            env,calls=harness(errors={"series":"unavailable"})
            self.assertTrue(env["_TD_DAILY_BLOCKED"])
            self.assertEqual(env["_TD_HTTP_CALLS"],0)
            self.assertEqual(len([c for c in calls if c.startswith("read.")]),3)
            self.assertNotIn("budget.bootstrap",calls)


    def test_16_missing_required_json_404_is_not_treated_as_empty_success(self):
        stages={"status":"READ_PREVIOUS_STATUS","scanner":"READ_SCANNER",
                "series":"READ_CACHE"}
        for path,stage in stages.items():
            with self.subTest(path=path):
                env,calls=harness(missing_paths={path})
                self.assertTrue(env["_TD_DAILY_BLOCKED"])
                self.assertEqual(env["_TD_PREFLIGHT_DIAGNOSTIC"]["stage"],stage)
                self.assertNotIn("budget.bootstrap",calls)
                self.assertEqual(env["_TD_HTTP_CALLS"],0)

    def test_17_missing_series_read_preserves_previous_in_memory_cache(self):
        env,_=harness(missing_paths={"series"})
        self.assertEqual(env["_TD_SERIES"]["series"],
                         {"preexisting":"must-preserve-on-failure"})
        self.assertTrue(env["_TD_DAILY_BLOCKED"])

    def test_18_malformed_required_json_object_is_rejected(self):
        for path,stage in (("status","READ_PREVIOUS_STATUS"),
                           ("scanner","READ_SCANNER"),
                           ("series","READ_CACHE")):
            with self.subTest(path=path):
                env,_=harness(invalid_payloads={path:["not-a-dict"]})
                self.assertEqual(env["_TD_PREFLIGHT_DIAGNOSTIC"]["stage"],stage)
                self.assertTrue(env["_TD_DAILY_BLOCKED"])
        env,_=harness(invalid_payloads={"series":{"series":[]}})
        self.assertEqual(env["_TD_PREFLIGHT_DIAGNOSTIC"]["stage"],"READ_CACHE")
        self.assertTrue(env["_TD_DAILY_BLOCKED"])

    def test_19_market_cache_write_is_guarded_by_control_failure(self):
        tree=ast.parse(_source())
        main=next(n for n in tree.body
                  if isinstance(n,ast.FunctionDef) and n.name=="main")
        guards=[]
        for node in ast.walk(main):
            if not isinstance(node,ast.If):
                continue
            cond=ast.unparse(node.test)
            if "_TD_BLOCK_TYPE" not in cond or "CONTROLE_INDISPONIVEL" not in cond:
                continue
            writes=[n for body in node.orelse for n in ast.walk(body)
                    if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
                    and n.func.id=="gh_put_json" and n.args
                    and isinstance(n.args[0],ast.Name) and n.args[0].id=="SERIES_PATH"]
            guards.append(len(writes)==1 and not any(
                isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
                and n.func.id=="gh_put_json"
                for body in node.body for n in ast.walk(body)))
        self.assertIn(True,guards)


if __name__=="__main__":
    unittest.main(verbosity=2)
