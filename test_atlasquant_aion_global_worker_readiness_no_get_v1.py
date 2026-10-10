"""Actual readiness CLI no-GET when independent source trust is absent.

Offline tests extract the REAL _cli and activation_readiness_snapshot functions
without importing Streamlit, requests or any secret-bearing production modules.
Synthetic CLI arguments/workflow text only. No real HTTP/files/credentials.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from atlasquant_aion_global_worker_source_gate_v1 import (
    independent_worker_source_preflight,
)

SOURCE=Path(__file__).resolve().parent/"atlasquant_aion_global_worker_readiness.py"


def extract_real(name, scope):
    parsed=ast.parse(SOURCE.read_text("utf-8"))
    nodes=[n for n in parsed.body if isinstance(n, ast.FunctionDef) and n.name==name]
    if len(nodes)!=1:
        raise AssertionError("Production function not found uniquely: "+name)
    node=ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        nodes[0],
    ],type_ignores=[])
    env=dict(scope)
    exec(compile(ast.fix_missing_locations(node),str(SOURCE),"exec"),env)
    return env[name]


class ReadinessNoUnboundNetworkTests(unittest.TestCase):
    def setUp(self):
        self.config=SimpleNamespace(
            token="synthetic-secret-must-not-print",
            repo="companyA/repo", branch="atlasquant-runtime",
            path="dados/aion/checkpoint_master.json",
            tenant_id="tenantA", owner_id="ownerA", write_ready=True,
        )
        self.runtime_get=Mock(side_effect=AssertionError("CHECKPOINT_GET_SENT"))
        self.pulse_get=Mock(side_effect=AssertionError("PULSE_GET_SENT"))
        self.env_lookups=[]
        self.source_gate=independent_worker_source_preflight

        def getenv(key,default=""):
            self.env_lookups.append(key)
            if key in ("GITHUB_TOKEN_HISTORICO", "GITHUB_TOKEN"):
                raise AssertionError("GITHUB_TOKEN_ACCESSED")
            if key == "GLOBAL_WORKER_FLAG_STATE":
                return "1"  # even an enabled flag must never admit untrusted GET
            return default

        self.getenv=getenv
        class FakePath:
            def __init__(self,path):
                self.path=path
            def read_text(self,*,encoding):
                return "synthetic-workflow-content"

        self.scope={
            "argparse": argparse,
            "AUTOPILOT_WORKFLOW": ".github/workflows/autopilot-v107.yml",
            "config_from_mapping": lambda: self.config,
            "independent_worker_source_preflight": self.source_gate,
            "load_runtime_checkpoint": self.runtime_get,
            "fetch_recent_autopilot_pulses": self.pulse_get,
            "Path": FakePath,
            "os": SimpleNamespace(getenv=self.getenv),
            "datetime":datetime, "timezone":timezone, "json":json,
        }
        ready_scope={
            "SCHEMA":"SYNTHETIC_READINESS",
            "GLOBAL_FLAG":"ATLASQUANT_AION_GLOBAL_WORKER_ENABLED",
            "_utc":lambda t:t,
            "runtime_posture":lambda result,config:{
                "state":"BLOCKED", "source_trust_verified":False,
                "source_trust_state":"UNAVAILABLE", "global_worker_state":"ABSENT",
                "global_kill_switch":True,
            },
            "workflow_contract":lambda value:{"state":"PASS"},
            "pulse_health":lambda items,now:{"state":"BLOCKED"},
            "protocol_shadow_probe":lambda now:{"state":"PASS"},
            "feature_flag_state":lambda value:"ENABLED",
        }
        self.scope["activation_readiness_snapshot"] = extract_real(
            "activation_readiness_snapshot", ready_scope
        )

    def run_cli(self, *, source=None):
        scope=dict(self.scope)
        if source is not None:
            scope["independent_worker_source_preflight"]=source
        fn=extract_real("_cli",scope)
        buf=StringIO()
        with patch.object(sys,"argv",["readiness","--check-runtime"]),redirect_stdout(buf):
            rc=fn()
        return rc,json.loads(buf.getvalue())

    def test_unenrolled_readiness_cli_no_checkpoint_pulse_or_token(self):
        rc,report=self.run_cli()
        self.assertEqual(rc,1)
        self.assertEqual(report["status"],"BLOCKED")
        self.assertEqual(report["activation_stage"],"BLOCKED")
        self.assertIn("INDEPENDENT_CHECKPOINT_SOURCE_UNAVAILABLE",report["blockers"])
        self.assertIn("PULSE_EVIDENCE_UNAVAILABLE",report["blockers"])
        self.assertEqual(report["pulse_source_status"],"SKIPPED_SOURCE_UNBOUND")
        self.assertFalse(report["private_checkpoint_fetch_performed"])
        self.assertFalse(report["pulse_fetch_performed"])
        self.assertTrue(report["read_only"])
        self.assertFalse(report["worker_armed_by_this_check"])
        self.runtime_get.assert_not_called()
        self.pulse_get.assert_not_called()
        self.assertNotIn("GITHUB_TOKEN", " ".join(self.env_lookups))
        self.assertNotIn("synthetic-secret",str(report))

    def test_valid_admin_flag_and_tenant_B_claim_still_blocked(self):
        for tenant in ("tenantA","tenantB"):
            with self.subTest(tenant=tenant):
                self.config.tenant_id=tenant
                rc,report=self.run_cli()
                self.assertEqual(rc,1)
                self.assertFalse(report["private_checkpoint_fetch_performed"])
                self.runtime_get.assert_not_called()
                self.pulse_get.assert_not_called()

    def test_forged_status_without_source_verified_still_skips_all_reads(self):
        for row in (
            {"status":"VERIFIED"},
            {"status":"VERIFIED","source_verified":False},
            {"status":"CONFIRMED","source_verified":True},
            {"status":"VERIFIED","source_verified":"true"},
            {"source_verified":True,"checkpoint":"attacker"},
        ):
            with self.subTest(row=row):
                rc,out=self.run_cli(source=lambda cfg:row)
                self.assertEqual(rc,1)
                self.assertEqual(out["status"],"BLOCKED")
                self.assertFalse(out["private_checkpoint_fetch_performed"])
                self.runtime_get.assert_not_called()
                self.pulse_get.assert_not_called()

    def test_zero_credentials_from_process_even_with_env_token(self):
        with patch.dict(os.environ,{"GITHUB_TOKEN":"real-value-not-in-test",
                                   "ATLASQUANT_AION_GLOBAL_WORKER_ENABLED":"1"}):
            rc,out=self.run_cli()
        self.assertEqual(rc,1)
        self.assertNotIn("real-value-not-in-test",str(out))
        self.assertFalse(out["pulse_fetch_performed"])
        self.runtime_get.assert_not_called()

    def test_no_get_is_static_dominating_preflight_before_fetch(self):
        source=SOURCE.read_text("utf-8")
        fn=next(n for n in ast.parse(source).body
                if isinstance(n,ast.FunctionDef) and n.name=="_cli")
        segment=ast.get_source_segment(source,fn)
        self.assertLess(segment.index("independent_worker_source_preflight(config)"),
                        segment.index("load_runtime_checkpoint(config"))
        self.assertLess(segment.index("independent_worker_source_preflight(config)"),
                        segment.index("fetch_recent_autopilot_pulses("))
        self.assertLess(segment.index("if not source_admitted:"),
                        segment.index("load_runtime_checkpoint(config"))
        self.assertIn('pulse_result = {"status": "SKIPPED_SOURCE_UNBOUND"',segment)

    def test_no_production_positive_provider_or_enrollment_in_source_gate(self):
        code=(SOURCE.parent/"atlasquant_aion_global_worker_source_gate_v1.py").read_text("utf-8")
        self.assertNotIn("os.environ",code)
        self.assertNotIn("st.session_state",code)
        self.assertNotIn("source_verified\": True",code)
        self.assertFalse(independent_worker_source_preflight(self.config)["source_verified"])


if __name__=="__main__":
    unittest.main()
