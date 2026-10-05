"""V2.8 global consistency red-team: consistency is never atomicity."""
from copy import deepcopy
import pytest
from test_atlasquant_aion_v26_core_health_adapter import evidence, build, board

class AtomicityTruthTests:
    __test__ = True

    def test_maximum_health_never_claims_atomic_snapshot(self):
        payload = build(**deepcopy(evidence()))
        assert board(payload)["state"] == "CONFIRMED"
        assert payload.get("snapshot_atomic") is False
        assert payload["execution_allowed"] is False

    @pytest.mark.parametrize("claim", [True, "true", 1])
    def test_runtime_atomic_claim_is_overridden(self, claim):
        from atlasquant_aion_core_health_adapter import build_loaded_runtime_health_evidence
        payload = build_loaded_runtime_health_evidence({"snapshot_atomic": claim, "snapshot": {"atomic": claim}})
        assert payload.get("snapshot_atomic") is False
        assert payload["execution_allowed"] is False

from dataclasses import replace
from itertools import combinations
from datetime import timedelta
import json
import re
from concurrent.futures import ThreadPoolExecutor

DOMAINS = ("journal", "checkpoint", "recovery", "memory", "audit_chain", "mission")

def observed_inputs():
    inputs = deepcopy(evidence())
    for domain in DOMAINS:
        source = inputs[domain + "_evidence"]
        inputs[domain + "_evidence"] = replace(source, as_of=inputs["now"].isoformat(), temporal={"timestamp": inputs["now"].isoformat(), "expires_at": "2026-10-05T12:00:00+00:00"})
    return inputs

def envelope(inputs=None):
    return build(**(observed_inputs() if inputs is None else inputs))["consistency_envelope"]

class ConsistencyEnvelopeContractTests:
    __test__ = True

    def test_complete_observation_has_explicit_owner_and_no_authority(self):
        result = envelope()
        assert result["schema"] == "ATLASQUANT_AION_CONSISTENCY_ENVELOPE_V1"
        assert result["owner"] == "AION_CORE_HEALTH"
        assert result["authority"] == "READ_ONLY_DERIVED_EVIDENCE"
        assert result["consistency_state"] == "CONFIRMED"
        assert result["snapshot_complete"] is True
        assert result["snapshot_atomic"] is False
        assert result["execution_allowed"] is False
        assert result["expected_domains"] == list(DOMAINS)
        assert result["verified_domains"] == list(DOMAINS)

    @pytest.mark.parametrize("missing", [c for n in (1, 3, 5) for c in combinations(DOMAINS, n)])
    def test_partial_domains_have_no_vote(self, missing):
        inputs = observed_inputs()
        for domain in missing: inputs[domain + "_evidence"] = None
        result = envelope(inputs)
        assert result["consistency_state"] == "PARTIAL"
        assert result["snapshot_complete"] is False
        assert result["unknown_domains"] == [domain for domain in DOMAINS if domain in missing]

    def test_no_sources_unknown_and_inventory_is_explicit(self):
        result = envelope({})
        assert result["consistency_state"] == "UNKNOWN"
        assert result["unknown_domains"] == list(DOMAINS)
        assert result["snapshot_atomic"] is False

class LineageConsistencyTests:
    __test__ = True

    @pytest.mark.parametrize("domain", ["journal", "audit_chain", "recovery"])
    def test_canonical_triad_split_brain_dominates(self, domain):
        from atlasquant_aion_unified_journal import append_request_event
        inputs = observed_inputs(); source = inputs[domain + "_evidence"]
        target = source.value["journal"] if domain == "recovery" else source.value
        updated = append_request_event(target, event_type="REQUEST_ACCEPTED", observed_at=inputs["now"].isoformat(), metadata={"later": True})
        value = {**source.value, "journal": updated} if domain == "recovery" else updated
        inputs[domain + "_evidence"] = replace(source, value=value)
        result = envelope(inputs)
        assert result["lineage_consistency"] == "MISMATCH"
        assert result["consistency_state"] == "MISMATCH"

    @pytest.mark.parametrize("missing", ["journal", "audit_chain", "recovery"])
    def test_missing_triad_member_is_not_full_lineage(self, missing):
        inputs = observed_inputs(); inputs[missing + "_evidence"] = None
        result = envelope(inputs)
        assert result["lineage_consistency"] == "PARTIAL"
        assert result["consistency_state"] == "PARTIAL"

