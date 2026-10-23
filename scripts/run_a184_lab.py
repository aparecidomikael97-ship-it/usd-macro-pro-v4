"""A184 synthetic LAB protection suites and genuine unmet acceptance requirements."""
import argparse
from pathlib import Path
import platform
import runpy
import socket
import sqlite3
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("suite", choices=["specific", "regression", "sqlite", "external-red"])
args = parser.parse_args()
print("A184_CAPABILITIES", platform.system(), platform.python_version(),
      "SQLite", sqlite3.sqlite_version, "deserialize",
      hasattr(sqlite3.Connection, "deserialize"), "native_fileno",
      hasattr(sqlite3.Connection, "fileno"), flush=True)
socket.socket.connect = Mock(side_effect=AssertionError("LAB network forbidden"))
socket.socket.connect_ex = Mock(side_effect=AssertionError("LAB network forbidden"))
socket.create_connection = Mock(side_effect=AssertionError("LAB network forbidden"))
if args.suite != "specific":
    sys.argv = [str(Path(__file__).with_name("run_a183_lab.py")), args.suite]
    runpy.run_path(sys.argv[0], run_name="__main__")
else:
    names = [
        "test_atlasquant_aion_native_path_a183_lab",
        "test_atlasquant_aion_snapshot_a183_lab",
        "test_atlasquant_aion_authority_a183_lab",
        "test_atlasquant_aion_sqlite_recovery_a184_lab",
        "test_atlasquant_aion_snapshot_limits_a184_lab",
        "test_atlasquant_aion_callback_boundary_a184_lab",
        "test_atlasquant_aion_authority_boundary_a184_lab",
    ]
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromNames(names))
    raise SystemExit(0 if result.wasSuccessful() else 1)
