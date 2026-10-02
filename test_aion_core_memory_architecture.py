import unittest

from aion_core.memory_architecture import (
    MemoryArchitectureError,
    create_record,
    list_history,
    mark_conflicting,
    mark_stale,
    new_store,
    put_record,
    quarantine,
    read_allowed,
    read_record,
    reject,
    supersede,
    validate_record,
)


def tenant_record(tenant="T-A", layer="TENANT", content="fato do tenant"):
    return create_record(layer=layer, content=content, tenant_id=tenant)


class MemoryArchitectureTests(unittest.TestCase):
    def test_creates_candidate(self):
        record = create_record(layer="WORKING", content="contexto transitório")
        self.assertEqual(record.state, "CANDIDATE")
        self.assertTrue(record.memory_id.startswith("MAM-"))

    def test_candidate_not_validated(self):
        record = create_record(layer="SEMANTIC", content="fato")
        decision = read_allowed(record, requesting_tenant_id="", requesting_domain_id="")
        self.assertFalse(decision["state_visible_as_valid"])

    def test_explicit_validation(self):
        record = create_record(layer="SEMANTIC", content="fato")
        validated = validate_record(record, reviewer="admin")
        self.assertEqual(validated.state, "VALIDATED")
        self.assertEqual(validated.metadata.get("reviewer"), "admin")

    def test_invalid_transition_fails(self):
        record = create_record(layer="WORKING", content="x")
        with self.assertRaises(MemoryArchitectureError):
            validate_record(quarantine(record))  # QUARANTINED -> VALIDATED not allowed
        rejected = reject(record)
        with self.assertRaises(MemoryArchitectureError):
            validate_record(rejected)  # REJECTED terminal

    def test_quarantine_hidden_from_operational_read(self):
        record = create_record(layer="WORKING", content="suspeito")
        store = put_record(new_store(), record)
        store = put_record(store, quarantine(record, reason="review"))
        # the stored row must now be QUARANTINED
        result = read_record(store, record.memory_id)
        self.assertTrue(result["found"])
        self.assertFalse(result["allowed"])
        self.assertIn("quarantined_not_operational", result["reasons"])

    def test_reject_preserves_record(self):
        record = create_record(layer="EPISODIC", content="evento")
        store = put_record(new_store(), reject(record, reason="duplicado"))
        history = list_history(store, memory_id=record.memory_id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["state"], "REJECTED")

    def test_supersede_preserves_predecessor(self):
        old = create_record(layer="SEMANTIC", content="regra v1")
        new = create_record(layer="SEMANTIC", content="regra v2", version="2")
        store = put_record(new_store(), supersede(old, successor_id=new.memory_id))
        store = put_record(store, new)
        history = list_history(store)
        states = {row["memory_id"]: row["state"] for row in history}
        self.assertEqual(states[old.memory_id], "SUPERSEDED")
        self.assertEqual(states[new.memory_id], "CANDIDATE")
        self.assertEqual(history[0]["metadata"].get("superseded_by"), new.memory_id)

    def test_tenant_layer_requires_tenant_id(self):
        with self.assertRaises(MemoryArchitectureError):
            create_record(layer="TENANT", content="x")

    def test_domain_layer_requires_domain_id(self):
        with self.assertRaises(MemoryArchitectureError):
            create_record(layer="DOMAIN", content="x")

    def test_tenant_a_cannot_read_tenant_b(self):
        record = tenant_record(tenant="T-A")
        decision = read_allowed(record, requesting_tenant_id="T-B")
        self.assertFalse(decision["allowed"])
        self.assertIn("tenant_mismatch", decision["reasons"])

    def test_tenant_reads_own_memory(self):
        record = tenant_record(tenant="T-A")
        decision = read_allowed(record, requesting_tenant_id="T-A")
        self.assertTrue(decision["allowed"])

    def test_domain_a_cannot_read_domain_b_by_default(self):
        record = create_record(layer="DOMAIN", content="regra trader", domain_id="TRADER")
        decision = read_allowed(record, requesting_domain_id="NEGOCIOS")
        self.assertFalse(decision["allowed"])
        self.assertIn("cross_domain_requires_explicit_permission", decision["reasons"])

    def test_cross_domain_explicit_works(self):
        record = create_record(layer="DOMAIN", content="regra trader", domain_id="TRADER")
        decision = read_allowed(record, requesting_domain_id="NEGOCIOS", explicit_cross_domain_permission=True)
        self.assertTrue(decision["allowed"])

    def test_admin_layer_not_readable_by_regular_user(self):
        record = create_record(layer="ADMIN", content="config admin")
        decision = read_allowed(record, is_admin=False)
        self.assertFalse(decision["allowed"])
        self.assertIn("admin_layer_requires_admin", decision["reasons"])
        self.assertTrue(read_allowed(record, is_admin=True)["allowed"])

    def test_conflicting_not_shown_as_valid(self):
        record = create_record(layer="SEMANTIC", content="prazo 10 dias")
        validated = validate_record(record)
        conflicting = mark_conflicting(validated, conflict_ref="doc-b")
        decision = read_allowed(conflicting)
        self.assertFalse(decision["state_visible_as_valid"])

    def test_stale_stays_marked(self):
        record = create_record(layer="SEMANTIC", content="preço atual")
        validated = validate_record(record)
        stale = mark_stale(validated, reason="realtime_expired")
        self.assertEqual(stale.state, "STALE")
        self.assertEqual(stale.metadata.get("stale_reason"), "realtime_expired")
        self.assertFalse(read_allowed(stale)["state_visible_as_valid"])

    def test_repetition_does_not_promote(self):
        record = create_record(layer="SEMANTIC", content="mesmo fato")
        store = new_store()
        for _ in range(50):
            store = put_record(store, record)
        rows = list_history(store, memory_id=record.memory_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["state"], "CANDIDATE")

    def test_list_history_preserves_chain(self):
        r1 = create_record(layer="SEMANTIC", content="v1")
        r2 = create_record(layer="SEMANTIC", content="v2", version="2")
        r3 = create_record(layer="SEMANTIC", content="v3", version="3")
        store = new_store()
        store = put_record(store, r1)
        store = put_record(store, supersede(r1, successor_id=r2.memory_id))
        store = put_record(store, r2)
        store = put_record(store, supersede(r2, successor_id=r3.memory_id))
        store = put_record(store, r3)
        history = list_history(store)
        by_id = {row["memory_id"]: row for row in history}
        self.assertEqual(by_id[r1.memory_id]["state"], "SUPERSEDED")
        self.assertEqual(by_id[r2.memory_id]["state"], "SUPERSEDED")
        self.assertEqual(by_id[r3.memory_id]["state"], "CANDIDATE")

    def test_deterministic_ids(self):
        a = create_record(layer="WORKING", content="x", created_at="2026-10-01T00:00:00+00:00")
        b = create_record(layer="WORKING", content="x", created_at="2026-10-01T00:00:00+00:00")
        self.assertEqual(a.memory_id, b.memory_id)


if __name__ == "__main__":
    unittest.main()
