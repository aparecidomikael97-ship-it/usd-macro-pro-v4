import ast
import unittest
from datetime import datetime, timezone
from pathlib import Path

from atlasquant_aion_business_privacy_audit import (
    access_decision,
    audit_event,
    automation_version,
    consent_record,
    data_subject_request,
    governance_snapshot,
    privacy_profile,
    retention_review,
    role_access_matrix,
    rollback_plan,
)

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


class BusinessPrivacyAuditGovernanceTests(unittest.TestCase):
    def _profile(self):
        return privacy_profile(
            client_name="Clínica Demo",
            purposes=["Atendimento", "Qualificação de leads"],
            data_categories=["CONTACT", "LEAD", "SUPPORT"],
            legal_basis_label="Base jurídica a validar com responsável",
            retention_days=90,
            controller_contact="responsavel@demo.local",
        )

    def test_profile_is_demo_only_and_requires_purpose_retention_and_categories(self):
        row = self._profile()
        self.assertEqual(row["state"], "PROFILE_READY")
        self.assertEqual(row["retention_days"], 90)
        self.assertFalse(row["real_personal_data_present"])
        self.assertFalse(row["legal_conclusion"])
        self.assertFalse(row["executes_action"])
        bad = privacy_profile(
            client_name="", purposes=[], data_categories=[], legal_basis_label="", retention_days=0
        )
        self.assertEqual(bad["state"], "INCOMPLETE")

    def test_consent_requires_exact_boolean_and_timestamp(self):
        granted = consent_record(
            subject_reference="subject-demo-1",
            purpose="Atendimento",
            granted=True,
            recorded_at="2026-09-30T10:00:00Z",
            source="form-demo",
        )
        self.assertEqual(granted["state"], "GRANTED")
        self.assertTrue(granted["consent_digest"])
        self.assertFalse(granted["real_subject_verified"])
        invalid = consent_record(
            subject_reference="subject-demo-1",
            purpose="Atendimento",
            granted="true",
            recorded_at="2026-09-30T10:00:00Z",
            source="form-demo",
        )
        self.assertEqual(invalid["state"], "INCOMPLETE")

    def test_access_is_default_deny_and_write_is_tighter_than_read(self):
        matrix = role_access_matrix(self._profile())
        read = access_decision(matrix, role="CLIENT_OPERATOR", category="CONTACT", requested_action="READ")
        self.assertTrue(read["allowed"])
        write = access_decision(matrix, role="CLIENT_OPERATOR", category="CONTACT", requested_action="WRITE")
        self.assertFalse(write["allowed"])
        admin_write = access_decision(matrix, role="CLIENT_ADMIN", category="CONTACT", requested_action="WRITE")
        self.assertTrue(admin_write["allowed"])
        unknown = access_decision(matrix, role="UNKNOWN", category="CONTACT", requested_action="READ")
        self.assertFalse(unknown["allowed"])
        self.assertEqual(unknown["reason"], "DEFAULT_DENY")
        self.assertFalse(unknown["external_write_executed"])

    def test_retention_review_never_deletes(self):
        row = retention_review(
            self._profile(),
            created_at="2026-06-01T00:00:00Z",
            now=NOW,
        )
        self.assertEqual(row["state"], "RETENTION_REVIEW_DUE")
        self.assertTrue(row["deletion_review_required"])
        self.assertFalse(row["deletion_executed"])
        self.assertFalse(row["executes_action"])

    def test_subject_request_is_review_only(self):
        req = data_subject_request(
            request_type="DELETE",
            subject_reference="subject-demo-1",
            requested_at="2026-09-30T10:00:00Z",
            reason="Teste",
        )
        self.assertEqual(req["state"], "REVIEW_REQUIRED")
        self.assertFalse(req["identity_verified"])
        self.assertFalse(req["human_approval_recorded"])
        self.assertFalse(req["deletion_executed"])
        self.assertFalse(req["export_executed"])
        self.assertFalse(req["executes_action"])

    def test_audit_event_records_digests_but_never_authorizes_action(self):
        event = audit_event(
            actor="Mikael",
            action="CONFIG_CHANGE",
            target="Automação Demo",
            approval_reference="approval-demo",
            before={"enabled": False},
            after={"enabled": True},
            timestamp="2026-09-30T11:00:00Z",
        )
        self.assertEqual(event["state"], "RECORDED_DEMO")
        self.assertTrue(event["before_digest"])
        self.assertTrue(event["after_digest"])
        self.assertTrue(event["event_digest"])
        self.assertTrue(event["immutable_demo_record"])
        self.assertFalse(event["authorizes_action"])
        self.assertFalse(event["external_write"])

    def test_versioning_and_rollback_are_preparation_only(self):
        v1 = automation_version(
            automation_name="followup-demo",
            version="1",
            config={"cadence": "manual-review"},
            approved_by="Mikael",
        )
        v2 = automation_version(
            automation_name="followup-demo",
            version="2",
            config={"cadence": "draft-only"},
            approved_by="Mikael",
        )
        plan = rollback_plan(v2, v1)
        self.assertEqual(plan["state"], "ROLLBACK_READY_DEMO")
        self.assertEqual(plan["from_version"], "2")
        self.assertEqual(plan["to_version"], "1")
        self.assertTrue(plan["human_approval_required"])
        self.assertFalse(plan["rollback_executed"])
        self.assertFalse(plan["production_write"])
        self.assertFalse(plan["executes_action"])

    def test_governance_snapshot_never_claims_real_operations(self):
        profile = self._profile()
        event = audit_event(
            actor="Mikael",
            action="VIEW",
            target="Portal Demo",
        )
        snap = governance_snapshot(profile, [event])
        self.assertEqual(snap["state"], "DEMO_READY")
        self.assertTrue(snap["privacy_profile_ready"])
        self.assertEqual(snap["audit_event_count"], 1)
        self.assertFalse(snap["real_personal_data_present"])
        self.assertEqual(snap["exports_executed"], 0)
        self.assertEqual(snap["deletions_executed"], 0)
        self.assertEqual(snap["production_rollbacks_executed"], 0)
        self.assertFalse(snap["runtime_activated"])

    def test_module_has_no_external_io_provider_or_ui_imports(self):
        source = Path("atlasquant_aion_business_privacy_audit.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for banned in ("requests", "urllib", "httpx", "socket", "subprocess", "openai", "streamlit"):
            self.assertNotIn(banned, imported)


if __name__ == "__main__":
    unittest.main()
