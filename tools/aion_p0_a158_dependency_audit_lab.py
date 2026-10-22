"""A158: independently re-audit exact pinned dependency set, never waive CVEs.

Scope: pypdf patch verification; Pillow remains a separate blocked review.
Report stdout from pip-audit, do not edit canonical security workflow.
No GitHub access, secrets, provider actions, approvals or deploys.
"""
from __future__ import annotations

import argparse
from importlib import metadata
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "requirements.txt"
SCHEMA = "AION_P0_A158_DEPENDENCY_ADVISORY_PARTIAL_REMEDIATION_LAB_V1"
EXPECTED = {"streamlit": "1.64.0", "pypdf": "6.21.1"}
NEVER_GO = "HARD_NO_GO_FULL_SECURITY_AUDIT_UNCLOSED"


class AuditInputRejected(ValueError):
    pass


def _reject_duplicates(pairs):
    item={}
    for key, value in pairs:
        if key in item:
            raise AuditInputRejected("DUPLICATE_AUDIT_JSON_KEY:"+str(key))
        item[key]=value
    return item


def _pkg(name: Any) -> str:
    if type(name) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,100}", name):
        raise AuditInputRejected("PACKAGE_NAME_INVALID")
    return re.sub(r"[-_.]+", "-", name).lower()


def check_requirements(source: Any) -> dict[str, Any]:
    if type(source) is not str or len(source) > 20_000:
        raise AuditInputRejected("REQUIREMENTS_SOURCE_INVALID")
    found={}
    for line in source.splitlines():
        line=line.strip()
        if not line or line.startswith("#"):
            continue
        match=re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9_-]*)==([0-9][A-Za-z0-9.]+)",line)
        if not match:
            raise AuditInputRejected("REQUIREMENT_NOT_EXACT_PIN")
        name=_pkg(match.group(1))
        if name in found:
            raise AuditInputRejected("DUPLICATE_REQUIREMENT:"+name)
        found[name]=match.group(2)
    if len(found) < 9 or not all(found.get(k)==v for k,v in EXPECTED.items()):
        raise AuditInputRejected("PINNED_STREAMLIT_OR_PYPDF_VERSION_DRIFT")
    if "pillow" in found:
        raise AuditInputRejected("PILLOW_OVERRIDE_REQUIRES_INDEPENDENT_COMPATIBILITY_PROOF")
    return found


def parse_audit_json(text: Any, exit_code: int) -> dict[str, Any]:
    """Parse actual machine-readable pip-audit output; never trust exit alone."""
    if type(text) is not str or not (0 <= len(text) <= 2_000_000):
        raise AuditInputRejected("AUDIT_PAYLOAD_INVALID")
    if type(exit_code) is not int or exit_code not in (0,1):
        raise AuditInputRejected("AUDITOR_EXECUTION_NOT_TRUSTWORTHY")
    try:
        obj=json.loads(text,object_pairs_hook=_reject_duplicates)
    except (ValueError,TypeError,RecursionError) as exc:
        raise AuditInputRejected("AUDIT_JSON_INVALID_OR_AMBIGUOUS") from exc
    if type(obj) is not dict or type(obj.get("dependencies")) is not list:
        raise AuditInputRejected("AUDIT_SCHEMA_INVALID")
    deps={}
    for dep in obj["dependencies"]:
        if type(dep) is not dict or set(dep) - {"name","version","vulns","skip_reason"}:
            raise AuditInputRejected("AUDIT_DEPENDENCY_FIELDS_INVALID")
        name=_pkg(dep.get("name"))
        if name in deps:
            raise AuditInputRejected("AUDIT_DUPLICATE_PACKAGE:"+name)
        if type(dep.get("version")) is not str or not dep["version"]:
            raise AuditInputRejected("AUDIT_PACKAGE_VERSION_INVALID:"+name)
        vulns=dep.get("vulns")
        if type(vulns) is not list:
            raise AuditInputRejected("AUDIT_VULNERABILITY_ARRAY_MISSING:"+name)
        if dep.get("skip_reason"):
            raise AuditInputRejected("AUDIT_SKIPPED_PACKAGE:"+name)
        ids=[]
        for v in vulns:
            if type(v) is not dict or type(v.get("id")) is not str or not v["id"]:
                raise AuditInputRejected("AUDIT_ADVISORY_ID_INVALID:"+name)
            ids.append(v["id"])
        if len(ids)!=len(set(ids)):
            raise AuditInputRejected("AUDIT_ADVISORY_DUPLICATED:"+name)
        deps[name]={"version":dep["version"],"ids":ids}
    if len(deps) < 9 or not all(k in deps for k in ("pypdf","pillow","streamlit")):
        raise AuditInputRejected("AUDIT_EXPECTED_PACKAGES_MISSING")
    total=sum(len(d["ids"]) for d in deps.values())
    if exit_code != (1 if total else 0):
        raise AuditInputRejected("AUDIT_EXIT_STATUS_INCONSISTENT_WITH_ADVISORIES")
    return deps


