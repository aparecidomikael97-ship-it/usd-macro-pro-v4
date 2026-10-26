"""Execute named canonical test/audit commands without editing their selectors.

Harness difference: Python test socket egress is denied in this process; on
Windows, only stdlib asyncio's internal 127.0.0.1 self-pipe socketpair works.
Subprocesses do not inherit Python mocks. No CI/provider credentials are loaded.
"""
import argparse
import hashlib
from pathlib import Path
import shlex
import socket
import subprocess
import sys
import textwrap
import unittest

# A184 deliberately copies this canonical runner to RUNNER_TEMP before
# launching it; the helper remains under the checked-out repo's scripts/.
# Direct execution finds its sibling, while isolated copy execution locates
# the helper from the same repository worktree used by canonical selectors.
# A missing helper is always an error; never fall back to site-packages.
_guard_name = "aion_a190_scoped_socketpair_guard.py"
_script_dir = Path(__file__).resolve().parent
_repo_scripts = Path.cwd().resolve() / "scripts"
if (_script_dir / _guard_name).is_file():
    _guard_dir = _script_dir
elif (_repo_scripts / _guard_name).is_file():
    _guard_dir = _repo_scripts
else:
    raise RuntimeError("A183_LAB_SOCKET_GUARD_MISSING_DENIED")
sys.path.insert(0, str(_guard_dir))
from aion_a190_scoped_socketpair_guard import canonical_lab_socket_guard

p=argparse.ArgumentParser(description=__doc__)
p.add_argument("suite",choices=["quality","security-unittest","security-pytest","security-audit"])
args=p.parse_args()
sys.path.insert(0,str(Path.cwd()))
source=Path(".github/workflows/quality-tests.yml" if args.suite=="quality"
            else ".github/workflows/aion-core-security-gate.yml")
text=source.read_text()
print("CANONICAL_SOURCE",str(source),"sha256",hashlib.sha256(source.read_bytes()).hexdigest(),flush=True)

def command(label):
    lines=text.splitlines()
    for i,line in enumerate(lines):
        if line.strip()=="- name: "+label:
            for j in range(i+1,len(lines)):
                if lines[j].strip().startswith("run: ") and lines[j].strip()!="run: |":
                    return shlex.split(lines[j].strip()[5:])
                if lines[j].strip()=="run: |":
                    indent=len(lines[j])-len(lines[j].lstrip())
                    body=[]
                    for item in lines[j+1:]:
                        if item.strip() and len(item)-len(item.lstrip())<=indent: break
                        body.append(item)
                    result=textwrap.dedent("\n".join(body)).strip()
                    if not result:raise RuntimeError("empty canonical step")
                    return shlex.split(result.replace("\\\n"," "))
                if lines[j].lstrip().startswith("- name:"):break
    raise RuntimeError("canonical step not found: "+label)

if args.suite=="security-audit":
    # These are the exact canonical vulnerability and severity selectors.
    results=[]
    for label in ("Audit Python dependencies",
                  "Scan AION security-critical Python for high severity findings"):
        cmd=command(label)
        print("CANONICAL_COMMAND",shlex.join(cmd),flush=True)
        results.append(subprocess.run(cmd,check=False).returncode)
    # SBOM generation is intentionally not claimed here; no upload/retention changes.
    raise SystemExit(1 if any(results) else 0)

label={"quality":"Run quality suite",
       "security-unittest":"Run authority, injection, isolation and recovery tests",
       "security-pytest":"Run AION v2.1 scope and quarantine tests"}[args.suite]
cmd=command(label)
print("CANONICAL_COMMAND",shlex.join(cmd),flush=True)
if cmd[:3]!=["python","-m","unittest"] and cmd[:3]!=["python","-m","pytest"]:
    raise RuntimeError("unexpected canonical command")
# Windows asyncio needs its own local self-pipe socketpair while external
# socket connects (including arbitrary loopback) must remain denied.
# Linux retains A183's original all-connects-denied behavior.
with canonical_lab_socket_guard():
    if cmd[2]=="unittest":
        result=unittest.main(module=None,argv=["canonical"]+cmd[3:],exit=False).result
        raise SystemExit(0 if result.wasSuccessful() else 1)
    import pytest
    raise SystemExit(pytest.main(cmd[3:]))

