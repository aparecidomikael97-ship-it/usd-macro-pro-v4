"""Tamper test on a temporary COPY; original MT5 snapshots never altered."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

SOURCE = (Path(os.environ["LOCALAPPDATA"]) / "AtlasQuant" / "LAB" /
          "MT5_Snapshots" / "20261107_AM12")
AUDITOR = Path(__file__).with_name("atlasquant_mt5_snapshot_audit_lab.py")
with TemporaryDirectory(prefix="atlasquant_mt5_integrity_test_") as directory:
    root = Path(directory)
    for original in SOURCE.glob("batch_??_manifest.json"):
        shutil.copy2(original, root / original.name)
    for original in SOURCE.glob("*_closedbar.csv.gz"):
        shutil.copy2(original, root / original.name)
    originals = list(root.glob("*_closedbar.csv.gz"))
    if len(originals) != 84:
        raise SystemExit("FAIL wrong number of original snapshots")
    target = root / "EURUSD_M15_closedbar.csv.gz"
    payload = bytearray(target.read_bytes())
    payload[-12] ^= 0x01
    target.write_bytes(payload)
    proc = subprocess.run([sys.executable, str(AUDITOR), "--root", str(root)],
                          capture_output=True, text=True, timeout=35)
    good = (proc.returncode == 2 and
            "AUDIT_STATUS LOCAL_INTEGRITY_FAIL" in proc.stdout and
            ("CSV_VERIFY_FAILED:EURUSD:M15" in proc.stdout or
             "HASH_MISMATCH:EURUSD:M15" in proc.stdout))
    print("TAMPER_TEST", "PASS" if good else "FAIL")
    print("AUDIT_EXIT",proc.returncode)
    print("AUDIT_ERRORS",next((x for x in proc.stdout.splitlines()
                               if x.startswith("ERRORS ")), "NO_ERRORS_PRINT"))
    if not good:
        print(proc.stdout[-2000:])
        print(proc.stderr[-2000:])
        raise SystemExit(2)
print("ORIGINAL_SNAPSHOTS_UNTOUCHED YES")
