"""A264 LAB: validate an ADMIN-ONLY GitHub main ruleset *proposal*.

The JSON in docs/lab/a264_main_ruleset_admin_proposal.json is a proposed
GitHub REST payload, not an installed ruleset. This reviewer reads source
text only. It does NOT call the GitHub administration API, deploy, merge,
activate Worker or authorize any AION effect.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping

import yaml

SCHEMA = "ATLASQUANT_AION_A264_ADMIN_MAIN_RULESET_DRAFT_V1"
BLUEPRINT_PATH = "docs/lab/a264_main_ruleset_admin_proposal.json"
CODEOWNERS_PATH = ".github/CODEOWNERS"
QUALITY_PATH = ".github/workflows/quality-tests.yml"
REPO = "aparecidomikael97-ship-it/usd-macro-pro-v4"
GITHUB_ACTIONS_APP_ID = 15368
PRIMARY_OWNER = "@aparecidomikael97-ship-it"
NO_GO = "HARD_NO_GO_ADMIN_RULESET_NOT_INSTALLED_OR_ATTESTED"


def _one_rule(rules, kind):
    if type(rules) is not list:
        return None
    matches = [r for r in rules if type(r) is dict and r.get("type") == kind]
    return matches[0] if len(matches) == 1 else None


def review_blueprint(blueprint, *, codeowners_text, quality_text):
    """Strict contract check; a passing proposal is NEVER live protection."""
    reasons = []
    if type(blueprint) is not dict or set(blueprint) != {
        "name", "target", "enforcement", "bypass_actors",
        "conditions", "rules",
    }:
        reasons.append("UNKNOWN_RULESET_TOP_LEVEL_OR_FIELDS")
        blueprint = {}
    if blueprint.get("name") != "ATLASQUANT_AION_MAIN_FREEZE_ADMIN_REVIEW_REQUIRED":
        reasons.append("NAME_NOT_PINNED")
    if blueprint.get("target") != "branch" or blueprint.get("enforcement") != "active":
        reasons.append("NOT_ACTIVE_BRANCH_RULESET_PROPOSAL")
    if blueprint.get("bypass_actors") != []:
        reasons.append("BYPASS_ACTORS_NOT_EMPTY")
    if blueprint.get("conditions") != {
        "ref_name": {"include": ["refs/heads/main"], "exclude": []}
    }:
        reasons.append("MAIN_TARGET_NOT_EXACT")
    rules = blueprint.get("rules")
    if (
        type(rules) is not list or len(rules) != 4
        or {x.get("type") for x in rules if type(x) is dict}
        != {"deletion", "non_fast_forward", "pull_request", "required_status_checks"}
    ):
        reasons.append("RULE_SET_NOT_EXACT")
        rules = []
    for kind in ("deletion", "non_fast_forward"):
        item = _one_rule(rules, kind)
        if type(item) is not dict or set(item) != {"type"}:
            reasons.append("MISSING_" + kind.upper() + "_RULE")
    pr = _one_rule(rules, "pull_request")
    expected_pr = {
        "required_approving_review_count": 1,
        "dismiss_stale_reviews_on_push": True,
        "require_code_owner_review": True,
        "require_last_push_approval": True,
        "required_review_thread_resolution": True,
    }
    if pr != {"type": "pull_request", "parameters": expected_pr}:
        reasons.append("PR_APPROVAL_OR_INDEPENDENT_REVIEW_WEAKENED")
    checks = _one_rule(rules, "required_status_checks")
    expected_checks = {
        "strict_required_status_checks_policy": True,
        "required_status_checks": [
            {"context": "test", "integration_id": GITHUB_ACTIONS_APP_ID}
        ],
    }
    if checks != {"type": "required_status_checks", "parameters": expected_checks}:
        reasons.append("REQUIRED_QUALITY_TEST_NOT_PINNED")
    if type(codeowners_text) is not str or not codeowners_text.strip():
        reasons.append("CODEOWNERS_MISSING")
    else:
        # Exact owner of workflow directory and policy file are important.
        if (
            "/.github/workflows/ " + PRIMARY_OWNER not in codeowners_text
            or "/.github/CODEOWNERS " + PRIMARY_OWNER not in codeowners_text
            or "* " + PRIMARY_OWNER not in codeowners_text
        ):
            reasons.append("CODEOWNERS_SENSITIVE_PATH_OWNERSHIP_MISSING")
    try:
        if type(quality_text) is not str:
            raise ValueError("quality source missing")
        doc = yaml.safe_load(quality_text)
        if type(doc) is not dict or doc.get("name") != "Quality tests":
            raise ValueError("wrong workflow name")
        jobs = doc.get("jobs")
        if type(jobs) is not dict or "test" not in jobs:
            raise ValueError("job context not declared")
        # GitHub workflows with pull_request trigger on main can produce
        # this context on a main-targeted PR. PyYAML 1.1 parses 'on' as True.
        triggers = doc.get("on", doc.get(True))
        if type(triggers) is not dict:
            raise ValueError("PR trigger missing")
        pr_target = triggers.get("pull_request")
        if type(pr_target) is not dict or "main" not in pr_target.get("branches", []):
            raise ValueError("required check not configured for main PR")
    except (yaml.YAMLError, TypeError, ValueError, AttributeError):
        reasons.append("QUALITY_JOB_OR_MAIN_PR_TRIGGER_NOT_CONFIRMED")
    # Repository is currently a personal account with CODEOWNERS naming one
    # author. This code cannot verify a DIFFERENT human with write access.
    return {
        "schema": SCHEMA,
        "status": NO_GO,
        "proposal_structure_valid": not reasons,
        "proposal_issues": sorted(set(reasons)),
        "required_quality_context_candidate": "test",
        "github_actions_integration_id_candidate": GITHUB_ACTIONS_APP_ID,
        "quality_context_verified_in_required_checks_ui": False,
        "independent_human_reviewer_confirmed": False,
        "admin_ruleset_applied_verified": False,
        "main_protection_applied_verified": False,
        "p0_homologated": 0,
        "authorizes_send": False,
        "permits_merge": False,
        "permits_deploy": False,
        "permits_worker": False,
    }


def review_repository(root: Path):
    root = Path(root)
    try:
        if root.is_symlink() or not root.is_dir():
            raise ValueError("root invalid")
        blueprint = json.loads((root / BLUEPRINT_PATH).read_text("utf-8"))
        codeowners_text = (root / CODEOWNERS_PATH).read_text("utf-8")
        quality_text = (root / QUALITY_PATH).read_text("utf-8")
        return review_blueprint(
            blueprint, codeowners_text=codeowners_text,
            quality_text=quality_text,
        )
    except (OSError, ValueError, TypeError, UnicodeDecodeError):
        result = review_blueprint(
            {}, codeowners_text="", quality_text="",
        )
        return {**result, "proposal_issues": sorted(
            set(result["proposal_issues"]) | {"LOCAL_EVIDENCE_NOT_READABLE"}
        ), "proposal_structure_valid": False}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="A264 inspect main ruleset ADMIN proposal; never install it"
    )
    parser.add_argument("--source-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    result = review_repository(args.source_root)
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 3  # NEVER return exit 0 as authorization to publish/merge.


if __name__ == "__main__":
    raise SystemExit(main())
