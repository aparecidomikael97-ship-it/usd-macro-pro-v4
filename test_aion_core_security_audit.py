import unittest
from datetime import datetime, timezone

from aion_core.provenance import (
    create_provenance,
    provenance_access_allowed,
    validate_provenance,
    ProvenanceError,
    _transition,
)
from aion_core.trust_engine import assess_claim, create_evidence_item, independent_source_count

NOW = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)


def prov(**kw):
    p = dict(source_type="BOOK", source_reference="isbn:x", checksum="sha256:a",
             published_at="2020-01-01", tenant_id="T-A", domain_id="TRADER")
    p.update(kw)
    return create_provenance(**p)


class SecurityAuditTests(unittest.TestCase):
    # A. UNREVIEWED -> VALIDATED only via explicit controlled operation
    def test_validation_is_explicit_operation(self):
        record = prov()
        self.assertEqual(record.review_status, "UNREVIEWED")
        # no mutation in place: original stays UNREVIEWED
        decision = validate_provenance(record)
        self.assertEqual(record.review_status, "UNREVIEWED")
        self.assertEqual(decision["record"].review_status, "VALIDATED")

    def test_validation_without_reference_fails_closed(self):
        record = prov(source_reference="")
        decision = validate_provenance(record)
        self.assertFalse(decision["validatable"])
        self.assertIn("source_reference_missing", decision["reasons"])

    def test_terminal_rejected_cannot_be_revalidated(self):
        record = prov()
        q = _transition(record, "QUARANTINED")
        r = _transition(q, "REJECTED")
        with self.assertRaises(ProvenanceError):
            _transition(r, "VALIDATED")

    # B. Cross-domain isolation: unknown / different / missing authorization
    def test_unknown_requesting_domain_denied_for_private(self):
        record = prov(domain_id="TRADER")
        decision = provenance_access_allowed(record, requesting_tenant_id="T-A", requesting_domain_id="NAO_EXISTE")
        self.assertFalse(decision["allowed"])
        self.assertIn("cross_domain_requires_explicit_permission", decision["reasons"])

    def test_different_domain_denied_without_permission(self):
        record = prov(domain_id="TRADER")
        decision = provenance_access_allowed(record, requesting_tenant_id="T-A", requesting_domain_id="NEGOCIOS")
        self.assertFalse(decision["allowed"])

    def test_missing_context_denied_for_tenant_private(self):
        record = prov(tenant_id="T-A")
        decision = provenance_access_allowed(record)  # no tenant, no domain, no admin
        self.assertFalse(decision["allowed"])
        self.assertIn("tenant_mismatch", decision["reasons"])

    def test_explicit_permission_allows_cross_domain(self):
        record = prov(domain_id="TRADER")
        decision = provenance_access_allowed(record, requesting_tenant_id="T-A",
                                             requesting_domain_id="NEGOCIOS",
                                             explicit_cross_domain_permission=True)
        self.assertTrue(decision["allowed"])

    # C. Trust engine determinism and shared lineage
    def test_order_independence(self):
        a = create_evidence_item(claim_id="C1", claim="x", source_fingerprint="fp-a",
                                 independence_group="g1", confidence=0.9, provenance_id="P1")
        b = create_evidence_item(claim_id="C1", claim="x", source_fingerprint="fp-b",
                                 independence_group="g2", confidence=0.9, provenance_id="P2")
        r1 = assess_claim([a, b], now=NOW)
        r2 = assess_claim([b, a], now=NOW)
        self.assertEqual(r1.assessment_digest, r2.assessment_digest)

    def test_shared_lineage_not_independent(self):
        items = [create_evidence_item(claim_id="C1", claim="x", source_fingerprint=f"fp-{i}",
                                      independence_group="same-lineage", confidence=0.9,
                                      provenance_id=f"P{i}") for i in range(5)]
        self.assertEqual(independent_source_count(items), 1)
        result = assess_claim(items, now=NOW)
        self.assertEqual(result.supporting_independent_sources, 1)


if __name__ == "__main__":
    unittest.main()
