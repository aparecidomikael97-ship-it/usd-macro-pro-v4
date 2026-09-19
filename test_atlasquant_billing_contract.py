import unittest

from atlasquant_billing_contract import (
    BillingEvent,
    billing_contract_ready,
    evaluate_verified_billing_event,
)

class AtlasQuantBillingContractTests(unittest.TestCase):
    def test_contract_is_ready_without_provider_activation(self):
        self.assertTrue(billing_contract_ready())

    def test_unverified_event_fails_closed(self):
        event=BillingEvent("evt_1","cust_1","sub_1","active")
        out=evaluate_verified_billing_event(event,signature_verified=False)
        self.assertFalse(out["accepted_for_review"])
        self.assertFalse(out["automatic_entitlement"])
        self.assertFalse(out["automatic_role_change"])
        self.assertFalse(out["automatic_charge"])
        self.assertFalse(out["card_data_stored"])
        self.assertTrue(out["requires_human_review"])

    def test_verified_event_is_only_accepted_for_review(self):
        event=BillingEvent("evt_2","cust_2","sub_2","cancelled")
        out=evaluate_verified_billing_event(event,signature_verified=True)
        self.assertTrue(out["signature_verified"])
        self.assertTrue(out["accepted_for_review"])
        self.assertFalse(out["automatic_entitlement"])
        self.assertFalse(out["automatic_role_change"])

    def test_invalid_or_incomplete_event_is_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_verified_billing_event(BillingEvent("","cust","sub","active"),signature_verified=True)
        with self.assertRaises(ValueError):
            evaluate_verified_billing_event(BillingEvent("evt","cust","sub","invented"),signature_verified=True)

if __name__=="__main__":
    unittest.main()
