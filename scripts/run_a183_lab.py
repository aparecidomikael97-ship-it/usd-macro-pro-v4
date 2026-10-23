"""A183 explicit synthetic suites; external-red is an actual failing suite."""
from pathlib import Path
import argparse
import runpy
import socket
import sqlite3
import platform
import sys
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
p=argparse.ArgumentParser(description=__doc__)
p.add_argument("suite",choices=["specific","regression","sqlite","external-red"])
args=p.parse_args()
print("A183_CAPABILITIES",platform.system(),platform.python_version(),
      "SQLite",sqlite3.sqlite_version,"deserialize",
      hasattr(sqlite3.Connection,"deserialize"),"native_fileno",
      hasattr(sqlite3.Connection,"fileno"),flush=True)
for name in ("connect","connect_ex"):
    setattr(socket.socket,name,Mock(side_effect=AssertionError("LAB network forbidden")))
socket.create_connection=Mock(side_effect=AssertionError("LAB network forbidden"))
if args.suite in {"regression","sqlite"}:
    sys.argv=[str(Path(__file__).with_name("run_a182_lab.py")),args.suite]
    runpy.run_path(sys.argv[0],run_name="__main__")
names=(["test_atlasquant_aion_native_path_a183_lab",
        "test_atlasquant_aion_snapshot_a183_lab","test_atlasquant_aion_authority_a183_lab"]
       if args.suite=="specific" else ["lab_a183_external_requirements_red"])
result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
raise SystemExit(0 if result.wasSuccessful() else 1)