class TemporalConsistencyTests:
    __test__ = True

    @pytest.mark.parametrize("skew", [0, 1, 30, 300, 3600, 86400])
    def test_window_reports_actual_skew_without_invented_threshold(self, skew):
        inputs = observed_inputs(); source = inputs["checkpoint_evidence"]
        stamp = (inputs["now"] - timedelta(seconds=skew)).isoformat()
        inputs["checkpoint_evidence"] = replace(source, as_of=stamp, temporal={"timestamp": stamp, "expires_at": "2026-10-05T12:00:00+00:00"})
        result = envelope(inputs)
        assert result["temporally_mixed"] is (skew != 0)
        assert result["observation_window"]["earliest"] == stamp
        assert result["observation_window"]["latest"] == inputs["now"].isoformat()
        assert result["snapshot_atomic"] is False
        if skew: assert result["consistency_state"] == "PARTIAL"

    @pytest.mark.parametrize("domain", DOMAINS)
    def test_stale_material_domain_prevents_global_current(self, domain):
        inputs = observed_inputs(); inputs[domain + "_evidence"] = replace(inputs[domain + "_evidence"], temporal={"stale": True})
        result = envelope(inputs)
        assert domain in result["stale_domains"]
        assert result["temporal_consistency"] == "STALE"
        assert result["consistency_state"] != "CONFIRMED"

    @pytest.mark.parametrize("stamp", [None, True, 1, "", "bad", "2026-10-04T12:00:00", "2026-10-06T12:00:00+00:00"])
    def test_invalid_observation_cannot_certify_epoch_time(self, stamp):
        inputs = observed_inputs(); inputs["checkpoint_evidence"] = replace(inputs["checkpoint_evidence"], as_of=stamp, temporal={} if stamp=="" else inputs["checkpoint_evidence"].temporal)
        result = envelope(inputs)
        assert result["consistency_state"] != "CONFIRMED"
        assert result["snapshot_atomic"] is False

class ScopeConsistencyTests:
    __test__ = True

    def test_missing_expected_scope_is_not_inferred_trust(self):
        inputs = observed_inputs(); inputs.pop("expected_scope")
        result = envelope(inputs)
        assert result["scope_consistency"] == "UNKNOWN"
        assert result["consistency_state"] == "PARTIAL"

    @pytest.mark.parametrize("field", ["owner_id", "tenant_id", "workspace_id", "ecosystem", "project"])
    def test_scope_epoch_replay_cannot_certify_changed_scope(self, field):
        inputs = observed_inputs(); original = envelope(inputs)
        inputs["expected_scope"][field] = "other"
        if field in ("owner_id", "tenant_id", "workspace_id"):
            from atlasquant_aion_core_health_adapter import HealthEvidenceError
            with pytest.raises(HealthEvidenceError): envelope(inputs)
        else:
            updated = envelope(inputs)
            assert updated["evidence_epoch"] != original["evidence_epoch"]

