"""Architectural import boundary for the pure AION core.

The pure core is an explicit allowlist of contract modules. This test does
not claim that every atlasquant_aion_*.py file is independent. Known couplings
are frozen so a new domain import fails until the inventory is updated.
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PURE_CORE = (
    "atlasquant_aion_core",
    "atlasquant_aion_fortress",
    "atlasquant_aion_resilience",
    "atlasquant_aion_durable_tasks",
    "atlasquant_aion_critical_review",
    "atlasquant_aion_memory_quarantine",
    "atlasquant_aion_memory_layers",
    "atlasquant_aion_tenant",
    "atlasquant_aion_knowledge_graph",
    "atlasquant_aion_vault",
    "atlasquant_aion_observability",
    "atlasquant_aion_evaluation_lab",
    "atlasquant_aion_model_router",
    "atlasquant_aion_model_registry",
    "atlasquant_aion_loop_governor",
)
FORBIDDEN_ROOTS = frozenset({
    "streamlit",
    "requests",
    "httpx",
    "openai",
    "atlasquant_aion_business",
    "atlasquant_home_radar",
    "atlasquant_radar_board",
    "atlasquant_investment_ecosystem",
    "atlasquant_investment_panel",
    "atlasquant_brokers_guide",
    "atlasquant_tradingview_parity",
    "atlasquant_post_trade_diagnosis",
    "paper_trading_v112",
})
# Direct imports observed on 2026-09-29. This is debt, not an approval to add more.
KNOWN_AION_COUPLINGS = frozenset({
    ("atlasquant_aion_admin.py", "streamlit"),
    ("atlasquant_aion_admin.py", "atlasquant_aion_business"),
    ("atlasquant_aion_global_worker.py", "requests"),
    ("atlasquant_aion_global_worker_activation.py", "requests"),
    ("atlasquant_aion_global_worker_persisted_arming.py", "requests"),
    ("atlasquant_aion_global_worker_readiness.py", "requests"),
    ("atlasquant_aion_memory.py", "atlasquant_aion_business"),
    ("atlasquant_aion_provider.py", "requests"),
    ("atlasquant_aion_replay_panel.py", "streamlit"),
})


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
    return found


def _local_edges() -> dict[str, set[str]]:
    edges: dict[str, set[str]] = {}
    for path in ROOT.glob("atlasquant_*.py"):
        edges[path.stem] = set()
        for mod in _imports(path):
            root = mod.split(".", 1)[0]
            if root.startswith("atlasquant") or root in FORBIDDEN_ROOTS:
                edges[path.stem].add(root)
    return edges


def _closure(start: str, edges: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    stack = [start]
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        for child in edges.get(name, ()):
            if child.startswith("atlasquant"):
                stack.append(child)
    return seen


class AtlasQuantAionCoreIndependenceTests(unittest.TestCase):
    def test_pure_core_closure_does_not_import_domain_ui_or_network(self):
        edges = _local_edges()
        for module in PURE_CORE:
            with self.subTest(module=module):
                self.assertTrue((ROOT / f"{module}.py").is_file(), module)
                closure = _closure(module, edges)
                forbidden = sorted(closure & FORBIDDEN_ROOTS)
                self.assertEqual(forbidden, [], module)

    def test_known_domain_couplings_stay_explicit(self):
        observed = set()
        for path in sorted(ROOT.glob("atlasquant_aion*.py")):
            for mod in _imports(path):
                root = mod.split(".", 1)[0]
                if root in FORBIDDEN_ROOTS:
                    observed.add((path.name, root))
        self.assertEqual(observed, set(KNOWN_AION_COUPLINGS))

    def test_pure_core_imports_without_optional_runtime(self):
        blocker = (
            "import sys\n"
            "blocked=set(%r)\n"
            "class Finder:\n"
            "    def find_spec(self, name, path, target=None):\n"
            "        root=name.split('.',1)[0]\n"
            "        if root in blocked:\n"
            "            raise ImportError('pure core blocked '+name)\n"
            "sys.meta_path.insert(0, Finder())\n"
            "import importlib\n"
            "for name in %r:\n"
            "    importlib.import_module(name)\n"
            "print('IMPORTED')\n"
        ) % (sorted(FORBIDDEN_ROOTS), list(PURE_CORE))
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(ROOT),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
        }
        result = subprocess.run(
            [sys.executable, "-c", blocker],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:] + result.stdout[-500:])
        self.assertIn("IMPORTED", result.stdout)
        self.assertNotIn("blocked", result.stderr)

    def test_memory_and_recovery_operate_empty_without_business(self):
        blocker = (
            "import sys\n"
            "class Finder:\n"
            "    def find_spec(self, name, path, target=None):\n"
            "        if name.split('.',1)[0]=='atlasquant_aion_business':\n"
            "            raise ImportError('business absent')\n"
            "sys.meta_path.insert(0, Finder())\n"
            "import atlasquant_aion_memory as memory\n"
            "import atlasquant_aion_recovery\n"
            "checkpoint=memory.default_checkpoint()\n"
            "normalized=memory.ensure_operating_checkpoint(checkpoint)\n"
            "assert normalized['business']['products']==[]\n"
            "report=memory.checkpoint_integrity_report(normalized)\n"
            "assert report['state']=='CONFIRMED', report\n"
            "assert report['write_safe'] is True\n"
            "tampered=memory.default_checkpoint()\n"
            "tampered['business']['metrics']['revenue']=1\n"
            "blocked=memory.checkpoint_integrity_report(tampered)\n"
            "assert blocked['state']=='UNKNOWN', blocked\n"
            "assert blocked['write_safe'] is False\n"
            "assert 'business.metrics' in blocked['unavailable_items']\n"
            "try:\n"
            "    memory.ensure_operating_checkpoint(tampered)\n"
            "except memory.BusinessAdapterUnavailableError:\n"
            "    pass\n"
            "else:\n"
            "    raise AssertionError('non-empty business data must fail closed')\n"
            "print('OPERATIONAL')\n"
        )
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(ROOT),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
        }
        result = subprocess.run(
            [sys.executable, "-c", blocker],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:] + result.stdout[-500:])
        self.assertIn("OPERATIONAL", result.stdout)


    def test_memory_and_recovery_operate_empty_without_studio_or_promotions(self):
        blocker = (
            "import sys\n"
            "blocked={'atlasquant_aion_studio','atlasquant_aion_promotions'}\n"
            "class Finder:\n"
            "    def find_spec(self, name, path, target=None):\n"
            "        if name.split('.',1)[0] in blocked:\n"
            "            raise ImportError('optional product absent '+name)\n"
            "sys.meta_path.insert(0, Finder())\n"
            "import atlasquant_aion_memory as memory\n"
            "import atlasquant_aion_recovery\n"
            "checkpoint=memory.default_checkpoint()\n"
            "normalized=memory.ensure_operating_checkpoint(checkpoint)\n"
            "assert normalized['studio']['projects']==[]\n"
            "assert normalized['promotions']['campaigns']==[]\n"
            "assert normalized['promotions']['redemptions']==[]\n"
            "report=memory.checkpoint_integrity_report(normalized)\n"
            "assert report['state']=='CONFIRMED', report\n"
            "assert report['write_safe'] is True\n"
            "studio_cp=memory.default_checkpoint()\n"
            "studio_cp['studio']['projects']=[{'content_id':'foreign-project'}]\n"
            "studio_report=memory.checkpoint_integrity_report(studio_cp)\n"
            "assert studio_report['state']=='UNKNOWN', studio_report\n"
            "assert studio_report['write_safe'] is False\n"
            "assert 'studio' in studio_report['unavailable_items']\n"
            "promo_cp=memory.default_checkpoint()\n"
            "promo_cp['promotions']['redemptions']=[{'redemption_id':'R-1'}]\n"
            "promo_report=memory.checkpoint_integrity_report(promo_cp)\n"
            "assert promo_report['state']=='UNKNOWN', promo_report\n"
            "assert promo_report['write_safe'] is False\n"
            "assert 'promotions' in promo_report['unavailable_items']\n"
            "try:\n"
            "    memory.ensure_operating_checkpoint(studio_cp)\n"
            "except memory.OptionalProductAdapterUnavailableError:\n"
            "    pass\n"
            "else:\n"
            "    raise AssertionError('non-empty Studio data must fail closed')\n"
            "try:\n"
            "    memory.ensure_operating_checkpoint(promo_cp)\n"
            "except memory.OptionalProductAdapterUnavailableError:\n"
            "    pass\n"
            "else:\n"
            "    raise AssertionError('non-empty Promotions data must fail closed')\n"
            "print('OPERATIONAL')\n"
        )
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(ROOT),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
        }
        result = subprocess.run(
            [sys.executable, "-c", blocker],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            result.stderr[-2000:] + result.stdout[-500:],
        )
        self.assertIn("OPERATIONAL", result.stdout)

    def test_memory_and_recovery_import_without_requests(self):
        blocker = (
            "import sys\n"
            "class Finder:\n"
            "    def find_spec(self, name, path, target=None):\n"
            "        if name.split('.',1)[0]=='requests':\n"
            "            raise ImportError('requests absent')\n"
            "sys.meta_path.insert(0, Finder())\n"
            "import atlasquant_aion_memory\n"
            "import atlasquant_aion_recovery\n"
            "print('IMPORTED')\n"
        )
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(ROOT),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
        }
        result = subprocess.run(
            [sys.executable, "-c", blocker],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:] + result.stdout[-500:])
        self.assertIn("IMPORTED", result.stdout)



    def test_specialist_contracts_import_without_business_or_investments(self):
        blocker = (
            "import sys\n"
            "blocked={'atlasquant_aion_business','atlasquant_investment_ecosystem'}\n"
            "class Finder:\n"
            "    def find_spec(self, name, path, target=None):\n"
            "        if name.split('.',1)[0] in blocked:\n"
            "            raise ImportError('domain absent '+name)\n"
            "sys.meta_path.insert(0, Finder())\n"
            "import atlasquant_aion_approval_inbox\n"
            "import atlasquant_aion_specialist_evidence\n"
            "import atlasquant_aion_specialist_session\n"
            "print('IMPORTED')\n"
        )
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(ROOT),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
        }
        result = subprocess.run(
            [sys.executable, "-c", blocker],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:] + result.stdout[-500:])
        self.assertIn("IMPORTED", result.stdout)


if __name__ == "__main__":
    unittest.main()
