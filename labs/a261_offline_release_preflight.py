"""A261 LAB: executable OFFLINE release-boundary preflight (always NO-GO).

This code NEVER deploys, merges, invokes Render, starts Worker or sends
network traffic. It must not be mistaken for a Render pre-deploy hook: the
existing Render service DOES NOT run this module. The A260 ZIP contains
only chat/Outbox source, not the Streamlit Trader app.

Only positive classification permitted: A260 archive STRUCTURE valid.
Authority, independent provenance and publish/deploy permission remain False.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from labs.a260_offline_runtime_bundle import (
    OfflineBundleRejected, verify_offline_candidate,
)

SCHEMA = "ATLASQUANT_AION_A261_OFFLINE_RELEASE_PREFLIGHT_V1"
MAX_CONFIG_BYTES = 64 * 1024
NO_GO = "HARD_NO_GO_NOT_A_DEPLOY_AUTHORIZATION"


class DuplicateKeySafeLoader(yaml.SafeLoader):
    """Do not let duplicate YAML keys silently override a safety setting."""


def _mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if type(key) is not str or key in result:
            raise ValueError("invalid or duplicate YAML key")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


DuplicateKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping
)


def _config(raw):
    if type(raw) is not bytes or len(raw) > MAX_CONFIG_BYTES:
        raise ValueError("configuration too large, absent or of wrong type")
    data = yaml.load(raw.decode("utf-8"), Loader=DuplicateKeySafeLoader)
    if type(data) is not dict or set(data) != {"services"}:
        raise ValueError("unknown render configuration document")
    services = data["services"]
    if type(services) is not list or not services:
        raise ValueError("no services or non-list")
    names = set()
    for service in services:
        if type(service) is not dict:
            raise ValueError("service must be a mapping")
        required = {"type", "name", "runtime", "branch", "autoDeployTrigger",
                    "buildCommand", "startCommand"}
        allowed = required | {"healthCheckPath"}
        if not required.issubset(service) or set(service) - allowed:
            raise ValueError("unexpected or missing service fields")
        if any(type(service[k]) is not str or not service[k].strip()
               for k in required - {"autoDeployTrigger"}):
            raise ValueError("missing or invalid service detail")
        name = service["name"]
        if name in names:
            raise ValueError("duplicate service name")
        names.add(name)
    return services


def inspect_release_boundary(*, candidate: bytes | Path,
                             render_config: bytes) -> dict:
    """Inspect one A260 study candidate and the actual Render source config.

    The result is *always* deny for deployment, even with valid source ZIP
    and apparently safe settings. Claims passed within YAML are NOT trusted.
    """
    issues = []
    verified = None
    try:
        verified = verify_offline_candidate(candidate)
    except (OfflineBundleRejected, OSError, ValueError, TypeError):
        issues.append("A260_STUDY_CANDIDATE_UNVERIFIED")
    try:
        services = _config(render_config)
    except (ValueError, UnicodeDecodeError, yaml.YAMLError, TypeError):
        services = []
        issues.append("RENDER_CONFIG_INVALID_OR_UNTRUSTED")
    for service in services:
        name = service["name"]
        auto = service["autoDeployTrigger"]
        if auto is not False and auto != "off":
            issues.append("AUTO_DEPLOY_NOT_DISABLED:" + name)
        # This service is sourced from a Git checkout rather than from the
        # exact six-file A260 ZIP, even if its buildCommand claims otherwise.
        issues.append("RENDER_SOURCE_CHECKOUT_NOT_A260_BOUND:" + name)
        if service["runtime"] != "python":
            issues.append("RUNTIME_UNEXPECTED:" + name)
        # A260 ZIP contains no web app, and is in any case a non-authority
        # study candidate. Do not treat textual 'preflight' commands in YAML
        # as proof of a protected artifact hand-off.
        if "streamlit" in service["startCommand"].lower():
            issues.append("STREAMLIT_APPLICATION_NOT_IN_A260:" + name)
        if service["branch"] == "main":
            issues.append("MAIN_SOURCE_BRANCH_NOT_ATTESTED:" + name)
    if verified is None and not issues:
        issues.append("NO_STRUCTURAL_PROOF")
    return {
        "schema": SCHEMA, "status": NO_GO,
        "candidate_structure_verified": verified is not None,
        "candidate_is_deployable_app": False,
        "render_config_recognized": bool(services),
        "issues": sorted(set(issues)),
        "p0_homologated": 0,
        "independent_provenance_verified": False,
        "authorizes_send": False, "permits_worker": False,
        "permits_deploy": False, "permits_merge": False,
        "release_approved": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="AION A261 OFFLINE safety preflight; ALWAYS exits NO-GO"
    )
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--render-config", required=True)
    args = parser.parse_args(argv)
    try:
        result = inspect_release_boundary(
            candidate=Path(args.candidate),
            render_config=Path(args.render_config).read_bytes(),
        )
    except (OSError, ValueError, TypeError):
        result = {
            "schema": SCHEMA, "status": NO_GO,
            "candidate_structure_verified": False,
            "candidate_is_deployable_app": False,
            "render_config_recognized": False,
            "issues": ["PREFLIGHT_INPUT_UNREADABLE"],
            "p0_homologated": 0,
            "independent_provenance_verified": False,
            "authorizes_send": False, "permits_worker": False,
            "permits_deploy": False, "permits_merge": False,
            "release_approved": False,
        }
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 2  # Reserved failure/NO-GO code, NEVER 0 for publish approval.


if __name__ == "__main__":
    raise SystemExit(main())
