import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_expansion_cycle_audit_ledger import (
    append_verified_expansion_cycle,
    audit_expansion_cycle_ledger,
    expansion_cycle_ledger_template,
)


def _genesis(scope="pilot", tenants=None):
    if tenants is None:
        tenants = ["tenant-001"]
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_SCOPE_EXPANSION_BOUNDARY_PACKET_V1",
        "state": "EXPLICIT_EXPANSION_DECISION_REQUIRED",
        "activation_verification_digest": "9" * 64,
        "current_scope": scope,
        "current_tenant_ids": tenants,
        "generic_confirmation_is_authorization": False,
        "automatic_expansion_allowed": False,
        "scope_expansion_authorized": False,
        "expansion_execution_authorized": False,
        "client_actions_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def _verification(
    digest_char="a",
    auth_char="b",
    previous_scope="pilot",
    previous_tenants=None,
    verified_scope="pilot",
    verified_tenants=None,
):
    if previous_tenants is None:
        previous_tenants = ["tenant-001"]
    if verified_tenants is None:
        verified_tenants = ["tenant-001", "tenant-002"]
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_POST_EXPANSION_CYCLE_FREEZE_V1",
        "version": "1",
        "state": "SCOPE_EXPANSION_VERIFIED_AND_FROZEN",
        "authorization_digest": digest_char.replace(digest_char, auth_char) * 64,
        "previous_scope": previous_scope,
        "previous_tenant_ids": previous_tenants,
        "verified_scope": verified_scope,
        "verified_tenant_ids": verified_tenants,
        "expansion_verification_digest": digest_char * 64,
        "scope_expansion_verified": True,
        "scope_frozen": True,
        "automatic_expansion_allowed": False,
        "scope_expansion_authorized": False,
        "expansion_execution_authorized": False,
        "client_actions_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


