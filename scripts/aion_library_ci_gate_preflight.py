"""Read-only guard for AION Library synthetic browser+PG main-PR CI coverage.

A green check from an older branch does NOT substitute for a run on the exact
new SHA. This preflight neither changes workflows nor dispatches any run.
It checks the known canonical YAML layout with the Python standard library;
unsupported YAML constructs deliberately fail closed.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parent.parent / ".github/workflows/aion-library-browser-pg-joint.yml"
EXPECTED_PATHS = {
    "aion_core/library_*.py",
    "atlasquant_aion_library_*.py",
    "atlasquant_aion_admin.py",
    "atlasquant_access_control.py",
    "atlasquant_access_panel.py",
    "test_aion_core_library_*.py",
    "test_atlasquant_aion_library_*.py",
    "scripts/aion_library_ci_*.py",
    "scripts/test_aion_library_browser_pg_joint.py",
    ".github/workflows/aion-library-browser-pg-joint.yml",
    "AION_LIBRARY_BROWSER_PG_JOINT_V1_README.md",
}
EXPECTED_FLAGS = {
    "CI": "true",
    "ATLASQUANT_ENV": "SANDBOX",
    "ATLASQUANT_REAL_APP_SYNTHETIC": "1",
    "AION_LIB_BROWSER_PG_E2E": "1",
    "AION_LIB_FULL_CHAIN_TEST": "1",
    "AION_LIB_JOINT_E2E": "1",
    "AION_LIB_TEST_PG_DSN": "postgresql://library_sandbox:synthetic_ci_only_not_for_production@localhost:5432/aion_library_sandbox",
}


def _block(lines: list[str], heading: str, indent: int) -> list[str]:
    """Extract exactly one canonical YAML mapping section; refuse ambiguity."""
    pattern = re.compile(r"^" + " " * indent + re.escape(heading) + r":\s*$")
    indexes = [i for i, line in enumerate(lines) if pattern.fullmatch(line)]
    if len(indexes) != 1:
        raise ValueError("missing or ambiguous section: " + heading)
    start = indexes[0] + 1
    end = start
    while end < len(lines):
        stripped = lines[end].strip()
        if stripped and not lines[end].startswith(" " * (indent + 1)):
            break
        end += 1
    return lines[start:end]


def _list(lines: list[str], heading: str, indent: int) -> set[str]:
    block = _block(lines, heading, indent)
    values: set[str] = set()
    for line in block:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r" {" + str(indent + 2) + r"}-\s+([A-Za-z0-9_./*:-]+|'[^']+'|\"[^\"]+\")\s*", line)
        if not match:
            raise ValueError("unsupported list entry in " + heading)
        value = match.group(1).strip("'\"")
        if value in values:
            raise ValueError("duplicate list entry in " + heading)
        values.add(value)
    return values


def inspect_workflow(source: str) -> list[str]:
    errors: list[str] = []
    # Exclude comment-only text so comments cannot manufacture passing flags.
    clean = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
    lines = clean.splitlines()
    try:
        on = _block(lines, "on", 0)
        events = set(re.findall(r"^  ([A-Za-z_]+):\s*$", "\n".join(on), re.M))
        if events != {"pull_request", "workflow_dispatch"}:
            errors.append("only workflow_dispatch and pull_request events permitted")
        pull = _block(on, "pull_request", 2)
        branches = _list(pull, "branches", 4)
        if not {"main", "review/aion-library-joint-reconciliation-v1-20261001"} <= branches:
            errors.append("missing main or existing stacked-PR trigger")
        paths = _list(pull, "paths", 4)
        missing = sorted(EXPECTED_PATHS - paths)
        if missing:
            errors.append("missing exact path filters: " + ", ".join(missing))
        if paths.intersection({"*", "**", "**/*", "*.py"}):
            errors.append("unbounded path filter")
    except ValueError as exc:
        errors.append(str(exc))

    try:
        perm = _block(lines, "permissions", 0)
        effective = [s.strip() for s in perm if s.strip() and not s.lstrip().startswith("#")]
        if effective != ["contents: read"]:
            errors.append("workflow requires global permissions: contents: read ONLY")
    except ValueError as exc:
        errors.append(str(exc))
    if re.search(r"(?m)^\s*contents:\s*write\s*$", clean):
        errors.append("write permissions are forbidden")
    try:
        jobs = _block(lines, "jobs", 0)
        job = _block(jobs, "actual-app-browser-pg-synthetic", 2)
        job_env = _block(job, "env", 4)
        env_text = "\n".join(job_env)
        for key, expected in EXPECTED_FLAGS.items():
            expected_line = re.compile(
                r"(?m)^      " + re.escape(key) + r":\s*['\"]?" + re.escape(expected) + r"['\"]?\s*$"
            )
            if not expected_line.search(env_text):
                errors.append("missing strict job-level synthetic environment flag: " + key)
        services = _block(job, "services", 4)
        postgres = _block(services, "postgres", 6)
        if not any(line.strip() == "image: postgres:16" for line in postgres):
            errors.append("PostgreSQL service must use postgres:16")
    except ValueError as exc:
        errors.append(str(exc))
    for label, marker in {
        "PostgreSQL 16 ephemeral service": "image: postgres:16",
        "local synthetic database": "localhost:5432/aion_library_sandbox",
        "real-app browser + PG test": "python scripts/test_aion_library_browser_pg_joint.py",
        "independent PG adversarial suite": "test_atlasquant_aion_library_server_selection_pg",
    }.items():
        if marker not in clean:
            errors.append("missing " + label)
    if "RENDER_DEPLOY_HOOK_URL" in clean or "secrets." in clean:
        errors.append("no runtime deploy hook or production secrets permitted")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow", type=Path, default=WORKFLOW)
    args = parser.parse_args()
    try:
        failures = inspect_workflow(args.workflow.read_text(encoding="utf-8"))
    except OSError:
        failures = ["workflow unavailable"]
    print(json.dumps({
        "schema": "AION_LIBRARY_MAIN_PR_BROWSER_PG_GATE_PREFLIGHT_V1",
        "status": "BLOCKED" if failures else "PREFLIGHT_PASS_NOT_CI_SUCCESS",
        "failures": failures,
    }, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
