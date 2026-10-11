"""Run only the closure audit's reviewed offline tests and static source audits.

No installer, provider, real credential or physical/network probe.
Synthetic reference signing keys and pure Python restart tests are included.
Run from the repository root with: python -B scripts/aion1155_closure_audit.py
"""
import ast
from contextlib import ExitStack
import importlib
import inspect
from pathlib import Path
from types import ModuleType
import os
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TESTS = (
    "test_atlasquant_aion_v2_legacy_jsonl_read_after_write",
    "test_atlasquant_aion_v2_github_write_no_automatic_replay",
    "test_atlasquant_aion_v2_legacy_persistence_unknown_outcome",
    "test_atlasquant_aion_v2_github_write_response_status",
    "test_atlasquant_aion_v2_github_get_response_status",
    "test_atlasquant_aion_v2_github_token_read_no_redirect",
    "test_atlasquant_aion_v2_github_write_url_runtime_guard_v1",
    "test_atlasquant_aion_v2_legacy_github_destination_source_review",
    "test_atlasquant_aion_v2_repository_paid_egress_static_audit",
    "test_atlasquant_aion_v2_closure_audit_regressions",
    "test_atlasquant_capture_reconciliation",
    "test_atlasquant_aion_v2_autopilot_evidence_guard",
    "test_atlasquant_aion_v2_evidence_consolidation",
    "test_atlasquant_aion_v2_one_shot_unknown_outcome_journal_reference",
    "test_atlasquant_aion_v2_dispatch_journal_dual_witness_reference",
    "test_atlasquant_aion_v2_unknown_outcome_reconciliation_reference",
    "test_atlasquant_aion_v2_isolated_sqlite_witness_cas_reference",
)


def main():
    os.chdir(ROOT)
    # Never read a production credential from inherited environment in fixtures.
    for key in list(os.environ):
        if any(word in key.upper() for word in ("TOKEN", "SECRET", "API_KEY", "PASSWORD")):
            os.environ.pop(key, None)
    fixture_root = ROOT / "tests" / ".audit-fixtures"
    fixture_root.mkdir(exist_ok=True)
    tempfile.tempdir = str(fixture_root)
    # Pre-containment legacy HTTP/CAS behavior is historical PROTOCOL REFERENCE,
    # not runtime permission. Reconstruct only inside this offline, network-blocked
    # audit. The production store methods remain unconditionally HARD_DENIED.
    def legacy_protocol_fixture(module, function_name):
        original = getattr(module, function_name)
        source = inspect.getsource(original)
        syntax = ast.parse(source)
        node = syntax.body[0]
        if not isinstance(node, ast.FunctionDef):
            raise AssertionError("Unexpected legacy store syntax")
        # Fail closed if the production method no longer has the reviewed guard.
        if not isinstance(node.body[0], ast.Return):
            raise AssertionError("Cannot locate production HARD_DENIED return")
        value = node.body[0].value
        if not isinstance(value, ast.Dict) or "HARD_DENIED" not in source.split("    try:", 1)[0]:
            raise AssertionError("Missing mandatory production HARD_DENIED guard")
        if not isinstance(node.body[1], ast.Try):
            raise AssertionError("Legacy simulation body changed; audit needs review")
        node.body = node.body[1:]
        compiled = compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                           str(ROOT / (module.__name__ + ".py")), "exec")
        # Use the real module namespace so legacy fixtures can patch _fetch and
        # requests.get/put in memory, without enabling ANY production writer.
        exec(compiled, module.__dict__)
        fixture = getattr(module, function_name)
        setattr(module, function_name, original)
        return fixture

    # The existing protocol tests intentionally model accepted/uncertain HTTP
    # responses. Temporarily replace only the test process' store references.
    # All outgoing network is still hard-blocked, and synthetic secrets removed.
    with ExitStack() as guards:
        guards.enter_context(patch("socket.socket.connect", side_effect=AssertionError("NETWORK_FORBIDDEN")))
        guards.enter_context(patch("socket.socket.connect_ex", side_effect=AssertionError("NETWORK_FORBIDDEN")))
        guards.enter_context(patch("socket.create_connection", side_effect=AssertionError("NETWORK_FORBIDDEN")))
        guards.enter_context(patch("requests.sessions.Session.request", side_effect=AssertionError("UNMOCKED_HTTP_FORBIDDEN")))
        guards.enter_context(patch.dict(sys.modules, {"streamlit": ModuleType("streamlit")}))
        shadow_store = importlib.import_module("atlasquant_shadow_store")
        research_store = importlib.import_module("atlasquant_research_evidence_store")
        flight_store = importlib.import_module("atlasquant_flight_recorder_store")
        shadow_capture = importlib.import_module("atlasquant_shadow_capture")
        research_capture = importlib.import_module("atlasquant_research_evidence_capture")
        for store, capture, name in (
            (shadow_store, shadow_capture, "persist_shadow_samples"),
            (research_store, research_capture, "persist_research_evidence"),
        ):
            fixture = legacy_protocol_fixture(store, name)
            guards.enter_context(patch.object(store, name, fixture))
            guards.enter_context(patch.object(capture, name, fixture))
            guards.enter_context(patch.object(capture, "private_read_allowed", return_value=True))
            # Only the synthetic, network-blocked protocol reference may pass
            # source provenance to exercise historical CAS/readback behavior.
            guards.enter_context(patch.object(capture, "legacy_private_remote_resource_allowed", return_value=True))
        # Historical Flight Recorder transport is a protocol reference only.
        # The actual deployed writer stays unconditionally HARD_DENIED.
        flight_protocol = legacy_protocol_fixture(flight_store, "persist_records")
        guards.enter_context(patch.object(flight_store, "persist_records", flight_protocol))
        # Historical _fetch tests use synthetic transport and explicitly grant
        # private-read fixture authority; runtime never receives this override.
        guards.enter_context(patch("atlasquant_private_read_gate_v1.private_read_allowed", return_value=True))
        # Historical protocol simulation only: never bypass this gate in runtime.
        # All unmocked network and sockets are blocked in this scope.
        guards.enter_context(patch("atlasquant_legacy_private_resource_gate_v1.require_legacy_private_remote_resource", return_value=None))
        suite = unittest.TestSuite()
        for name in TESTS:
            suite.addTests(unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern=name + ".py"))
        suite.addTests(unittest.defaultTestLoader.loadTestsFromNames((
            "test_atlasquant_flight_recorder_store", "test_atlasquant_shadow_store",
            "test_atlasquant_shadow_persistence", "test_atlasquant_shadow_mode",
        )))
        result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
