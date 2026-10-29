"""A262 LAB: inspect actual AtlasQuant publication surfaces, always NO-GO.

No GitHub, Render, Worker, adapter or network call. Reading source is not
evidence of protection on remote Render or in another workflow version.
A262 adds a literal hard-stop to the DRAFT GitHub Render webhook workflow,
and this auditor detects removal, bypass, and extra webhook routes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from collections.abc import Mapping

import yaml
from labs.a261_offline_release_preflight import DuplicateKeySafeLoader

SCHEMA = "ATLASQUANT_AION_A262_DEPLOY_SURFACE_HARD_STOP_LAB_V1"
NO_GO = "HARD_NO_GO_0_OF_6_P0"
MAX_SOURCE_BYTES = 80_000
SURFACES = (
    "render.yaml",
    ".github/workflows/render-deploy-control.yml",
    ".github/render-reconcile.trigger",
    ".github/workflows/production-build-identity.yml",
    ".github/workflows/production-browser-smoke.yml",
    ".github/workflows/production-health.yml",
    ".github/workflows/atlasquant-source-backup.yml",
    ".github/workflows/atlasquant-release-readiness.yml",
)
GUARD_NAME = "A262 HARD NO-GO before Render deploy hook"
GUARD_LINES = (
    "set -euo pipefail",
    'echo "::error::AION HARD NO-GO: 0/6 P0, Render hook forbidden."',
    "exit 2",
)


def _read(root: Path, relative: str) -> bytes:
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("unsafe root")
    file = root / relative
    if not file.is_file() or file.is_symlink():
        raise ValueError("source missing or symlink")
    content = file.read_bytes()
    if not content or len(content) > MAX_SOURCE_BYTES:
        raise ValueError("source blank or oversized")
    return content


def _strict_yaml(value: bytes):
    doc = yaml.load(value.decode("utf-8"), Loader=DuplicateKeySafeLoader)
    if type(doc) is not dict:
        raise ValueError("YAML mapping required")
    return doc


def _hook_step(step) -> bool:
    if type(step) is not dict:
        return False
    run = step.get("run")
    return type(run) is str and (
        "RENDER_DEPLOY_HOOK_URL" in run
        and ("curl " in run or "requests.post" in run)
    )


def _guard_step(step) -> bool:
    if type(step) is not dict:
        return False
    run = step.get("run")
    return (
        step.get("name") == GUARD_NAME
        and type(run) is str
        and tuple(x.strip() for x in run.splitlines() if x.strip()) == GUARD_LINES
        and step.get("shell") == "bash"
        and "if" not in step
        and "continue-on-error" not in step
        and "env" not in step
        and "uses" not in step
    )


def _actions_deploy_review(data: bytes) -> dict:
    try:
        workflow = _strict_yaml(data)
        jobs = workflow.get("jobs")
        # YAML 1.1 SafeLoader parses 'on' as True: prefer either form.
        trigger = workflow.get("on", workflow.get(True))
        if type(jobs) is not dict or type(trigger) is not dict:
            raise ValueError("workflow triggers/jobs invalid")
        manual = "workflow_dispatch" in trigger
        push = trigger.get("push", {})
        push_main = (
            type(push) is dict
            and "main" in push.get("branches", [])
            and ".github/render-reconcile.trigger" in push.get("paths", [])
        )
        publisher_paths = 0
        guarded_paths = 0
        details = []
        for job_name, job in jobs.items():
            if type(job_name) is not str or type(job) is not dict:
                raise ValueError("invalid job")
            steps = job.get("steps")
            if type(steps) is not list:
                raise ValueError("steps missing")
            guard_indices = [i for i, step in enumerate(steps) if _guard_step(step)]
            hook_indices = [i for i, step in enumerate(steps) if _hook_step(step)]
            publisher_paths += len(hook_indices)
            for index in hook_indices:
                step = steps[index]
                # A failing guard must be the first executable shell step after
                # checkout, with no condition, and the hook cannot be "always()"
                # or "failure()" or use continue-on-error to bypass failure.
                index_guard = guard_indices[0] if len(guard_indices) == 1 else None
                earlier = steps[:index_guard] if index_guard is not None else []
                only_checkout_before = (
                    len(earlier) == 1
                    and type(earlier[0]) is dict
                    and type(earlier[0].get("uses")) is str
                    and earlier[0]["uses"].startswith("actions/checkout@")
                    and "if" not in earlier[0]
                    and "run" not in earlier[0]
                )
                safe = (
                    index_guard is not None
                    and index_guard < index
                    and only_checkout_before
                    and "if" not in step
                    and "continue-on-error" not in step
                )
                if safe:
                    guarded_paths += 1
                details.append({
                    "job": job_name, "hook_step_index": index,
                    "draft_hard_stop_precedes_hook": bool(safe),
                })
        return {
            "recognized": True,
            "manual_dispatch": bool(manual),
            "main_reconcile_push": bool(push_main),
            "webhook_paths": publisher_paths,
            "guarded_in_draft": guarded_paths,
            "details": details,
        }
    except (ValueError, TypeError, AttributeError, yaml.YAMLError, UnicodeDecodeError):
        return {
            "recognized": False, "manual_dispatch": False,
            "main_reconcile_push": False, "webhook_paths": 0,
            "guarded_in_draft": 0, "details": [],
        }


def inspect_publication_surfaces(sources: Mapping[str, bytes]) -> dict:
    """Audit known tracked paths. Absence/alteration always means unknown/NO-GO."""
    loaded = {}
    for name in SURFACES:
        raw = sources.get(name) if type(sources) is dict else None
        loaded[name] = raw if type(raw) is bytes and 0 < len(raw) <= MAX_SOURCE_BYTES else b""

    hook = _actions_deploy_review(loaded[".github/workflows/render-deploy-control.yml"])
    current_render = False
    automatic_deploy_off = False
    try:
        doc = _strict_yaml(loaded["render.yaml"])
        services = doc.get("services")
        if type(services) is list and len(services) == 1 and type(services[0]) is dict:
            service = services[0]
            automatic_deploy_off = service.get("autoDeployTrigger") is False or service.get("autoDeployTrigger") == "off"
            current_render = (
                service.get("name") == "atlasquant-private"
                and service.get("branch") == "main"
                and service.get("buildCommand") == "pip install -r requirements.txt"
                and type(service.get("startCommand")) is str
                and service["startCommand"].startswith("streamlit run usd_macro_pro_v4_cloud.py")
            )
    except (ValueError, TypeError, yaml.YAMLError, UnicodeDecodeError):
        pass

    path_trigger = b"expected_main=" in loaded[".github/render-reconcile.trigger"]
    postbuild_probe = b"workflow_dispatch:" in loaded[".github/workflows/production-build-identity.yml"]
    browser_probe = b"workflow_dispatch:" in loaded[".github/workflows/production-browser-smoke.yml"]
    health_probe = b"/_stcore/health" in loaded[".github/workflows/production-health.yml"]
    source_backup = b"zip -qr" in loaded[".github/workflows/atlasquant-source-backup.yml"]
    readiness_only = b"automatic_public_launch" in loaded[".github/workflows/atlasquant-release-readiness.yml"]
    github_guarded = hook["recognized"] and hook["webhook_paths"] >= 1 and hook["webhook_paths"] == hook["guarded_in_draft"]
    findings = []
    if not github_guarded:
        findings.append("UNGUARDED_OR_UNKNOWN_GITHUB_DEPLOY_HOOK")
    if hook["manual_dispatch"]:
        findings.append("GITHUB_MANUAL_DISPATCH_PRESENT")
    if hook["main_reconcile_push"] and path_trigger:
        findings.append("MAIN_RECONCILE_TRIGGER_PRESENT")
    if current_render:
        findings.append("RENDER_SOURCE_BUILD_NOT_A260_ARTIFACT")
    else:
        findings.append("RENDER_CONFIGURATION_NOT_RECOGNIZED")
    findings.append("RENDER_MANUAL_UI_OR_EXTERNAL_HOOK_NOT_VERIFIABLE_FROM_REPO")
    if source_backup:
        findings.append("WHOLE_SOURCE_ZIP_IS_BACKUP_NOT_RUNTIME_ALLOWLIST")
    if postbuild_probe or browser_probe or health_probe or readiness_only:
        findings.append("POST_DEPLOY_PROBES_AND_READINESS_ARE_NOT_P0_AUTHORITY")
    return {
        "schema": SCHEMA, "status": NO_GO,
        "surface_count": len(SURFACES),
        "all_sources_present": all(loaded.values()),
        "github": hook,
        "github_draft_hard_stop_present": bool(github_guarded),
        "render_source_build_observed": bool(current_render),
        "render_auto_deploy_off_configured": bool(automatic_deploy_off),
        "reconcile_trigger_observed": bool(path_trigger),
        "after_deploy_probes_observed": bool(postbuild_probe and browser_probe and health_probe),
        "source_backup_only_observed": bool(source_backup),
        "release_readiness_only_observed": bool(readiness_only),
        "findings": sorted(set(findings)),
        "independently_attested_pipeline": False,
        "p0_homologated": 0,
        "authorizes_send": False, "permits_worker": False,
        "permits_merge": False, "permits_deploy": False,
    }


def inspect_repository(root: Path) -> dict:
    sources = {}
    for relative in SURFACES:
        try:
            sources[relative] = _read(root, relative)
        except (OSError, ValueError):
            sources[relative] = b""
    return inspect_publication_surfaces(sources)


def main(argv=None):
    parser = argparse.ArgumentParser(description="A262 offline source deployment-path inventory, NO-GO")
    parser.add_argument("--source-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    result = inspect_repository(args.source_root)
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 2  # diagnostic NO-GO, not approval to deploy


if __name__ == "__main__":
    raise SystemExit(main())
