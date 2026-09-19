import unittest

from atlasquant_data_licensing_inventory import (
    data_inventory_ready,
    data_licensing_status,
    data_source_inventory,
)

class AtlasQuantDataLicensingInventoryTests(unittest.TestCase):
    def test_current_source_inventory_is_complete_and_unique(self):
        rows=data_source_inventory()
        ids=[x["id"] for x in rows]
        self.assertTrue(data_inventory_ready())
        self.assertEqual(len(ids),len(set(ids)))
        self.assertGreaterEqual(len(ids),8)

    def test_inventory_never_treats_technical_access_as_commercial_license(self):
        rows=data_source_inventory()
        self.assertTrue(rows)
        self.assertTrue(all(x["commercial_license_verified"] is False for x in rows))
        status=data_licensing_status()
        self.assertEqual(status["commercially_verified"],0)
        self.assertFalse(status["all_commercial_licenses_verified"])
        self.assertTrue(status["manual_review_required"])
        self.assertFalse(status["automatic_license_assumption"])

    def test_known_provider_families_are_explicit(self):
        ids={x["id"] for x in data_source_inventory()}
        self.assertTrue({"fred","bcb-sgs","newsapi","eodhd","twelve-data"}.issubset(ids))

if __name__=="__main__":
    unittest.main()
