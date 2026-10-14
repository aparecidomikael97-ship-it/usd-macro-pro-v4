"""A69: fail closed for mutable checkpoint bootstrap/migration workflows.

Only reads YAML sources; never requests the GitHub API or executes jobs.
This is temporary NO-GO containment, not proof of independent F1/T1 witness.
"""
import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent
BOOTSTRAP = ROOT / ".github/workflows/aion-runtime-checkpoint-bootstrap.yml"
MIGRATE = ROOT / ".github/workflows/aion-runtime-checkpoint-migrate.yml"


def header(path, name):
    source = path.read_text(encoding="utf-8")
    match = re.search(
        r"(?ms)^jobs:\s*\n  " + re.escape(name) +
        r":\s*\n(?P<body>(?:^    (?!steps:)[^\n]*\n|^\s{6,}[^\n]*\n|^\s*\n)*)",
        source,
    )
    if not match:
        raise AssertionError("A69_CHECKPOINT_WRITER_JOB_HEADER_MISSING")
    return match.group("body")


class CheckpointWriterHardStopA69Tests(unittest.TestCase):
    def test_01_bootstrap_entire_job_has_unconditional_pre_runner_deny(self):
        block = header(BOOTSTRAP, "bootstrap")
        self.assertRegex(block, r"(?m)^    if: \$\{\{ false \}\}\s*$")
        self.assertLess(block.index("if: ${{ false }}"), block.index("runs-on:"))
        self.assertNotIn("vars.", block)
        self.assertNotIn("inputs.", block)
        self.assertNotIn("github.actor", block)

    def test_02_migration_entire_job_has_unconditional_pre_runner_deny(self):
        block = header(MIGRATE, "migrate")
        self.assertRegex(block, r"(?m)^    if: \$\{\{ false \}\}\s*$")
        self.assertLess(block.index("if: ${{ false }}"), block.index("runs-on:"))
        self.assertNotIn("vars.", block)
        self.assertNotIn("inputs.", block)
        self.assertNotIn("github.actor", block)

    def test_03_manual_dispatch_cannot_enable_bootstrap(self):
        source = BOOTSTRAP.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", source)
        self.assertIn("contents: write", source)  # Existing recovery contract.
        self.assertIn("branch='atlasquant-runtime'", source)
        self.assertIn("if: ${{ false }}", header(BOOTSTRAP, "bootstrap"))

    def test_04_push_trigger_cannot_enable_migration(self):
        source = MIGRATE.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", source)
        self.assertIn("\n  push:", source)
        self.assertIn("contents: write", source)
        self.assertIn("if: ${{ false }}", header(MIGRATE, "migrate"))

    def test_05_migration_sha_guard_preserved_but_is_not_independent_witness(self):
        source = MIGRATE.read_text(encoding="utf-8")
        self.assertIn('CURRENT_SHA="$(cat /tmp/runtime_sha.txt)"', source)
        self.assertIn('-f sha="$CURRENT_SHA"', source)
        self.assertIn("Read back and verify migration", source)
        self.assertIn("if: ${{ false }}", header(MIGRATE, "migrate"))

    def test_06_bootstrap_existing_state_still_never_overwritten(self):
        source = BOOTSTRAP.read_text(encoding="utf-8")
        existing = source.split('if gh api "$API_PATH?ref=atlasquant-runtime"', 1)[1].split("else\n            CONTENT=", 1)[0]
        self.assertNotIn("gh api --method PUT", existing)
        self.assertIn("migration workflow", existing)
        self.assertIn("if: ${{ false }}", header(BOOTSTRAP, "bootstrap"))


if __name__ == "__main__":
    unittest.main()
