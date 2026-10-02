import unittest
from datetime import datetime, timezone

from aion_core.trust_engine import (
    TrustEngineError,
    assess_claim,
    create_evidence_item,
    deduplicate_evidence,
    independent_source_count,
    trust_assessment_digest,
)

NOW = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)


def item(fingerprint="fp-1", group="g1", **kw):
    params = dict(
        claim_id="CLM-1",
        claim="afirmacao de teste",
        source_fingerprint=fingerprint,
        source_type="BOOK",
        authority=0.8,
        primary_source=False,
        independence_group=group,
        freshness_class="STATIC",
        published_at="2020-01-01T00:00:00+00:00",
        confidence=0.9,
        provenance_id="PRV-1",
    )
    params.update(kw)
    return create_evidence_item(**params)


class TrustEngineTests(unittest.TestCase):
    def test_single_trusted_source(self):
        result = assess_claim([item()], now=NOW)
        self.assertEqual(result.status, "WEAKLY_SUPPORTED")
        self.assertEqual(result.supporting_independent_sources, 1)
        self.assertTrue(result.reason_codes)

    def test_single_unknown_source(self):
        result = assess_claim([item(source_type="UNKNOWN", provenance_id="", authority=0.2)], now=NOW)
        self.assertIn("UNKNOWN_ORIGIN_PRESENT", result.reason_codes)
        self.assertLess(result.confidence, 0.5)

    def test_two_independent_sources(self):
        result = assess_claim([item(fingerprint="fp-1", group="g1"), item(fingerprint="fp-2", group="g2")], now=NOW)
        self.assertEqual(result.status, "SUPPORTED")
        self.assertEqual(result.supporting_independent_sources, 2)

    def test_duplicates_counted_once(self):
        dupes = [item(fingerprint="fp-same") for _ in range(10)]
        result = assess_claim(dupes, now=NOW)
        self.assertEqual(result.duplicate_sources_ignored, 9)
        self.assertEqual(result.supporting_independent_sources, 1)
        self.assertIn("DUPLICATES_DEDUPLICATED", result.reason_codes)

    def test_real_conflict_between_independent(self):
        support = item(fingerprint="fp-1", group="g1")
        contra = item(fingerprint="fp-2", group="g2", supports_claim=False, contradicts_claim=True)
        result = assess_claim([support, contra], now=NOW)
        self.assertEqual(result.status, "CONFLICTING")
        self.assertIn("INDEPENDENT_CONFLICT", result.reason_codes)

    def test_primary_source_recognized(self):
        result = assess_claim([item(primary_source=True)], now=NOW)
        self.assertEqual(result.primary_sources, 1)
        self.assertNotIn("NO_PRIMARY_SOURCE", result.reason_codes)

    def test_stale_source(self):
        stale = item(freshness_class="FAST_CHANGING", published_at="2020-01-01T00:00:00+00:00")
        result = assess_claim([stale], now=NOW)
        self.assertEqual(result.stale_sources, 1)
        self.assertIn("STALE_SOURCES_PRESENT", result.reason_codes)

    def test_realtime_stale_never_current(self):
        old_realtime = item(freshness_class="REALTIME", published_at="2026-09-30T00:00:00+00:00")
        result = assess_claim([old_realtime], now=NOW)
        self.assertEqual(result.status, "STALE_EVIDENCE")
        self.assertIn("REALTIME_STALE_NEVER_CURRENT", result.reason_codes)

    def test_missing_provenance_flagged(self):
        result = assess_claim([item(provenance_id="")], now=NOW)
        self.assertIn("UNKNOWN_ORIGIN_PRESENT", result.reason_codes)

    def test_supporting_and_contradicting_same_group_not_conflict(self):
        # same independence group supporting and contradicting is internal noise,
        # not an independent conflict
        a = item(fingerprint="fp-1", group="g1")
        b = item(fingerprint="fp-1b", group="g1", supports_claim=False, contradicts_claim=True)
        result = assess_claim([a, b], now=NOW)
        self.assertNotEqual(result.status, "CONFLICTING")

    def test_digest_deterministic(self):
        r1 = assess_claim([item(), item(fingerprint="fp-2", group="g2")], now=NOW)
        r2 = assess_claim([item(), item(fingerprint="fp-2", group="g2")], now=NOW)
        self.assertEqual(trust_assessment_digest(r1), trust_assessment_digest(r2))
        self.assertEqual(r1.assessment_digest, r2.assessment_digest)

    def test_order_does_not_change_assessment(self):
        a = item(fingerprint="fp-1", group="g1")
        b = item(fingerprint="fp-2", group="g2")
        r1 = assess_claim([a, b], now=NOW)
        r2 = assess_claim([b, a], now=NOW)
        self.assertEqual(r1.assessment_digest, r2.assessment_digest)

    def test_adversarial_100_duplicates_vs_primary(self):
        """100 copies of the same false origin must not outvote one stronger
        independent primary source."""
        fake_origin = "fp-false-origin"
        duplicates = [
            create_evidence_item(
                claim_id="CLM-ADVERSARIAL",
                claim="afirmacao falsa replicada",
                source_fingerprint=fake_origin,
                source_type="WEB",
                authority=0.5,
                primary_source=False,
                independence_group="grp-false-origin",
                freshness_class="STATIC",
                published_at="2024-01-01T00:00:00+00:00",
                confidence=0.9,
                supports_claim=True,
                contradicts_claim=False,
                provenance_id="PRV-FALSE",
            )
            for _ in range(100)
        ]
        primary = create_evidence_item(
            claim_id="CLM-ADVERSARIAL",
            claim="afirmacao falsa replicada",
            source_fingerprint="fp-primary-independent",
            source_type="PRIMARY_SOURCE",
            authority=0.95,
            primary_source=True,
            independence_group="grp-primary",
            freshness_class="STATIC",
            published_at="2024-06-01T00:00:00+00:00",
            confidence=0.95,
            supports_claim=False,
            contradicts_claim=True,
            human_validated=True,
            provenance_id="PRV-PRIMARY",
        )
        result = assess_claim(duplicates + [primary], now=NOW)
        self.assertEqual(result.duplicate_sources_ignored, 99)
        self.assertEqual(independent_source_count(duplicates + [primary]), 2)
        self.assertEqual(result.primary_sources, 1)
        self.assertIn("DUPLICATES_DEDUPLICATED", result.reason_codes)
        # the primary contradiction is seen as an independent conflict,
        # the 100 copies never became 100 votes
        self.assertEqual(result.status, "CONFLICTING")
        self.assertEqual(result.contradicting_independent_sources, 1)
        self.assertEqual(result.supporting_independent_sources, 1)

    def test_shared_lineage_not_full_independence(self):
        # two fingerprints but same independence group (shared lineage)
        a = item(fingerprint="fp-a", group="lineage-x")
        b = item(fingerprint="fp-b", group="lineage-x")
        self.assertEqual(independent_source_count([a, b]), 1)

    def test_empty_evidence_insufficient(self):
        result = assess_claim([], now=NOW)
        self.assertEqual(result.status, "INSUFFICIENT_EVIDENCE")
        self.assertIn("NO_EVIDENCE", result.reason_codes)

    def test_reason_always_present(self):
        for items in ([item()], [], [item(), item(fingerprint="fp-2", group="g2")]):
            result = assess_claim(items, now=NOW)
            self.assertTrue(len(result.reason_codes) >= 1)

    def test_fingerprint_required(self):
        with self.assertRaises(TrustEngineError):
            create_evidence_item(claim_id="C", claim="x", source_fingerprint="")


if __name__ == "__main__":
    unittest.main()
