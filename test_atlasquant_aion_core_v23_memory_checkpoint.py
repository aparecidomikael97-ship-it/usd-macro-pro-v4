from __future__ import annotations

import math
import unittest

from atlasquant_aion_memory_contract import (
    MEMORY_CLASSES,
    MEMORY_NAMESPACES,
    MemoryContractError,
    create_memory_record,
    memory_contract_digest,
    normalize_lesson,
    operational_decision,
    to_architecture_record,
    validate_library_document_contract,
    validation_mapping,
)
from atlasquant_aion_checkpoint_master import (
    MAX_EVENT_BYTES,
    CheckpointConflict,
    CheckpointIntegrityError,
    CheckpointMasterError,
    append_checkpoint_patch,
    checkpoint_master_digest,
    compact_checkpoint,
    future_signature_hook,
    new_checkpoint_master,
    reconstruct_checkpoint,
    rollback_candidate,
)


class AtlasQuantAionCoreV23MemoryContractTests(unittest.TestCase):
    def test_namespaces_and_seven_classes_are_explicit(self):
        self.assertIn("TENANT",MEMORY_NAMESPACES)
        self.assertIn("PERSONA",MEMORY_NAMESPACES)
        self.assertIn("LESSON",MEMORY_NAMESPACES)
        self.assertEqual(len(MEMORY_CLASSES),7)

    def test_validated_memory_requires_evidence_or_provenance(self):
        with self.assertRaises(MemoryContractError):
            create_memory_record(
                namespace="PROJECT",
                memory_class="SEMANTIC",
                content="fato",
                scope={"project_id":"atlasquant"},
                validation_state="VALIDATED",
            )
        record=create_memory_record(
            namespace="PROJECT",
            memory_class="SEMANTIC",
            content="fato",
            scope={"project_id":"atlasquant"},
            validation_state="VALIDATED",
            evidence_refs=["EV-1"],
        )
        decision=operational_decision(record)
        self.assertTrue(decision["allowed_for_operational_use"])
        self.assertEqual(decision["truth_state"],"CONFIRMED")
        self.assertFalse(decision["execution_allowed"])

    def test_conflicting_memory_creates_explicit_blocker(self):
        record=create_memory_record(
            namespace="EVIDENCE",
            memory_class="SEMANTIC",
            content="fontes divergem",
            validation_state="CONFLICTING",
            evidence_refs=["EV-A","EV-B"],
        )
        decision=operational_decision(record)
        self.assertFalse(decision["allowed_for_operational_use"])
        self.assertIn("CONFLICT_BLOCKER",decision["blockers"])
        self.assertEqual(decision["truth_state"],"UNKNOWN")

    def test_absence_of_evidence_never_becomes_fact(self):
        record=create_memory_record(
            namespace="SUBJECT",
            memory_class="SEMANTIC",
            content="hipotese",
            validation_state="UNVERIFIED",
        )
        decision=operational_decision(record)
        self.assertFalse(decision["allowed_for_operational_use"])
        self.assertEqual(decision["truth_state"],"UNKNOWN")
        self.assertIn("EVIDENCE_NOT_VALIDATED",decision["blockers"])

    def test_truth_and_architecture_state_mapping_is_compatible(self):
        self.assertEqual(validation_mapping("OUTDATED")["architecture_state"],"STALE")
        self.assertEqual(validation_mapping("DOUBTFUL")["truth_state"],"HYPOTHESIS")
        self.assertEqual(validation_mapping("PROPOSED")["architecture_state"],"CANDIDATE")

    def test_tenant_persona_sector_and_version_scope_fail_closed(self):
        with self.assertRaises(MemoryContractError):
            create_memory_record(namespace="TENANT",memory_class="TENANT",content="x")
        with self.assertRaises(MemoryContractError):
            create_memory_record(namespace="PERSONA",memory_class="EPISODIC",content="x")
        with self.assertRaises(MemoryContractError):
            create_memory_record(namespace="SECTOR",memory_class="DOMAIN",content="x")
        with self.assertRaises(MemoryContractError):
            create_memory_record(
                namespace="PROJECT",memory_class="SEMANTIC",content="v2",
                scope={"project_id":"atlasquant"},version=2,
            )

    def test_restricted_memory_requires_tenant_or_admin(self):
        with self.assertRaises(MemoryContractError):
            create_memory_record(
                namespace="PROJECT",
                memory_class="SEMANTIC",
                content="segredo",
                scope={"project_id":"atlasquant"},
                sensitivity="RESTRICTED",
            )
        record=create_memory_record(
            namespace="TENANT",
            memory_class="TENANT",
            content="segredo tenant",
            scope={"tenant_id":"T-A"},
            sensitivity="RESTRICTED",
        )
        self.assertEqual(record.sensitivity,"RESTRICTED")

    def test_tombstone_never_validated(self):
        with self.assertRaises(MemoryContractError):
            create_memory_record(
                namespace="DECISION",
                memory_class="SEMANTIC",
                content="",
                tombstone=True,
                validation_state="VALIDATED",
                evidence_refs=["EV-1"],
            )

    def test_adapter_reuses_existing_memory_architecture(self):
        record=create_memory_record(
            namespace="SECTOR",
            memory_class="DOMAIN",
            content="regra core",
            scope={"sector_id":"CORE"},
            validation_state="VALIDATED",
            evidence_refs=["EV-CORE"],
        )
        architecture=to_architecture_record(record)
        self.assertEqual(architecture.layer,"DOMAIN")
        self.assertEqual(architecture.state,"VALIDATED")
        self.assertEqual(architecture.domain_id,"CORE")

    def test_memory_digest_is_deterministic(self):
        kwargs=dict(
            namespace="PROJECT",
            memory_class="SEMANTIC",
            content="mesmo conteudo",
            scope={"project_id":"atlasquant"},
            created_at="2026-10-04T00:00:00+00:00",
        )
        a=create_memory_record(**kwargs)
        b=create_memory_record(**kwargs)
        self.assertEqual(a.memory_id,b.memory_id)
        self.assertEqual(memory_contract_digest(a),memory_contract_digest(b))

    def test_lessons_are_not_global_rules(self):
        with self.assertRaises(MemoryContractError):
            normalize_lesson({"lesson":"aprendido"},state="VALIDATED")
        lesson=normalize_lesson(
            {"lesson":"aprendido","evidence_refs":["EV-LESSON"]},
            state="VALIDATED",
        )
        self.assertEqual(lesson["state"],"VALIDATED")
        self.assertFalse(lesson["global_rule"])
        self.assertFalse(lesson["automatic_policy_change"])

    def test_library_contract_requires_provenance_for_validated_state(self):
        base={
            "document_id":"DOC-1","hash":"sha256:x","version":"1","author":"A",
            "date":"2026-01-01","origin":"book","subject":"core",
            "evidence_refs":[],"excerpts":[],"quality":"HIGH","conflict":False,
            "status":"VALIDATED","superseded_by":"","provenance_chain":[],
        }
        invalid=validate_library_document_contract(base)
        self.assertFalse(invalid["valid"])
        fixed=dict(base)
        fixed["evidence_refs"]=["EV-1"]
        fixed["provenance_chain"]=["PRV-1"]
        valid=validate_library_document_contract(fixed)
        self.assertTrue(valid["valid"])
        self.assertFalse(valid["embeddings_executed"])
        self.assertFalse(valid["provider_call_executed"])


