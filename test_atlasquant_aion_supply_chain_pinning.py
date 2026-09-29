import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
WORKFLOWS = ROOT / ".github" / "workflows"
SHA40 = re.compile(r"@[0-9a-f]{40}(?:\\s|$)", re.I)
REQUIREMENT = re.compile(r"^[A-Za-z0-9_.-]+==[^=\\s]+$")


class AionSupplyChainPinningTests(unittest.TestCase):
    def test_runtime_requirements_are_exactly_pinned(self):
        rows = [
            line.strip()
            for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertTrue(rows)
        for row in rows:
            with self.subTest(requirement=row):
                self.assertRegex(row, REQUIREMENT)

    def test_external_github_actions_are_pinned_to_commit_sha(self):
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped.startswith("uses:"):
                    continue
                value = stripped.split("uses:", 1)[1].split("#", 1)[0].strip()
                if value.startswith("./") or value.startswith("docker://"):
                    continue
                with self.subTest(workflow=path.name, action=value):
                    self.assertRegex(value, SHA40)

    def test_python_workflows_do_not_reintroduce_loose_pip_or_runtime_installs(self):
        forbidden = (
            re.compile(r"pip\\s+install\\s+--upgrade\\s+pip\\b"),
            re.compile(r"pip\\s+install\\s+streamlit\\s+pandas\\s+numpy\\s+requests\\b"),
            re.compile(r"pip\\s+install\\s+playwright(?:\\s|$)"),
        )
        for path in sorted(WORKFLOWS.glob("*.yml")):
            source = path.read_text(encoding="utf-8")
            for pattern in forbidden:
                with self.subTest(workflow=path.name, pattern=pattern.pattern):
                    self.assertIsNone(pattern.search(source))

    def test_browser_workflows_pin_playwright_and_python_pip(self):
        browser_workflows = (
            "atlasquant-ui-smoke.yml",
            "mobile-dom-stability.yml",
            "production-browser-smoke.yml",
            "production-build-identity.yml",
        )
        for name in browser_workflows:
            source = (WORKFLOWS / name).read_text(encoding="utf-8")
            with self.subTest(workflow=name):
                self.assertIn("pip==26.2.1", source)
                self.assertIn("playwright==1.63.0", source)
                self.assertIn("python -m playwright install", source)

    def test_security_gate_keeps_pinned_audit_tooling_and_retained_sbom(self):
        source = (WORKFLOWS / "aion-core-security-gate.yml").read_text(
            encoding="utf-8"
        )
        expected_artifact = "aion-sbom-" + "$" + "{{ github.sha }}"
        for token in (
            "pip==26.2.1",
            "pip-audit==2.10.1",
            "bandit==1.9.4",
            "cyclonedx-bom==7.4.0",
            "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
            expected_artifact,
            "retention-days: 30",
        ):
            self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main()
