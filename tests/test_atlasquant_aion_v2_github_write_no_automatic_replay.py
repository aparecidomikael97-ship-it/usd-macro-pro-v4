"""Offline regression: no automatic GitHub write replay even on HTTP 409."""
from __future__ import annotations
import ast,base64,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import requests
from atlasquant_aion_v2_github_write_url_guard import guard_github_token_read_destination,guard_github_write_destination
from atlasquant_aion_v2_github_read_response_guard import reject_github_read_unexpected_status
from atlasquant_aion_v2_github_write_response_guard import reject_github_write_unexpected_status

ROOT=Path(__file__).resolve().parents[1]
def extract_autopilot_real_function():
    path=ROOT/"autopilot_v107.py"
    src=path.read_text("utf-8")
    t=ast.parse(src,filename=str(path))
    functions=[n for n in t.body if isinstance(n,ast.FunctionDef) and n.name=="gh_put_bytes"]
    assert len(functions)==1
    fn=functions[0]
    assert not any(isinstance(n,(ast.For,ast.While,ast.AsyncFor)) for n in ast.walk(fn))
    return compile(ast.Module(body=[fn],type_ignores=[]),str(path),"exec")
REAL_AUTOPILOT=extract_autopilot_real_function()

def fake(status):
    return SimpleNamespace(status_code=status,json=lambda:{"sha":"synthetic_old_sha"},
                           raise_for_status=lambda:None)

def run_autopilot(*,get_status=200,put_status=200,put_error=None):
    get=Mock(return_value=fake(get_status))
    put=Mock(side_effect=put_error) if put_error is not None else Mock(return_value=fake(put_status))
    ns={
        "TOKEN":"SYNTHETIC_NON_REAL","REPO":"example/repository","BRANCH":"atlasquant-runtime",
        "gh_headers":lambda:{"Authorization":"Bearer SYNTHETIC_NON_REAL"},
        "requests":SimpleNamespace(get=get,put=put),"base64":base64,
        "guard_github_token_read_destination":guard_github_token_read_destination,
        "guard_github_write_destination":guard_github_write_destination,
        "reject_github_read_unexpected_status":reject_github_read_unexpected_status,
        "reject_github_write_unexpected_status":reject_github_write_unexpected_status,
    }
    exec(REAL_AUTOPILOT,ns)
    ret=ns["gh_put_bytes"]("dados/autopilot_status_v107.json",b"fake","synthetic")
    return ret,get,put

class NoAutomaticReplay(unittest.TestCase):
    def test_409_no_replay(self):
        (ok,reason),get,put=run_autopilot(put_status=409)
        self.assertFalse(ok)
        self.assertEqual(reason,"REPORTED_GITHUB_HTTP_409_NO_AUTORETRY_RECONCILE_FIRST")
        self.assertEqual((get.call_count,put.call_count),(1,1))
    def test_422_no_replay(self):
        (ok,reason),get,put=run_autopilot(put_status=422)
        self.assertFalse(ok)
        self.assertEqual(reason,"REPORTED_GITHUB_HTTP_422_VALIDATION_NO_AUTORETRY_RECONCILE_FIRST")
        self.assertEqual((get.call_count,put.call_count),(1,1))
    def test_forged_302_no_replay(self):
        (ok,reason),get,put=run_autopilot(put_status=302)
        self.assertFalse(ok)
        self.assertTrue(reason.startswith("UNKNOWN_GITHUB_WRITE_OUTCOME_RECONCILE_NO_RETRY:"))
        self.assertEqual((get.call_count,put.call_count),(1,1))
    def test_write_timeout_does_not_replay(self):
        (ok,reason),get,put=run_autopilot(put_error=requests.Timeout("synthetic"))
        self.assertFalse(ok)
        self.assertEqual(reason,"UNKNOWN_GITHUB_WRITE_OUTCOME_RECONCILE_NO_RETRY:Timeout")
        self.assertEqual((get.call_count,put.call_count),(1,1))
        self.assertNotIn("SYNTHETIC_NON_REAL",reason)
    def test_read_rejected_sends_no_write(self):
        (ok,reason),get,put=run_autopilot(get_status=302)
        self.assertFalse(ok)
        self.assertEqual(reason,"PRE_WRITE_GITHUB_READ_OR_VALIDATION_FAILED:ValueError")
        self.assertEqual((get.call_count,put.call_count),(1,0))
    def test_real_success_still_one_write(self):
        (ok,reason),get,put=run_autopilot(put_status=200)
        self.assertTrue(ok)
        self.assertEqual(reason,"")
        self.assertEqual((get.call_count,put.call_count),(1,1))
        self.assertEqual(put.call_args.args[0],"https://api.github.com/repos/example/repository/contents/dados/autopilot_status_v107.json")
        self.assertEqual(put.call_args.kwargs["json"]["sha"],"synthetic_old_sha")
        self.assertIs(put.call_args.kwargs["allow_redirects"],False)
    def test_three_legacy_writers_one_attempt_static(self):
        mapping={
            "atlasquant_flight_recorder_store.py":"persist_records",
            "atlasquant_research_evidence_store.py":"persist_research_evidence",
            "atlasquant_shadow_store.py":"persist_shadow_samples",
        }
        for path,func in mapping.items():
            with self.subTest(path=path):
                text=(ROOT/path).read_text("utf-8")
                tree=ast.parse(text)
                funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==func]
                self.assertEqual(len(funcs),1)
                fn=funcs[0]
                assigns=[n for n in ast.walk(fn) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="attempts" for t in n.targets)]
                self.assertEqual(len(assigns),1)
                self.assertIsInstance(assigns[0].value,ast.Constant)
                self.assertEqual(assigns[0].value.value,1)
                writes=[n for n in ast.walk(fn) if isinstance(n,ast.Call)
                        and isinstance(n.func,ast.Attribute)
                        and isinstance(n.func.value,ast.Name)
                        and n.func.value.id=="requests" and n.func.attr=="put"]
                self.assertEqual(len(writes),1)
                self.assertNotIn("continue",ast.get_source_segment(text,fn))
if __name__=="__main__":
    unittest.main()