class BusinessExpansionCycleAuditLedgerTests(unittest.TestCase):
    def test_unbound_genesis_is_integrity_valid_but_not_appendable(self):
        ledger = expansion_cycle_ledger_template()
        audit = audit_expansion_cycle_ledger(ledger)
        self.assertTrue(audit["integrity_verified"])
        self.assertFalse(audit["genesis_bound"])
        result = append_verified_expansion_cycle(ledger, _verification())
        self.assertEqual(result["state"], "EXPANSION_CYCLE_APPEND_BLOCKED")
        self.assertIn("genesis_boundary_required", result["blockers"])

    def test_first_cycle_must_match_genesis_boundary(self):
        ledger = expansion_cycle_ledger_template(_genesis())
        verification = _verification(
            previous_scope="pilot",
            previous_tenants=["tenant-999"],
            verified_scope="pilot",
            verified_tenants=["tenant-999", "tenant-1000"],
        )
        result = append_verified_expansion_cycle(ledger, verification)
        self.assertEqual(result["state"], "EXPANSION_CYCLE_APPEND_BLOCKED")
        self.assertIn("genesis_tenant_mismatch", result["blockers"])

    def test_empty_template_is_integrity_valid(self):
        ledger = expansion_cycle_ledger_template(_genesis())
        audit = audit_expansion_cycle_ledger(ledger)
        self.assertTrue(audit["integrity_verified"])
        self.assertEqual(audit["entry_count"], 0)
        self.assertFalse(audit["automatic_expansion_allowed"])
        self.assertFalse(audit["executes_action"])

    def test_first_verified_cycle_is_recorded(self):
        result = append_verified_expansion_cycle(
            expansion_cycle_ledger_template(_genesis()),
            _verification(),
        )
        self.assertEqual(result["state"], "VERIFIED_EXPANSION_CYCLE_RECORDED")
        ledger = result["ledger"]
        self.assertEqual(ledger["entry_count"], 1)
        self.assertEqual(len(ledger["ledger_digest"]), 64)
        self.assertEqual(ledger["entries"][0]["sequence"], 1)
        self.assertFalse(result["automatic_expansion_allowed"])
        self.assertFalse(result["scope_expansion_authorized"])

    def test_second_cycle_requires_exact_continuity(self):
        first = append_verified_expansion_cycle(
            expansion_cycle_ledger_template(_genesis()),
            _verification(),
        )["ledger"]
        second_verification = _verification(
            digest_char="c",
            auth_char="d",
            previous_scope="pilot",
            previous_tenants=["tenant-001", "tenant-002"],
            verified_scope="bounded_production",
            verified_tenants=["tenant-001", "tenant-002"],
        )
        second = append_verified_expansion_cycle(first, second_verification)
        self.assertEqual(second["state"], "VERIFIED_EXPANSION_CYCLE_RECORDED")
        self.assertEqual(second["ledger"]["entry_count"], 2)
        self.assertTrue(
            audit_expansion_cycle_ledger(second["ledger"])["integrity_verified"]
        )

    def test_replay_is_blocked(self):
        verification = _verification()
        first = append_verified_expansion_cycle(
            expansion_cycle_ledger_template(_genesis()),
            verification,
        )["ledger"]
        replay = append_verified_expansion_cycle(first, verification)
        self.assertEqual(replay["state"], "EXPANSION_CYCLE_APPEND_BLOCKED")
        self.assertIn("verification_replay", replay["blockers"])

    def test_history_drift_is_blocked(self):
        first = append_verified_expansion_cycle(
            expansion_cycle_ledger_template(_genesis()),
            _verification(),
        )["ledger"]
        drift = _verification(
            digest_char="c",
            auth_char="d",
            previous_scope="pilot",
            previous_tenants=["tenant-999"],
            verified_scope="pilot",
            verified_tenants=["tenant-999", "tenant-1000"],
        )
        result = append_verified_expansion_cycle(first, drift)
        self.assertEqual(result["state"], "EXPANSION_CYCLE_APPEND_BLOCKED")
        self.assertIn("tenant_continuity_broken", result["blockers"])

    def test_tenant_removal_or_no_growth_is_invalid(self):
        bad = _verification(
            previous_tenants=["tenant-001", "tenant-002"],
            verified_tenants=["tenant-001"],
        )
        result = append_verified_expansion_cycle(
            expansion_cycle_ledger_template(_genesis()),
            bad,
        )
        self.assertEqual(result["state"], "EXPANSION_CYCLE_APPEND_BLOCKED")
        self.assertIn("verification_invalid", result["blockers"])

    def test_corrupted_entry_digest_blocks_ledger(self):
        ledger = append_verified_expansion_cycle(
            expansion_cycle_ledger_template(_genesis()),
            _verification(),
        )["ledger"]
        ledger["entries"][0]["entry_digest"] = "0" * 64
        audit = audit_expansion_cycle_ledger(ledger)
        self.assertFalse(audit["integrity_verified"])
        self.assertIn("entry_1_digest_mismatch", audit["blockers"])

    def test_generic_operational_flags_can_never_be_true(self):
        ledger = expansion_cycle_ledger_template(_genesis())
        ledger["automatic_expansion_allowed"] = True
        audit = audit_expansion_cycle_ledger(ledger)
        self.assertFalse(audit["integrity_verified"])
        self.assertIn(
            "automatic_expansion_allowed_must_be_false",
            audit["blockers"],
        )

    def test_admin_exposes_twentieth_view(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("20 · Ledger auditável de ciclos de expansão", source)
        self.assertIn("business_expansion_cycle_ledger_template", source)

    def test_module_has_no_network_git_process_or_runtime_executor(self):
        source = Path(
            "atlasquant_aion_business_expansion_cycle_audit_ledger.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for banned in (
            "requests",
            "urllib",
            "httpx",
            "socket",
            "subprocess",
            "github",
            "paramiko",
            "docker",
            "kubernetes",
        ):
            self.assertNotIn(banned, imported)


if __name__ == "__main__":
    unittest.main()