class AtlasQuantAionCoreV23CheckpointTests(unittest.TestCase):
    def master(self):
        return new_checkpoint_master(
            {
                "project":"AtlasQuant",
                "task":{"state":"PLANNED","value":0},
                "memory":{"items":[]},
            },
            created_at="2026-10-04T00:00:00+00:00",
            source_refs=[
                "AION_CORE_NIGHTSHIFT_CHECKPOINT.json",
                "CONTEXTO_DO_PROJETO.md",
                "HISTORICO_DE_ALTERACOES.md",
                "PENDENCIAS_MIKAEL.md",
            ],
        )

    def test_new_master_is_read_only_and_reconstructs_exactly(self):
        master=self.master()
        replay=reconstruct_checkpoint(master)
        self.assertEqual(replay["snapshot"]["project"],"AtlasQuant")
        self.assertEqual(replay["revision"],0)
        self.assertFalse(master["external_action_executed"])
        self.assertFalse(master["execution_allowed"])
        self.assertFalse(master["real_orders_enabled"])

    def test_append_patch_and_replay_are_deterministic(self):
        master=self.master()
        changed=append_checkpoint_patch(
            master,
            event_id="EV-1",
            patch={"task":{"value":1}},
            expected_revision=0,
            created_at="2026-10-04T00:01:00+00:00",
            evidence_refs=["EVSRC-1"],
        )
        a=reconstruct_checkpoint(changed)
        b=reconstruct_checkpoint(changed)
        self.assertEqual(a,b)
        self.assertEqual(a["snapshot"]["task"]["value"],1)
        self.assertEqual(a["revision"],1)

    def test_stale_writer_is_rejected_by_expected_revision(self):
        master=self.master()
        changed=append_checkpoint_patch(
            master,event_id="EV-A",patch={"x":1},expected_revision=0,
        )
        with self.assertRaises(CheckpointConflict):
            append_checkpoint_patch(
                changed,event_id="EV-B",patch={"x":2},expected_revision=0,
            )

    def test_duplicate_same_id_same_payload_is_idempotent(self):
        master=self.master()
        changed=append_checkpoint_patch(
            master,event_id="EV-A",patch={"x":1},expected_revision=0,
        )
        replay=append_checkpoint_patch(
            changed,event_id="EV-A",patch={"x":1},expected_revision=1,
        )
        self.assertEqual(replay,changed)

    def test_duplicate_same_id_different_payload_is_conflict(self):
        master=self.master()
        changed=append_checkpoint_patch(
            master,event_id="EV-A",patch={"x":1},expected_revision=0,
        )
        with self.assertRaises(CheckpointConflict):
            append_checkpoint_patch(
                changed,event_id="EV-A",patch={"x":2},expected_revision=1,
            )

    def test_replay_cannot_promote_planned_to_executed(self):
        master=self.master()
        with self.assertRaises(CheckpointMasterError):
            append_checkpoint_patch(
                master,
                event_id="EV-EXEC",
                patch={"task":{"state":"EXECUTED"}},
                expected_revision=0,
            )
        self.assertEqual(reconstruct_checkpoint(master)["snapshot"]["task"]["state"],"PLANNED")

    def test_execution_flags_cannot_be_enabled_by_patch(self):
        master=self.master()
        for key in ("external_action_executed","execution_allowed","real_orders_enabled"):
            with self.subTest(key=key):
                with self.assertRaises(CheckpointMasterError):
                    append_checkpoint_patch(
                        master,event_id=f"EV-{key}",
                        patch={key:True},expected_revision=0,
                    )

    def test_merge_patch_delete_is_deterministic(self):
        master=self.master()
        changed=append_checkpoint_patch(
            master,event_id="EV-DEL",
            patch={"memory":None},
            expected_revision=0,
        )
        self.assertNotIn("memory",reconstruct_checkpoint(changed)["snapshot"])

    def test_rollback_candidate_is_review_only(self):
        master=self.master()
        one=append_checkpoint_patch(master,event_id="EV-1",patch={"task":{"value":1}},expected_revision=0)
        two=append_checkpoint_patch(one,event_id="EV-2",patch={"task":{"value":2}},expected_revision=1)
        candidate=rollback_candidate(two,target_revision=1)
        self.assertEqual(candidate["snapshot"]["task"]["value"],1)
        self.assertTrue(candidate["requires_explicit_approval"])
        self.assertFalse(candidate["automatic_rollback"])
        self.assertFalse(candidate["execution_allowed"])

    def test_compaction_preserves_state_and_revision(self):
        master=self.master()
        one=append_checkpoint_patch(master,event_id="EV-1",patch={"x":1},expected_revision=0)
        two=append_checkpoint_patch(one,event_id="EV-2",patch={"y":2},expected_revision=1)
        before=reconstruct_checkpoint(two)
        compacted=compact_checkpoint(two,expected_revision=2)
        after=reconstruct_checkpoint(compacted)
        self.assertEqual(before["snapshot"],after["snapshot"])
        self.assertEqual(before["state_digest"],after["state_digest"])
        self.assertEqual(after["revision"],2)
        self.assertEqual(compacted["journal"],[])
        self.assertEqual(compacted["compaction_generation"],1)

    def test_tampered_patch_is_detected(self):
        master=self.master()
        changed=append_checkpoint_patch(master,event_id="EV-1",patch={"x":1},expected_revision=0)
        changed["journal"][0]["patch"]["x"]=999
        with self.assertRaises(CheckpointIntegrityError):
            reconstruct_checkpoint(changed)

    def test_tampered_chain_is_detected(self):
        master=self.master()
        one=append_checkpoint_patch(master,event_id="EV-1",patch={"x":1},expected_revision=0)
        two=append_checkpoint_patch(one,event_id="EV-2",patch={"y":2},expected_revision=1)
        two["journal"][1]["prev_digest"]="sha256:"+"0"*64
        with self.assertRaises(CheckpointIntegrityError):
            reconstruct_checkpoint(two)

    def test_nonfinite_and_oversized_payloads_fail_closed(self):
        with self.assertRaises(CheckpointMasterError):
            new_checkpoint_master({"x":math.inf})
        master=self.master()
        with self.assertRaises(CheckpointMasterError):
            append_checkpoint_patch(
                master,event_id="EV-BIG",
                patch={"blob":"x"*(MAX_EVENT_BYTES+100)},
                expected_revision=0,
            )

    def test_original_snapshot_survives_failed_append(self):
        master=self.master()
        original=checkpoint_master_digest(master)
        with self.assertRaises(CheckpointMasterError):
            append_checkpoint_patch(
                master,event_id="EV-BAD",
                patch={"execution_allowed":True},
                expected_revision=0,
            )
        self.assertEqual(checkpoint_master_digest(master),original)
        self.assertEqual(reconstruct_checkpoint(master)["revision"],0)

    def test_future_signature_hook_is_inactive_and_digest_bound(self):
        master=self.master()
        hook=future_signature_hook(master)
        self.assertEqual(hook["digest_to_sign"],checkpoint_master_digest(master))
        self.assertFalse(hook["active"])
        self.assertFalse(hook["biometric_capture_performed"])
        self.assertFalse(hook["signature_performed"])
        self.assertFalse(hook["execution_allowed"])

    def test_master_digest_is_deterministic_for_same_state(self):
        a=self.master()
        b=self.master()
        self.assertEqual(checkpoint_master_digest(a),checkpoint_master_digest(b))


if __name__=="__main__":
    unittest.main()
