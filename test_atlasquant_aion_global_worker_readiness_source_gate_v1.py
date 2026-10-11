"""Readiness must not advertise PASS before independent source trust exists.

Runs real production function source extracted by AST with no network or
trusted authority. Synthetic old-case positive readiness tests remain local.
"""
from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Mapping
import unittest
from unittest.mock import Mock

from atlasquant_aion_global_worker_source_gate_v1 import (
    independent_worker_source_preflight,
)

SRC=Path(__file__).resolve().parent/"atlasquant_aion_global_worker_readiness.py"


def extract(name, scope):
    program=ast.parse(SRC.read_text("utf-8"))
    matches=[x for x in program.body if isinstance(x,ast.FunctionDef) and x.name==name]
    if len(matches)!=1:
        raise AssertionError("Missing/ambiguous function: "+name)
    node=ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        matches[0],
    ], type_ignores=[])
    args=dict(scope)
    exec(compile(ast.fix_missing_locations(node),str(SRC),"exec"),args)
    return args[name]


class GlobalWorkerReadinessSourceTruthTests(unittest.TestCase):
    def setUp(self):
        self.network=Mock(side_effect=AssertionError("NO_NETWORK"))
        self.run=Mock(side_effect=AssertionError("NO_EXECUTOR"))
        self.config=SimpleNamespace(
            token="fake-token",repo="fake/repo",branch="atlasquant-runtime",
            path="dados/aion/checkpoint_master.json",write_ready=True,
        )
        self.result={
            "status":"CONFIRMED", "sha":"gitsha-synthetic",
            "checkpoint":{},
            "integrity":{"state":"CONFIRMED"},
        }
        self.scope={
            "Mapping": Mapping,  # Source function extracted by AST: type imported in real module.
            "evaluate_runtime_branch": lambda branch: SimpleNamespace(
                safe_for_runtime_writes=True, branch="atlasquant-runtime"
            ),
            "checkpoint_integrity_report": lambda value: {"state":"CONFIRMED"},
            "independent_worker_source_preflight":independent_worker_source_preflight,
            "GLOBAL_WORKER_NAMESPACE":"aion_global_worker_v1",
            "GLOBAL_FLAG":"ATLASQUANT_AION_GLOBAL_WORKER_ENABLED",
            "SCHEMA":"SYNTHETIC_READINESS_V1",
            "_utc":lambda dt:dt,
            "workflow_contract":lambda x:{"state":"PASS"},
            "pulse_health":lambda *a,**kw:{"state":"PASS"},
            "protocol_shadow_probe":lambda *a,**kw:{"state":"PASS"},
            "feature_flag_state":lambda value:"UNSET",
            "load_global_worker_state": self.run,
            "global_worker_integrity": self.run,
            "requests_get":self.network,
        }
        self.posture=extract("runtime_posture",self.scope)

    def test_fully_confirmed_github_sha_still_not_ready(self):
        p=self.posture(self.result,self.config)
        self.assertEqual(p["state"],"BLOCKED")
        self.assertEqual(p["source_trust_state"],"UNAVAILABLE")
        self.assertFalse(p["source_trust_verified"])
        self.assertEqual(p["checkpoint_integrity"],"CONFIRMED")
        self.assertTrue(p["runtime_sha_present"])
        self.network.assert_not_called()

    def test_forged_source_fields_in_checkpoint_are_not_authority(self):
        for payload in [
            {"source_trust_verified":True},
            {"status":"CONFIRMED","source_trust_state":"VERIFIED"},
            {"source_proof":{"signature":"fake","owner_id":"owner"}},
            {"witness":{"head_sequence":10000}},
            {"owner_id":"HUMAN_OWNER","tenant_id":"company-A"},
        ]:
            with self.subTest(payload=payload):
                p=self.posture({**self.result,**payload},self.config)
                self.assertEqual(p["state"],"BLOCKED")
                self.assertFalse(p["source_trust_verified"])

    def test_readiness_stage_blocks_before_arming_or_flag_enable(self):
        scope={**self.scope,"runtime_posture":self.posture}
        snapshot=extract("activation_readiness_snapshot",scope)
        out=snapshot(
            runtime_result=self.result,
            config=self.config,
            feature_flag_raw="",
            workflow_text="synthetic-healthy",
            pulse_rows=[],
            now=datetime(2026,10,10,12,0,tzinfo=timezone.utc),
        )
        self.assertEqual(out["status"],"BLOCKED")
        self.assertEqual(out["activation_stage"],"BLOCKED")
        self.assertIn("INDEPENDENT_CHECKPOINT_SOURCE_UNAVAILABLE",out["blockers"])
        self.assertIn("RUNTIME_POSTURE_NOT_CONFIRMED",out["blockers"])
        self.assertFalse(out["runtime"]["source_trust_verified"])
        self.assertFalse(out["worker_armed_by_this_check"])
        self.network.assert_not_called()

    def test_no_readiness_adapter_calls_network_or_worker(self):
        result=self.posture(self.result,self.config)
        self.assertEqual(result["state"],"BLOCKED")
        self.network.assert_not_called()
        self.run.assert_not_called()

    def test_unverified_source_positive_status_alone_cannot_mark_ready(self):
        scope={**self.scope,"independent_worker_source_preflight":lambda cfg: {
            "status":"VERIFIED","source_verified":False}}
        p=extract("runtime_posture",scope)(self.result,self.config)
        self.assertEqual(p["state"],"BLOCKED")
        self.assertFalse(p["source_trust_verified"])

    def test_source_gate_checked_before_ready_state_is_decided(self):
        code=SRC.read_text("utf-8")
        node=next(x for x in ast.parse(code).body
                  if isinstance(x,ast.FunctionDef) and x.name=="runtime_posture")
        part=ast.get_source_segment(code,node)
        self.assertLess(part.index("independent_worker_source_preflight(config)"),
                        part.index("safe = bool("))
        self.assertIn("and branch.safe_for_runtime_writes",part)


if __name__=="__main__":
    unittest.main()
