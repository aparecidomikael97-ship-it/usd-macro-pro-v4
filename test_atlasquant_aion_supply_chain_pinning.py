import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
WORKFLOWS = ROOT / ".github" / "workflows"
ACTION_SHA = re.compile(r"^.+@[0-9a-f]{40}$", re.I)


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
                self.assertIn("==", row)
                name, version = row.split("==", 1)
                self.assertTrue(name.strip())
                self.assertTrue(version.strip())
                self.assertNotIn(">=", row)
                self.assertNotIn("<=", row)
                self.assertNotIn("~=", row)
                self.assertFalse(any(ch.isspace() for ch in row))

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
                    self.assertRegex(value, ACTION_SHA)

    def test_python_workflows_do_not_reintroduce_loose_installs(self):
        violations = []
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                command = line.strip()
                if re.search(
                    r"\b(?:python -m )?pip install (?:--upgrade|-U) pip\b",
                    command,
                ):
                    violations.append(
                        f"{path.name}:{line_number}:pip-upgrade"
                    )
                    continue
                install = re.search(
                    r"\b(?:python -m )?pip install\s+(.+?)(?:;|$)",
                    command,
                )
                if not install:
                    continue
                args = install.group(1).strip()
                if re.search(
                    r"(?:^|\s)-r\s+requirements[^\s]*",
                    args,
                ):
                    continue
                tokens = [
                    token
                    for token in args.split()
                    if not token.startswith("-")
                ]
                if any("==" not in token for token in tokens):
                    violations.append(
                        f"{path.name}:{line_number}:unpinned:{args}"
                    )
        self.assertEqual(
            violations,
            [],
            f"Unpinned Python workflow installs: {violations}",
        )

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

    def test_security_gate_commands_preserve_shell_continuations_and_residual_tests(self):
        source = (WORKFLOWS / "aion-core-security-gate.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "test_atlasquant_aion_critical_review.py \\\n"
            "            test_atlasquant_aion_resource_bounds_residual.py \\\n"
            "            test_atlasquant_aion_supply_chain_pinning.py",
            source,
        )
        self.assertIn(
            "test_atlasquant_aion_durable_tasks.py \\\n"
            "            test_atlasquant_aion_resource_bounds_residual.py \\\n"
            "            test_atlasquant_aion_supply_chain_pinning.py",
            source,
        )

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