class DigestEpochTests:
    __test__ = True

    def test_digest_format_roundtrip_and_keyword_order(self):
        inputs = observed_inputs(); result = envelope(inputs)
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", result["snapshot_digest"])
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", result["evidence_epoch"])
        assert json.loads(json.dumps(result)) == result
        assert envelope(dict(reversed(list(inputs.items())))) == result

    def test_source_mutation_does_not_change_previous_envelope(self):
        inputs = observed_inputs(); result = envelope(inputs); before = deepcopy(result)
        inputs["journal_evidence"].value["head_digest"] = "changed"
        assert result == before
        updated = envelope(inputs)
        assert updated["snapshot_digest"] != result["snapshot_digest"]
        assert updated["consistency_state"] == "MISMATCH"

    def test_memory_content_change_changes_epoch_without_global_revision(self):
        from atlasquant_aion_memory_contract import create_memory_record
        inputs = observed_inputs(); before = envelope(inputs)
        record = inputs["memory_evidence"].value[0]
        raw = vars(record).copy(); raw.pop("memory_id")
        raw["content"] = "different canonical memory"
        updated = create_memory_record(**{key:raw[key] for key in (
            "namespace","memory_class","content","scope","provenance_ids","version","previous_version",
            "evidence_refs","validation_state","retention","sensitivity","rollback_pointer","tombstone","created_at","metadata")})
        inputs["memory_evidence"] = replace(inputs["memory_evidence"], value=[updated])
        after = envelope(inputs)
        assert after["evidence_epoch"] != before["evidence_epoch"]
        assert after["snapshot_atomic"] is False

class StatusBoardTruthTests:
    __test__ = True

    def test_health_confirmed_partial_snapshot_is_visible(self):
        inputs = deepcopy(evidence()); payload = build(**inputs)
        item = board(payload)
        assert item["state"] == "CONFIRMED"
        assert "consistency=PARTIAL" in item["detail"]
        assert "snapshot_atomic=False" in item["detail"]

class AuthorityBarrierTests:
    __test__ = True

    @pytest.mark.parametrize("path", ["system_context", "runtime", "admin", "status", "health", "metadata"])
    def test_nested_snapshot_spoofing_admin_boundary(self, monkeypatch, path):
        from test_atlasquant_aion_v26_evidence_wiring_status_truth import test_real_admin_boundary_same_loader_budget_and_no_extra_io as verify
        verify(monkeypatch, {path: {"snapshot": {"atomic": True, "consistent": True, "complete": True, "epoch": "trusted"}}})

class SideEffectGuardTests:
    __test__ = True

    def test_readonly_chain_guarded(self, monkeypatch):
        from test_atlasquant_aion_v27_health_attestation_redteam import test_entire_readonly_chain_without_side_effects as verify
        verify(monkeypatch)

class DeterminismTests:
    __test__ = True

    def test_repeat_one_hundred_and_two_threads(self):
        inputs = observed_inputs(); expected = envelope(inputs)
        for _ in range(100): assert envelope(inputs) == expected
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(envelope, [inputs] * 10))
        assert all(result == expected for result in results)

