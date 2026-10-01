import unittest

from aion_core.provenance import (
    ProvenanceError,
    create_provenance,
    derive_provenance,
    mark_provenance_conflicting,
    mark_provenance_stale,
    provenance_access_allowed,
    provenance_digest,
    provenance_lineage,
    validate_provenance,
)


def base_prov(**kw):
    params = dict(
        source_type="BOOK",
        source_reference="isbn:978-0-000-00000-0",
        source_title="Livro de exemplo",
        author="Autor Exemplo",
        publisher="Editora Exemplo",
        published_at="2020-01-15",
        retrieved_at="2026-10-01T00:00:00+00:00",
        document_version="1st",
        checksum="sha256:abc123",
        tenant_id="T-A",
        domain_id="BIBLIOTECA",
    )
    params.update(kw)
    return create_provenance(**params)


class ProvenanceTests(unittest.TestCase):
    def test_valid_creation(self):
        record = base_prov()
        self.assertTrue(record.provenance_id.startswith("PRV-"))
        self.assertEqual(record.review_status, "UNREVIEWED")

    def test_unknown_stays_unknown(self):
        record = create_provenance(source_type="unknown")
        self.assertEqual(record.source_type, "UNKNOWN")
        decision = validate_provenance(record)
        self.assertFalse(decision["validatable"])
        self.assertIn("unknown_source_type", decision["reasons"])

    def test_source_reference_preserved(self):
        record = base_prov(source_reference="https://exemplo.gov.br/doc/42")
        self.assertEqual(record.source_reference, "https://exemplo.gov.br/doc/42")

    def test_digest_deterministic(self):
        a = base_prov()
        b = base_prov()
        self.assertEqual(provenance_digest(a), provenance_digest(b))

    def test_material_change_changes_digest(self):
        a = base_prov()
        b = base_prov(published_at="2021-01-15")
        self.assertNotEqual(provenance_digest(a), provenance_digest(b))

    def test_metadata_order_does_not_change_digest(self):
        a = base_prov(metadata={"z": "1", "a": "2"})
        b = base_prov(metadata={"a": "2", "z": "1"})
        self.assertEqual(provenance_digest(a), provenance_digest(b))

    def test_tenant_and_domain_preserved(self):
        record = base_prov(tenant_id="T-9", domain_id="trader")
        self.assertEqual(record.tenant_id, "T-9")
        self.assertEqual(record.domain_id, "TRADER")

    def test_tenant_a_cannot_access_private_b(self):
        record = base_prov(tenant_id="T-B")
        decision = provenance_access_allowed(record, requesting_tenant_id="T-A")
        self.assertFalse(decision["allowed"])
        self.assertIn("tenant_mismatch", decision["reasons"])
        self.assertTrue(provenance_access_allowed(record, requesting_tenant_id="T-B")["allowed"])

    def test_derived_keeps_parents(self):
        p1 = base_prov()
        p2 = base_prov(source_reference="isbn:978-1-111-11111-1")
        derived = derive_provenance(parents=[p1, p2], analysis_note="comparacao")
        self.assertEqual(derived.source_type, "DERIVED_ANALYSIS")
        self.assertEqual(set(derived.parent_provenance_ids), {p1.provenance_id, p2.provenance_id})

    def test_derived_requires_parents(self):
        with self.assertRaises(ProvenanceError):
            derive_provenance(parents=[])

    def test_lineage_walks_chain(self):
        root = base_prov()
        mid = derive_provenance(parents=[root], analysis_note="etapa1")
        top = derive_provenance(parents=[mid], analysis_note="etapa2")
        known = {root.provenance_id: root, mid.provenance_id: mid, top.provenance_id: top}
        chain = provenance_lineage(top, known)
        self.assertIn(mid.provenance_id, chain)
        self.assertIn(root.provenance_id, chain)

    def test_explicit_validation(self):
        record = base_prov()
        decision = validate_provenance(record)
        self.assertTrue(decision["validatable"])
        self.assertEqual(decision["record"].review_status, "VALIDATED")

    def test_stale_explicit(self):
        record = base_prov()
        validated = validate_provenance(record)["record"]
        stale = mark_provenance_stale(validated, reason="nova_edicao")
        self.assertEqual(stale.review_status, "STALE")
        self.assertEqual(stale.metadata.get("stale_reason"), "nova_edicao")

    def test_conflicting_explicit(self):
        record = base_prov()
        validated = validate_provenance(record)["record"]
        conflicting = mark_provenance_conflicting(validated, conflict_ref="PRV-X")
        self.assertEqual(conflicting.review_status, "CONFLICTING")

    def test_invalid_transition_fails_closed(self):
        record = base_prov()
        with self.assertRaises(ProvenanceError):
            mark_provenance_stale(record)  # UNREVIEWED -> STALE not allowed

    def test_rejected_does_not_disappear(self):
        record = base_prov()
        quarantined = None
        from aion_core.provenance import _transition
        quarantined = _transition(record, "QUARANTINED")
        rejected = _transition(quarantined, "REJECTED")
        self.assertEqual(rejected.review_status, "REJECTED")
        self.assertTrue(rejected.provenance_id)  # record still exists for audit
        with self.assertRaises(ProvenanceError):
            _transition(rejected, "VALIDATED")  # terminal

    def test_confidence_bounded(self):
        record = base_prov(confidence=5.0)
        self.assertLessEqual(record.confidence, 1.0)
        self.assertEqual(base_prov(confidence="abc").confidence, 0.0)

    def test_missing_critical_origin_flagged(self):
        record = create_provenance(source_type="WEB", source_reference="", checksum="")
        decision = validate_provenance(record)
        self.assertFalse(decision["validatable"])
        self.assertIn("source_reference_missing", decision["reasons"])
        self.assertIn("checksum_missing", decision["warnings"])


if __name__ == "__main__":
    unittest.main()
