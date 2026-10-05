"""V2.9 provenance-truth red-team: digests are not signatures and source refs are not authenticated origin."""
from copy import deepcopy
import pytest

import atlasquant_aion_core_health_adapter as adapter
from atlasquant_aion_core_health_adapter import (
    build_loaded_runtime_health_evidence,
    consistency_envelope_view,
)
from atlasquant_aion_status_board import build_master_status_board
import test_atlasquant_aion_v28_global_snapshot_consistency_redteam as v28


@pytest.mark.parametrize("field", ["origin_authenticated", "snapshot_signed"])
def test_complete_consistent_snapshot_never_claims_provenance_authentication(field):
    payload = v28.build(**v28.observed_inputs())
    envelope = payload["consistency_envelope"]
    assert envelope["consistency_state"] == "CONFIRMED"
    assert envelope[field] is False
    assert payload[field] is False
    assert envelope["execution_allowed"] is False


@pytest.mark.parametrize("field", ["origin_authenticated", "snapshot_signed"])
@pytest.mark.parametrize("claim", [True, 1, "true", {"value": True}])
def test_runtime_claims_cannot_promote_authentication(field, claim):
    payload = build_loaded_runtime_health_evidence({
        field: claim,
        "snapshot": {field: claim},
        "consistency_envelope": {field: claim},
    })
    assert payload[field] is False
    assert payload["consistency_envelope"][field] is False
    assert payload["execution_allowed"] is False


@pytest.mark.parametrize("field", ["origin_authenticated", "snapshot_signed"])
def test_rehashed_envelope_authentication_spoof_fails_closed(field):
    payload = v28.build(**v28.observed_inputs())
    forged = deepcopy(payload)
    forged["consistency_envelope"][field] = True
    forged["consistency_envelope"]["snapshot_digest"] = adapter._fingerprint({
        key: value for key, value in forged["consistency_envelope"].items()
        if key != "snapshot_digest"
    })
    view = consistency_envelope_view(forged)
    assert view["consistency_state"] == "UNKNOWN"
    assert view["origin_authenticated"] is False
    assert view["snapshot_signed"] is False
    assert view["execution_allowed"] is False


@pytest.mark.parametrize("field", ["origin_authenticated", "snapshot_signed"])
def test_rehashed_envelope_missing_truth_field_fails_closed(field):
    payload = v28.build(**v28.observed_inputs())
    forged = deepcopy(payload)
    forged["consistency_envelope"].pop(field)
    forged["consistency_envelope"]["snapshot_digest"] = adapter._fingerprint({
        key: value for key, value in forged["consistency_envelope"].items()
        if key != "snapshot_digest"
    })
    view = consistency_envelope_view(forged)
    assert view["consistency_state"] == "UNKNOWN"
    assert view["origin_authenticated"] is False
    assert view["snapshot_signed"] is False


def test_source_refs_and_content_digests_do_not_authenticate_origin():
    result = v28.envelope()
    assert all(result["domains"][name]["source_ref"] for name in v28.DOMAINS)
    assert all(result["domains"][name]["identity_digest"] for name in v28.DOMAINS)
    assert result["evidence_epoch"].startswith("sha256:")
    assert result["snapshot_digest"].startswith("sha256:")
    assert result["origin_authenticated"] is False
    assert result["snapshot_signed"] is False


def test_board_exposes_provenance_truth_separately_from_consistency():
    payload = v28.build(**v28.observed_inputs())
    board = build_master_status_board(system_context={"aion_core_health": payload})
    item = next(row for row in board["items"] if row["id"] == "aion_core_health")
    assert "consistency=CONFIRMED" in item["detail"]
    assert "snapshot_atomic=False" in item["detail"]
    assert "origin_authenticated=False" in item["detail"]
    assert "snapshot_signed=False" in item["detail"]


def test_admin_caption_exposes_non_authenticated_non_signed_truth(monkeypatch):
    import atlasquant_aion_admin as admin
    payload = v28.build(**v28.observed_inputs())
    board = build_master_status_board(system_context={"aion_core_health": payload})
    captions = []
    monkeypatch.setattr(admin.st, "caption", lambda value, *a, **k: captions.append(str(value)))
    admin._render_core_consistency_truth(board)
    combined = "\n".join(captions)
    assert "snapshot_atomic=False" in combined
    assert "origin_authenticated=False" in combined
    assert "snapshot_signed=False" in combined
    assert "não autorizam execução" in combined


def test_unknown_view_preserves_explicit_negative_truth():
    view = consistency_envelope_view({})
    assert view["consistency_state"] == "UNKNOWN"
    assert view["snapshot_atomic"] is False
    assert view["origin_authenticated"] is False
    assert view["snapshot_signed"] is False
    assert view["execution_allowed"] is False


def test_provenance_truth_is_deterministic_across_rebuilds():
    first = v28.envelope()
    second = v28.envelope()
    assert first == second
    assert first["origin_authenticated"] is second["origin_authenticated"] is False
    assert first["snapshot_signed"] is second["snapshot_signed"] is False


def test_authenticated_origin_is_not_inferred_from_confirmed_health():
    payload = v28.build(**v28.observed_inputs())
    item = v28.board(payload)
    assert item["state"] == "CONFIRMED"
    assert payload["consistency_envelope"]["consistency_state"] == "CONFIRMED"
    assert payload["origin_authenticated"] is False
    assert payload["snapshot_signed"] is False