class AdditionalContractTests:
    __test__ = True

    @pytest.mark.parametrize("revision,version", [(7, 7), (100, 27)])
    def test_independent_revision_namespaces_never_prove_global_epoch(self, revision, version):
        from atlasquant_aion_checkpoint_master import append_checkpoint_patch
        from atlasquant_aion_memory_contract import create_memory_record
        inputs = observed_inputs(); source = inputs["checkpoint_evidence"]
        value = source.value
        for n in range(revision):
            value = append_checkpoint_patch(value, event_id="event-"+str(n), patch={"counter": n}, expected_revision=n, created_at=inputs["now"].isoformat())
        inputs["checkpoint_evidence"] = replace(source, value=value)
        record = create_memory_record(namespace="TENANT", memory_class="TENANT", content="canonical independent version", scope={"tenant_id": "t"}, version=version, previous_version=version-1, validation_state="VALIDATED", evidence_refs=["EV-1"], created_at=inputs["now"].isoformat())
        inputs["memory_evidence"] = replace(inputs["memory_evidence"], value=[record])
        result = envelope(inputs)
        assert result["consistency_state"] == "CONFIRMED"
        assert result["snapshot_atomic"] is False
        assert "global_revision" not in result

    @pytest.mark.parametrize("field,value", [("global_revision",42), ("epoch",42), ("snapshot_id","trusted"), ("atomic",True), ("consistent",True), ("snapshot_atomic",True), ("consistency_state","CONFIRMED")])
    def test_caller_cross_binding_claims_do_not_strengthen_observation(self, field, value):
        from atlasquant_aion_core_health_adapter import build_loaded_runtime_health_evidence
        result = build_loaded_runtime_health_evidence({field:value,"snapshot":{field:value}})["consistency_envelope"]
        assert result["consistency_state"] == "UNKNOWN"
        assert result["snapshot_atomic"] is False

    @pytest.mark.parametrize("missing", ["checkpoint", "memory", "mission"])
    def test_request_lineage_view_can_be_confirmed_while_global_is_partial(self, missing):
        inputs = observed_inputs(); inputs[missing+"_evidence"] = None
        result = envelope(inputs)
        assert result["lineage_consistency"] == "CONFIRMED"
        assert result["consistency_state"] == "PARTIAL"
        assert missing in result["reasons"][0]

    def test_degraded_memory_can_have_coherent_observation_without_authority(self):
        from atlasquant_aion_memory_contract import create_memory_record
        inputs = observed_inputs()
        record = create_memory_record(namespace="TENANT", memory_class="TENANT", content="quarantined", scope={"tenant_id":"t"}, validation_state="QUARANTINED", evidence_refs=["EV-1"], created_at=inputs["now"].isoformat())
        inputs["memory_evidence"] = replace(inputs["memory_evidence"], value=[record])
        payload = build(**inputs); result = payload["consistency_envelope"]
        assert result["consistency_state"] == "CONFIRMED"
        assert result["snapshot_complete"] is True
        assert result["integrity_consistency"] == "DEGRADED"
        assert board(payload)["state"] == "BLOCKED"
        assert result["execution_allowed"] is False

    @pytest.mark.parametrize("domain", DOMAINS)
    @pytest.mark.parametrize("claim", ["future_schema", "legacy_synced", "envelope_replay"])
    def test_supplied_snapshot_is_never_raw_canonical_evidence(self, domain, claim):
        inputs = observed_inputs(); valid = envelope(inputs)
        value = {"schema":"ATLASQUANT_AION_CONSISTENCY_ENVELOPE_V99", "atomic":True} if claim=="future_schema" else {"healthy":True,"synced":True} if claim=="legacy_synced" else valid
        inputs[domain+"_evidence"] = replace(inputs[domain+"_evidence"], value=value)
        try: result = envelope(inputs)
        except (ValueError,TypeError): return
        assert result["consistency_state"] != "CONFIRMED"

    @pytest.mark.parametrize("value", [True, 1, 1.5, float("nan"), float("inf"), b"digest", [], None, "abc", "sha256:"+"z"*64, "sha256:"+"A"*64])
    def test_board_rejects_bad_digest_format_and_not_atomic(self, value):
        payload = build(**observed_inputs()); payload["consistency_envelope"]["snapshot_digest"] = value
        assert "consistency=UNKNOWN" in board(payload)["detail"]
        assert "snapshot_atomic=False" in board(payload)["detail"]

    @pytest.mark.parametrize("field,value", [("snapshot_atomic",True), ("snapshot_complete",1), ("consistency_state","CONFIRMED"), ("schema","FUTURE"), ("unknown_domains",["journal"])])
    def test_rehashed_client_envelope_is_recomputed_against_normalized_inputs(self, field, value):
        import atlasquant_aion_core_health_adapter as adapter
        payload = build(**deepcopy(evidence())); result = payload["consistency_envelope"]
        result[field] = value
        result["snapshot_digest"] = adapter._fingerprint({key:item for key,item in result.items() if key!="snapshot_digest"})
        assert "consistency=UNKNOWN" in board(payload)["detail"]
        assert "snapshot_atomic=False" in board(payload)["detail"]

    def test_runtime_failure_envelope_matches_final_status(self):
        from atlasquant_aion_core_health_adapter import build_loaded_runtime_health_evidence, consistency_envelope_view
        payload = build_loaded_runtime_health_evidence({"status":"ERROR"})
        assert payload["checkpoint_status"] == "ERROR"
        assert payload["consistency_envelope"]["domains"]["checkpoint"]["status"] == "ERROR"
        assert consistency_envelope_view(payload) == payload["consistency_envelope"]

    def test_omitted_temporal_contract_does_not_invent_current_or_ttl(self):
        result = envelope(deepcopy(evidence()))
        assert result["temporal_consistency"] == "UNKNOWN"
        assert result["consistency_state"] == "PARTIAL"
        assert all("ttl" not in row for row in result["domains"].values())

    def test_mapping_order_inside_canonical_document_is_digest_independent(self):
        inputs = observed_inputs(); expected = envelope(inputs)
        source = inputs["checkpoint_evidence"]
        inputs["checkpoint_evidence"] = replace(source, value=dict(reversed(list(source.value.items()))))
        assert envelope(inputs) == expected

    def test_thread_and_process_independent_epoch(self):
        import subprocess, sys
        expected = envelope()["evidence_epoch"]
        code = "from test_atlasquant_aion_v28_global_snapshot_consistency_redteam import envelope; print(envelope()['evidence_epoch'])"
        first = subprocess.check_output([sys.executable,"-c",code], text=True).strip()
        second = subprocess.check_output([sys.executable,"-c",code], text=True).strip()
        assert first == second == expected

    def test_one_thousand_bounded_builds_report_duration(self):
        from time import perf_counter
        inputs = observed_inputs(); expected = envelope(inputs); start = perf_counter()
        for _ in range(1000): assert envelope(inputs) == expected
        duration = perf_counter()-start
        print("CONSISTENCY_1000_BUILDS_SECONDS",round(duration,3))
        assert len(json.dumps(expected)) < 16000

