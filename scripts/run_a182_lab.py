"""Explicit A182 synthetic suites; external-red exits nonzero by design."""
import argparse
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
SUITES = {
    "regression": [
        "test_atlasquant_aion_intent_binding_a182_lab",
        "test_atlasquant_aion_separate_custody_a181_lab",
        "test_atlasquant_aion_first_attempt_witness_a180_lab",
        "test_atlasquant_aion_witness_admission_a179_lab",
        "test_atlasquant_aion_signed_receipt_a178_lab",
        "test_atlasquant_aion_outbox_receipt_admission_a177_lab",
        "test_atlasquant_aion_outbox_uncertain_retry_a176_lab",
        "test_atlasquant_aion_execution_outbox",
        "test_atlasquant_aion_execution_saga",
    ],
    "sqlite": [
        "test_atlasquant_aion_chat_sqlite_lifecycle",
        "test_atlasquant_aion_chat_sqlite_path_identity",
        "test_atlasquant_aion_chat_sqlite_inode_anchor",
        "test_atlasquant_aion_chat_sqlite_live_mutations",
        "test_atlasquant_aion_chat_sqlite_ancestor_chain",
        "test_atlasquant_aion_chat_sqlite_read_snapshot",
        "test_atlasquant_aion_chat_sqlite_narrow_rename",
        "test_atlasquant_aion_chat_sqlite_write_outcome",
        "test_atlasquant_aion_chat_uncertain_reservation_lab",
        "test_atlasquant_aion_chat_host_staging",
        "test_atlasquant_aion_chat_staged_runtime_resilience",
    ],
    "external-red": ["lab_a182_external_requirements_red"],
}
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("suite", choices=SUITES)
args = parser.parse_args()
# In-process network guard; not an OS firewall or proof of remote independence.
socket.socket.connect = Mock(side_effect=AssertionError("LAB network forbidden"))
socket.socket.connect_ex = Mock(side_effect=AssertionError("LAB network forbidden"))
socket.create_connection = Mock(side_effect=AssertionError("LAB network forbidden"))
result = unittest.TextTestRunner(verbosity=2).run(
    unittest.defaultTestLoader.loadTestsFromNames(SUITES[args.suite]))
raise SystemExit(0 if result.wasSuccessful() else 1)

