"""A157 emergency Draft proposal vs main: six-workflow source-only hardstop.

ALWAYS NO-GO. Never execute workflows, use credentials or modify main.
A successful source review is NOT proof these changes have been merged,
that any GitHub workflow is enabled/disabled, or that an external witness
exists. Intended solely for explicit owner review before potential merge.
"""
from pathlib import Path
import argparse
import json
import re
import yaml

ROOT=Path(__file__).resolve().parents[1]
WORKFLOWS=ROOT/".github"/"workflows"
POLICY={
    "autopilot-v107.yml":("autopilot","read",True,"python autopilot_setup_audit_v114.py"),
    "coleta_automatica.yml":("coletar","read",True,"python coleta_automatica_v86.py"),
    "aion-runtime-checkpoint-bootstrap.yml":("bootstrap","write",True,"gh api --method PUT"),
    "aion-runtime-checkpoint-migrate.yml":("migrate","write",True,"gh api --method PUT"),
    "atlasquant-checkpoint.yml":("checkpoint","read",False,None),
    "atlasquant-source-backup.yml":("backup","read",False,None),
}
CHECKOUT="actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
UPLOAD="actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
BAD_BACKUP_RE=re.compile(
    r"\bgit\s+push\b|\bgh\s+api\s+--method\s+(?:PUT|POST|PATCH|DELETE)\b"
    r"|\brequests\.(?:put|post|patch|delete)\s*\(",
    re.I,
)


class YAMLUnsafe(ValueError):
    pass


class StrictLoader(yaml.BaseLoader):
    def construct_mapping(self,node,deep=False):
        seen=set()
        for k,_ in node.value:
            key=self.construct_object(k,deep=deep)
            if type(key) is not str or key=="<<" or key in seen:
                raise YAMLUnsafe("DUPLICATE_OR_UNSAFE_YAML_KEY")
            seen.add(key)
        return super().construct_mapping(node,deep=deep)


def check_source(name,source):
    problems=[]
    if name not in POLICY or type(source) is not str:
        problems.append("UNKNOWN_OR_NONSTRING_WORKFLOW")
        return {"workflow":name,"source_pinned":False,"findings":problems,
                "verdict":"HARD_NO_GO_MAIN_NOT_MERGED"}
    try:
        for t in yaml.scan(source):
            if isinstance(t,(yaml.tokens.AnchorToken,yaml.tokens.AliasToken,yaml.tokens.TagToken)):
                raise YAMLUnsafe("UNREVIEWED_YAML_ALIAS_OR_TAG")
        doc=yaml.load(source,Loader=StrictLoader)
    except (yaml.YAMLError,YAMLUnsafe,ValueError,TypeError) as exc:
        doc={}
        problems.append("YAML_INVALID:"+type(exc).__name__)
    jobname,scope,must_stop,writer=POLICY[name]
    if type(doc) is not dict:
        doc={}
        problems.append("NOT_A_WORKFLOW_MAPPING")
    if doc.get("permissions")!={"contents":scope}:
        problems.append("WRONG_REPOSITORY_TOKEN_SCOPE")
    jobs=doc.get("jobs")
    if type(jobs) is not dict or set(jobs)!={jobname}:
        problems.append("JOB_ADDED_REMOVED_OR_DUPLICATED")
        job={}
    else:
        job=jobs[jobname]
        if type(job) is not dict:
            job={}
            problems.append("EXPECTED_JOB_NOT_MAPPING")
    if "permissions" in job:
        problems.append("JOB_LEVEL_PERMISSION_OVERRIDE")
    if must_stop and job.get("if")!="$"+"{{ false }}":
        problems.append("UNCONDITIONAL_JOB_FALSE_MISSING")
    steps=job.get("steps")
    if type(steps) is not list or any(type(s) is not dict for s in steps):
        steps=[]
        problems.append("JOB_STEPS_INVALID")
    scripts="\n".join(str(x.get("run","")) for x in steps)
    if writer and writer not in scripts:
        problems.append("EXPECTED_REAL_WRITER_COMMAND_MISSING")
    if not must_stop:
        checks=[s for s in steps if s.get("uses")==CHECKOUT]
        uploads=[s for s in steps if s.get("uses")==UPLOAD]
        if len(checks)!=1 or checks[0].get("with")!={"persist-credentials":"false"}:
            problems.append("BACKUP_CHECKOUT_TOKEN_MAY_PERSIST")
        if len(uploads)!=1 or len(steps)!=3:
            problems.append("BACKUP_ARTIFACT_STEPS_DRIFT")
        if BAD_BACKUP_RE.search(scripts):
            problems.append("BACKUP_CONTAINS_DIRECT_GITHUB_MUTATION")
    return {
        "workflow":name,
        "source_pinned":not bool(problems),
        "findings":sorted(set(problems)),
        "github_iam_verified":False,
        "current_main_workflow_state_verified":False,
        "real_write_authorized":False,
        "external_witness_enrolled":False,
        "homologated_p0_count":0,
        "verdict":"HARD_NO_GO_MAIN_NOT_MERGED",
    }


def audit():
    reports={}
    for name in POLICY:
        p=WORKFLOWS/name
        try:
            if p.is_symlink() or not p.is_file():
                raise OSError("missing or symlink")
            reports[name]=check_source(name,p.read_text(encoding="utf-8"))
        except (OSError,UnicodeError):
            reports[name]={"workflow":name,"source_pinned":False,
                           "findings":["SOURCE_MISSING_OR_UNREADABLE"],
                           "verdict":"HARD_NO_GO_MAIN_NOT_MERGED"}
    return {
        "schema":"A157_MAIN_EMERGENCY_REVIEW_NO_GO_V1",
        "six_source_shapes_pinned":all(x["source_pinned"] for x in reports.values()),
        "critical_job_count":4,"source_backup_count":2,
        "job_runtime_states_observed":False,
        "proof_main_contains_this_candidate":False,
        "real_execution_authorized":False,
        "homologated_p0_count":0,
        "verdict":"HARD_NO_GO_MAIN_NOT_MERGED",
        "reports":reports,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--enforce",action="store_true")
    args=parser.parse_args()
    result=audit()
    print(json.dumps(result,indent=2,sort_keys=True))
    return 3 if args.enforce and not result["six_source_shapes_pinned"] else 0


if __name__=="__main__":
    raise SystemExit(main())
