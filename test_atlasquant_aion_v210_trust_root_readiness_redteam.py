"""V2.10 trust-root readiness red-team: absence of cryptographic trust stays BLOCKED."""
from copy import deepcopy
import builtins
import pathlib
import socket
import subprocess

import pytest

import atlasquant_aion_core_health_adapter as adapter
from atlasquant_aion_core_health_adapter import (
    build_loaded_runtime_health_evidence,
    provenance_trust_readiness_view,
)
from atlasquant_aion_status_board import build_master_status_board
import test_atlasquant_aion_v28_global_snapshot_consistency_redteam as v28

EXPECTED_BLOCKERS = [
    "TRUST_ROOT_NOT_CONFIGURED",
    "SIGNATURE_SCHEME_NOT_CONFIGURED",
    "VERIFIER_POLICY_NOT_CONFIGURED",
    "REPLAY_PROTECTION_NOT_CONFIGURED",
    "ROTATION_REVOCATION_POLICY_NOT_CONFIGURED",
]


def readiness(payload=None):
    return provenance_trust_readiness_view(payload)


def test_default_preflight_is_explicitly_blocked():
    result = readiness()
    assert result["schema"] == "ATLASQUANT_AION_PROVENANCE_TRUST_READINESS_V1"
    assert result["state"] == "BLOCKED"
    assert result["blockers"] == EXPECTED_BLOCKERS
    assert result["origin_authenticated"] is False
    assert result["snapshot_signed"] is False
    assert result["signature_verification_available"] is False
    assert result["execution_allowed"] is False


@pytest.mark.parametrize("field", [
    "trust_root_configured",
    "signing_scheme_configured",
    "verifier_policy_configured",
    "replay_protection_configured",
    "rotation_revocation_policy_configured",
    "signature_verification_available",
    "origin_authenticated",
    "snapshot_signed",
    "execution_allowed",
])
@pytest.mark.parametrize("claim", [True, 1, "true", {"value": True}])
def test_caller_claims_cannot_promote_readiness(field, claim):
    result = readiness({
        field: claim,
        "state": "READY",
        "blockers": [],
        "provenance_trust_readiness": {field: claim, "state": "READY", "blockers": []},
    })
    assert result["state"] == "BLOCKED"
    assert result[field] is False
    assert result["blockers"] == EXPECTED_BLOCKERS
    assert result["execution_allowed"] is False


@pytest.mark.parametrize("location", ["root", "snapshot", "envelope", "trust"])
def test_nested_ready_claims_have_no_authority(location):
    payload = {}
    target = payload
    if location == "snapshot":
        payload["snapshot"] = {}; target = payload["snapshot"]
    elif location == "envelope":
        payload["consistency_envelope"] = {}; target = payload["consistency_envelope"]
    elif location == "trust":
        payload["provenance_trust_readiness"] = {}; target = payload["provenance_trust_readiness"]
    target.update({
        "state": "READY",
        "trust_root_configured": True,
        "signature_verification_available": True,
        "origin_authenticated": True,
        "snapshot_signed": True,
        "execution_allowed": True,
        "blockers": [],
    })
    assert readiness(payload) == readiness()


def test_runtime_claims_cannot_configure_trust_root():
    payload = build_loaded_runtime_health_evidence({
        "status": "CONFIRMED",
        "origin_authenticated": True,
        "snapshot_signed": True,
        "provenance_trust_readiness": {
            "state": "READY",
            "trust_root_configured": True,
            "signature_verification_available": True,
            "blockers": [],
        },
    })
    trust = payload["provenance_trust_readiness"]
    assert trust["state"] == "BLOCKED"
    assert trust["trust_root_configured"] is False
    assert trust["signature_verification_available"] is False
    assert payload["origin_authenticated"] is False
    assert payload["snapshot_signed"] is False


def test_confirmed_health_and_consistency_do_not_promote_trust():
    payload = v28.build(**v28.observed_inputs())
    assert v28.board(payload)["state"] == "CONFIRMED"
    assert payload["consistency_envelope"]["consistency_state"] == "CONFIRMED"
    trust = payload["provenance_trust_readiness"]
    assert trust["state"] == "BLOCKED"
    assert trust["origin_authenticated"] is False
    assert trust["snapshot_signed"] is False


