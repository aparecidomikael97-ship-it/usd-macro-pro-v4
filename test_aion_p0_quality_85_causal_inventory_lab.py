"""Quality RED inventory integrity and safe activation trace (offline LAB).

The existing failing tests are not xfailed, removed, patched, skipped or
rebranded as passed. This audit only verifies the original 85 reported
FAIL/ERROR names from the full canonical Quality run and identifies at which
read-only validation stage an activation fixture stops.
"""
from __future__ import annotations

import ast
from collections import Counter
from datetime import timedelta
import json
from pathlib import Path
import unittest

from atlasquant_aion_global_worker_activation import (
    _runtime_armed_contract, _readiness_contract,
    prepare_global_worker_activation_plan,
    activate_global_worker_feature_flag,
)
from atlasquant_aion_global_worker_reactivation_gate import (
    assess_post_incident_reactivation_gate,
    validate_reactivation_gate_for_plan,
    validate_reactivation_gate_for_execution,
)
import test_atlasquant_aion_global_worker_activation as old_activation
import test_atlasquant_aion_global_worker_reactivation_gate as old_reactivation

ROOT=Path(__file__).resolve().parent
REGISTRY=ROOT/"docs/aion/AION_P0_QUALITY_CANONICAL_85_FAILURES_CASE_REGISTRY_20261019.json"
EXPECTED={
  "test_atlasquant_aion_global_worker":(21,0),
  "test_atlasquant_aion_global_worker_activation":(15,0),
  "test_atlasquant_aion_worker_runtime":(6,0),
  "test_atlasquant_aion_global_worker_live_verification":(5,0),
  "test_atlasquant_aion_global_worker_readiness":(2,0),
  "test_atlasquant_aion_global_worker_reactivation_gate":(1,2),
  "test_atlasquant_aion_execution_outbox":(0,23),
  "test_atlasquant_aion_execution_saga":(0,9),
  "test_quality_workflow_coverage":(1,0),
}
BLOCKER_M71="FRESH_INDEPENDENT_INCIDENT_SOURCE_NOT_ENROLLED"


def registry():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_methods(path):
    tree=ast.parse(path.read_text(encoding="utf-8"),filename=str(path))
    return {node.name for node in ast.walk(tree)
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))
            and node.name.startswith("test_")}


