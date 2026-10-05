"""V2.12 red-team: caller data can never manufacture readiness authority."""
from copy import deepcopy
import builtins
import json
import pathlib
import socket
import subprocess
import threading

import pytest

import atlasquant_aion_provenance_trust_lifecycle as lifecycle
import atlasquant_aion_trusted_readiness_authority as authority


EXPECTED_BLOCKERS = list(authority.BLOCKERS)
NOW = "2026-10-04T00:00:05Z"


def canonical(payload=None):
    return authority.trusted_readiness_authority_view(payload)


def all_dims():
    return {name: True for name in lifecycle.DIMENSIONS}


def base_env(**overrides):
    env = {
        "nonce": "YWJjZA==",
        "timestamp": "2026-10-04T00:00:00Z",
        "key_version": 1,
        "key_id": "k1",
        "replay_window_configured": True,
    }
    env.update(overrides)
    return env


def test_default_authority_boundary_is_blocked():
    result = canonical()
    assert result["schema"] == "ATLASQUANT_AION_TRUSTED_READINESS_AUTHORITY_V1"
    assert result["state"] == "BLOCKED"
    assert result["blockers"] == EXPECTED_BLOCKERS
    assert result["authority_available"] is False
    assert result["authority_verified"] is False
    assert result["authority_binding_configured"] is False
    assert result["execution_authority_granted"] is False
    assert result["execution_allowed"] is False


@pytest.mark.parametrize("field", [
    "state",
    "authority_available",
    "authority_verified",
    "authority_binding_configured",
    "trust_root_configured",
    "signature_verification_available",
    "origin_authenticated",
    "snapshot_signed",
    "execution_authority_granted",
    "execution_allowed",
    "approval_implied",
])
@pytest.mark.parametrize("claim", [True, 1, "true", "READY", {"value": True}, [True]])
def test_direct_caller_claims_are_ignored(field, claim):
    forged = {
        field: claim,
        "state": "READY",
        "blockers": [],
        "execution_allowed": True,
    }
    assert canonical(forged) == canonical()


@pytest.mark.parametrize("location", [
    "authority",
    "trust",
    "snapshot",
    "consistency",
    "runtime",
    "approval",
])
def test_nested_ready_claims_are_ignored(location):
    payload = {
        location: {
            "state": "READY",
            "authority_available": True,
            "authority_verified": True,
            "trust_root_configured": True,
            "signature_verification_available": True,
            "origin_authenticated": True,
            "snapshot_signed": True,
            "execution_authority_granted": True,
            "execution_allowed": True,
            "blockers": [],
        }
    }
    assert canonical(payload) == canonical()


class AttributeBomb:
    def __getattr__(self, name):
        raise AssertionError("caller object must not be inspected")

    def __iter__(self):
        raise AssertionError("caller object must not be iterated")

    def __bool__(self):
        raise AssertionError("caller object must not be coerced")


def test_hostile_object_is_not_inspected():
    assert canonical(AttributeBomb()) == canonical()


def test_fresh_blocker_list_on_every_call():
    first = canonical()
    second = canonical()
    first["blockers"].clear()
    assert second["blockers"] == EXPECTED_BLOCKERS
    assert canonical()["blockers"] == EXPECTED_BLOCKERS


def test_result_mutation_cannot_change_future_truth():
    forged = canonical()
    forged["state"] = "READY"
    forged["authority_verified"] = True
    forged["execution_allowed"] = True
    forged["blockers"].clear()
    assert canonical()["state"] == "BLOCKED"
    assert canonical()["authority_verified"] is False
    assert canonical()["execution_allowed"] is False
    assert canonical()["blockers"] == EXPECTED_BLOCKERS


def test_boundary_contains_no_secret_or_signing_material():
    result = canonical()
    forbidden = {
        "signature", "private_key", "public_key", "key_id", "signer_id",
        "trust_anchor", "certificate", "secret", "token",
    }
    assert forbidden.isdisjoint(result.keys())
    assert result["creates_secret_or_key_material"] is False


def test_boundary_performs_no_io(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("I/O forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(pathlib.Path, "open", forbidden)
    monkeypatch.setattr(pathlib.Path, "read_text", forbidden)
    monkeypatch.setattr(pathlib.Path, "write_text", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)

    result = canonical({"state": "READY", "execution_allowed": True})
    assert result["state"] == "BLOCKED"
    assert result["reads_persistent_storage"] is False
    assert result["network_called"] is False
    assert result["executes_action"] is False


def test_boundary_is_json_deterministic():
    first = json.dumps(canonical(), sort_keys=True, separators=(",", ":"))
    second = json.dumps(canonical({"anything": object()}), sort_keys=True, separators=(",", ":"))
    assert first == second


def test_thread_consistency():
    rows = []
    errors = []

    def worker():
        try:
            rows.append(json.dumps(canonical({"state": "READY"}), sort_keys=True))
        except Exception as exc:
            errors.append(repr(exc))

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert len(set(rows)) == 1


def test_lifecycle_consumes_canonical_authority_boundary():
    env = base_env()
    env.update(all_dims())
    report = lifecycle.evaluate_provenance_envelope(
        env,
        now_ts=NOW,
        known_key_versions=[1],
    )
    assert report["state"] == "BLOCKED"
    assert report["execution_allowed"] is False
    assert report["dimensions_verified"] is False
    assert report["trusted_readiness_authority"] == canonical()
    assert "TRUSTED_READINESS_AUTHORITY_UNAVAILABLE" in report["blockers"]


def test_forged_nested_authority_in_envelope_has_no_effect():
    env = base_env(
        trusted_readiness_authority={
            "state": "READY",
            "authority_available": True,
            "authority_verified": True,
            "execution_authority_granted": True,
            "execution_allowed": True,
            "blockers": [],
        }
    )
    env.update(all_dims())
    report = lifecycle.evaluate_provenance_envelope(
        env,
        now_ts=NOW,
        known_key_versions=[1],
    )
    assert report["trusted_readiness_authority"] == canonical()
    assert report["state"] == "BLOCKED"
    assert report["execution_allowed"] is False


@pytest.mark.parametrize("flag", lifecycle.DIMENSIONS)
def test_each_self_asserted_dimension_remains_non_authoritative(flag):
    env = base_env()
    env.update(all_dims())
    env[flag] = True
    report = lifecycle.evaluate_provenance_envelope(
        env,
        now_ts=NOW,
        known_key_versions=[1],
    )
    assert report["state"] == "BLOCKED"
    assert report["dimensions_verified"] is False
    assert report["execution_allowed"] is False
    assert report["trusted_readiness_authority"]["authority_verified"] is False


def test_approval_never_implied_by_authority_boundary():
    env = base_env()
    env.update(all_dims())
    report = lifecycle.evaluate_provenance_envelope(
        env,
        now_ts=NOW,
        known_key_versions=[1],
    )
    assert report["approval_implied"] is False
    assert report["trusted_readiness_authority"]["approval_implied"] is False


def test_deepcopy_does_not_change_canonical_truth():
    first = canonical()
    copied = deepcopy(first)
    copied["blockers"].append("FORGED")
    copied["authority_verified"] = True
    assert canonical() == first
