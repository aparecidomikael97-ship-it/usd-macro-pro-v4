"""Execute a selected original Quality workflow run block without modification.

Offline/local CI helper: no credential reads, GitHub API writes, app deploys,
Worker activation, or production behavior. The authoritative test lists and
their order stay in .github/workflows/quality-tests.yml.
"""
from __future__ import annotations

import re
import subprocess
import sys
import textwrap
from pathlib import Path


def _official_step(name: str, workflow_text: str) -> str:
    marker = "      - name: " + name + "\n        run: |\n"
    if workflow_text.count(marker) != 1:
        raise ValueError("Quality step is missing or ambiguous: " + name)
    start = workflow_text.index(marker) + len(marker)
    stop = workflow_text.find("\n      - name:", start)
    if stop == -1:
        stop = len(workflow_text)
    raw = workflow_text[start:stop].strip("\n")
    if not raw:
        raise ValueError("Empty official Quality block")
    script = textwrap.dedent(raw) + "\n"
    if not script.strip().startswith("python "):
        raise ValueError("Unexpected official Quality block start")
    return script


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    root = Path(__file__).resolve().parents[2]
    src = (root / ".github" / "workflows" / "quality-tests.yml").read_text(
        encoding="utf-8"
    )
    listed = set(re.findall(
        r"(?m)^\s+(test_[A-Za-z0-9_]+\.py)\s*\\?$", src
    ))
    discovered = {f.name for f in root.glob("test_*.py")}
    missing = sorted(discovered - listed)
    print(
        f"OFFICIAL_QUALITY_DISCOVERED={len(discovered)} "
        f"LISTED={len(listed)} MISSING={len(missing)}", flush=True
    )
    if missing or not discovered:
        print("MISSING_ROOT_QUALITY_MODULES:", missing, flush=True)
        return 2
    script = _official_step(sys.argv[1], src)
    print("OFFICIAL_QUALITY_STEP=", sys.argv[1], flush=True)
    # bash -e and pipefail avoid losing unittest or browser failures. No test
    # names, skip marks, or assertions are modified by this helper.
    return subprocess.call(["bash", "-e", "-o", "pipefail", "-c", script], cwd=root)


if __name__ == "__main__":
    raise SystemExit(main())
