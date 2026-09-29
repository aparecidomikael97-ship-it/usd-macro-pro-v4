from __future__ import annotations
import unittest

from atlasquant_aion_release_confidence import (
    DIMENSIONS, evidence_dimension, release_confidence,
    normalize_release_confidence,
)


def _verifier(dimension, refs):
    return {"state":"VERIFIED","bound_refs":list(refs)}


class AtlasQuantAionReleaseConfidenceTests(unittest.TestCase):
    def _rows(self):
        return [
            {
                "dimension":name,
                "confirmed":True,
                "evidence_refs":[f"evidence:{name.lower()}"],
            }
            for name in DIMENSIONS
        ]

    def test_full_evidence_only_reaches_human_review(self):
        out=release_confidence(
            candidate_ref="candidate@abc",
            dimensions=self._rows(),
            evidence_verifier=_verifier,
        )
        self.assertEqual(out["state"],"HUMAN_REVIEW_READY")
        self.assertEqual(out["evidence_coverage_pct"],100.0)
        self.assertFalse(out["merge_allowed"])
        self.assertFalse(out["deploy_allowed"])
        self.assertTrue(out["requires_human_approval"])
        self.assertIn("not probability",out["meaning"])

    def test_missing_evidence_needs_evidence(self):
        rows=self._rows()[:-1]
        out=release_confidence(
            candidate_ref="candidate@abc",
            dimensions=rows,
            evidence_verifier=_verifier,
        )
        self.assertEqual(out["state"],"NEEDS_EVIDENCE")
        self.assertLess(out["evidence_coverage_pct"],100.0)

    def test_blocker_overrides_full_coverage(self):
        rows=self._rows()
        rows[0]={
            "dimension":DIMENSIONS[0],
            "confirmed":True,
            "evidence_refs":["evidence:block"],
            "blocker":True,
        }
        out=release_confidence(
            candidate_ref="candidate@abc",
            dimensions=rows,
            evidence_verifier=_verifier,
        )
        self.assertEqual(out["state"],"BLOCKED")
        self.assertFalse(out["deploy_allowed"])

    def test_textual_confirmation_and_unverified_refs_are_not_evidence(self):
        rows=[
            {"dimension":name,"confirmed":"false","evidence_refs":["invented"]}
            for name in DIMENSIONS
        ]
        out=release_confidence(candidate_ref="candidate@abc",dimensions=rows)
        self.assertEqual(out["state"],"NEEDS_EVIDENCE")
        self.assertFalse(any(row["confirmed"] for row in out["dimensions"]))
        self.assertFalse(out["merge_allowed"])
        self.assertFalse(out["deploy_allowed"])
        numeric=evidence_dimension("QUALITY",confirmed=1,evidence_refs=["invented"])
        self.assertFalse(numeric["confirmed"])
        unverified=release_confidence(candidate_ref="candidate@abc",dimensions=self._rows())
        self.assertEqual(unverified["state"],"NEEDS_EVIDENCE")
        self.assertFalse(any(row["confirmed"] for row in unverified["dimensions"]))

    def test_persisted_fake_ready_state_is_recomputed(self):
        fake={
            "candidate_ref":"candidate@abc",
            "state":"HUMAN_REVIEW_READY",
            "dimensions":[],
        }
        out=normalize_release_confidence(fake)
        self.assertEqual(out["state"],"NEEDS_EVIDENCE")
        self.assertFalse(out["deploy_allowed"])

    def test_confirmed_without_evidence_is_not_confirmed(self):
        row=evidence_dimension("QUALITY",confirmed=True,evidence_refs=[])
        self.assertFalse(row["confirmed"])


if __name__=="__main__":
    unittest.main()
