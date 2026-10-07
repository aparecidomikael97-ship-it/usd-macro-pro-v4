from __future__ import annotations

from pathlib import Path

import atlasquant_aion_b2b_terminal_certificate_read_model_runtime_projection_offline_v1 as projection
import atlasquant_aion_b2b_terminal_certificate_read_model_ui_runtime_binding_offline_v1 as binding
from atlasquant_reference_ui import reference_html


def ready_projection():
    row = {
        "schema": projection.SCHEMA,
        "mode": projection.MODE,
        "contract_schema": projection.contract.SCHEMA,
        "schema_version": "1",
        "state": "VERIFIED",
        "certificate_status": "VERIFIED",
        "execution_id": "EXE-REFERENCE-TERMINAL-001",
        "error_code": "",
        "owner_id": "owner-reference",
        "tenant_id": "tenant-reference",
        "workspace_id": "workspace-reference",
        "final_execution_state": "FINALIZED_SUCCESS",
        "terminal_revision": 7,
        "certificate_manifest_digest": "reference-certificate-manifest",
        "certificate_digest": "reference-certificate-digest",
        "certificate_persistence_record_digest": "reference-certificate-persistence",
        "finalization_record_digest": "reference-finalization-digest",
        "audit_seal_manifest_digest": "reference-audit-seal-manifest",
        "audit_seal_persistence_record_digest": "reference-audit-seal-record",
        "terminal_evidence_set_digest": "reference-terminal-evidence",
        "finops_observation_digest": "reference-finops-observation",
        "observability_trace_id": "reference-trace-001",
        "pre_terminal_audit_chain_digest": "reference-pre-terminal-audit",
        "persisted_at": "2026-10-06T15:00:00Z",
        "observed_at": "2026-10-06T15:01:00Z",
        "age_seconds": 60,
        "max_age_seconds": 300,
        "digest_algorithm": "SHA256",
        "canonical_encoding": "UTF8_CANONICAL_JSON",
        "read_model_projection_is_evidence_not_authority": True,
        "next_allowed_step": projection.NEXT_ALLOWED_STEP,
    }
    row.update({key: False for key in projection.FALSE_FIELDS})
    return row


def ready_panel_view_model():
    return binding.build_terminal_certificate_panel_view_model_offline(
        read_model_projection=ready_projection(),
    )


def test_privacy_module_mounts_terminal_certificate_component_from_view_model():
    html = reference_html(
        "negocios",
        selected="privacy",
        terminal_certificate_panel_view_model=ready_panel_view_model(),
    )
    assert 'data-module="privacy"' in html
    assert 'data-terminal-certificate-reference="draft-only"' in html
    assert 'data-component="terminal-certificate-panel-offline-v1"' in html
    assert "reference-certificate-digest" in html
    assert "EXE-REFERENCE-TERMINAL-001" in html
    assert "CERTIFICADO VERIFIED" in html
    assert "EXECUÇÃO</small><strong>BLOQUEADA" in html
    for forbidden in (
        "execute_action_button",
        "retry_button",
        "reopen_execution_button",
        "issue_certificate_button",
        "sign_certificate_button",
        "billing_button",
        "crm_write_button",
        "deploy_button",
        "production_mutation_button",
    ):
        assert forbidden not in html


def test_terminal_certificate_does_not_mount_outside_privacy_module():
    model = ready_panel_view_model()
    for selected in ("roi", "finops", "companies", "b2b", "sla"):
        html = reference_html(
            "negocios",
            selected=selected,
            terminal_certificate_panel_view_model=model,
        )
        assert 'data-terminal-certificate-reference="draft-only"' not in html
        assert "reference-certificate-digest" not in html


def test_invalid_view_model_fails_closed_without_rendering_certificate_claims():
    model = ready_panel_view_model()
    model["retry_authorized"] = True
    html = reference_html(
        "negocios",
        selected="privacy",
        terminal_certificate_panel_view_model=model,
    )
    assert 'data-terminal-certificate-reference="fail-closed"' in html
    assert 'data-component="terminal-certificate-panel-offline-v1"' not in html
    assert "reference-certificate-digest" not in html
    assert "Certificado terminal indisponível" in html
    assert "CERTIFICADO FAIL-CLOSED" in html


def test_reference_ui_has_no_live_session_binding_for_terminal_certificate():
    source = Path("atlasquant_reference_ui.py").read_text(encoding="utf-8")
    runtime = source[
        source.index("def render_reference_workspace("):
        source.index("def render_trader_entry(")
    ]
    assert "terminal_certificate_panel_view_model" not in runtime
    assert "terminal_certificate_panel" not in runtime
    assert "atlasquant_b2b_terminal_certificate" not in runtime


def test_reference_html_accepts_only_view_model_path_not_raw_html_argument():
    source = Path("atlasquant_reference_ui.py").read_text(encoding="utf-8")
    signature = source[
        source.index("def reference_html("):
        source.index("):", source.index("def reference_html(")) + 2
    ]
    assert "terminal_certificate_panel_view_model" in signature
    assert "terminal_certificate_html" not in signature
    assert "terminal_certificate_panel_html" not in signature


def test_component_styling_is_static_and_responsive():
    html = reference_html(
        "negocios",
        selected="privacy",
        terminal_certificate_panel_view_model=ready_panel_view_model(),
    )
    assert ".aq-terminal-certificate-panel{" in html
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in html
    assert "@media(max-width:760px)" in html
    assert "grid-template-columns:1fr" in html
