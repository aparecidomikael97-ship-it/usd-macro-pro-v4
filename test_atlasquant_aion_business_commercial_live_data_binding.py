import ast
import unittest
from datetime import datetime, timezone
from pathlib import Path

from atlasquant_aion_business_commercial_live_data_binding import (
    live_binding_policy,
    live_binding_review_packet,
    normalize_commercial_snapshot,
    observed_pipeline_state,
    source_attestation,
)


NOW = datetime(2026, 9, 30, 18, 0, tzinfo=timezone.utc)


def _attestation(source="CRM"):
    return source_attestation(
        integration=source,
        connection_ref=f"connector://{source.lower()}-readonly",
        authentication_verified=True,
        read_only_scope_verified=True,
        write_scope_present=False,
        credential_value_present=False,
        observed_at="2026-09-30T17:50:00+00:00",
    )


def _snapshot():
    return normalize_commercial_snapshot(
        [
            {
                "source": "CRM",
                "record_ref": "lead-001",
                "subject_ref": "company-ref-001",
                "source_ref": "crm://lead-001",
                "stage": "QUALIFICATION",
                "contact_permission_state": "OPT_IN",
                "observed_at": "2026-09-30T17:45:00+00:00",
                "estimated_value_brl": 800.0,
                "source_confidence_pct": 95,
            },
            {
                "source": "FORMS",
                "record_ref": "form-001",
                "subject_ref": "company-ref-002",
                "source_ref": "forms://submission-001",
                "stage": "DIAGNOSTIC",
                "contact_permission_state": "PERMITTED",
                "observed_at": "2026-09-30T17:40:00+00:00",
                "estimated_value_brl": 1200.0,
                "source_confidence_pct": 90,
            },
        ],
        tenant_id="tenant-demo",
        source_attestations=[_attestation("CRM"), _attestation("FORMS")],
        now=NOW,
        max_age_hours=24,
    )


