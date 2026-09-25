from __future__ import annotations
import unittest

from atlasquant_aion_release_confidence import (
    DIMENSIONS, evidence_dimension, release_confidence,
)


class AtlasQuantAionReleaseConfidenceTests(unittest.TestCase):
    def _rows(self):
        return [
            evidence_dimension(name,confirmed=True,evidence_refs=[f"evidence:{name.lower()}"])
            for name in DIMENSIONS
        ]

    def test_full_evidence_only_reaches_human_review(self):
        out=release_confidence(candidate_ref="candidate@abc",dimensions=self._rows())
        self.assertEqual(out["state"],"HUMAN_REVIEW_READY")
        self.assertEqual(out["evidence_coverage_pct"],100.0)
        self.assertFalse(out["merge_allowed"])
        self.assertFalse(out["deploy_allowed"])
        self.assertTrue(out["requires_human_approval"])
        self.assertIn("not probability",out["meaning"])

    def test_missing_evidence_needs_evidence(self):
        rows=self._rows()[:-1]
        out=release_confidence(candidate_ref="candidate@abc",dimensions=rows)
        self.assertEqual(out["state"],"NEEDS_EVIDENCE")
        self.assertLess(out["evidence_coverage_pct"],100.0)

    def test_blocker_overrides_full_coverage(self):
        rows=self._rows()
        rows[0]=evidence_dimension(
            DIMENSIONS[0],confirmed=True,evidence_refs=["evidence:block"],
            blocker=True,
        )
        out=release_confidence(candidate_ref="candidate@abc",dimensions=rows)
        self.assertEqual(out["state"],"BLOCKED")
        self.assertFalse(out["deploy_allowed"])

    def test_confirmed_without_evidence_is_not_confirmed(self):
        row=evidence_dimension("QUALITY",confirmed=True,evidence_refs=[])
        self.assertFalse(row["confirmed"])


if __name__=="__main__":
    unittest.main()
