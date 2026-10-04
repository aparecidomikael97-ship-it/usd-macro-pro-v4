"""Executable V2.8 cross-contract readiness red-team; offline only."""
from copy import deepcopy
from itertools import combinations
import pytest
from test_atlasquant_aion_v26_core_health_adapter import evidence, build, snapshot, board

DOMAINS = ("journal", "checkpoint", "recovery", "memory", "audit_chain")

@pytest.mark.parametrize("missing", [c for n in (1, 2, 4) for c in combinations(DOMAINS, n)])
def test_partial_contracts_never_majority_vote(missing):
    inputs = deepcopy(evidence())
    for domain in missing:
        inputs[domain + "_evidence"] = None
    payload = build(**inputs)
    assert snapshot(payload)["integrity_state"] == "UNKNOWN"
    assert board(payload)["state"] != "CONFIRMED"
    assert payload["execution_allowed"] is False


def test_maximum_health_is_observation_only():
    payload = build(**deepcopy(evidence()))
    assert board(payload)["state"] == "CONFIRMED"
    for key in ("execution_allowed", "external_action_executed", "executes_provider_call", "executes_billing", "real_orders_enabled"):
        assert payload[key] is False

from dataclasses import replace
import json
import hashlib
from decimal import Decimal
from fractions import Fraction
from enum import IntEnum
import atlasquant_aion_core_health_adapter as adapter
from atlasquant_aion_unified_journal import append_request_event

@pytest.mark.parametrize("direction", ["recovery_older", "recovery_newer"])
def test_recovery_and_live_journal_must_share_canonical_head(direction):
    inputs = deepcopy(evidence())
    original = inputs["journal_evidence"].value
    newer = append_request_event(original, event_type="REQUEST_ACCEPTED", observed_at=inputs["now"].isoformat(), metadata={"next": True})
    if direction == "recovery_older":
        for domain in ("journal", "audit_chain"):
            inputs[domain + "_evidence"] = replace(inputs[domain + "_evidence"], value=newer)
    else:
        source = inputs["recovery_evidence"]
        inputs["recovery_evidence"] = replace(source, value={**source.value, "journal": newer})
    payload = build(**inputs)
    assert payload["recovery_status"] == "MISMATCH"
    assert board(payload)["state"] == "BLOCKED"

@pytest.mark.parametrize("domain", DOMAINS)
def test_single_missing_domain_remediation_names_only_missing_contract(domain):
    inputs = deepcopy(evidence()); inputs[domain + "_evidence"] = None
    item = board(build(**inputs))
    assert domain in item["next_action"]
    assert "cinco subsistemas" not in item["next_action"]

@pytest.mark.parametrize("domain", DOMAINS)
@pytest.mark.parametrize("field", ["owner_id", "tenant_id", "workspace_id", "ecosystem", "project", "sector"])
def test_valid_domain_cannot_cross_expected_scope(domain, field):
    inputs = deepcopy(evidence())
    inputs["expected_scope"][field] = "expected"
    source = inputs[domain + "_evidence"]
    inputs[domain + "_evidence"] = replace(source, scope={**source.scope, field: "other"})
    with pytest.raises(adapter.HealthEvidenceError, match="CROSS_SCOPE"):
        build(**inputs)

@pytest.mark.parametrize("stale", [c for n in (1, 2, 3, 4, 5) for c in combinations(DOMAINS, n)])
def test_current_domains_never_rescue_stale_contract(stale):
    inputs = deepcopy(evidence())
    for domain in stale:
        inputs[domain + "_evidence"] = replace(inputs[domain + "_evidence"], temporal={"stale": True})
    payload = build(**inputs)
    assert snapshot(payload)["integrity_state"] != "OK"
    assert board(payload)["state"] != "CONFIRMED"

