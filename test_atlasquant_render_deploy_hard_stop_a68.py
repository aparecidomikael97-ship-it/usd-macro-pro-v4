"""A68 LAB: deployment workflow must be incapable of dispatch while P0 is open.

Pure source contracts: never call Render, GitHub APIs, curl, GH CLI or a real
shell; GitHub Actions semantics: a job with `if: ${{ false }}` never starts.
The block is a temporary hard deny, NOT independent HUMAN_OWNER evidence.
"""
from pathlib import Path
import re
import unittest


WORKFLOW = Path(__file__).resolve().parent / ".github/workflows/render-deploy-control.yml"


def _workflow():
    return WORKFLOW.read_text(encoding="utf-8")


def _redeploy_header():
    source = _workflow()
    # Match only keys of jobs.redeploy, not the always() step condition.
    match = re.search(
        r"(?ms)^jobs:\s*\n  redeploy:\s*\n(?P<body>(?:^    (?!steps:)[^\n]*\n|^\s{6,}[^\n]*\n|^\s*\n)*)",
        source,
    )
    if not match:
        raise AssertionError("A68_DEPLOY_JOB_HEADER_MISSING")
    return match.group("body")


class RenderDeployFailClosedA68Tests(unittest.TestCase):
    def test_01_deploy_job_has_constant_false_guard_before_runner(self):
        header = _redeploy_header()
        self.assertRegex(header, r"(?m)^    if: \$\{\{ false \}\}\s*$")
        self.assertLess(header.index("if: ${{ false }}"), header.index("runs-on:"))
        self.assertNotIn("vars.", header)
        self.assertNotIn("inputs.", header)
        self.assertNotIn("github.actor", header)

    def test_02_manual_dispatch_cannot_be_assumed_owner_consent(self):
        source = _workflow()
        self.assertIn("workflow_dispatch:", source)
        self.assertIn('RENDER_DEPLOY_HOOK_URL: ${{ secrets.RENDER_DEPLOY_HOOK_URL }}', source)
        self.assertIn("if: ${{ false }}", _redeploy_header())
        # A dispatch reason or existing hook never authenticates F2 HUMAN_OWNER.
        self.assertNotIn("human_approved:", source)

    def test_03_push_trigger_cannot_bypass_job_hard_stop(self):
        source = _workflow()
        self.assertIn("push:", source)
        self.assertIn('".github/render-reconcile.trigger"', source)
        self.assertIn("if: ${{ false }}", _redeploy_header())

    def test_04_legacy_recovery_permission_cannot_bypass_job_deny(self):
        source = _workflow()
        permissions = source.split("permissions:", 1)[1].split("concurrency:", 1)[0]
        # The original recovery contract requires actions:write. GitHub Actions
        # does not allocate a token to a skipped job, so the security boundary
        # is the unconditional job-level hard stop, NOT a permission rename.
        self.assertIn("  contents: read", permissions)
        self.assertIn("  actions: write", permissions)
        self.assertIn("if: ${{ false }}", _redeploy_header())

    def test_05_original_deploy_hook_code_preserved_but_unreachable(self):
        source = _workflow()
        self.assertIn("Trigger Render deploy", source)
        self.assertIn('curl -fsS --connect-timeout 20 --max-time 60 -X POST "$RENDER_DEPLOY_HOOK_URL"', source)
        self.assertIn("if: ${{ false }}", _redeploy_header())


if __name__ == "__main__":
    unittest.main()
