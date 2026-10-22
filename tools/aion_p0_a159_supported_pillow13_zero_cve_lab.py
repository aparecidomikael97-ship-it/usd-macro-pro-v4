"""A159: independently prove current full dependency audit is zero-advisory.

No suppressed advisories, no --ignore-vuln, no silent package omissions.
Scans exact requirements using pip-audit as installed in GitHub Actions.
Does NOT authorize merge, runtime operations, trusted external evidence,
P0 homologation, auto-resend or a declaration that future advisories cannot
emerge. Package metadata and dependency solver do NOT prove application
compatibility; full canonical UI/Security/Quality jobs must independently pass.
"""
from __future__ import annotations
import json
import sys
import subprocess
from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from tools.aion_p0_a158_dependency_audit_lab import (
    AuditInputRejected, check_requirements, parse_audit_json,
    streamlit_pillow_constraint,
)

EXPECTED={"streamlit":"1.66.1","pillow":"13.0.0","pypdf":"6.21.1"}
SCHEMA="AION_P0_A159_RESOLVED_SECURITY_DEPENDENCIES_NO_GO_V1"

def check_environment(requirements_text, audit_json, audit_exit, actual_versions,
                      streamlit_requires):
    findings=[]
    try:
        reqs=check_requirements(requirements_text)
    except AuditInputRejected as exc:
        findings.append("PINS_INVALID:"+str(exc))
        reqs={}
    for name,version in EXPECTED.items():
        if reqs.get(name)!=version:
            findings.append("APPROVED_SECURITY_PIN_MISSING:"+name)
        if actual_versions.get(name)!=version:
            findings.append("INSTALLED_VERSION_NOT_EXACT:"+name)
    try:
        compat=streamlit_pillow_constraint(streamlit_requires)
        if not compat["pillow_13_supported_by_current_streamlit_metadata"]:
            findings.append("STREAMLIT_DOES_NOT_OFFICIALLY_ACCEPT_PILLOW13")
    except AuditInputRejected as exc:
        compat={}
        findings.append("UPSTREAM_METADATA_UNTRUSTED:"+str(exc))
    try:
        parsed=parse_audit_json(audit_json,audit_exit)
    except AuditInputRejected as exc:
        parsed={}
        findings.append("AUDIT_JSON_UNTRUSTED:"+str(exc))
    for name,version in EXPECTED.items():
        if parsed.get(name,{}).get("version")!=version:
            findings.append("AUDITED_VERSION_MISMATCH:"+name)
    if parsed:
        missing=sorted(set(reqs)-set(parsed))
        if missing:
            findings.append("DIRECT_PACKAGES_MISSING_FROM_AUDIT:"+",".join(missing))
        vulns={name:len(item["ids"]) for name,item in parsed.items() if item["ids"]}
        if vulns:
            findings.append("UNRESOLVED_ADVISORIES:"+",".join(sorted(vulns)))
    else:
        vulns={}
    findings=sorted(set(findings))
    return {
        "schema":SCHEMA,
        "package_versions_installed":actual_versions,
        "streamlit_pillow_dependency_metadata":compat,
        "pip_audit_full_dependency_scan_zero_advisories":not findings,
        "pip_audit_observed_package_count":len(parsed),
        "pip_audit_observed_advisory_counts_by_package":vulns,
        "findings":findings,
        "canonical_security_gate_verified_by_this_script":False,
        "canonical_quality_verified_by_this_script":False,
        "owner_identity_verified":False,
        "trusted_external_witness_verified":False,
        "real_worker_allowed":False,
        "automatic_resend_allowed":False,
        "homologated_p0_count":0,
        "verdict":"HARD_NO_GO_P0_EXTERNAL_H0_AND_OWNER_PROOFS_MISSING",
    }


def main()->int:
    try:
        source=(ROOT/"requirements.txt").read_text(encoding="utf-8")
        proc=subprocess.run(
            [sys.executable,"-m","pip_audit","-r",str(ROOT/"requirements.txt"),
             "--format","json"],
            cwd=str(ROOT),capture_output=True,text=True,timeout=180,check=False,
        )
        if proc.returncode not in (0,1):
            raise AuditInputRejected("PIP_AUDIT_TOOL_FAILED:"+str(proc.returncode))
        versions={name:metadata.version(name) for name in EXPECTED}
        result=check_environment(source,proc.stdout,proc.returncode,
                                 versions,metadata.requires("streamlit"))
    except (OSError,UnicodeError,subprocess.TimeoutExpired,
            metadata.PackageNotFoundError,AuditInputRejected,TypeError) as exc:
        result={"schema":SCHEMA,"findings":["LIVE_SCAN_ERROR:"+type(exc).__name__],
                "pip_audit_full_dependency_scan_zero_advisories":False,
                "homologated_p0_count":0,
                "verdict":"HARD_NO_GO_P0_EXTERNAL_H0_AND_OWNER_PROOFS_MISSING"}
    print(json.dumps(result,sort_keys=True,indent=2))
    return 0 if result.get("pip_audit_full_dependency_scan_zero_advisories") is True else 3


if __name__=="__main__":
    raise SystemExit(main())