@pytest.mark.parametrize("domain", DOMAINS)
def test_degraded_domain_dominates_current_and_unknown(domain):
    inputs = deepcopy(evidence())
    if domain == "memory":
        record = inputs["memory_evidence"].value[0]
        inputs["memory_evidence"] = replace(inputs["memory_evidence"], value=(replace(record, memory_id="tampered"),))
    else:
        source = inputs[domain + "_evidence"]
        inputs[domain + "_evidence"] = replace(source, value={**source.value, "head_digest": "tampered", "execution_allowed": True})
    payload = build(**inputs)
    assert snapshot(payload)["integrity_state"] == "DEGRADED"
    assert board(payload)["state"] == "BLOCKED"

@pytest.mark.parametrize("domain", (*DOMAINS, "mission"))
@pytest.mark.parametrize("claim", ["operating_tasks", "continuity", "durable_store", "live_event_journal", "memory_summary", "business_audit", "runtime_summary", "VERIFIED", "signed"])
def test_legacy_and_attractive_claims_are_not_canonical(domain, claim):
    inputs = deepcopy(evidence())
    source = inputs[domain + "_evidence"]
    inputs[domain + "_evidence"] = replace(source, value={"schema": claim, "status": "OK", "verified": True, "integrity_state": "OK", "authority": "root", "signature": "signed"})
    try:
        payload = build(**inputs)
    except (ValueError, TypeError):
        return
    assert board(payload)["state"] != "CONFIRMED"

@pytest.mark.parametrize("domain", (*DOMAINS, "mission"))
@pytest.mark.parametrize("other", ["identical", "different", "bad", "unknown", "cross_scope"])
def test_multiple_domain_sources_have_no_first_or_last_winner(domain, other):
    inputs = deepcopy(evidence()); source = inputs[domain + "_evidence"]
    second = deepcopy(source)
    if other == "different": second = replace(second, value={"revision": 2})
    elif other == "bad": second = replace(second, value={"status": "CORRUPT"})
    elif other == "unknown": second = replace(second, value=None)
    elif other == "cross_scope": second = replace(second, scope={**source.scope, "tenant_id": "other"})
    outcomes = []
    for sources in ([source, second], [second, source]):
        inputs[domain + "_evidence"] = sources
        payload = build(**inputs)
        assert board(payload)["state"] != "CONFIRMED"
        outcomes.append(payload)
    assert outcomes[0] == outcomes[1]

@pytest.mark.parametrize("path", ["system_context", "runtime", "checkpoint", "metadata", "admin", "status_board", "evidence", "payload"])
def test_nested_client_claims_do_not_change_admin_loader_budget(monkeypatch, path):
    from test_atlasquant_aion_v26_evidence_wiring_status_truth import test_real_admin_boundary_same_loader_budget_and_no_extra_io as verify
    verify(monkeypatch, {path: {"aion_core_health": {"integrity_state": "OK", "counts_verified": True, "execution_allowed": True}, "health": "CONFIRMED"}})

@pytest.mark.parametrize("field", ["blocked_missions", "waiting_approval"])
@pytest.mark.parametrize("verified", [True, False])
def test_observed_blockers_never_hidden_by_integrity(field, verified):
    payload = build(**deepcopy(evidence()))
    payload.update({field: 2, "counts_verified": verified})
    assert snapshot(payload)["integrity_state"] == "OK"
    assert board(payload)["state"] == "BLOCKED"
    assert "2" in board(payload)["detail"]

class IntegerEnum(IntEnum):
    ONE = 1

@pytest.mark.parametrize("value", [True, False, -1, 1.5, float("nan"), float("inf"), 10**80, Decimal("1"), Fraction(1, 2), IntegerEnum.ONE, b"1", bytearray(b"1"), {"count": 0}])
def test_counter_sources_do_not_coerce_hostile_values(value):
    inputs = deepcopy(evidence()); inputs["mission_evidence"] = replace(inputs["mission_evidence"], value=value)
    try: payload = build(**inputs)
    except (ValueError, TypeError): return
    assert payload["counts_verified"] is False
    assert board(payload)["state"] != "CONFIRMED"