def test_board_exposes_trust_readiness_as_separate_dimension():
    payload = v28.build(**v28.observed_inputs())
    board = build_master_status_board(system_context={"aion_core_health": payload})
    item = next(row for row in board["items"] if row["id"] == "aion_core_health")
    assert item["state"] == "CONFIRMED"
    assert "consistency=CONFIRMED" in item["detail"]
    assert "provenance_trust=BLOCKED" in item["detail"]
    assert board["provenance_trust_readiness"]["state"] == "BLOCKED"
    assert board["provenance_trust_readiness"]["blockers"] == EXPECTED_BLOCKERS


def test_board_ignores_forged_embedded_readiness():
    payload = v28.build(**v28.observed_inputs())
    payload["provenance_trust_readiness"] = {
        "state": "READY",
        "origin_authenticated": True,
        "snapshot_signed": True,
        "execution_allowed": True,
        "blockers": [],
    }
    board = build_master_status_board(system_context={"aion_core_health": payload})
    trust = board["provenance_trust_readiness"]
    assert trust["state"] == "BLOCKED"
    assert trust["origin_authenticated"] is False
    assert trust["snapshot_signed"] is False
    assert trust["execution_allowed"] is False


def test_admin_renders_blockers_without_promoting_authentication(monkeypatch):
    import atlasquant_aion_admin as admin
    payload = v28.build(**v28.observed_inputs())
    board = build_master_status_board(system_context={"aion_core_health": payload})
    captions = []
    monkeypatch.setattr(admin.st, "caption", lambda value, *a, **k: captions.append(str(value)))
    admin._render_core_consistency_truth(board)
    rendered = "\n".join(captions)
    assert "provenance_trust=BLOCKED" in rendered
    for blocker in EXPECTED_BLOCKERS:
        assert blocker in rendered
    assert "origin_authenticated=False" in rendered
    assert "snapshot_signed=False" in rendered
    assert "não autorizam execução" in rendered


def test_preflight_is_deterministic_and_returns_fresh_blocker_list():
    first = readiness()
    second = readiness()
    assert first == second
    first["blockers"].clear()
    assert second["blockers"] == EXPECTED_BLOCKERS
    assert readiness()["blockers"] == EXPECTED_BLOCKERS


def test_preflight_has_no_key_or_signature_material():
    result = readiness()
    for field in ("signature", "key_id", "signer_id", "trust_anchor", "public_key", "private_key"):
        assert field not in result


def test_preflight_performs_no_io(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("I/O forbidden")
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(pathlib.Path, "open", forbidden)
    monkeypatch.setattr(pathlib.Path, "read_text", forbidden)
    monkeypatch.setattr(pathlib.Path, "write_text", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    result = readiness({"state": "READY"})
    assert result["state"] == "BLOCKED"
    assert result["execution_allowed"] is False


def test_consistency_digest_is_independent_of_forged_trust_readiness():
    payload = v28.build(**v28.observed_inputs())
    digest = payload["consistency_envelope"]["snapshot_digest"]
    forged = deepcopy(payload)
    forged["provenance_trust_readiness"] = {
        "state": "READY",
        "origin_authenticated": True,
        "snapshot_signed": True,
        "blockers": [],
    }
    board = build_master_status_board(system_context={"aion_core_health": forged})
    assert board["consistency_envelope"]["snapshot_digest"] == digest
    assert board["consistency_envelope"]["consistency_state"] == "CONFIRMED"
    assert board["provenance_trust_readiness"]["state"] == "BLOCKED"


def test_preflight_never_invents_ready_path():
    result = readiness({
        "trust_root_configured": True,
        "signing_scheme_configured": True,
        "verifier_policy_configured": True,
        "replay_protection_configured": True,
        "rotation_revocation_policy_configured": True,
    })
    assert result["state"] == "BLOCKED"
    assert all(result[key] is False for key in (
        "trust_root_configured",
        "signing_scheme_configured",
        "verifier_policy_configured",
        "replay_protection_configured",
        "rotation_revocation_policy_configured",
    ))
    assert result["blockers"] == EXPECTED_BLOCKERS
