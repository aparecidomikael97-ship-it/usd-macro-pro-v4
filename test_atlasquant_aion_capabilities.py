from __future__ import annotations

import unittest

from atlasquant_aion_capabilities import (
    capability_feature_flags,
    normalize_capability,
)


class AtlasQuantAionCapabilityRegistryHardeningTests(unittest.TestCase):
    def base(self):
        return {
            "capability_id": "test.capability",
            "specialist": "test",
            "domains": ["central"],
            "description": "Test capability.",
            "inputs": [],
            "outputs": [],
        }

    def test_negative_cost_is_rejected_not_clamped_to_zero(self):
        raw=self.base()
        raw["estimated_cost_usd"]=-1
        with self.assertRaises(ValueError):
            normalize_capability(raw)

    def test_boolean_cost_is_rejected(self):
        raw=self.base()
        raw["estimated_cost_usd"]=True
        with self.assertRaises(ValueError):
            normalize_capability(raw)

    def test_text_cost_is_rejected(self):
        raw=self.base()
        raw["estimated_cost_usd"]="0.25"
        with self.assertRaises(ValueError):
            normalize_capability(raw)

    def test_requires_confirmation_needs_exact_true(self):
        raw=self.base()
        raw["requires_confirmation"]="true"
        item=normalize_capability(raw)
        self.assertFalse(item.requires_confirmation)

    def test_invalid_truthy_feature_override_fails_closed(self):
        flags=capability_feature_flags({"AION_DEV_ENABLED":"false"})
        self.assertFalse(flags["AION_DEV_ENABLED"])

    def test_immutable_external_flags_stay_off(self):
        flags=capability_feature_flags({
            "AION_EXTERNAL_ACTIONS_ENABLED":True,
            "REAL_TRADING_ENABLED":True,
        })
        self.assertFalse(flags["AION_EXTERNAL_ACTIONS_ENABLED"])
        self.assertFalse(flags["REAL_TRADING_ENABLED"])


if __name__=="__main__":
    unittest.main()