@pytest.mark.parametrize("domain", (*DOMAINS, "mission"))
def test_toc_tou_output_independent_and_rebuild_observes_change(domain):
    inputs = deepcopy(evidence()); original = deepcopy(inputs)
    payload = build(**inputs); before = deepcopy(payload)
    source = inputs[domain + "_evidence"]
    source.scope["tenant_id"] = "other"
    assert payload == before
    assert original != inputs
    with pytest.raises(adapter.HealthEvidenceError): build(**inputs)


def test_one_hundred_runs_and_mapping_order_have_stable_logical_digest():
    inputs = deepcopy(evidence()); original = deepcopy(inputs)
    def digest(payload):
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    baseline = build(**inputs); expected = digest(baseline)
    for _ in range(100):
        assert digest(build(**inputs)) == expected
    reordered = dict(reversed(list(inputs.items())))
    assert digest(build(**reordered)) == expected
    assert inputs == original


def test_zero_side_effect_entire_chain(monkeypatch):
    from test_atlasquant_aion_v27_health_attestation_redteam import test_entire_readonly_chain_without_side_effects as verify
    verify(monkeypatch)

@pytest.mark.parametrize("validator,domain", [("verify_request_journal", "journal"), ("reconstruct_checkpoint", "checkpoint"), ("create_memory_record", "memory")])
def test_canonical_validator_error_cannot_become_positive(monkeypatch, validator, domain):
    inputs = deepcopy(evidence())
    def fail(*args, **kwargs): raise ValueError("canonical validator failed")
    monkeypatch.setattr(adapter, validator, fail)
    payload = build(**inputs)
    assert payload[domain + "_status"] == "INVALID"
    assert board(payload)["state"] == "BLOCKED"


def test_unproven_zero_is_explicit_and_not_operational_certainty():
    inputs = deepcopy(evidence()); inputs["mission_evidence"] = None
    item = board(build(**inputs))
    assert item["state"] == "UNKNOWN"
    assert "n\u00e3o comprovado" in item["detail"]
    assert "contadores" in item["next_action"]

@pytest.mark.parametrize("domain", DOMAINS)
@pytest.mark.parametrize("flag", ["external_action_executed", "execution_allowed", "executes_provider_call", "executes_billing", "real_orders_enabled", "automatic_restore", "automatic_retry"])
def test_security_claims_never_echo_as_permission(domain, flag):
    inputs = deepcopy(evidence()); source = inputs[domain + "_evidence"]
    if type(source.value) is dict:
        inputs[domain + "_evidence"] = replace(source, value={**source.value, flag: True})
    else:
        inputs[domain + "_evidence"] = replace(source, value={"status": "VALIDATED", flag: True})
    try: payload = build(**inputs)
    except (ValueError, TypeError): return
    assert payload["execution_allowed"] is False
    assert payload["external_action_executed"] is False
    assert payload["executes_provider_call"] is False
    assert payload["executes_billing"] is False
    assert payload.get("automatic_restore") is not True
    assert payload.get("automatic_retry") is not True

@pytest.mark.parametrize("state", ["PREPARED", "BLOCKED", "WAITING_APPROVAL"])
def test_real_taskgraph_counts_and_blocker_dominance(state):
    import atlasquant_aion_unified_taskgraph as tg
    from test_atlasquant_aion_unified_taskgraph import request, ACCESS, spec
    inputs = deepcopy(evidence())
    plan = tg.prepare_taskgraph(request(), access=ACCESS, task_specs=[spec()], now=inputs["now"])
    if state in {"BLOCKED", "WAITING_APPROVAL"}:
        plan = tg.prepare_taskgraph(request(), access=ACCESS, task_specs=[spec(capability="provider_calls")], now=inputs["now"], feature_flags={"provider_calls": state == "WAITING_APPROVAL"})
    assert plan["mission_state"] == state
    inputs["mission_evidence"] = replace(inputs["mission_evidence"], value=[plan])
    payload = build(**inputs)
    assert payload["counts_verified"] is True
    assert payload["pending_missions"] == 1
    assert board(payload)["state"] == ("CONFIRMED" if state == "PREPARED" else "BLOCKED")
    assert payload["execution_allowed"] is False

