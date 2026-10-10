"""Run only the closure audit's reviewed offline tests and static source audits.

No installer, provider, real credential or physical/network probe.
Synthetic reference signing keys and pure Python restart tests are included.
Run from the repository root with: python -B scripts/aion1155_closure_audit.py
"""
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
    with patch("socket.socket.connect", side_effect=AssertionError("NETWORK_FORBIDDEN")), \
         patch("socket.socket.connect_ex", side_effect=AssertionError("NETWORK_FORBIDDEN")), \
         patch("socket.create_connection", side_effect=AssertionError("NETWORK_FORBIDDEN")), \
         patch("requests.sessions.Session.request", side_effect=AssertionError("UNMOCKED_HTTP_FORBIDDEN")):
        suite = unittest.TestSuite()
        for name in TESTS:
            suite.addTests(unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern=name + ".py"))
        # Pure capture/hydration tests need only module definitions, never UI.
        with patch.dict(sys.modules, {"streamlit": ModuleType("streamlit")}):
            suite.addTests(unittest.defaultTestLoader.loadTestsFromNames((
                "test_atlasquant_flight_recorder_store", "test_atlasquant_shadow_store",
                "test_atlasquant_shadow_persistence", "test_atlasquant_shadow_mode",
            )))
        result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
