"""AION A137 — read-only GitHub Actions credential/write-surface audit.

Static textual guard against a narrow, explicitly enumerated set of workflow
jobs capable of running with repository write tokens or directly mutating
Checkpoint Mestre. It never executes source code, workflows, external tools,
GitHub API writes or app code. No claim of live IAM state is made.

A textual YAML audit is defense in depth, not a complete YAML parser or
sound proof of all transitive scripts, aliases, actions or indirect paths.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SCHEMA="AION_P0_WORKFLOW_CREDENTIAL_SURFACE_A137_LAB"
WORKFLOWS=Path(".github/workflows")
GUARDED={
    "autopilot-v107.yml":"autopilot",
    "coleta_automatica.yml":"coletar",
    "aion-runtime-checkpoint-bootstrap.yml":"bootstrap",
    "aion-runtime-checkpoint-migrate.yml":"migrate",
}
EXPECTED_WRITERS={
    "autopilot-v107.yml":"autopilot_setup_audit_v114.py",
    "coleta_automatica.yml":"coleta_automatica_v86.py",
    "aion-runtime-checkpoint-bootstrap.yml":"gh api --method PUT",
    "aion-runtime-checkpoint-migrate.yml":"gh api --method PUT",
}
EXPECTED_GUARD_EXPRESSION=re.compile(r"^    if:\s*\$\{\{\s*false\s*\}\}\s*(?:#.*)?$",re.M)


def workflow_job_body(text:str, job_name:str)->str:
    if type(text) is not str or type(job_name) is not str:
        return ""
    lines=text.splitlines()
    jobs_idx=next((i for i,line in enumerate(lines) if line=="jobs:"),None)
    if jobs_idx is None:
        return ""
    start=next((i for i in range(jobs_idx+1,len(lines))
                if lines[i]==f"  {job_name}:"),None)
    if start is None:
        return ""
    end=next((i for i in range(start+1,len(lines))
              if re.fullmatch(r"  [a-zA-Z0-9_-]+:",lines[i])),len(lines))
    return "\n".join(lines[start:end])


def inspect_one(name:str,text:str)->dict:
    job=GUARDED.get(name)
    block=workflow_job_body(text,job) if job else ""
    permission_write=bool(re.search(r"(?m)^\s+contents:\s*write\s*(?:#.*)?$",text))
    schedule=bool(re.search(r"(?m)^  schedule:\s*$",text))
    app_token=bool(
        re.search(r"\bGITHUB_TOKEN_HISTORICO\s*:",text)
        or re.search(r"\bGH_TOKEN_APP\s*:",text)
        or re.search(r"\bGH_TOKEN\s*:",text)
    )
    direct_checkpoint=bool(
        "contents/dados/aion/checkpoint_master.json" in text
        or "dados/aion/checkpoint_master.json" in text
    )
    job_disabled=bool(
        block and EXPECTED_GUARD_EXPRESSION.search(block)
    )
    expected_writer_present=(
        EXPECTED_WRITERS[name] in block if job else None
    )
    # Two independent LAB fences on scheduled write-capable jobs:
    # unconditional skip plus least-privilege repo token. The bootstrap and
    # migration jobs are unscheduled, already skipped and not changed here.
    guarded_ok=bool(
        job and job_disabled and expected_writer_present
        and (not schedule or not permission_write)
    )
    return {
        "path":str(WORKFLOWS/name),
        "guarded_job":job,
        "guarded_job_present":bool(block),
        "scheduled":schedule,
        "contents_write_declared":permission_write,
        "token_exposed_in_workflow_text":app_token,
        "checkpoint_path_mentioned":direct_checkpoint,
        "job_disabled_unconditionally":job_disabled if job else None,
        "expected_writer_present":expected_writer_present,
        "target_p0_fence_ok":guarded_ok if job else None,
    }


def audit(root:Path)->dict:
    folder=root/WORKFLOWS
    files=sorted(folder.glob("*.yml"))+sorted(folder.glob("*.yaml"))
    rows=[]
    for path in sorted(files):
        try:
            text=path.read_text(encoding="utf-8")
            rows.append(inspect_one(path.name,text))
        except (OSError,UnicodeError) as exc:
            rows.append({"path":str(path.relative_to(root)),"read_error":type(exc).__name__})
    by_name={Path(r["path"]).name:r for r in rows}
    missing=sorted(set(GUARDED)-set(by_name))
    blocked=[
        {"file":name,"job":GUARDED[name],"reason":"JOB_NOT_UNCONDITIONALLY_DENIED"}
        for name in GUARDED
        if name in by_name and not by_name[name].get("target_p0_fence_ok")
    ]
    broad=[
        {"file":Path(r["path"]).name,
         "scheduled":r["scheduled"],
         "contents_write":r["contents_write_declared"],
         "token":r["token_exposed_in_workflow_text"]}
        for r in rows if r.get("scheduled") and r.get("contents_write_declared")
    ]
    return {
        "schema":SCHEMA,
        "status":"STATIC_WORKFLOW_INVENTORY_NO_GO",
        "workflow_files_scanned":len(rows),
        "guarded_critical_jobs":len(GUARDED),
        "missing_critical_workflows":missing,
        "critical_jobs_not_hard_stopped":blocked,
        "scheduled_with_repository_write_permissions":broad,
        "all_source_lines_ignored_execution":True,
        "external_monotonic_witness_enrolled":False,
        "human_owner_identity_verified":False,
        "worker_activated":False,
        "runtime_restored":False,
        "evidence_limited_to_repository_source":True,
        "read_errors":[r for r in rows if "read_error" in r],
        "critical_jobs":{n:by_name.get(n) for n in GUARDED},
    }


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--enforce",action="store_true")
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    result=audit(root)
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    if args.enforce and (
        result["missing_critical_workflows"]
        or result["critical_jobs_not_hard_stopped"]
        or result["read_errors"]
    ):
        return 1
    return 0


if __name__=="__main__":
    raise SystemExit(main())
