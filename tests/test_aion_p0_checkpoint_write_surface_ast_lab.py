"""Synthetic tests for the read-only A136 Checkpoint Mestre surface inventory."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "tools" / "aion_p0_checkpoint_write_surface_audit.py"
SPEC = importlib.util.spec_from_file_location("aion_write_surface_audit", PATH)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(mod)


class CheckpointWriteSurfaceASTLAB(unittest.TestCase):
    def test_01_direct_requests_put_detected(self):
        entry=mod.inspect_source('requests.put("https://example.invalid")',"sample.py")
        self.assertEqual(entry["network_or_mutator_candidates"][0]["kind"],"requests.put")

    def test_02_indirect_request_put_method_detected(self):
        entry=mod.inspect_source('requests.request("PUT", url)',"sample.py")
        self.assertEqual(entry["network_or_mutator_candidates"][0]["kind"],"requests.request")

    def test_03_request_get_is_not_a_mutator(self):
        entry=mod.inspect_source('requests.request("GET", url)',"sample.py")
        self.assertEqual(entry["network_or_mutator_candidates"],[])

    def test_04_dynamic_unknown_http_verb_is_not_proved_safe(self):
        # A limitation: dynamic method dispatch cannot be resolved statically.
        entry=mod.inspect_source('requests.request(method_name, url)',"sample.py")
        self.assertEqual(entry["network_or_mutator_candidates"],[])

    def test_05_literal_checkpoint_path_located(self):
        entry=mod.inspect_source('RUNTIME_PATH="dados/aion/checkpoint_master.json"',"sample.py")
        self.assertEqual(entry["checkpoint_literal_lines"],[1])

    def test_06_main_writer_call_located(self):
        entry=mod.inspect_source('save_runtime_checkpoint(payload, cfg, approved=True)',"sample.py")
        self.assertEqual(len(entry["runtime_save_calls"]),1)

    def test_07_fully_qualified_writer_call_located(self):
        entry=mod.inspect_source('memory.save_runtime_checkpoint(payload)',"sample.py")
        self.assertEqual(entry["runtime_save_calls"][0]["callee"],"memory.save_runtime_checkpoint")

    def test_08_other_create_file_mutator_detected(self):
        entry=mod.inspect_source('github.create_file(path, data)',"sample.py")
        self.assertEqual(entry["network_or_mutator_candidates"][0]["kind"],"github.create_file")

    def test_09_other_client_put_heuristic_candidate(self):
        entry=mod.inspect_source('client.put(endpoint, data=body)',"sample.py")
        self.assertEqual(entry["network_or_mutator_candidates"][0]["kind"],"client.put")

    def test_10_other_python_named_put_not_checkpoint_by_itself(self):
        entry=mod.inspect_source('q.put(item)',"sample.py")
        self.assertFalse(entry["contextual"])

    def test_11_source_call_is_parsed_not_executed(self):
        entry=mod.inspect_source('raise AssertionError("EXECUTED")\nrequests.put(x)',"sample.py")
        self.assertEqual(len(entry["network_or_mutator_candidates"]),1)

    def test_12_configured_a135_writer_guard_comes_before_put(self):
        shape=mod.guard_shape(ROOT)
        self.assertTrue(shape["ok"],shape)

    def test_13_inventory_always_labels_no_go_not_enrolled(self):
        report=mod.audit_tree(ROOT)
        self.assertEqual(report["status"],"STATIC_SOURCE_INVENTORY_ONLY_NO_GO")
        self.assertIs(report["runtime_write_authorized"],False)
        self.assertIs(report["external_witness_enrolled"],False)
        self.assertGreater(report["scanned_python_files"],300)


if __name__=="__main__":
    unittest.main()
