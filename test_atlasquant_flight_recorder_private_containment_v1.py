"""Flight Recorder private tenant-source containment. No real data/network.

Real production code is imported or executed from the exact source AST.
Only synthetic session dictionaries and patch-mocked prohibited sinks are used.
"""
from __future__ import annotations
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from atlasquant_flight_recorder_store import (
    FLIGHT_RECORDER_PATH, _fetch_remote, load_persistent_records, persist_records,
)
import atlasquant_flight_recorder_panel as panel
from atlasquant_private_read_gate_v1 import (
    clear_private_ui_state, DISPLAY_KEYS, PENDING_KEYS, QUARANTINE_KEY, SCOPE_KEY,
)
from atlasquant_legacy_private_resource_gate_v1 import legacy_private_remote_resource_allowed

ROOT=Path(__file__).resolve().parent

class FlightPrivateContainmentTests(unittest.TestCase):
    def test_shared_flight_recorder_path_never_authorized_by_admin_from_either_tenant(self):
        self.assertEqual(FLIGHT_RECORDER_PATH,"dados/atlasquant_flight_recorder.jsonl")
        for tenant in ("tenant_one", "tenant_two"):
            with self.subTest(tenant=tenant):
                self.assertFalse(legacy_private_remote_resource_allowed(FLIGHT_RECORDER_PATH))

    def test_production_writer_is_unconditional_HARD_DENIED_with_no_network(self):
        for branch in ("atlasquant-runtime","main"):
            for token in ("synthetic", ""):
                with self.subTest(branch=branch,token=token), \
                     patch("atlasquant_flight_recorder_store.requests.get",side_effect=AssertionError("GET")) as get, \
                     patch("atlasquant_flight_recorder_store.requests.put",side_effect=AssertionError("PUT")) as put, \
                     patch("atlasquant_flight_recorder_store.require_runtime_branch",side_effect=AssertionError("BRANCH")) as branch_check:
                    result=persist_records([{"private":"A"}],repo="fake/repo",branch=branch,token=token)
                self.assertEqual(result["reason"],"HARD_DENIED")
                self.assertFalse(result["ok"])
                self.assertFalse(result["safe_to_retry"])
                self.assertTrue(result["reconciliation_required"])
                get.assert_not_called(); put.assert_not_called(); branch_check.assert_not_called()

    def test_remote_fetch_denied_even_if_session_auth_were_authorized(self):
        with patch("atlasquant_private_read_gate_v1.require_private_read",return_value=None), \
             patch("atlasquant_flight_recorder_store.requests.get",side_effect=AssertionError("NETWORK")) as network:
            with self.assertRaisesRegex(PermissionError,"TENANT_SOURCE_UNBOUND"):
                _fetch_remote("fake/repo","atlasquant-runtime","synthetic",15)
        network.assert_not_called()

    def test_loader_denies_before_branch_validation_token_or_network(self):
        with patch("atlasquant_private_read_gate_v1.require_private_read",return_value=None), \
             patch("atlasquant_flight_recorder_store.require_runtime_branch",side_effect=AssertionError("BRANCH")) as branch, \
             patch("atlasquant_flight_recorder_store.requests.get",side_effect=AssertionError("NETWORK")) as network:
            with self.assertRaisesRegex(PermissionError,"TENANT_SOURCE_UNBOUND"):
                load_persistent_records(repo="fake/repo",branch="atlasquant-runtime",token="fake")
        branch.assert_not_called(); network.assert_not_called()

    def test_unscoped_private_rows_and_hydrated_flag_are_evicted(self):
        self.assertIn("atlasquant_session_flight_recorder",DISPLAY_KEYS)
        for tenant in ("tenant_one", "tenant_two"):
            with self.subTest(tenant=tenant):
                state={SCOPE_KEY:"synthetic-"+tenant,
                       "atlasquant_session_flight_recorder":[{"secret":"FROM_A"}],
                       "atlasquant_flight_recorder_hydrated":True,
                       "atlasquant_flight_recorder_load_status":{"ok":True,"reason":"LOADED"}}
                fake=SimpleNamespace(session_state=state)
                with patch.object(panel,"st",fake), \
                     patch.object(panel,"private_read_allowed",return_value=True), \
                     patch.object(panel,"load_remote_records",side_effect=AssertionError("REMOTE")) as remote, \
                     patch.object(panel,"persist_current_record",side_effect=AssertionError("PERSIST")) as persist, \
                     patch.object(panel,"prepare_flight_capture",side_effect=AssertionError("CAPTURE")) as capture:
                    result=panel.capture_flight_recorder({"pair":"EUR/USD"},"synthetic")
                self.assertEqual(result["rows"],[])
                self.assertEqual(result["load_status"]["reason"],"TENANT_SOURCE_UNBOUND")
                self.assertEqual(result["summary"]["records"],0)
                for key in (*DISPLAY_KEYS,SCOPE_KEY):
                    self.assertNotIn(key,state)
                remote.assert_not_called(); persist.assert_not_called(); capture.assert_not_called()

    def test_expired_session_produces_ACCESS_DENIED_and_evicts_display(self):
        state={"atlasquant_session_flight_recorder":[{"secret":"A"}],
               "atlasquant_flight_recorder_hydrated":True}
        with patch.object(panel,"st",SimpleNamespace(session_state=state)), \
             patch.object(panel,"private_read_allowed",return_value=False):
            result=panel.capture_flight_recorder({}, "synthetic")
        self.assertEqual(result["persistence"]["reason"],"ACCESS_DENIED")
        self.assertNotIn("atlasquant_session_flight_recorder",state)

    def test_caller_supplied_capture_cannot_export_or_display_private_rows(self):
        state={"atlasquant_session_flight_recorder":[{"secret":"A"}]}
        view=SimpleNamespace(session_state=state,
            warning=Mock(),download_button=Mock(),dataframe=Mock(),markdown=Mock(),caption=Mock())
        with patch.object(panel,"st",view), \
             patch.object(panel,"private_read_allowed",return_value=True), \
             patch.object(panel,"capture_flight_recorder",side_effect=AssertionError("CAPTURE")) as capture:
            summary=panel.render_flight_recorder(None,"synthetic",capture_result={
                "rows":[{"secret":"FROM_A"}], "added":True,
                "summary":{"records":1,"decisions":1,"blocked":0},
            })
        self.assertEqual(summary,{"records":0,"decisions":0,"blocked":0})
        self.assertNotIn("atlasquant_session_flight_recorder",state)
        view.warning.assert_called_once()
        view.download_button.assert_not_called()
        view.dataframe.assert_not_called(); capture.assert_not_called()

    def test_pending_unknown_outcome_is_preserved_in_quarantine_not_exported(self):
        state={SCOPE_KEY:"from-A",
               "atlasquant_session_flight_recorder":[{"private":"A"}],
               "atlasquant_flight_recorder_hydrated":True,
               "atlasquant_flight_recorder_persistence":{
                   "reason":"UNKNOWN_OUTCOME","write_attempted":True,
                   "reconciliation_required":True}}
        with patch.object(panel,"st",SimpleNamespace(session_state=state)), \
             patch.object(panel,"private_read_allowed",return_value=True):
            result=panel.capture_flight_recorder({}, "synthetic")
        self.assertEqual(result["rows"],[])
        self.assertTrue(state[QUARANTINE_KEY])
        self.assertEqual(state[PENDING_KEYS[2]]["reason"],"UNKNOWN_OUTCOME")
        self.assertTrue(state[PENDING_KEYS[2]]["write_attempted"])
        self.assertNotIn("atlasquant_session_flight_recorder",state)
        self.assertNotIn("atlasquant_flight_recorder_persistence",state)
        self.assertNotIn(SCOPE_KEY,state)

    def test_public_snapshot_helpers_do_not_claim_persisted_when_denied(self):
        with patch.object(panel,"st",SimpleNamespace(session_state={})), \
             patch.object(panel,"private_read_allowed",return_value=True), \
             patch.object(panel,"runtime_persistence_config",side_effect=AssertionError("TOKEN")) as token:
            rows, status=panel.load_remote_records()
            save=panel.persist_current_record({"secret":"A"})
        self.assertEqual(rows,[])
        self.assertEqual(status["reason"],"TENANT_SOURCE_UNBOUND")
        self.assertEqual(save["reason"],"TENANT_SOURCE_UNBOUND")
        token.assert_not_called()

    def test_source_guards_at_actual_store_io_and_status_keys(self):
        store=(ROOT/"atlasquant_flight_recorder_store.py").read_text("utf-8")
        source=(ROOT/"atlasquant_flight_recorder_panel.py").read_text("utf-8")
        tree=ast.parse(store)
        fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=="persist_records")
        self.assertIsInstance(fn.body[0],ast.Return)
        self.assertIn("HARD_DENIED",ast.get_source_segment(store,fn.body[0]))
        for func in ("_fetch_remote","load_persistent_records"):
            x=next(z for z in tree.body if isinstance(z,ast.FunctionDef) and z.name==func)
            code=ast.get_source_segment(store,x)
            self.assertLess(code.index("require_legacy_private_remote_resource"),code.find("requests.get(") if "requests.get(" in code else len(code))
        self.assertIn("def _flight_private_denial()",source)
        self.assertIn('st.warning("🔒 Flight Recorder privado indisponível:',source)

if __name__=="__main__":
    unittest.main()
