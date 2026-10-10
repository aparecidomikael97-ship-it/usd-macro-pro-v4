"""No-network tests: legacy durable stores must not claim write was absent.

These are module-level tests for real application writer functions, with
mocked GitHub reads and writes. No keys, API, owner device, or paid provider.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import ast
import unittest

import requests
from legacy_protocol_reference_v1 import install_historical_write_protocol_fixture
import atlasquant_flight_recorder_store as flight
import atlasquant_research_evidence_store as research
import atlasquant_shadow_store as shadow

CASES=(
    (flight,"persist_records","_fetch_remote",[{"decision_id":"case-1"}],"records"),
    (research,"persist_research_evidence","_fetch",[{"record_id":"case-1","strategy":"reference"}],"records"),
    (shadow,"persist_shadow_samples","_fetch",[{"sample_id":"case-1"}],"samples"),
)
ARGS={"repo":"example/repository","branch":"atlasquant-runtime","token":"SYNTHETIC_DO_NOT_USE","retry_conflict_once":True}

def fake_response(status):
    def raise_status():
        if status>=400:
            raise requests.HTTPError("Synthetic HTTP conflict")
    return SimpleNamespace(status_code=status,raise_for_status=raise_status)

class LegacyPersistenceUnknownOutcomeTests(unittest.TestCase):
    def setUp(self):
        install_historical_write_protocol_fixture(self)

    def test_transport_timeout_after_dispatch_boundary_never_retries(self):
        for module,method,reader,data,field in CASES:
            with self.subTest(module=module.__name__), \
                 patch.object(module,reader,return_value=([],"")) as read, \
                 patch.object(module.requests,"put",side_effect=requests.Timeout("synthetic timeout")) as put:
                outcome=getattr(module,method)(data,**ARGS)
                self.assertEqual(outcome["reason"],"UNKNOWN_OUTCOME",outcome)
                self.assertEqual(outcome["write_outcome"],"UNKNOWN")
                self.assertIs(outcome["reconciliation_required"],True)
                self.assertIs(outcome["safe_to_retry"],False)
                self.assertIs(outcome["write_attempted"],True)
                self.assertEqual(outcome["error"],"Timeout")
                self.assertFalse(outcome["ok"])
                self.assertEqual(outcome[field],0)
                self.assertEqual(put.call_count,1)
                self.assertEqual(read.call_count,1)
                self.assertNotIn("SYNTHETIC_DO_NOT_USE",str(outcome))

    def test_302_forged_write_success_never_replayed_or_saved(self):
        for module,method,reader,data,_ in CASES:
            with self.subTest(module=module.__name__), \
                 patch.object(module,reader,return_value=([],"")) as read, \
                 patch.object(module.requests,"put",return_value=fake_response(302)) as put:
                outcome=getattr(module,method)(data,**ARGS)
                self.assertEqual(outcome["reason"],"UNKNOWN_OUTCOME")
                self.assertTrue(outcome["reconciliation_required"])
                self.assertFalse(outcome["safe_to_retry"])
                self.assertNotEqual(outcome["reason"],"CORRUPT_REMOTE")
                self.assertEqual(put.call_count,1)
                self.assertEqual(read.call_count,1)

    def test_known_409_stops_without_replay_even_if_retry_enabled(self):
        for module,method,reader,data,_ in CASES:
            with self.subTest(module=module.__name__), \
                 patch.object(module,reader,return_value=([],"")) as read, \
                 patch.object(module.requests,"put",return_value=fake_response(409)) as put:
                outcome=getattr(module,method)(data,**ARGS)
                self.assertEqual(outcome["reason"],"CONFLICT",outcome)
                self.assertEqual(outcome["write_outcome"],"REPORTED_CAS_CONFLICT")
                self.assertIs(outcome["safe_to_retry"],False)
                self.assertIs(outcome["reconciliation_required"],True)
                self.assertEqual(put.call_count,1)
                self.assertEqual(read.call_count,1)

    def test_http_422_validation_error_cannot_trigger_second_put(self):
        for module,method,reader,data,_ in CASES:
            with self.subTest(module=module.__name__), \
                 patch.object(module,reader,return_value=([],"")) as read, \
                 patch.object(module.requests,"put",return_value=fake_response(422)) as put:
                outcome=getattr(module,method)(data,**ARGS)
                self.assertEqual(outcome["reason"],"VALIDATION_REJECTED",outcome)
                self.assertEqual(outcome["write_outcome"],"REPORTED_HTTP_422")
                self.assertTrue(outcome["reconciliation_required"])
                self.assertIs(outcome["safe_to_retry"],False)
                self.assertEqual(put.call_count,1)
                self.assertEqual(read.call_count,1)

    def test_pre_send_corrupted_remote_is_not_claimed_as_dispatched(self):
        for module,method,reader,data,_ in CASES:
            with self.subTest(module=module.__name__), \
                 patch.object(module,reader,side_effect=ValueError("corrupt synthetic jsonl")), \
                 patch.object(module.requests,"put",side_effect=AssertionError("not allowed")) as put:
                outcome=getattr(module,method)(data,**ARGS)
                self.assertEqual(outcome["reason"],"CORRUPT_REMOTE",outcome)
                self.assertNotIn("write_outcome",outcome)
                put.assert_not_called()

    def test_pre_send_read_timeout_not_an_ambiguous_write(self):
        for module,method,reader,data,_ in CASES:
            with self.subTest(module=module.__name__), \
                 patch.object(module,reader,side_effect=requests.Timeout("synthetic read failed")), \
                 patch.object(module.requests,"put",side_effect=AssertionError("not allowed")) as put:
                outcome=getattr(module,method)(data,**ARGS)
                self.assertEqual(outcome["reason"],"IO_ERROR",outcome)
                self.assertNotIn("write_outcome",outcome)
                put.assert_not_called()

    def test_source_guard_pins_three_actual_writers(self):
        root=Path(__file__).resolve().parents[1]
        for module,method,_,_,_ in CASES:
            path=root/(module.__name__+".py")
            tree=ast.parse(path.read_text("utf-8"),filename=str(path))
            found=[node for node in ast.walk(tree)
                   if isinstance(node,ast.FunctionDef) and node.name==method]
            self.assertEqual(len(found),1,module.__name__)
            fn=found[0]
            writes=[node for node in ast.walk(fn)
                    if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
                    and isinstance(node.func.value,ast.Name)
                    and node.func.value.id=="requests" and node.func.attr=="put"]
            self.assertEqual(len(writes),1,module.__name__)
            self.assertTrue(any(
                isinstance(node,ast.Assign)
                and any(isinstance(t,ast.Name) and t.id=="write_attempted" for t in node.targets)
                and isinstance(node.value,ast.Constant) and node.value.value is True
                and node.lineno<writes[0].lineno
                for node in ast.walk(fn)),module.__name__)
            source=ast.get_source_segment(path.read_text("utf-8"),fn)
            self.assertIn('"reason":"UNKNOWN_OUTCOME"',source)
            self.assertIn('"reconciliation_required":True',source)
            self.assertIn('"safe_to_retry":False',source)
            self.assertIn('"write_outcome":"REPORTED_CAS_CONFLICT"',source)
            self.assertIn('"write_outcome":"REPORTED_HTTP_422"',source)
            self.assertIn("attempts=1",source)
            self.assertNotIn("continue  # Bounded re-read",source)

if __name__=="__main__":
    unittest.main()
