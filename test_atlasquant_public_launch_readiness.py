import unittest

from atlasquant_public_launch_readiness import collect_public_launch_readiness

class AtlasQuantPublicLaunchReadinessTests(unittest.TestCase):
    def test_internal_preparation_is_complete_but_external_dependencies_are_not(self):
        status=collect_public_launch_readiness()
        self.assertTrue(status["internal_preparation_complete"])
        self.assertFalse(status["external_dependencies_complete"])
        self.assertFalse(status["public_launch_ready"])

    def test_all_internal_contracts_are_true(self):
        status=collect_public_launch_readiness()
        self.assertTrue(status["internal"])
        self.assertTrue(all(status["internal"].values()))

    def test_external_items_remain_fail_closed(self):
        status=collect_public_launch_readiness()
        self.assertTrue(status["external"])
        self.assertTrue(all(v is False for v in status["external"].values()))
        self.assertFalse(status["automatic_launch"])
        self.assertFalse(status["broker_execution_enabled"])
        self.assertFalse(status["real_orders_enabled"])
        self.assertTrue(status["manual_final_review_required"])

if __name__=="__main__":
    unittest.main()