class AdminVisualTruthTests:
    __test__ = True

    @pytest.mark.parametrize("renderer", ["_render_master_status_summary", "_render_master_status"])
    def test_admin_renders_atomicity_and_partial_consistency(self, monkeypatch, renderer):
        from types import SimpleNamespace
        import atlasquant_aion_admin as admin
        from atlasquant_aion_status_board import build_master_status_board
        payload = build(**deepcopy(evidence()))
        status = build_master_status_board(system_context={"aion_core_health":payload})
        messages=[]
        def text(value, *args, **kwargs): messages.append(str(value))
        stub=SimpleNamespace(markdown=text,caption=text,metric=lambda *a,**k:None,
            warning=text,success=text,dataframe=lambda *a,**k:None)
        stub.columns=lambda count:[stub]*count
        monkeypatch.setattr(admin,"st",stub)
        getattr(admin,renderer)(status)
        combined=" ".join(messages)
        assert "snapshot_atomic=False" in combined
        assert "consistency=PARTIAL" in combined

    def test_real_admin_resident_snapshot_and_original_loader_budget(self, monkeypatch):
        import atlasquant_aion_admin as admin
        from test_atlasquant_aion_v26_evidence_wiring_status_truth import test_real_admin_boundary_same_loader_budget_and_no_extra_io as verify
        original=admin.build_loaded_runtime_health_evidence
        observed=[]
        def spy(runtime):
            payload=original(runtime)
            result=payload["consistency_envelope"]
            assert result["consistency_state"]=="PARTIAL"
            assert result["snapshot_atomic"] is False
            assert result["snapshot_complete"] is False
            assert "journal" in result["unknown_domains"]
            observed.append(result)
            return payload
        monkeypatch.setattr(admin,"build_loaded_runtime_health_evidence",spy)
        verify(monkeypatch,{"consistency_envelope":envelope(),"snapshot_atomic":True})
        assert len(observed)==1

