"""Adversarial offline key-lifecycle log tests. NO REAL KEYS OR AUTHORITY."""
from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_aion_p0_key_lifecycle_appendonly_lab import (
    GENESIS, calculate_record_head_lab, audit_key_lifecycle_claims_lab,
)
from atlasquant_aion_p0_incident_external_witness_proposal_lab import NO_GO_FLAGS


def fixture(actions=(("ENROLL", "key-alpha"), ("ROTATE", "key-bravo"),
                     ("REVOKE", "key-bravo"), ("RECOVER", "key-charlie"))):
    events = []
    head = GENESIS
    for i, (action, key) in enumerate(actions, 1):
        row = {
            "sequence": i, "epoch": i, "event_type": action,
            "key_id": key, "previous_head": head,
            "recorded_at_utc": f"2026-10-20T12:00:{i:02d}Z",
        }
        row["record_head"] = calculate_record_head_lab(row)
        events.append(row)
        head = row["record_head"]
    final = events[-1]
    views = [
        {"observer_id": f"observer-{suffix}", "admin_root": f"admin-{suffix}",
         "recovery_root": f"recovery-{suffix}", "sequence": final["sequence"],
         "epoch": final["epoch"], "head": final["record_head"]}
        for suffix in ("east", "west")
    ]
    return events, views


