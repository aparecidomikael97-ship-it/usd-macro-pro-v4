"""Combined fail-closed Twelve budget preflight contracts — synthetic, offline only.

Do not import operational Autopilot or invoke provider, GitHub, workers or SEND.
The AST isolates _td_initialize, while the real Budget/GitHubStore code is
executed against a mocked HTTP response to test cross-module interaction.
"""
from __future__ import annotations

import ast
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from atlasquant_twelve_preflight_diagnostic import preflight_diagnostic
from twelve_budget_v1108 import Budget, GitHubStore


NOW=datetime(2026,10,27,12,0,tzinfo=timezone.utc)
SRC=Path(__file__).resolve().parents[1]/"autopilot_v107.py"


class Clock:
    def to_pydatetime(self):
        return NOW


def isolated_preflight(*, missing=None):
    tree=ast.parse(SRC.read_text(encoding="utf-8"))
    init=next(n for n in tree.body
              if isinstance(n,ast.FunctionDef) and n.name=="_td_initialize")
    calls=[]
    old_status={"last_run":NOW.isoformat(),
                "twelve_daily_blocked":True,
                "twelve_daily_block_reason":"Orçamento persistido indisponível"}
    old_scanner={"autopilot_v107":{
        "daily_budget":{"day":NOW.date().isoformat(),"calls":7}}}
    responses={
        "status":old_status,
        "scanner":old_scanner,
        "series":{"series":{}},
    }
    def read(path,default):
        calls.append(path)
        return (default if path==missing else responses[path]),""
    env={
        "__builtins__":__builtins__,
        "preflight_diagnostic":preflight_diagnostic,
        "Budget":Budget,"GitHubStore":GitHubStore,
        "TOKEN":"synthetic-not-a-credential",
        "REPO":"example/never-connected",
        "BRANCH":"atlasquant-runtime",
        "gh_get_json":read,
        "utcnow":lambda:Clock(),
        "STATUS_PATH":"status","SCANNER_PATH":"scanner","SERIES_PATH":"series",
        "_TD_BUDGET":None,
        "_TD_SERIES":{"series":{"local-only":"do-not-overwrite"}},
        "_TD_DAILY_BLOCKED":False,"_TD_BLOCK_TYPE":"",
        "_TD_DAILY_BLOCK_REASON":"","_TD_STOP_UNTIL":"",
        "_TD_HTTP_CALLS":0,"_TD_CACHE_HITS":0,
        "_TD_CALL_TIMES":[],
        "_TD_PREFLIGHT_DIAGNOSTIC":{},
    }
    exec(compile(ast.Module(body=[init],type_ignores=[]),
                 "<offline-cross-contract-preflight>","exec"),env)
    env["_td_initialize"]()
    return env,calls


class CombinedSafetyTests(unittest.TestCase):
    def test_01_missing_budget_404_blocks_bootstrap_without_http_provider_or_write(self):
        with patch("twelve_budget_v1108.requests.get",
                   return_value=Mock(status_code=404)) as get, \
             patch("twelve_budget_v1108.requests.put",
                   side_effect=AssertionError("never write")) as put:
            env,reads=isolated_preflight()
        self.assertEqual(reads,["status","scanner","series"])
        self.assertEqual(env["_TD_PREFLIGHT_DIAGNOSTIC"]["stage"],"BOOTSTRAP")
        self.assertEqual(env["_TD_BLOCK_TYPE"],"CONTROLE_INDISPONIVEL")
        self.assertTrue(env["_TD_DAILY_BLOCKED"])
        self.assertEqual(env["_TD_HTTP_CALLS"],0)
        self.assertEqual(get.call_count,1)
        self.assertIn("api.github.com",get.call_args.args[0])
        self.assertNotIn("twelvedata.com",get.call_args.args[0])
        put.assert_not_called()

    def test_02_missing_required_cache_blocks_before_budget_io(self):
        with patch("twelve_budget_v1108.requests.get",
                   side_effect=AssertionError("should not read budget")) as get, \
             patch("twelve_budget_v1108.requests.put",
                   side_effect=AssertionError("never write")) as put:
            env,reads=isolated_preflight(missing="series")
        self.assertEqual(reads,["status","scanner","series"])
        self.assertEqual(env["_TD_PREFLIGHT_DIAGNOSTIC"]["stage"],"READ_CACHE")
        self.assertTrue(env["_TD_DAILY_BLOCKED"])
        self.assertEqual(env["_TD_SERIES"]["series"],
                         {"local-only":"do-not-overwrite"})
        self.assertEqual(env["_TD_HTTP_CALLS"],0)
        get.assert_not_called()
        put.assert_not_called()

    def test_03_intact_ledger_preserves_14_over_legacy_7_and_completes_without_write(self):
        state={"version":1,"day":NOW.date().isoformat(),"used":14,
               "hours":{"02":14},"recent":[],"migration_done":True}
        payload={"sha":"synthetic-sha",
                 "content":base64.b64encode(json.dumps(state).encode()).decode()}
        response=Mock(status_code=200,json=Mock(return_value=payload))
        with patch("twelve_budget_v1108.requests.get",
                   return_value=response) as get, \
             patch("twelve_budget_v1108.requests.put",
                   side_effect=AssertionError("never write")) as put:
            env,reads=isolated_preflight()
        self.assertEqual(reads,["status","scanner","series"])
        self.assertEqual(env["_TD_PREFLIGHT_DIAGNOSTIC"]["stage"],"COMPLETE")
        self.assertFalse(env["_TD_DAILY_BLOCKED"])
        self.assertEqual(env["_TD_HTTP_CALLS"],0)
        self.assertEqual(env["_TD_BUDGET"].summary(NOW)["used"],14)
        self.assertEqual(get.call_count,3)
        put.assert_not_called()


if __name__=="__main__":
    unittest.main(verbosity=2)