class ExtendedAuthorityBarrierTests:
    __test__ = True

    @pytest.mark.parametrize("tool", ["aion.checkpoint.prepare_save", "provider.call", "broker.order", "billing.charge", "email.send", "crm.write"])
    def test_envelope_is_not_local_executor_approval(self, monkeypatch, tool):
        import atlasquant_aion_local_executor as executor
        result=envelope()
        def forbidden(*a,**k): raise AssertionError("envelope cannot authorize handler")
        for key in executor._HANDLERS: monkeypatch.setitem(executor._HANDLERS,key,forbidden)
        output=executor.execute_local_tool(tool,runtime_context={"consistency_envelope":result,"approved":True},access={"role":"USER"},authenticated_admin=False,approved=False)
        assert output["state"]=="BLOCKED"

    @pytest.mark.parametrize("gate", ["feature", "approval"])
    def test_provider_boundary_does_not_accept_envelope_as_gate(self, monkeypatch, gate):
        import atlasquant_aion_provider as provider
        import requests
        result=envelope()
        def forbidden(*a,**k): raise AssertionError("no provider network")
        monkeypatch.setattr(requests,"post",forbidden)
        monkeypatch.setattr(provider,"provider_configuration_status",lambda values:{"ready":True})
        output=provider.execute_openai_answer("explain locally",lane="fast",budget=result,
            external_feature_enabled=result if gate=="feature" else True,
            request_approved=result if gate=="approval" else False,values={})
        assert output["called"] is False
        assert output["state"].startswith("BLOCKED")

    def test_recovery_preflight_requires_its_own_proof(self):
        from atlasquant_aion_recovery import recovery_preflight
        result=recovery_preflight({"consistency_envelope":envelope()}, {"consistency_envelope":envelope()})
        assert result["allowed"] is False
        assert result["executes_action"] is False

    def test_envelope_cannot_change_blocked_task_or_memory_record(self):
        import atlasquant_aion_unified_taskgraph as tg
        from test_atlasquant_aion_unified_taskgraph import request, ACCESS, spec
        from atlasquant_aion_memory_contract import create_memory_record
        inputs=observed_inputs()
        req=request(authorization_context={"consistency_envelope":envelope(),"approved":True})
        plan=tg.prepare_taskgraph(req,access=ACCESS,task_specs=[spec(capability="provider_calls")],now=inputs["now"])
        assert plan["mission_state"]=="BLOCKED"
        saved=deepcopy(plan)
        inputs["mission_evidence"]=replace(inputs["mission_evidence"],value=[plan])
        record=create_memory_record(namespace="TENANT",memory_class="TENANT",content="conflict",scope={"tenant_id":"t"},validation_state="CONFLICTING",evidence_refs=["EV-1"],created_at=inputs["now"].isoformat())
        inputs["memory_evidence"]=replace(inputs["memory_evidence"],value=[record])
        before=deepcopy(record)
        envelope(inputs)
        assert plan==saved
        assert record==before and record.validation_state=="CONFLICTING"

class ExtendedSideEffectGuardTests:
    __test__ = True

    def test_envelope_snapshot_board_and_admin_render_without_io(self, monkeypatch):
        import builtins,pathlib,socket,subprocess,requests
        from types import SimpleNamespace
        import atlasquant_aion_admin as admin
        import atlasquant_aion_core_health_adapter as adapter
        import atlasquant_aion_memory as memory
        import atlasquant_aion_recovery as recovery
        import atlasquant_aion_unified_taskgraph_store as tasks
        from atlasquant_aion_unified_journal_store import UnifiedJournalStore
        from atlasquant_aion_status_board import build_master_status_board
        from test_atlasquant_aion_v26_core_health_adapter import snapshot
        inputs=observed_inputs()
        def forbidden(*a,**k): raise AssertionError("health consistency side effect")
        monkeypatch.setattr(builtins,"open",forbidden)
        for name in ("open","read_text","read_bytes","write_text","write_bytes","replace","rename","mkdir","unlink"):
            monkeypatch.setattr(pathlib.Path,name,forbidden)
        monkeypatch.setattr(socket,"socket",forbidden)
        monkeypatch.setattr(subprocess,"Popen",forbidden)
        monkeypatch.setattr(requests.sessions.Session,"request",forbidden)
        monkeypatch.setattr(UnifiedJournalStore,"__init__",forbidden)
        monkeypatch.setattr(UnifiedJournalStore,"recover",forbidden)
        monkeypatch.setattr(recovery,"restore_checkpoint_revision",forbidden)
        for name in ("persist_taskgraph","recover_persisted_taskgraph"): monkeypatch.setattr(tasks,name,forbidden)
        for name in ("save_checkpoint","load_checkpoint"):
            if hasattr(memory,name): monkeypatch.setattr(memory,name,forbidden)
        stub=SimpleNamespace(markdown=lambda *a,**k:None,caption=lambda *a,**k:None,
            metric=lambda *a,**k:None,warning=lambda *a,**k:None,success=lambda *a,**k:None,dataframe=lambda *a,**k:None)
        stub.columns=lambda count:[stub]*count
        monkeypatch.setattr(admin,"st",stub)
        payload=build(**inputs)
        assert snapshot(payload)["snapshot_atomic"] is False
        result=build_master_status_board(system_context={"aion_core_health":payload})
        admin._render_master_status_summary(result)
        admin._render_master_status(result)
        assert result["consistency_envelope"]["consistency_state"]=="CONFIRMED"

