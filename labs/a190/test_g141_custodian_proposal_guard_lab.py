"""G141 negative architectural regressions; all outputs remain HARD NO-GO."""
from copy import deepcopy
import unittest

from labs.a190.g141_custodian_proposal_guard_lab import (
    SCHEMA, REQUIRED_REAL_TESTS, review_custodian_proposal_lab,
)


def proposal():
    # Hypothetical paper configuration. No operator, account, or cloud exists.
    return {
        "schema": SCHEMA,
        "vendor": "VENDOR_NEUTRAL",
        "writer_regions": ["one-authoritative-region"],
        "multi_active_event_writes": False,
        "manual_failover_with_external_epoch": True,
        "original_business_key_claimed": True,
        "atomic_unique_reservation_claimed": True,
        "relies_on_short_client_token": False,
        "provider_effect_inside_transaction_callback": False,
        "immutable_archive_version_pinned_claimed": True,
        "ack_loss_auto_resend": False,
        "offline_new_effect_allowed": False,
        "host_can_repin_custodian_root": False,
    }


class G141CustodianProposalSafetyTests(unittest.TestCase):
    def deny(self, value, *, risk=None, status=None):
        verdict = review_custodian_proposal_lab(value)
        self.assertIn("HARD_NO_GO", verdict.status)
        if status:
            self.assertEqual(verdict.status, status)
        if risk:
            self.assertIn(risk, verdict.risks)
        self.assertFalse(verdict.externally_verified)
        self.assertEqual(verdict.p0_homologated, 0)
        self.assertEqual(verdict.p0_total, 6)
        self.assertFalse(verdict.allows_worker)
        self.assertFalse(verdict.allows_provider_send)
        self.assertFalse(verdict.allows_retry)
        self.assertFalse(verdict.safe_to_install)
        return verdict

    def edit(self, field, value):
        x = proposal()
        x[field] = value
        return x

    def test_01_no_document_never_grants_authority(self):
        for bad in (None, {}, [], "ready", 1):
            with self.subTest(bad=bad):
                self.deny(bad, status="DENY_INVALID_DESIGN_HARD_NO_GO")

    def test_02_paper_perfect_still_unverified(self):
        result = self.deny(
            proposal(), status="DESIGN_REVIEW_ONLY_EXTERNAL_PROOF_MISSING_HARD_NO_GO"
        )
        self.assertTrue(result.requires_independent_review)
        print("G141_PAPER_PERFECT=EXTERNAL_PROOF_MISSING_ZERO_P0_NO_SEND")

    def test_03_two_writable_regions_rejected(self):
        self.deny(
            self.edit("writer_regions", ["us-east-1", "us-west-2"]),
            risk="MULTI_WRITER_NOT_A_GLOBAL_UNIQUE_RESERVATION",
        )
        print("G141_T9_TWO_WRITERS=DENY_NOT_GLOBAL_ONCE")

    def test_04_even_one_region_with_active_active_flag_rejected(self):
        self.deny(
            self.edit("multi_active_event_writes", True),
            risk="MULTI_WRITER_NOT_A_GLOBAL_UNIQUE_RESERVATION",
        )

    def test_05_failover_without_external_epoch_fence_rejected(self):
        self.deny(
            self.edit("manual_failover_with_external_epoch", False),
            risk="FAILOVER_WITHOUT_EXTERNAL_FENCE",
        )
        print("G141_T13_UNFENCED_FAILOVER=DENY")

    def test_06_self_renamed_economic_event_rejected(self):
        self.deny(
            self.edit("original_business_key_claimed", False),
            risk="CLIENT_CAN_RENAME_ECONOMIC_EVENT",
        )

    def test_07_nonatomic_local_only_reservation_rejected(self):
        self.deny(
            self.edit("atomic_unique_reservation_claimed", False),
            risk="NO_ATOMIC_SINGLE_USE_RESERVATION",
        )

    def test_08_client_token_window_not_durable_fence(self):
        self.deny(
            self.edit("relies_on_short_client_token", True),
            risk="FINITE_TOKEN_WINDOW_NOT_DURABLE_IDEMPOTENCY",
        )
        print("G141_T12_10_MIN_TOKEN_ONLY=DENY")

    def test_09_transaction_retry_cannot_perform_provider_send(self):
        self.deny(
            self.edit("provider_effect_inside_transaction_callback", True),
            risk="TRANSACTION_CALLBACK_MAY_REEXECUTE_EFFECT",
        )
        print("G141_T10_TRANSACTION_CALLBACK_EFFECT=DENY")

    def test_10_worm_object_without_version_pin_rejected(self):
        self.deny(
            self.edit("immutable_archive_version_pinned_claimed", False),
            risk="WORM_VERSION_NOT_INDEPENDENTLY_PINNED",
        )
        print("G141_T11_WORM_UNPINNED_VERSION=DENY")

    def test_11_lost_ack_auto_resend_rejected(self):
        self.deny(
            self.edit("ack_loss_auto_resend", True),
            risk="ACK_LOSS_MUST_NOT_TRIGGER_RETRY",
        )

    def test_12_offline_first_send_rejected(self):
        self.deny(
            self.edit("offline_new_effect_allowed", True),
            risk="OFFLINE_MODE_MUST_NOT_ENABLE_FIRST_SEND",
        )

    def test_13_local_custodian_root_repin_rejected(self):
        self.deny(
            self.edit("host_can_repin_custodian_root", True),
            risk="HOST_CONTROLLED_ROOT_IS_NOT_INDEPENDENT",
        )

    def test_14_aggregate_all_bad_controls_not_hidden(self):
        x = proposal()
        x.update({
            "writer_regions": ["us-east-1", "us-west-2"],
            "multi_active_event_writes": True,
            "manual_failover_with_external_epoch": False,
            "original_business_key_claimed": False,
            "atomic_unique_reservation_claimed": False,
            "relies_on_short_client_token": True,
            "provider_effect_inside_transaction_callback": True,
            "immutable_archive_version_pinned_claimed": False,
            "ack_loss_auto_resend": True,
            "offline_new_effect_allowed": True,
            "host_can_repin_custodian_root": True,
        })
        result = self.deny(x, status="DENY_UNSAFE_PROPOSED_DESIGN_HARD_NO_GO")
        self.assertEqual(len(result.risks), 10)

    def test_15_unknown_vendor_or_schema_rejected(self):
        for k, value in (("schema", "AION_APPROVED"), ("vendor", "PRODUCTION")):
            with self.subTest(k=k):
                self.deny(
                    self.edit(k, value),
                    status="DENY_INVALID_DESIGN_HARD_NO_GO",
                )

    def test_16_invalid_regions_rejected(self):
        for value in ([], "us-east-1", [None], ["../us-east-1"], [1]):
            with self.subTest(value=value):
                self.deny(
                    self.edit("writer_regions", value),
                    risk="VALID_WRITER_REGIONS_REQUIRED",
                )

    def test_17_string_int_or_none_for_boolean_rejected(self):
        for value in ("false", 1, None, 0):
            with self.subTest(value=value):
                self.deny(
                    self.edit("offline_new_effect_allowed", value),
                    risk="EXACT_BOOLEAN_TYPES_REQUIRED",
                )

    def test_18_inserted_green_or_worker_authority_field_rejected(self):
        for extra in ("externally_verified", "allows_worker", "homologated_p0"):
            with self.subTest(extra=extra):
                x = deepcopy(proposal())
                x[extra] = True
                self.deny(x, risk="EXACT_FIELDS_REQUIRED")
        print("G141_SELF_CLAIMED_APPROVAL=HARD_NO_GO")

    def test_19_external_cases_named_but_not_self_certifiable(self):
        self.assertEqual(len(REQUIRED_REAL_TESTS), 5)
        for key in ("T9_", "T10_", "T11_", "T12_", "T13_"):
            self.assertEqual(sum(name.startswith(key) for name in REQUIRED_REAL_TESTS), 1)
        result = self.deny(proposal())
        self.assertFalse(result.externally_verified)
        print("G141_T9_TO_T13=SPEC_ONLY_NOT_REAL_EXTERNAL_TEST")


if __name__ == "__main__":
    unittest.main()