class Quality85CaseInventoryTests(unittest.TestCase):
    def test_01_exact_6562_quality_count_and_51_fail_34_error(self):
        x=registry()
        self.assertEqual(x["quality_total"],6562)
        self.assertEqual((x["fail_total"],x["error_total"],x["entries_total"]),(51,34,85))
        self.assertEqual(len(x["entries"]),85)
        self.assertEqual(x["status"],"RED_CANONICAL_HARD_NO_GO")
        self.assertEqual(x["p0_homologated"],0)
        self.assertIs(x["external_authority_enrolled"],False)

    def test_02_every_reported_case_really_exists_in_original_test_source(self):
        for row in registry()["entries"]:
            with self.subTest(module=row["module"],case=row["case"]):
                self.assertIn(row["case"],test_methods(ROOT/(row["module"]+".py")))

    def test_03_no_duplicate_error_name_or_unwaived_case(self):
        entries=registry()["entries"]
        ids=[(e["module"],e["case"]) for e in entries]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertTrue(all(e["triage_status"]=="OPEN_NOT_WAIVED" for e in entries))
        self.assertTrue(all(e["kind"] in ("FAIL","ERROR") for e in entries))

    def test_04_counts_by_module_are_fixed_to_actual_canonical_log(self):
        d=registry()
        self.assertEqual({k:(v["fail"],v["error"]) for k,v in d["module_totals"].items()},EXPECTED)
        counter=Counter((r["module"],r["kind"]) for r in d["entries"])
        for k,(f,e) in EXPECTED.items():
            self.assertEqual((counter[k,"FAIL"],counter[k,"ERROR"]),(f,e))

    def test_05_all_32_supplier_receipt_errors_remain_exceptions_not_waived(self):
        rows=[r for r in registry()["entries"]
              if r["module"] in ("test_atlasquant_aion_execution_outbox","test_atlasquant_aion_execution_saga")]
        self.assertEqual(len(rows),32)
        for item in rows:
            self.assertEqual(item["kind"],"ERROR")
            self.assertEqual(item["triage_group"],"PRODUCER_NOT_ENROLLED_HARDSTOP_OBSERVED")
            self.assertTrue(item["exception"].startswith("PermissionError: INDEPENDENT_PRODUCER"),item)

    def test_06_readiness_and_activation_positive_fixture_expectations_are_debt(self):
        rows=[r for r in registry()["entries"]
              if r["module"] in ("test_atlasquant_aion_global_worker_activation","test_atlasquant_aion_global_worker_readiness")]
        self.assertEqual(len(rows),17)
        self.assertTrue(all(r["kind"]=="FAIL" for r in rows))
        self.assertTrue(all("AssertionError" in r["exception"] for r in rows))

    def test_07_m71_original_canonical_three_failures_stay_recorded(self):
        rows=[r for r in registry()["entries"]
              if r["module"]=="test_atlasquant_aion_global_worker_reactivation_gate"]
        self.assertEqual(len(rows),3)
        self.assertEqual(sum(r["exception"].startswith("KeyError:") for r in rows),2)
        self.assertEqual(sum(r["exception"].startswith("AssertionError:") for r in rows),1)
        self.assertTrue(all(r["triage_status"]=="OPEN_NOT_WAIVED" for r in rows))

    def test_08_quality_coverage_red_explicitly_kept(self):
        rows=[r for r in registry()["entries"] if r["module"]=="test_quality_workflow_coverage"]
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["kind"],"FAIL")
        self.assertIn("Lists differ",rows[0]["exception"])

    def test_09_current_gate_execution_still_rejects_old_ready_receipt(self):
        runtime,_=old_reactivation._post_incident_runtime()
        flag=old_reactivation._safe_flag()
        readiness=old_reactivation._readiness()
        gate=assess_post_incident_reactivation_gate(
            runtime,old_reactivation._safe_reconciled_snapshot(runtime),
            readiness,flag,now=old_reactivation.NOW,
        )
        self.assertEqual(gate["status"],"REACTIVATION_GATE_READY")
        out=validate_reactivation_gate_for_execution(
            runtime,flag,
            {"post_incident_gate_required":True,
             "post_incident_closure_ledger_digest":gate["closure_ledger_digest"],
             "post_incident_latest_closure_record_id":gate["latest_closure_record_id"]},
            gate,now=old_reactivation.NOW+timedelta(seconds=10)
        )
        self.assertEqual(out,{"state":"BLOCKED",
                              "reason":BLOCKER_M71,
                              "gate_required":True,
                              "gate_digest":gate["gate_digest"],
                              "reactivation_authorized":False})

    def test_10_activation_plan_fixture_stage_tracing_never_executes(self):
        runtime,_=old_reactivation._post_incident_runtime()
        flag=old_reactivation._safe_flag()
        readiness=old_reactivation._readiness()
        gate=assess_post_incident_reactivation_gate(
            runtime,old_reactivation._safe_reconciled_snapshot(runtime),
            readiness,flag,now=old_reactivation.NOW,
        )
        stage={
            "runtime":_runtime_armed_contract(runtime),
            "readiness":_readiness_contract(readiness),
            "plan_gate":validate_reactivation_gate_for_plan(
                runtime,readiness,flag,gate,now=old_reactivation.NOW),
        }
        result=prepare_global_worker_activation_plan(
            old_reactivation._access(),runtime,readiness,flag,
            reactivation_gate=gate,now=old_reactivation.NOW,
        )
        self.assertEqual(result["status"],"BLOCKED",result)
        self.assertIs(result["feature_flag_modified"],False)
        self.assertIs(result["global_worker_executed"],False)
        self.assertNotIn("plan",result)
        print("P0_QUALITY_REACTIVATION_PREPLAN_CAUSAL_STAGE "+json.dumps({
            k:{"state":v.get("state"),"reason":v.get("reason")} for k,v in stage.items()
        },sort_keys=True))
        print("P0_QUALITY_REACTIVATION_FINAL_REASON="+str(result.get("reason")))

    def test_11_nonincident_legacy_activation_plan_stage_tracing_no_execution(self):
        fixture=old_activation.GlobalWorkerActivationCeremonyTests("test_plan_is_read_only_and_bound_to_persisted_armed_runtime")
        fixture.setUp() # creates ONLY local in-memory staged fixture
        runtime=fixture.runtime;readiness=fixture.readiness;flag=old_activation._safe_flag()
        result=prepare_global_worker_activation_plan(
            fixture.access,runtime,readiness,flag,now=old_activation.NOW,
        )
        self.assertEqual(result["status"],"BLOCKED")
        self.assertIs(result["feature_flag_modified"],False)
        self.assertIs(result["global_worker_executed"],False)
        print("P0_QUALITY_NONINCIDENT_PREPLAN_CAUSAL_STAGE "+json.dumps({
            "runtime":_runtime_armed_contract(runtime).get("state"),
            "readiness":_readiness_contract(readiness).get("state"),
            "gate":validate_reactivation_gate_for_plan(runtime,readiness,flag,None,now=old_activation.NOW).get("state"),
            "final_reason":result.get("reason"),
        },sort_keys=True))

    def test_12_no_injected_activation_writer_on_invalid_ticket(self):
        runtime,_=old_reactivation._post_incident_runtime()
        writes=[]
        out=activate_global_worker_feature_flag(
            old_reactivation._access(),runtime,{},old_reactivation._config(),
            confirmation=True,reactivation_gate=None,
            runtime_reader=lambda *a,**kw:runtime,
            flag_reader=lambda *a,**kw:old_reactivation._safe_flag(),
            flag_writer=lambda *a,**kw:writes.append(1),
            flag_disabler=lambda *a,**kw:writes.append(2),
            now=old_reactivation.NOW,
        )
        self.assertEqual(out["status"],"BLOCKED")
        self.assertEqual(writes,[])
        self.assertIs(out["global_worker_executed"],False)


if __name__=="__main__":
    unittest.main()