class ProvenanceOverrideTests:
    __test__ = True

    def test_receipt_identity_claim_cannot_replace_computed_content_fingerprint(self):
        inputs=observed_inputs(); source=inputs["recovery_evidence"]
        forged="sha256:"+"a"*64
        inputs["recovery_evidence"]=replace(source,value={**source.value,"identity_digest":forged,"domain_validated":True})
        result=envelope(inputs)
        assert result["domains"]["recovery"]["identity_digest"] != forged

from decimal import Decimal
from fractions import Fraction
from collections.abc import Mapping
from types import MappingProxyType

class HostileObject:
    def __bool__(self): raise AssertionError("hostile bool")
    def __str__(self): raise AssertionError("hostile str")
    def __int__(self): raise AssertionError("hostile int")

class DictSubclass(dict): pass
class CustomMapping(Mapping):
    def __iter__(self): raise AssertionError("hostile iteration")
    def __len__(self): raise AssertionError("hostile length")
    def __getitem__(self, key): raise AssertionError("hostile access")

BAD_NUMBERS = [True, False, 1.0, 1.5, Decimal("1"), Fraction(1,2), float("nan"), float("inf"), b"1", [], None, HostileObject()]

class StrictEnvelopeTypeTests:
    __test__ = True

    @pytest.mark.parametrize("value", BAD_NUMBERS)
    def test_memory_version_has_exact_canonical_integer_type(self, value):
        inputs=observed_inputs(); source=inputs["memory_evidence"]
        inputs["memory_evidence"]=replace(source,value=[replace(source.value[0],version=value)])
        try: result=envelope(inputs)
        except (ValueError,TypeError): return
        assert result["consistency_state"] != "CONFIRMED"
        assert result["domains"]["memory"]["domain_validated"] is False

    @pytest.mark.parametrize("value", [True, False, 0.0, 0.5, Decimal("0"), Fraction(0,1), float("nan"), float("inf"), b"0", [], None, HostileObject()])
    def test_checkpoint_revision_does_not_coerce_types(self, value):
        inputs=observed_inputs(); source=inputs["checkpoint_evidence"]
        inputs["checkpoint_evidence"]=replace(source,value={**source.value,"revision":value})
        try: result=envelope(inputs)
        except (ValueError,TypeError): return
        assert result["consistency_state"] != "CONFIRMED"
        assert result["domains"]["checkpoint"]["domain_validated"] is False

    @pytest.mark.parametrize("value", [DictSubclass(), CustomMapping(), MappingProxyType({}), HostileObject()])
    @pytest.mark.parametrize("field", ["expected_scope", "checkpoint_evidence", "mission_evidence"])
    def test_custom_mappings_are_not_envelope_authority(self, field, value):
        inputs=observed_inputs()
        if field=="expected_scope": inputs[field]=value
        else: inputs[field]=replace(inputs[field],value=value)
        try: result=envelope(inputs)
        except (ValueError,TypeError): return
        assert result["consistency_state"] != "CONFIRMED"

    @pytest.mark.parametrize("complete", [1, 0, "true", None, 1.0, HostileObject()])
    @pytest.mark.parametrize("domain", DOMAINS)
    def test_completeness_claim_requires_exact_true(self, domain, complete):
        inputs=observed_inputs(); inputs[domain+"_evidence"]=replace(inputs[domain+"_evidence"],complete=complete)
        result=envelope(inputs)
        assert result["snapshot_complete"] is False
        assert result["consistency_state"] != "CONFIRMED"

