"""A157 offline, fail-closed YAML policy for four disabled writer jobs and two backups.

Checks repository SOURCE only. No Action executes here, no credential is used,
and a passing exit code NEVER authorizes live writes, real IAM or restore.
Other workflows remain outside this narrow six-workflow contract.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
from typing import Any
import yaml

ROOT=Path(__file__).resolve().parents[1]
FOLDER=Path(".github/workflows")
SCHEMA="AION_P0_A157_STRICT_WORKFLOW_YAML_NO_GO_V1"
CRITICAL={
    "autopilot-v107.yml":"autopilot",
    "coleta_automatica.yml":"coletar",
    "aion-runtime-checkpoint-bootstrap.yml":"bootstrap",
    "aion-runtime-checkpoint-migrate.yml":"migrate",
}
BACKUPS={
    "atlasquant-checkpoint.yml":"checkpoint",
    "atlasquant-source-backup.yml":"backup",
}
WRITER={
    "autopilot-v107.yml":"python autopilot_setup_audit_v114.py",
    "coleta_automatica.yml":"python coleta_automatica_v86.py",
    "aion-runtime-checkpoint-bootstrap.yml":"gh api --method PUT",
    "aion-runtime-checkpoint-migrate.yml":"gh api --method PUT",
}
TRIGGERS={
    "autopilot-v107.yml":{"workflow_dispatch","push","schedule"},
    "coleta_automatica.yml":{"workflow_dispatch","schedule"},
    "aion-runtime-checkpoint-bootstrap.yml":{"workflow_dispatch","push"},
    "aion-runtime-checkpoint-migrate.yml":{"workflow_dispatch","push"},
    "atlasquant-checkpoint.yml":{"push","workflow_dispatch"},
    "atlasquant-source-backup.yml":{"workflow_dispatch","push"},
}
CHECKOUT="actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
UPLOAD="actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
MUTATOR_PATTERNS=tuple(re.compile(p,re.I) for p in (
    r"\bgit\s+push\b",
    r"\bgh\s+api\s+--method\s+(?:PUT|POST|PATCH|DELETE)\b",
    r"\bgh\s+(?:pr\s+merge|workflow\s+run|release\s+create)\b",
    r"\brequests\.(?:put|post|patch|delete)\s*\(",
    r"\bhttpx\.(?:put|post|patch|delete)\s*\(",
    r"\bcurl\s+(?:-X|--request)\s+(?:PUT|POST|PATCH|DELETE)\b",
))


class A157InvalidYAML(ValueError):
    pass


class StrictLoader(yaml.BaseLoader):
    """Treat 'on' as text; reject all duplicate YAML keys at every depth."""
    def construct_mapping(self,node,deep=False):
        if not isinstance(node,yaml.MappingNode):
            raise A157InvalidYAML("MAPPING_EXPECTED")
        seen=set()
        for k,_ in node.value:
            key=self.construct_object(k,deep=deep)
            if type(key) is not str or key=="<<":
                raise A157InvalidYAML("UNSUPPORTED_YAML_KEY")
            if key in seen:
                raise A157InvalidYAML("DUPLICATE_YAML_KEY:"+key)
            seen.add(key)
        return super().construct_mapping(node,deep=deep)


def parse(source:Any)->dict:
    if type(source) is not str or len(source.encode("utf-8"))>250_000:
        raise A157InvalidYAML("SOURCE_NOT_TEXT_OR_TOO_BIG")
    try:
        for tok in yaml.scan(source):
            if isinstance(tok,(yaml.tokens.AnchorToken,yaml.tokens.AliasToken,yaml.tokens.TagToken)):
                raise A157InvalidYAML("YAML_ALIAS_ANCHOR_TAG_UNREVIEWED")
        result=yaml.load(source,Loader=StrictLoader)
    except (yaml.YAMLError,UnicodeError,ValueError,RecursionError,TypeError) as e:
        raise A157InvalidYAML("YAML_PARSE_OR_AMBIGUITY:"+str(e)) from e
    if type(result) is not dict:
        raise A157InvalidYAML("YAML_ROOT_NOT_MAPPING")
    return result


def result(name:str,issues:list[str])->dict[str,Any]:
    issues=sorted(set(issues))
    return {
        "schema":SCHEMA,"workflow":str(name),
        "source_shape_strict":not bool(issues),"findings":issues,
        "no_live_iam_verified":True,"real_writes_allowed":False,
        "external_witness_enrolled":False,"human_owner_verified":False,
        "automatic_resend_allowed":False,"homologated_p0_count":0,
        "new_spend_authorized_brl":0,
        "verdict":"HARD_NO_GO_WORKFLOW_CUSTODY_NOT_VERIFIED",
    }


def common(name:str,source:Any,expected_job:str,permission:str):
    try:
        doc=parse(source)
    except A157InvalidYAML as exc:
        return None,["UNPARSEABLE_OR_AMBIGUOUS_WORKFLOW:"+str(exc)]
    problems=[]
    on=doc.get("on")
    onkeys=set(on) if type(on) is dict else {on} if type(on) is str else None
    if onkeys!=TRIGGERS.get(name):
        problems.append("TRIGGER_SET_INVALID_OR_CHANGED")
    if doc.get("permissions")!={"contents":permission}:
        problems.append("TOP_LEVEL_TOKEN_PERMISSION_CHANGED")
    jobs=doc.get("jobs")
    if type(jobs) is not dict or set(jobs)!={expected_job}:
        problems.append("ADDITIONAL_OR_MISSING_JOB")
        return None,problems
    job=jobs[expected_job]
    if type(job) is not dict:
        problems.append("JOB_NOT_MAPPING")
        return None,problems
    if "permissions" in job:
        problems.append("UNREVIEWED_JOB_PERMISSION_OVERRIDE")
    steps=job.get("steps")
    if type(steps) is not list or not steps or any(type(s) is not dict for s in steps):
        problems.append("JOB_STEPS_INVALID")
    return job,problems


def inspect_critical_workflow(name:str,source:Any)->dict[str,Any]:
    if name not in CRITICAL:
        return result(name,["UNKNOWN_CRITICAL_WORKFLOW"])
    permission=("read" if name in ("autopilot-v107.yml","coleta_automatica.yml")
                else "write")
    job,issues=common(name,source,CRITICAL[name],permission)
    if job is not None:
        if job.get("if")!="$"+"{{ false }}":
            issues.append("UNCONDITIONAL_JOB_HARDSTOP_NOT_PINNED")
        steps=job.get("steps")
        scripts=([x.get("run") for x in steps if type(x.get("run")) is str]
                 if type(steps) is list and all(type(x) is dict for x in steps)
                 else [])
        if not any(WRITER[name] in script for script in scripts):
            issues.append("EXPECTED_WRITER_NOT_IN_ACTUAL_RUN_STEP")
        if name in ("autopilot-v107.yml","coleta_automatica.yml") and job.get("runs-on")!="ubuntu-latest":
            issues.append("SCHEDULED_JOB_RUNNER_CHANGED")
    return result(name,issues)


def inspect_readonly_backup(name:str,source:Any)->dict[str,Any]:
    if name not in BACKUPS:
        return result(name,["UNKNOWN_BACKUP_WORKFLOW"])
    job,issues=common(name,source,BACKUPS[name],"read")
    if job is not None:
        steps=job.get("steps")
        steps=steps if type(steps) is list and all(type(x) is dict for x in steps) else []
        if len(steps)!=3:
            issues.append("BACKUP_STEPS_CHANGED")
        checkout=[s for s in steps if s.get("uses")==CHECKOUT]
        if len(checkout)!=1:
            issues.append("PINNED_CHECKOUT_MISSING")
        elif checkout[0].get("with")!={"persist-credentials":"false"}:
            issues.append("CHECKOUT_GIT_CREDENTIAL_PERSISTENCE_NOT_DISABLED")
        upload=[s for s in steps if s.get("uses")==UPLOAD]
        if len(upload)!=1:
            issues.append("PINNED_UPLOAD_ARTIFACT_MISSING")
        scripts="\n".join(str(s.get("run","")) for s in steps)
        if any(p.search(scripts) for p in MUTATOR_PATTERNS):
            issues.append("UNREVIEWED_BACKUP_GITHUB_MUTATION")
        if not any("zip" in str(s.get("run","")).lower() for s in steps):
            issues.append("BACKUP_ARCHIVE_COMMAND_MISSING")
        if "permissions" in job:
            issues.append("BACKUP_JOB_LEVEL_PERMISSION_OVERRIDE")
    return result(name,issues)


def audit(root:Path=ROOT)->dict[str,Any]:
    root=Path(root).resolve()
    reports={}
    for name in (*CRITICAL,*BACKUPS):
        path=root/FOLDER/name
        try:
            if path.is_symlink() or not path.is_file():
                raise A157InvalidYAML("MISSING_OR_SYMLINKED")
            src=path.read_text(encoding="utf-8")
        except (OSError,UnicodeError,A157InvalidYAML) as exc:
            reports[name]=result(name,["WORKFLOW_READ_FAILURE:"+str(exc)])
        else:
            reports[name]=(inspect_critical_workflow(name,src) if name in CRITICAL
                           else inspect_readonly_backup(name,src))
    return {
        "schema":SCHEMA,"source_only":True,
        "guarded_critical_workflows":len(CRITICAL),
        "readonly_source_backup_workflows":len(BACKUPS),
        "six_workflow_source_contracts_intact":all(
            x["source_shape_strict"] for x in reports.values()),
        "other_workflow_permissions_not_audited":True,
        "effective_github_iam_verified":False,
        "external_monotonic_head_verified":False,
        "real_execution_authorized":False,
        "automatic_resend_allowed":False,
        "homologated_p0_count":0,
        "verdict":"HARD_NO_GO_WORKFLOW_CUSTODY_NOT_VERIFIED",
        "reports":reports,
    }


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--enforce",action="store_true")
    opts=p.parse_args()
    out=audit()
    print(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True))
    return 3 if opts.enforce and not out["six_workflow_source_contracts_intact"] else 0


if __name__=="__main__":
    raise SystemExit(main())
