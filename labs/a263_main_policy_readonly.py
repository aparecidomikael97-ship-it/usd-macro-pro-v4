"""A263: read-only GitHub main-branch policy observation, fail closed.

Important: GitHub's branch listing is NOT the complete admin protection
contract. A status check that is green does not imply required status checks.
No release/merge/deploy authorization exists in this module.

Only GET /branches/main and /rulesets?includes_parents=true are used;
no branch/ruleset writes, actions dispatch, Render, secrets modification or
external effects. The CLI ALWAYS returns a nonzero exit status.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
from urllib.request import Request, urlopen

SCHEMA = "ATLASQUANT_AION_A263_MAIN_POLICY_READONLY_NO_GO_V1"
REPO = "aparecidomikael97-ship-it/usd-macro-pro-v4"
SHA40 = re.compile(r"[0-9a-f]{40}", re.ASCII)
BASE_URL = "https://api.github.com/repos/" + REPO
NO_GO = "HARD_NO_GO_REPOSITORY_POLICY_NOT_HOMOLOGATED"


def assess_policy_snapshot(branch, rulesets):
    """Pure analysis: caller JSON is an observation, never policy authority."""
    issues = []
    actual_main = (
        type(branch) is dict and branch.get("name") == "main"
        and type(branch.get("commit")) is dict
        and type(branch["commit"].get("sha")) is str
        and SHA40.fullmatch(branch["commit"]["sha"]) is not None
    )
    protected = actual_main and branch.get("protected") is True
    if not actual_main:
        issues.append("MAIN_BRANCH_RESPONSE_UNKNOWN_OR_INVALID")
    if not protected:
        issues.append("MAIN_PROTECTION_NOT_OBSERVED")
    protection = branch.get("protection", {}) if actual_main else {}
    if type(protection) is not dict:
        protection = {}
    status_checks = protection.get("required_status_checks")
    if type(status_checks) is not dict:
        status_checks = {}
    contexts = status_checks.get("contexts", [])
    checks = status_checks.get("checks", [])
    checks_visible = bool(
        protected and (
            (type(contexts) is list and contexts and
             all(type(c) is str and c for c in contexts))
            or (type(checks) is list and checks and
                all(type(c) is dict and type(c.get("context")) is str
                    and c.get("context") for c in checks))
        ) and status_checks.get("enforcement_level") == "on"
    )
    if not checks_visible:
        issues.append("REQUIRED_CHECKS_NOT_VISIBLE_AS_ENFORCED")
    ruleset_list_valid = type(rulesets) is list
    active = []
    if ruleset_list_valid:
        for row in rulesets:
            if type(row) is dict and row.get("enforcement") == "active":
                active.append(row.get("id"))
    if not active:
        issues.append("NO_ACTIVE_REPOSITORY_RULESET_OBSERVED")
    # Collection-level rulesets responses do NOT expose full PR-review
    # conditions, bypass actors, source delegation, or enforcement guarantees.
    issues.append("ADMIN_REQUIRED_REVIEWS_AND_BYPASS_UNVERIFIED")
    issues.append("RENDER_AND_EXTERNAL_DEPLOY_PERMISSIONS_UNVERIFIED")
    # The API is read-only, cannot assert what protections are really enforced
    # in GitHub org/admin settings or by Render outside this repository.
    return {
        "schema": SCHEMA, "status": NO_GO,
        "main_sha": branch["commit"]["sha"] if actual_main else None,
        "main_response_valid": bool(actual_main),
        "main_protected_visible": bool(protected),
        "required_checks_visible": bool(checks_visible),
        "active_repo_rulesets_visible": len(active),
        "rulesets_collection_valid": bool(ruleset_list_valid),
        "admin_protection_details_verified": False,
        "required_pr_review_verified": False,
        "bypass_users_verified": False,
        "render_permissions_verified": False,
        "issues": sorted(set(issues)),
        "p0_homologated": 0,
        "authorizes_send": False,
        "permits_merge": False,
        "permits_worker": False,
        "permits_deploy": False,
        "release_approved": False,
    }


def observe_live_policy(*, timeout=12):
    """Two GitHub GET requests; intentionally no write-capable API calls."""
    if type(timeout) not in (int, float) or timeout <= 0 or timeout > 30:
        raise ValueError("invalid GET timeout")
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AtlasQuant-AION-A263-read-only-policy-observation",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    def read(path):
        url = BASE_URL + path
        req = Request(url, headers=headers, method="GET")
        with urlopen(req, timeout=timeout) as res:
            if res.status != 200:
                raise ValueError("GitHub GET did not return HTTP 200")
            data = res.read(300_001)
        if len(data) > 300_000:
            raise ValueError("GitHub policy response too large")
        return json.loads(data)
    branch = read("/branches/main")
    rulesets = read("/rulesets?includes_parents=true")
    result = assess_policy_snapshot(branch, rulesets)
    result["observed_at_utc"] = datetime.now(timezone.utc).isoformat()
    result["source"] = "GITHUB_READ_ONLY_GET_TWO_ENDPOINTS_UNVERIFIED_ADMIN"
    return result


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="A263 read-only live main policy check; NO-GO")
    parser.add_argument("--live", action="store_true", help="read GitHub public policy endpoints")
    args = parser.parse_args(argv)
    try:
        if not args.live:
            raise ValueError("live observation flag missing")
        result = observe_live_policy()
    except Exception as exc:
        # Exception types only; never log token, URLs carrying secrets or
        # response bodies from external sources.
        result = {
            "schema": SCHEMA, "status": NO_GO,
            "issues": ["GITHUB_POLICY_READ_FAILED_CLOSED", type(exc).__name__],
            "source": "LIVE_POLICY_UNAVAILABLE",
            "p0_homologated": 0, "authorizes_send": False,
            "permits_merge": False, "permits_worker": False,
            "permits_deploy": False, "release_approved": False,
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    # Deliberately never return 0: this program cannot authorize release.
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