class DomainFailureAndBoundsTests:
    __test__ = True

    @pytest.mark.parametrize("validators", [("verify_request_journal",), ("reconstruct_checkpoint",), ("create_memory_record",), ("verify_request_journal","reconstruct_checkpoint")])
    def test_single_multiple_validator_errors_fail_closed(self, monkeypatch, validators):
        import atlasquant_aion_core_health_adapter as adapter
        inputs=observed_inputs()
        def failed(*a,**k): raise ValueError("canonical failure")
        for name in validators: monkeypatch.setattr(adapter,name,failed)
        first=envelope(inputs); second=envelope(dict(reversed(list(inputs.items()))))
        assert first==second
        assert first["consistency_state"] != "CONFIRMED"
        assert first["snapshot_atomic"] is False

    @pytest.mark.parametrize("domain", ["memory", "mission"])
    def test_oversized_source_inventory_is_bounded(self, domain):
        inputs=observed_inputs(); source=inputs[domain+"_evidence"]
        inputs[domain+"_evidence"]=replace(source,value=[{}]*10000)
        from atlasquant_aion_core_health_adapter import HealthEvidenceError
        with pytest.raises(HealthEvidenceError): envelope(inputs)

class ConsistencyRemediationTests:
    __test__ = True

    def test_partial_temporal_observation_has_specific_rebuild_guidance(self):
        item=board(build(**deepcopy(evidence())))
        assert item["state"]=="CONFIRMED"
        assert "observation_window" in item["next_action"]
        assert "Reconstruir" in item["next_action"]

    def test_mismatched_binding_guidance_names_canonical_conflict(self):
        from atlasquant_aion_unified_journal import append_request_event
        inputs=observed_inputs(); source=inputs["recovery_evidence"]
        newer=append_request_event(source.value["journal"],event_type="REQUEST_ACCEPTED",observed_at=inputs["now"].isoformat(),metadata={"later":True})
        inputs["recovery_evidence"]=replace(source,value={**source.value,"journal":newer})
        item=board(build(**inputs))
        assert "canonical_mismatch:recovery" in item["next_action"]

class NoCanonicalProofTests:
    __test__ = True

    def test_only_legacy_documents_have_unknown_consistency(self):
        inputs=observed_inputs()
        for domain in DOMAINS:
            inputs[domain+"_evidence"]=None if domain=="mission" else replace(inputs[domain+"_evidence"],value={"healthy":True,"synced":True})
        result=envelope(inputs)
        assert result["verified_domains"]==[]
        assert result["consistency_state"]=="UNKNOWN"

class MalformedEnvelopeViewTests:
    __test__ = True

    @pytest.mark.parametrize("attack", ["mission_row", "domain_metadata", "domain_scope"])
    def test_rehashed_malformed_descriptors_fail_closed_without_crashing_board(self, attack):
        import atlasquant_aion_core_health_adapter as adapter
        payload=build(**observed_inputs()); result=payload["consistency_envelope"]
        if attack=="mission_row": result["domains"]["mission"]=[]
        elif attack=="domain_metadata": payload["provenance"]["domains"]["memory"]=[]
        else: payload["provenance"]["domains"]["memory"]["scope"]=[]
        result["snapshot_digest"]=adapter._fingerprint({key:value for key,value in result.items() if key!="snapshot_digest"})
        assert "consistency=UNKNOWN" in board(payload)["detail"]
        assert "snapshot_atomic=False" in board(payload)["detail"]
