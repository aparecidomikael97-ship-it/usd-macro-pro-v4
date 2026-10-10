"""Hard-deny regression: no writer call without independently durable claim."""
from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import inspect
import subprocess
import sys
import unittest
from unittest.mock import Mock

from atlasquant_aion_v2_autopilot_evidence_guard import guarded_autopilot_evidence_write

ROOT = Path(__file__).resolve().parents[1]

def attempt(*,repo="fixture/repo",branch="atlasquant-runtime",sink="shadow",writer=None):
    return guarded_autopilot_evidence_write(
        repo=repo,branch=branch,sink=sink,
        write=writer if writer is not None else Mock(side_effect=AssertionError("WRITER_CALLED")),
    )


class TestDurableClaimRequired(unittest.TestCase):
    def assert_rejected(self,result,reason="DURABLE_CLAIM_REQUIRED"):
        self.assertIs(result["ok"],False)
        self.assertEqual(result["reason"],reason)
        self.assertIs(result["write_attempted"],False)
        self.assertIs(result["safe_to_retry"],False)
        self.assertIs(result["verified"],False)
        self.assertIs(result["external_writer_called"],False)
        self.assertIs(result["reconciliation_required"],True)

    def test_shadow_denied(self):
        self.assert_rejected(attempt())

    def test_flight_denied(self):
        self.assert_rejected(attempt(sink="flight"))

    def test_no_forged_success_can_be_returned(self):
        writer=Mock(return_value={"ok":True,"reason":"SAVED","verified":True})
        self.assert_rejected(attempt(writer=writer))
        writer.assert_not_called()

    def test_no_forged_already_present_can_be_returned(self):
        writer=Mock(return_value={"ok":True,"reason":"ALREADY_PRESENT"})
        self.assert_rejected(attempt(writer=writer))
        writer.assert_not_called()

    def test_no_simulated_unknown_writer_attempt(self):
        writer=Mock(side_effect=TimeoutError("an attempted write"))
        self.assert_rejected(attempt(writer=writer))
        writer.assert_not_called()

    def test_unknown_sink(self):
        self.assert_rejected(attempt(sink="other"),"INVALID_SINK_IDENTITY")

    def test_blank_repo(self):
        self.assert_rejected(attempt(repo=""),"INVALID_SINK_IDENTITY")

    def test_blank_branch(self):
        self.assert_rejected(attempt(branch=""),"INVALID_SINK_IDENTITY")

    def test_blank_sink(self):
        self.assert_rejected(attempt(sink=""),"INVALID_SINK_IDENTITY")

    def test_concurrent_shadow_calls_never_write(self):
        writer=Mock(side_effect=AssertionError("CALLED"))
        with ThreadPoolExecutor(max_workers=16) as pool:
            results=list(pool.map(lambda _:attempt(writer=writer),range(64)))
        self.assertTrue(all(r["reason"]=="DURABLE_CLAIM_REQUIRED" for r in results))
        writer.assert_not_called()

    def test_concurrent_different_sinks_never_write(self):
        writer=Mock(side_effect=AssertionError("CALLED"))
        with ThreadPoolExecutor(max_workers=16) as pool:
            results=list(pool.map(lambda i:attempt(sink=("shadow" if i%2 else "flight"),writer=writer),range(64)))
        self.assertTrue(all(not r["ok"] for r in results))
        writer.assert_not_called()

    def test_sequential_new_operations_still_denied(self):
        writer=Mock()
        for _ in range(20):
            self.assert_rejected(attempt(writer=writer))
        writer.assert_not_called()

    def test_no_argument_to_bypass_durable_gate(self):
        p=inspect.signature(guarded_autopilot_evidence_write).parameters
        self.assertEqual(set(p),{"repo","branch","sink","write"})

    def test_only_public_entrypoint(self):
        import atlasquant_aion_v2_autopilot_evidence_guard as m
        self.assertEqual(m.__all__,["guarded_autopilot_evidence_write"])
        self.assertFalse(hasattr(m,"clear_quarantine"))
        self.assertFalse(hasattr(m,"approve_claim"))

    def test_actual_autopilot_calls_guard_for_both_sinks(self):
        text=(ROOT/"autopilot_v107.py").read_text(encoding="utf-8")
        module=ast.parse(text)
        fn=next(x for x in module.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))
                and x.name=="persist_decision_evidence")
        calls=[x for x in ast.walk(fn) if isinstance(x,ast.Call) and
               isinstance(x.func,ast.Name) and x.func.id=="guarded_autopilot_evidence_write"]
        self.assertEqual(len(calls),2)
        sinks=sorted(k.value.value for c in calls for k in c.keywords
                     if k.arg=="sink" and isinstance(k.value,ast.Constant))
        self.assertEqual(sinks,["flight","shadow"])

    def test_new_python_process_same_denial(self):
        script=(
            "from atlasquant_aion_v2_autopilot_evidence_guard import guarded_autopilot_evidence_write as g;"
            "r=g(repo='fixture/repo',branch='atlasquant-runtime',sink='shadow',"
            "write=lambda: (_ for _ in ()).throw(AssertionError('CALLED')));"
            "assert r['reason']=='DURABLE_CLAIM_REQUIRED' and not r['external_writer_called']"
        )
        p=subprocess.run([sys.executable,"-B","-c",script],
                         cwd=ROOT,capture_output=True,text=True,timeout=10)
        self.assertEqual(p.returncode,0,p.stderr)


if __name__=="__main__":
    unittest.main()
