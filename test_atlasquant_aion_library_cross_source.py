import unittest

from atlasquant_aion_library_cross_source import compare_library_records


def _record(doc_id, *, title="Macro Guide", version="1", checksum="sha256:a", source="upload://macro.pdf", tenant="tenant:a", workspace="workspace:a", fingerprint="sha256:f1"):
    return {
        "document_id": doc_id,
        "tenant_id": tenant,
        "workspace_id": workspace,
        "title": title,
        "document_version": version,
        "checksum": checksum,
        "source_reference": source,
        "provenance": {"provenance_id": "PROV-" + doc_id},
        "document_intelligence": {"content_fingerprint": fingerprint},
    }


class AionLibraryCrossSourceTests(unittest.TestCase):
    def test_same_title_version_different_checksum_is_review_hint_not_auto_conflict(self):
        result = compare_library_records(
            _record("DOC-A", checksum="sha256:a", fingerprint="sha256:f1"),
            [_record("DOC-B", checksum="sha256:b", fingerprint="sha256:f2")],
        )
        self.assertEqual(result["status"], "REVIEW_HINTS_READY")
        relations = {x["relation"] for x in result["hints"]}
        self.assertIn("POTENTIAL_CONFLICT_SAME_VERSION", relations)
        self.assertIn("SOURCE_CONTENT_CHANGED", relations)
        self.assertGreaterEqual(result["conflict_candidate_count"], 1)
        self.assertFalse(result["automatic_state_change"])
        self.assertFalse(result["truth_decision_made"])
        self.assertFalse(result["external_action_executed"])
        self.assertTrue(all(x["requires_human_review"] for x in result["hints"]))
        self.assertTrue(all(not x["automatic_conflict_classification"] for x in result["hints"]))

    def test_same_checksum_is_duplicate_info_not_conflict(self):
        result = compare_library_records(
            _record("DOC-A"),
            [_record("DOC-B")],
        )
        relations = {x["relation"] for x in result["hints"]}
        self.assertIn("DUPLICATE_CONTENT", relations)
        self.assertEqual(result["conflict_candidate_count"], 0)

    def test_same_title_different_version_is_version_divergence(self):
        result = compare_library_records(
            _record("DOC-A", version="2", checksum="sha256:new", fingerprint="sha256:new"),
            [_record("DOC-B", version="1", checksum="sha256:old", fingerprint="sha256:old")],
        )
        relations = {x["relation"] for x in result["hints"]}
        self.assertIn("VERSION_DIVERGENCE", relations)

    def test_cross_scope_peer_is_never_compared_or_exposed(self):
        result = compare_library_records(
            _record("DOC-A"),
            [_record("DOC-B", tenant="tenant:b")],
        )
        self.assertEqual(result["compared_peers"], 0)
        self.assertEqual(result["skipped_scope_mismatch"], 1)
        self.assertEqual(result["hints"], [])

    def test_missing_candidate_scope_fails_closed(self):
        result = compare_library_records({"document_id": "DOC-X"}, [])
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("CANDIDATE_SCOPE_OR_ID_MISSING", result["blockers"])


if __name__ == "__main__":
    unittest.main()
