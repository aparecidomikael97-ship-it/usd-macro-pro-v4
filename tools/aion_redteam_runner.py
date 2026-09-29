"""Run audit tests offline with a scrubbed environment; never run providers.

This is a test harness, not a production sandbox. Uses a child interpreter and
Python audit hooks as defense in depth. No hostile native extensions are tested.
Usage: python tools/aion_redteam_runner.py -- -m unittest discover
       python tools/aion_redteam_runner.py --imports
       python tools/aion_redteam_runner.py --inventory
"""
from __future__ import annotations
import argparse
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
GUARD = r'''
import os, sys
from pathlib import Path
ROOT = Path(os.environ["AION_AUDIT_ROOT"]).resolve()
TMP = Path(os.environ["AION_AUDIT_TEMP"]).resolve()
def inside(path, root):
    try:
        Path(path).resolve().relative_to(root)
        return True
    except (ValueError, TypeError, OSError):
        return False
def guard(event, args):
    if event.startswith(("socket.connect", "socket.bind", "socket.getaddrinfo",
                         "subprocess.Popen", "os.system", "os.exec", "os.spawn")):
        raise PermissionError("AUDIT_BLOCKED_EXTERNAL_EFFECT:" + event)
    if event == "open":
        path, mode, flags = args
        writing = (isinstance(mode,str) and any(c in mode for c in "wax+")) or (
            isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
        if writing and not isinstance(path,int) and not inside(path,TMP):
            raise PermissionError("AUDIT_BLOCKED_WRITE")
    if event in {"os.remove", "os.rmdir", "os.mkdir", "os.rename", "os.replace"}:
        paths = args[:2] if event in {"os.rename","os.replace"} else args[:1]
        if any(not inside(p,TMP) for p in paths):
            raise PermissionError("AUDIT_BLOCKED_FILESYSTEM_MUTATION")
sys.dont_write_bytecode = True
sys.addaudithook(guard)
'''

def environment(temp):
    keep = {"SYSTEMROOT","WINDIR","PATH","PATHEXT","COMSPEC","SYSTEMDRIVE",
            "NUMBER_OF_PROCESSORS","PROCESSOR_ARCHITECTURE"}
    env = {k:v for k,v in os.environ.items() if k.upper() in keep}
    env.update({
        "HOME":temp, "USERPROFILE":temp, "APPDATA":temp, "LOCALAPPDATA":temp,
        "TEMP":temp, "TMP":temp, "TMPDIR":temp,
        "PYTHONPATH":temp + os.pathsep + str(ROOT),
        "PYTHONDONTWRITEBYTECODE":"1", "PYTHONIOENCODING":"utf-8",
        "AION_AUDIT_ROOT":str(ROOT), "AION_AUDIT_TEMP":temp,
        "ATLASQUANT_AION_GLOBAL_WORKER_ENABLED":"false",
        "STREAMLIT_BROWSER_GATHER_USAGE_STATS":"false",
    })
    return env

def inventory():
    rows = []
    paths = list(ROOT.glob("atlasquant_aion*.py")) + list((ROOT/"atlasquant_aion_core_intelligence").glob("*.py"))
    for path in sorted(paths):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        imports = []
        sensitive = []
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                imports.extend({"module":a.name,"line":node.lineno} for a in node.names)
            elif isinstance(node,ast.ImportFrom):
                imports.append({"module":node.module or "", "line":node.lineno})
            elif isinstance(node,ast.Call):
                name = ast.unparse(node.func)
                leaf = name.rsplit(".",1)[-1]
                if leaf in {"eval","exec","system","popen","run","Popen","loads",
                            "load","import_module","write_text","write_bytes","unlink",
                            "rmtree","remove","symlink_to"}:
                    sensitive.append({"call":name,"line":node.lineno})
        rows.append({"file":path.relative_to(ROOT).as_posix(),"imports":imports,"sensitive_calls":sensitive})
    print(json.dumps(rows,ensure_ascii=True,indent=2))

def imports(env, independent=False):
    modules = ["atlasquant_aion_core","atlasquant_aion_critical_review",
               "atlasquant_aion_durable_tasks","atlasquant_aion_fortress",
               "atlasquant_aion_resilience","atlasquant_aion_tenant",
               "atlasquant_aion_tenant_privacy","atlasquant_aion_vault",
               "atlasquant_aion_model_router","atlasquant_aion_memory",
               "atlasquant_aion_recovery","atlasquant_aion_workspaces",
               "atlasquant_aion_core_intelligence.service"]
    failures = 0
    for module in modules:
        code = ("import sys, threading, importlib, json, os; "
                "before=dict(os.environ); threads={t.ident for t in threading.enumerate()}; "
                f"importlib.import_module({module!r}); "
                "print(json.dumps({'module':"+repr(module)+","
                "'new_threads':len({t.ident for t in threading.enumerate()}-threads),"
                "'env_changed':before!=dict(os.environ),"
                "'ui_loaded':'streamlit' in sys.modules,"
                "'business_loaded':'atlasquant_aion_business' in sys.modules}))")
        if independent:
            code = ("import sys, importlib.abc\n"
                    "class NoProduct(importlib.abc.MetaPathFinder):\n"
                    " def find_spec(self, fullname, path=None, target=None):\n"
                    "  if fullname in {'atlasquant_aion_business','atlasquant_trader',"
                    "'atlasquant_radar','atlasquant_investments'}:\n"
                    "   raise ImportError('AUDIT_OPTIONAL_MODULE_UNAVAILABLE:'+fullname)\n"
                    "sys.meta_path.insert(0,NoProduct())\n") + code
        result = subprocess.run([sys.executable,"-B","-c",code],cwd=ROOT,env=env,
                                capture_output=True,text=True,encoding="utf-8",timeout=45)
        print(result.stdout.strip() or json.dumps({"module":module,"returncode":result.returncode}))
        if result.returncode:
            failures += 1
            print(result.stderr[-2000:])
    return bool(failures)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--imports",action="store_true")
    parser.add_argument("--independence",action="store_true")
    parser.add_argument("--inventory",action="store_true")
    parser.add_argument("--strict-defects",action="store_true",
                        help="Expose expected failures as ordinary failing assertions.")
    parser.add_argument("command",nargs=argparse.REMAINDER)
    args=parser.parse_args()
    if args.inventory:
        inventory()
        return 0
    with tempfile.TemporaryDirectory(prefix="aion-redteam-") as temp:
        Path(temp,"sitecustomize.py").write_text(GUARD,encoding="utf-8")
        env=environment(temp)
        if args.imports or args.independence:
            return imports(env,args.independence)
        if args.strict_defects:
            code = ("import unittest; import test_atlasquant_aion_redteam_extended as audit; "
                    "[setattr(fn,'__unittest_expecting_failure__',False) for name,fn in "
                    "vars(audit.ExpectedFailure).items() if name.startswith('test_')]; "
                    "r=unittest.TextTestRunner(verbosity=2).run("
                    "unittest.defaultTestLoader.loadTestsFromTestCase(audit.ExpectedFailure)); "
                    "raise SystemExit(not r.wasSuccessful())")
            return subprocess.run([sys.executable,"-B","-c",code],cwd=ROOT,env=env,
                                  timeout=90).returncode
        command=args.command
        if command[:1]==["--"]:
            command=command[1:]
        if not command:
            command=["-m","unittest","test_atlasquant_aion_redteam_extended.py"]
        return subprocess.run([sys.executable,"-B",*command],cwd=ROOT,env=env,
                              timeout=900).returncode

if __name__=="__main__":
    raise SystemExit(main())