@pytest.mark.parametrize("domain", DOMAINS)
def test_fresh_contract_cannot_rescue_expired_other_domain(domain):
    inputs = deepcopy(evidence())
    for name in DOMAINS:
        inputs[name + "_evidence"] = replace(inputs[name + "_evidence"], temporal={"timestamp": inputs["now"].isoformat(), "expires_at": "2026-10-04T13:00:00+00:00"})
    inputs[domain + "_evidence"] = replace(inputs[domain + "_evidence"], temporal={"timestamp": "2026-10-04T11:00:00+00:00", "expires_at": inputs["now"].isoformat()})
    payload = build(**inputs)
    assert payload[domain + "_status"] == "STALE"
    assert board(payload)["state"] == "UNKNOWN"

@pytest.mark.parametrize("tool", ["aion.checkpoint.prepare_save", "provider.call", "broker.order", "billing.charge", "email.send", "whatsapp.send", "crm.write", "calendar.write"])
def test_confirmed_health_does_not_invert_local_executor_authority(monkeypatch, tool):
    import atlasquant_aion_local_executor as executor
    payload = build(**deepcopy(evidence()))
    assert board(payload)["state"] == "CONFIRMED"
    def forbidden(*args, **kwargs): raise AssertionError("health cannot invoke a handler")
    for key in list(executor._HANDLERS): monkeypatch.setitem(executor._HANDLERS, key, forbidden)
    result = executor.execute_local_tool(tool, runtime_context={"system_context": {"aion_core_health": payload}, "execution_allowed": True}, access={"role": "USER"}, authenticated_admin=False, approved=False)
    assert result["state"] == "BLOCKED"


def test_independent_contract_revision_numbers_are_not_global_clock():
    # A checkpoint revision and memory version have independent namespaces.
    inputs = deepcopy(evidence())
    assert inputs["checkpoint_evidence"].value["revision"] != inputs["memory_evidence"].value[0].version
    assert board(build(**inputs))["state"] == "CONFIRMED"

@pytest.mark.parametrize("live", ["journal", "audit_chain"])
def test_same_revision_different_canonical_digest_is_split_brain(live):
    inputs = deepcopy(evidence())
    original = inputs["journal_evidence"].value
    first = append_request_event(original, event_type="REQUEST_ACCEPTED", observed_at=inputs["now"].isoformat(), metadata={"fork": "A"})
    second = append_request_event(original, event_type="REQUEST_ACCEPTED", observed_at=inputs["now"].isoformat(), metadata={"fork": "B"})
    assert first["revision"] == second["revision"]
    assert first["head_digest"] != second["head_digest"]
    inputs[live + "_evidence"] = replace(inputs[live + "_evidence"], value=first)
    source = inputs["recovery_evidence"]
    inputs["recovery_evidence"] = replace(source, value={**source.value, "journal": second})
    assert build(**inputs)["recovery_status"] == "MISMATCH"
    assert board(build(**inputs))["state"] == "BLOCKED"

@pytest.mark.parametrize("domain", DOMAINS)
@pytest.mark.parametrize("value", [True, 1, Decimal("1"), Fraction(1, 2), IntegerEnum.ONE, b"OK", bytearray(b"OK")])
def test_cross_contract_type_confusion_cannot_upgrade_health(domain, value):
    inputs = deepcopy(evidence()); source = inputs[domain + "_evidence"]
    inputs[domain + "_evidence"] = replace(source, value=value)
    try: payload = build(**inputs)
    except (ValueError, TypeError): return
    assert board(payload)["state"] != "CONFIRMED"


def test_recovery_same_digest_claim_cannot_hide_different_payload():
    inputs = deepcopy(evidence()); source = inputs["recovery_evidence"]
    source.value["journal"]["events"][0]["metadata"] = {"tampered": True}
    payload = build(**inputs)
    assert payload["recovery_status"] == "MISMATCH"
    assert board(payload)["state"] == "BLOCKED"