def streamlit_pillow_constraint(requires: Any) -> dict[str,Any]:
    if type(requires) is not list or not all(type(x) is str for x in requires):
        raise AuditInputRejected("STREAMLIT_PACKAGE_METADATA_MISSING")
    items=[]
    try:
        for text in requires:
            req=Requirement(text)
            if _pkg(req.name) == "pillow" and not req.marker:
                items.append(req)
    except (ValueError,TypeError) as exc:
        raise AuditInputRejected("STREAMLIT_DEPENDENCY_METADATA_INVALID") from exc
    if len(items)!=1:
        raise AuditInputRejected("PILLOW_REQUIREMENT_NOT_UNIQUELY_KNOWN")
    spec=str(items[0].specifier)
    if not spec:
        raise AuditInputRejected("PILLOW_REQUIREMENT_UNCONSTRAINED_NOT_ATTESTED")
    return {
        "streamlit_declared_pillow_requirement":spec,
        "pillow_13_supported_by_current_streamlit_metadata":
            items[0].specifier.contains("13.0.0",prereleases=False),
    }


def decision(reqs: Any, audit_payload: Any, auditor_exit: int,
             streamlit_requires: Any) -> dict[str,Any]:
    problems=[]
    try:
        checked=check_requirements(reqs)
    except AuditInputRejected as exc:
        checked={}
        problems.append(str(exc))
    try:
        observed=parse_audit_json(audit_payload,auditor_exit)
    except AuditInputRejected as exc:
        observed={}
        problems.append(str(exc))
    try:
        compat=streamlit_pillow_constraint(streamlit_requires)
    except AuditInputRejected as exc:
        compat={}
        problems.append(str(exc))
    if observed and checked:
        for name,version in EXPECTED.items():
            if observed[name]["version"]!=version:
                problems.append("AUDIT_VERSION_MISMATCH:"+name)
        if observed["pypdf"]["ids"]:
            problems.append("PYPDF_STILL_HAS_ADVISORIES")
        unexpected=sorted(name for name,d in observed.items()
                          if d["ids"] and name!="pillow")
        if unexpected:
            problems.append("UNEXPECTED_UNCLOSED_PACKAGE_ADVISORIES:"+",".join(unexpected))
    if compat.get("pillow_13_supported_by_current_streamlit_metadata") is True:
        # It could be supported, but any actual upgrade still needs a separate
        # compatibility regression. Never claim blocked purely by assumption.
        pass
    pillow_ids=observed.get("pillow",{}).get("ids",[])
    return {
        "schema":SCHEMA,
        "pypdf_patch_version_expected":"6.21.1",
        "pypdf_patch_audit_clear_in_lab":bool(observed and checked and not observed["pypdf"]["ids"]
                                               and not problems),
        "pypdf_advisory_ids":observed.get("pypdf",{}).get("ids",[]),
        "remaining_pillow_advisory_count":len(pillow_ids),
        "remaining_pillow_advisory_ids":sorted(pillow_ids),
        "other_unresolved_package_names":sorted(
            name for name,d in observed.items() if name!="pillow" and d["ids"]
        ),
        "constraint":compat,
        "findings":sorted(set(problems)),
        "pypdf_specific_partial_gate_passed":bool(observed and checked and not problems
                                                  and not observed["pypdf"]["ids"]),
        "canonical_supply_chain_security_gate_homologated":False,
        "full_quality_homologated":False,
        "provider_custody_verified":False,
        "new_security_exception_created":False,
        "worker_allowed":False,
        "automatic_resend_allowed":False,
        "homologated_p0_count":0,
        "verdict":NEVER_GO,
    }


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--verify-pypdf-only",action="store_true")
    opts=p.parse_args()
    try:
        source=REQUIREMENTS.read_text(encoding="utf-8")
        proc=subprocess.run(
            [sys.executable,"-m","pip_audit","-r",str(REQUIREMENTS),"-f","json"],
            cwd=str(ROOT),capture_output=True,text=True,timeout=180,check=False
        )
        if proc.returncode not in (0,1):
            raise AuditInputRejected("LIVE_PIP_AUDIT_FAILED_TO_EXECUTE")
        observed=decision(source,proc.stdout,proc.returncode,
                          metadata.requires("streamlit"))
    except (OSError,UnicodeError,AuditInputRejected,subprocess.TimeoutExpired,
            metadata.PackageNotFoundError) as exc:
        observed={"schema":SCHEMA,"verdict":NEVER_GO,
                  "pypdf_specific_partial_gate_passed":False,
                  "canonical_supply_chain_security_gate_homologated":False,
                  "findings":["LIVE_AUDIT_NOT_VERIFIABLE:"+type(exc).__name__]}
    print(json.dumps(observed,sort_keys=True,indent=2))
    if opts.verify_pypdf_only and not observed.get("pypdf_specific_partial_gate_passed"):
        return 3
    return 0


if __name__=="__main__":
    raise SystemExit(main())