class KeyLifecycleLAB(unittest.TestCase):
    def setUp(self):
        self.events, self.views = fixture()

    def check(self, events=None, views=None):
        return audit_key_lifecycle_claims_lab(
            self.events if events is None else events,
            self.views if views is None else views,
        )

    def denied(self, result):
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIs(result["allowed"], False)
        self.assertTrue(result["simulation_only"])
        self.assertIs(result["external_issuer_verified"], False)
        self.assertIs(result["external_latest_head_verified"], False)
        self.assertIs(result["external_revocation_verified"], False)
        self.assertIs(result["witnesses_independent_verified"], False)
        self.assertEqual(result["blockers"], tuple(sorted(set(result["blockers"]))))
        for flag in NO_GO_FLAGS:
            self.assertIs(result[flag], False, flag)
        return result

    def defect(self, expected, events=None, views=None):
        r = self.denied(self.check(events, views))
        self.assertTrue(any(expected in s for s in r["structural_defects"]),
                        (expected, r["structural_defects"]))
        return r

    def test_01_complete_self_consistent_chain_is_still_no_go(self):
        r = self.denied(self.check())
        self.assertTrue(r["synthetic_sequence_structurally_consistent"])
        self.assertEqual(r["structural_defects"], ())
        self.assertIn("OFF_HOST_LATEST_HEAD_NOT_AUTHENTICATED", r["blockers"])

    def test_02_repeated_input_does_not_grant_nonce_or_authority(self):
        self.assertEqual(self.denied(self.check()), self.denied(self.check()))

    def test_03_tampered_key_digest(self):
        e = deepcopy(self.events)
        e[1]["record_head"] = "f" * 64
        self.defect("EVENT_DIGEST_MISMATCH", e)

    def test_04_modified_previous_head(self):
        e = deepcopy(self.events)
        e[1]["previous_head"] = "e" * 64
        self.defect("CHAIN_PARENT_MISMATCH", e)

    def test_05_noncontiguous_sequence(self):
        e = deepcopy(self.events)
        e[1]["sequence"] = 6
        self.defect("NONCONTIGUOUS_SEQUENCE", e)

    def test_06_epoch_rollback(self):
        e = deepcopy(self.events)
        e[2]["epoch"] = 2
        self.defect("EPOCH_NOT_INCREMENTED", e)

    def test_07_duplicate_timestamp(self):
        e = deepcopy(self.events)
        e[2]["recorded_at_utc"] = e[1]["recorded_at_utc"]
        self.defect("CLOCK_NOT_INCREASING", e)

    def test_08_bad_timestamp_calendar(self):
        e = deepcopy(self.events)
        e[0]["recorded_at_utc"] = "2026-02-30T12:00:00Z"
        self.defect("EVENT_FIELD_INVALID", e)

    def test_09_boolean_sequence_not_integer(self):
        e = deepcopy(self.events)
        e[0]["sequence"] = True
        self.defect("EVENT_FIELD_INVALID", e)

    def test_10_unknown_action(self):
        e = deepcopy(self.events)
        e[0]["event_type"] = "UNREVOKE"
        self.defect("EVENT_FIELD_INVALID", e)

    def test_11_rotate_to_reused_key(self):
        e = deepcopy(self.events)
        e[1]["key_id"] = "key-alpha"
        self.defect("KEY_ID_REUSED", e)

    def test_12_revoke_wrong_key(self):
        e = deepcopy(self.events)
        e[2]["key_id"] = "key-alpha"
        self.defect("REVOKE_NON_ACTIVE_KEY", e)

    def test_13_recover_without_revoke(self):
        e = deepcopy(self.events)
        e[1]["event_type"] = "RECOVER"
        self.defect("RECOVER_WITHOUT_REVOCATION", e)

    def test_14_duplicate_enroll_not_allowed(self):
        e = deepcopy(self.events)
        e[1]["event_type"] = "ENROLL"
        self.defect("ENROLL_NOT_GENESIS", e)

    def test_15_revoke_before_enrollment(self):
        e, w = fixture((("REVOKE", "key-alpha"),))
        self.defect("REVOKE_NON_ACTIVE_KEY", e, w)

    def test_16_split_view_same_height_different_head(self):
        w = deepcopy(self.views)
        w[1]["head"] = "f" * 64
        self.defect("SPLIT_VIEW_FORK_CLAIM", views=w)

    def test_17_witness_falsely_reports_an_older_sequence(self):
        w = deepcopy(self.views)
        w[1]["sequence"] -= 1
        self.defect("WITNESS_VIEW_DIVERGES", views=w)

    def test_18_witness_admin_root_collision(self):
        w = deepcopy(self.views)
        w[1]["admin_root"] = w[0]["admin_root"]
        self.defect("CLAIMED_DOMAIN_COLLISION:admin_root", views=w)

    def test_19_witness_recovery_root_collision(self):
        w = deepcopy(self.views)
        w[1]["recovery_root"] = w[0]["recovery_root"]
        self.defect("CLAIMED_DOMAIN_COLLISION:recovery_root", views=w)

    def test_20_cross_role_admin_recovery_overlap(self):
        w = deepcopy(self.views)
        w[1]["recovery_root"] = w[0]["admin_root"]
        self.defect("CROSS_ROLE_ADMIN_RECOVERY_COLLISION", views=w)

    def test_21_only_one_witness_claim(self):
        self.defect("VIEW_COUNT_OUT_OF_BOUNDS", views=self.views[:1])

    def test_22_too_many_untrusted_witnesses(self):
        self.defect("VIEW_COUNT_OUT_OF_BOUNDS", views=self.views * 3)

    def test_23_event_list_too_large(self):
        self.defect("EVENT_COUNT_OUT_OF_BOUNDS", events=self.events * 17)

    def test_24_malicious_dict_subclass_not_read(self):
        class Hostile(dict):
            def keys(self): raise AssertionError("hostile dict keys")
            def __iter__(self): raise AssertionError("hostile dict iterator")
        e = deepcopy(self.events)
        e[0] = Hostile(e[0])
        self.defect("EVENT_SHAPE_INVALID", events=e)

    def test_25_malicious_field_eq_not_called(self):
        class Hostile:
            def __eq__(self, other): raise AssertionError("attacker eq")
            def __str__(self): raise AssertionError("attacker str")
        w = deepcopy(self.views)
        w[0]["admin_root"] = Hostile()
        self.defect("VIEW_FIELD_INVALID", views=w)

    def test_26_dict_subclass_witness_rejected(self):
        w = deepcopy(self.views)
        w[0] = type("HostileDict", (dict,), {})(w[0])
        self.defect("VIEW_SHAPE_INVALID", views=w)

    def test_27_missing_field_and_optimistic_authority_flag(self):
        e = deepcopy(self.events)
        del e[0]["previous_head"]
        e[0]["issuer_verified"] = True
        self.defect("EVENT_SHAPE_INVALID", events=e)

    def test_28_attacker_owns_all_claims_and_recalculates_chain(self):
        e, w = fixture((("ENROLL", "attacker-key-a"),
                        ("ROTATE", "attacker-key-b")))
        r = self.denied(self.check(e, w))
        self.assertTrue(r["synthetic_sequence_structurally_consistent"])

    def test_29_coordinated_history_and_witness_rollback_not_detectable_locally(self):
        e, w = fixture((("ENROLL", "key-alpha"),))
        r = self.denied(self.check(e, w))
        self.assertTrue(r["synthetic_sequence_structurally_consistent"])
        self.assertIn("INDEPENDENT_APPEND_ONLY_CONSISTENCY_PROOF_MISSING", r["blockers"])

    def test_30_invalid_input_types_fail_closed(self):
        for events, views in ((None, None), (True, []), ("events", "views")):
            with self.subTest(value=type(events).__name__):
                r = self.denied(audit_key_lifecycle_claims_lab(events, views))
                self.assertFalse(r["synthetic_sequence_structurally_consistent"])

    def test_31_recovered_old_key_cannot_be_reused(self):
        e = deepcopy(self.events)
        e[3]["key_id"] = "key-alpha"
        self.defect("KEY_ID_REUSED", e)

    def test_32_witness_boolean_height_not_integer(self):
        w = deepcopy(self.views)
        w[1]["sequence"] = True
        self.defect("VIEW_FIELD_INVALID", views=w)


if __name__ == "__main__":
    unittest.main()