class BusinessCommercialLiveDataBindingTests(unittest.TestCase):
    def test_policy_is_read_only_and_privacy_bounded(self):
        row = live_binding_policy()
        self.assertFalse(row["raw_personal_contact_fields_allowed"])
        self.assertFalse(row["raw_credentials_allowed"])
        self.assertFalse(row["external_write_allowed"])
        self.assertFalse(row["pipeline_auto_advance"])

    def test_source_attestation_requires_read_only_scope(self):
        row = _attestation("CRM")
        self.assertEqual(row["state"], "SOURCE_ATTESTATION_READY")
        self.assertFalse(row["write_scope_present"])
        self.assertFalse(row["credential_value_present"])
        self.assertFalse(row["executes_action"])

        bad = source_attestation(
            integration="CRM",
            connection_ref="connector://crm",
            authentication_verified=True,
            read_only_scope_verified=True,
            write_scope_present=True,
            credential_value_present=False,
            observed_at="2026-09-30T17:50:00+00:00",
        )
        self.assertEqual(bad["state"], "SOURCE_ATTESTATION_BLOCKED")

    def test_verified_snapshot_normalizes_multiple_sources(self):
        row = _snapshot()
        self.assertEqual(row["state"], "COMMERCIAL_LIVE_SNAPSHOT_READY")
        self.assertEqual(row["record_count"], 2)
        self.assertEqual(row["source_count"], 2)
        self.assertEqual(
            row["truth_state"],
            "EXTERNALLY_ATTESTED_READ_ONLY_INPUT",
        )
        self.assertFalse(row["external_write_authorized"])

    def test_raw_personal_contact_fields_are_rejected(self):
        row = normalize_commercial_snapshot(
            [{
                "source": "CRM",
                "record_ref": "lead-001",
                "subject_ref": "company-ref-001",
                "source_ref": "crm://lead-001",
                "stage": "QUALIFICATION",
                "contact_permission_state": "OPT_IN",
                "observed_at": "2026-09-30T17:45:00+00:00",
                "email": "person@example.com",
            }],
            tenant_id="tenant-demo",
            source_attestations=[_attestation("CRM")],
            now=NOW,
        )
        self.assertEqual(row["state"], "COMMERCIAL_LIVE_SNAPSHOT_BLOCKED")
        self.assertTrue(any("raw_sensitive_fields_forbidden" in x for x in row["blockers"]))

    def test_stale_record_blocks_snapshot(self):
        row = normalize_commercial_snapshot(
            [{
                "source": "CRM",
                "record_ref": "lead-001",
                "subject_ref": "company-ref-001",
                "source_ref": "crm://lead-001",
                "stage": "QUALIFICATION",
                "contact_permission_state": "OPT_IN",
                "observed_at": "2026-09-20T10:00:00+00:00",
            }],
            tenant_id="tenant-demo",
            source_attestations=[_attestation("CRM")],
            now=NOW,
            max_age_hours=24,
        )
        self.assertEqual(row["state"], "COMMERCIAL_LIVE_SNAPSHOT_BLOCKED")
        self.assertTrue(any(x.endswith("_stale") for x in row["blockers"]))

    def test_duplicate_external_record_blocks_snapshot(self):
        record = {
            "source": "CRM",
            "record_ref": "lead-001",
            "subject_ref": "company-ref-001",
            "source_ref": "crm://lead-001",
            "stage": "QUALIFICATION",
            "contact_permission_state": "OPT_IN",
            "observed_at": "2026-09-30T17:45:00+00:00",
        }
        row = normalize_commercial_snapshot(
            [record, dict(record)],
            tenant_id="tenant-demo",
            source_attestations=[_attestation("CRM")],
            now=NOW,
        )
        self.assertEqual(row["state"], "COMMERCIAL_LIVE_SNAPSHOT_BLOCKED")
        self.assertTrue(any("duplicate_record" in x for x in row["blockers"]))

    def test_observed_pipeline_never_advances_or_contacts(self):
        row = observed_pipeline_state(_snapshot())
        self.assertEqual(row["state"], "OBSERVED_PIPELINE_READY")
        self.assertEqual(row["counts"]["QUALIFICATION"], 1)
        self.assertEqual(row["counts"]["DIAGNOSTIC"], 1)
        self.assertEqual(row["observed_estimated_value_brl"], 2000.0)
        self.assertFalse(row["value_is_forecast_or_guarantee"])
        self.assertFalse(row["pipeline_auto_advance"])
        self.assertFalse(row["contact_authorized"])

    def test_do_not_contact_is_observed_but_never_overridden(self):
        snap = normalize_commercial_snapshot(
            [{
                "source": "CRM",
                "record_ref": "lead-009",
                "subject_ref": "company-ref-009",
                "source_ref": "crm://lead-009",
                "stage": "TARGETING",
                "contact_permission_state": "DO_NOT_CONTACT",
                "observed_at": "2026-09-30T17:45:00+00:00",
            }],
            tenant_id="tenant-demo",
            source_attestations=[_attestation("CRM")],
            now=NOW,
        )
        observed = observed_pipeline_state(snap)
        self.assertEqual(observed["do_not_contact_count"], 1)
        self.assertFalse(observed["contact_authorized"])

    def test_review_packet_only_reaches_admin_review(self):
        snap = _snapshot()
        observed = observed_pipeline_state(snap)
        row = live_binding_review_packet(
            snap,
            observed,
            requested_by="mikael",
        )
        self.assertEqual(
            row["state"],
            "READY_FOR_ADMIN_LIVE_READ_BINDING_REVIEW",
        )
        self.assertFalse(row["real_connector_configuration_authorized"])
        self.assertFalse(row["pipeline_write_authorized"])
        self.assertFalse(row["contact_authorized"])
        self.assertFalse(row["billing_authorized"])
        self.assertFalse(row["runtime_authorized"])

    def test_admin_exposes_live_binding_view(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("31 · Pipeline Comercial · Dados Reais", source)
        self.assertIn("business_live_binding_policy", source)

    def test_module_has_no_network_or_executor_imports(self):
        source = Path(
            "atlasquant_aion_business_commercial_live_data_binding.py"
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
