import tempfile
import unittest
from pathlib import Path

from atlasquant_finalization_audit import finalization_audit

class AtlasQuantFinalizationAuditTests(unittest.TestCase):
    def test_internal_release_preparation_is_complete(self):
        status=finalization_audit()
        self.assertTrue(status["internal_release_preparation_complete"])
        self.assertTrue(status["handoff_docs_complete"])
        self.assertEqual(status["missing_handoff_docs"],[])

    def test_external_completion_remains_fail_closed(self):
        status=finalization_audit()
        self.assertFalse(status["external_dependencies_complete"])
        self.assertFalse(status["public_launch_ready"])
        self.assertFalse(status["real_orders_enabled"])
        self.assertFalse(status["broker_execution_enabled"])
        self.assertFalse(status["automatic_public_launch"])
        self.assertTrue(status["manual_external_completion_required"])

    def test_missing_handoff_docs_blocks_internal_completion(self):
        with tempfile.TemporaryDirectory() as td:
            status=finalization_audit(Path(td))
        self.assertFalse(status["handoff_docs_complete"])
        self.assertFalse(status["internal_release_preparation_complete"])
        self.assertFalse(status["public_launch_ready"])

if __name__=="__main__":
    unittest.main()
