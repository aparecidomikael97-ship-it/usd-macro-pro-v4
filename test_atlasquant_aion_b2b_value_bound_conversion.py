import unittest

from atlasquant_aion_b2b_value_bound_conversion import (
    CONVERSION_SCHEMA,
    SCHEMA,
    VALUE_SCHEMA,
    bind_value_to_conversion_review,
)


SCOPE = {
    "owner_id": "owner-a",
    "tenant_id": "tenant-a",
    "workspace_id": "workspace-a",
}


def value_row(
    *,
    state="STRONG_VALUE",
    recommendation="EXPANSION_REVIEW_CANDIDATE",
    pilot_id="pilot-a",
):
    return {
        "schema": VALUE_SCHEMA,
        "state": state,
        "recommendation": recommendation,
        "pilot_id": pilot_id,
        "scope": dict(SCOPE),
        "blockers": [],
        "evidence_digest": "sha256:value",
        "owner_review_required": True,
        "automatic_renewal": False,
        "automatic_expansion": False,
        "automatic_pause": False,
        "automatic_termination": False,
        "automatic_scope_change": False,
        "automatic_contract_change": False,
        "automatic_billing": False,
        "automatic_customer_contact": False,
        "automatic_provisioning": False,
        "automatic_deploy": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "executes_action": False,
    }


def conversion_row(*, customer_id="customer-a"):
    return {
        "schema": CONVERSION_SCHEMA,
        "state": "REVIEWABLE",
        "decision": "COMMERCIAL_REVIEW_CANDIDATE",
        "customer_id": customer_id,
        "recommended_package": "PROFISSIONAL",
        "review_reasons": [],
        "blockers": [],
        "evidence_digest": "sha256:conversion",
        "owner_commercial_approval_required": True,
        "automatic_conversion": False,
        "automatic_package_change": False,
        "automatic_pricing_change": False,
        "automatic_contract": False,
        "automatic_billing": False,
        "automatic_provisioning": False,
        "automatic_customer_contact": False,
        "automatic_deploy": False,
        "production_mutation": False,
        "executes_action": False,
    }


def binding_row(**changes):
    row = {
        **SCOPE,
        "customer_id": "customer-a",
        "pilot_id": "pilot-a",
        "evidence_refs": ["bind:customer", "bind:pilot", "bind:scope"],
    }
    row.update(changes)
    return row


class ValueBoundConversionTests(unittest.TestCase):
    def test_strong_value_becomes_expansion_review_candidate(self):
        result = bind_value_to_conversion_review(
            trusted_scope=SCOPE,
            binding=binding_row(),
            value_realization=value_row(),
            conversion_capacity=conversion_row(),
        )
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["state"], "REVIEWABLE")
        self.assertEqual(
            result["decision"],
            "EXPANSION_COMMERCIAL_REVIEW_CANDIDATE",
        )
        self.assertEqual(result["recommended_package"], "PROFISSIONAL")
        self.assertTrue(result["owner_commercial_approval_required"])
        self.assertFalse(result["automatic_conversion"])
        self.assertFalse(result["automatic_expansion"])
        self.assertFalse(result["automatic_billing"])
        self.assertFalse(result["automatic_provisioning"])
        self.assertFalse(result["automatic_customer_contact"])
        self.assertFalse(result["automatic_deploy"])
        self.assertFalse(result["provider_called"])
        self.assertFalse(result["production_mutation"])
        self.assertFalse(result["executes_action"])

    def test_confirmed_value_becomes_continue_review_candidate(self):
        result = bind_value_to_conversion_review(
            trusted_scope=SCOPE,
            binding=binding_row(),
            value_realization=value_row(
                state="VALUE_CONFIRMED",
                recommendation="CONTINUE_REVIEW_CANDIDATE",
            ),
            conversion_capacity=conversion_row(),
        )
        self.assertEqual(result["state"], "REVIEWABLE")
        self.assertEqual(
            result["decision"],
            "CONTINUE_COMMERCIAL_REVIEW_CANDIDATE",
        )

    def test_cross_tenant_binding_fails_closed(self):
        result = bind_value_to_conversion_review(
            trusted_scope=SCOPE,
            binding=binding_row(tenant_id="tenant-b"),
            value_realization=value_row(),
            conversion_capacity=conversion_row(),
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("BINDING_SCOPE_MISMATCH", result["blockers"])

    def test_pilot_replay_fails_closed(self):
        result = bind_value_to_conversion_review(
            trusted_scope=SCOPE,
            binding=binding_row(),
            value_realization=value_row(pilot_id="pilot-other"),
            conversion_capacity=conversion_row(),
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("VALUE_PILOT_MISMATCH", result["blockers"])

    def test_customer_replay_fails_closed(self):
        result = bind_value_to_conversion_review(
            trusted_scope=SCOPE,
            binding=binding_row(),
            value_realization=value_row(),
            conversion_capacity=conversion_row(customer_id="customer-other"),
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("CONVERSION_CUSTOMER_MISMATCH", result["blockers"])

    def test_remediation_value_cannot_convert(self):
        result = bind_value_to_conversion_review(
            trusted_scope=SCOPE,
            binding=binding_row(),
            value_realization=value_row(
                state="VALUE_AT_RISK",
                recommendation="REMEDIATE_REVIEW_CANDIDATE",
            ),
            conversion_capacity=conversion_row(),
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("VALUE_NOT_CONVERSION_ELIGIBLE", result["blockers"])

    def test_capacity_hold_cannot_convert(self):
        conversion = conversion_row()
        conversion["state"] = "CAPACITY_HOLD"
        conversion["decision"] = "CAPACITY_REVIEW"
        result = bind_value_to_conversion_review(
            trusted_scope=SCOPE,
            binding=binding_row(),
            value_realization=value_row(),
            conversion_capacity=conversion,
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("CONVERSION_NOT_REVIEWABLE", result["blockers"])

    def test_unsafe_source_flag_fails_closed(self):
        value = value_row()
        value["automatic_expansion"] = True
        result = bind_value_to_conversion_review(
            trusted_scope=SCOPE,
            binding=binding_row(),
            value_realization=value,
            conversion_capacity=conversion_row(),
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn(
            "VALUE_UNSAFE_FIELD:automatic_expansion",
            result["blockers"],
        )

    def test_binding_requires_evidence(self):
        result = bind_value_to_conversion_review(
            trusted_scope=SCOPE,
            binding=binding_row(evidence_refs=["one", "two"]),
            value_realization=value_row(),
            conversion_capacity=conversion_row(),
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("BINDING_EVIDENCE_INSUFFICIENT", result["blockers"])


if __name__ == "__main__":
    unittest.main()
