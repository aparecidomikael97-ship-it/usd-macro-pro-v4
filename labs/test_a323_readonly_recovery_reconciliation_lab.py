"""A323 LAB: real read-only SQLite recovery vs full A322/A321 contracts.

Uses A321's existing synthetic fixture factory (not live custody).
No operational restore, retry, provider, Worker, new service or paid plan.
"""
import copy
from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from labs.a317_detached_signed_intent_anchor_lab import encode, sha
from labs.a321_signed_high_water_fork_detection_lab import signing_bytes as a321_signing_bytes
from labs.a322_genesis_out_of_band_handoff_lab import generate_genesis_card
from labs.a323_readonly_recovery_reconciliation_lab import (
    SCHEMA, DB_NAME, FIXTURE_MARKER, FIXTURE_TEXT, LOCAL_FIELDS,
    read_disposable_local_state, verify_recovery_hold,
)
from labs.test_a321_signed_high_water_fork_detection_lab import (
    A321TwoCustodianForkTests,
)


class A323ReadOnlyRecoveryTests(unittest.TestCase):
    def setUp(self):
        # Reuse the previous TEST-ONLY fixture builder, with no real
        # database, network call or external signer.
        f = A321TwoCustodianForkTests(
            methodName="test_two_round_signed_history_valid_math_still_no_external_proof"
        )
        f.setUp()
        self.f = f
        self.genesis = self.make_genesis_package()
        self.history = self.make_history_package()
        self.temp = TemporaryDirectory(prefix="a323-lab-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / DB_NAME
        (self.path.parent / FIXTURE_MARKER).write_text(
            FIXTURE_TEXT, encoding="utf-8"
        )
        self.write_local_state()

    def make_genesis_package(self):
        manifest = self.f.old
        card = generate_genesis_card(
            public_manifest=manifest, ceremony_id="a323-synthetic-handoff",
        )
        card_digest = sha(encode(card))
        copies = []
        for idx in range(2):
            suffix = "A" if idx == 0 else "B"
            copies.append({
                "card_sha256": card_digest, "copy_id": "copy-" + suffix,
                "claimed_custodian_id": "custodian-" + suffix,
                "claimed_admin_domain": "admin-" + suffix,
                "claimed_account_id": "account-" + suffix,
                "claimed_device_id": "device-" + suffix,
                "claimed_recovery_domain": "recovery-" + suffix,
                "claimed_delivery_channel": "channel-" + suffix,
                "claimed_retained_at": 10000 + idx,
                "decision": "OBSERVED_ONLY",
            })
        return {
            "public_manifest": manifest,
            "genesis_card": card,
            "custody_copies": copies,
        }

    def make_history_package(self):
        return {
            "ceremony_request": self.f.ceremony,
            "starting_reference": self.f.base,
            "checkpoints": self.f.checkpoints,
            "expected_challenges": self.f.challenges,
            "observed_clock_epoch": 10060,
            "competing_reports": (),
            "revoked_custodian_ids": (),
        }

    def signed_head(self):
        r = self.f.checkpoints[-1][0]
        return {
            "root_generation": r["root_generation"],
            "incident_epoch": r["incident_epoch"],
            "sequence": r["sequence"],
            "head_sha256": r["head_sha256"],
            "intent_digest": r["intent_digest"],
        }

    def write_local_state(self, **overrides):
        values = {**self.signed_head(), **overrides}
        with closing(sqlite3.connect(str(self.path))) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS a323_recovery_state "
                "(root_generation INTEGER, incident_epoch INTEGER, "
                "sequence INTEGER, head_sha256 TEXT, intent_digest TEXT)"
            )
            connection.execute("DELETE FROM a323_recovery_state")
            connection.execute(
                "INSERT INTO a323_recovery_state VALUES (?,?,?,?,?)",
                (values["root_generation"], values["incident_epoch"],
                 values["sequence"], values["head_sha256"],
                 values["intent_digest"]),
            )
            connection.commit()

    def call(self, **changes):
        args = {
            "genesis_package": self.genesis,
            "history_package": self.history,
            "local_db_path": self.path,
        }
        args.update(changes)
        return verify_recovery_hold(**args)

    def assert_hold(self, report):
        self.assertEqual(report["schema"], SCHEMA)
        self.assertTrue(report["research_only"])
        self.assertTrue(report["synthetic_only"])
        self.assertFalse(report["evidence_sources_independently_authenticated"])
        self.assertFalse(report["actual_custodians_independently_identified"])
        self.assertFalse(report["first_genesis_pin_authenticated_out_of_band"])
        self.assertFalse(report["high_water_off_host_authenticated"])
        self.assertFalse(report["immutable_off_host_custody_proven"])
        self.assertFalse(report["provider_effect_ack_attested"])
        self.assertFalse(report["trusted_time_proven"])
        self.assertFalse(report["semantic_exactly_once_proven"])
        self.assertFalse(report["recovery_authorized"])
        self.assertFalse(report["can_recover_or_restore"])
        self.assertFalse(report["can_authorize_real_effect"])
        self.assertFalse(report["can_resume"])
        self.assertFalse(report["can_resend"])
        self.assertFalse(report["can_auto_retry"])
        self.assertEqual(report["automatic_retries"], 0)
        self.assertTrue(report["zero_auto_resend"])
        self.assertTrue(report["hard_no_go"])
        self.assertEqual(report["p0_homologated"], 0)
        self.assertTrue(report["no_worker_deploy_provider_orders"])
        self.assertFalse(report["new_paid_services"])

    def assert_veto(self, result, issue, *, status=None):
        self.assertNotEqual(
            result["status"], "LAB_RECOVERY_CONSISTENT_HOLD_NO_EXTERNAL_AUTHORITY"
        )
        if status is not None:
            self.assertEqual(result["status"], status)
        self.assertIn(issue, result["issues"])
        self.assert_hold(result)

    def test_matched_genesis_signatures_and_local_db_still_hold(self):
        result = self.call()
        self.assertEqual(
            result["status"],
            "LAB_RECOVERY_CONSISTENT_HOLD_NO_EXTERNAL_AUTHORITY",
        )
        self.assertTrue(result["claimed_signature_chain_checked"])
        self.assertTrue(result["local_snapshot_matches_latest_claimed_head"])
        self.assertEqual(result["issues"], [])
        self.assert_hold(result)

    def test_read_only_database_reader_returns_exact_fields(self):
        state, reason = read_disposable_local_state(self.path)
        self.assertIsNone(reason)
        self.assertEqual(set(state), LOCAL_FIELDS)
        self.assertEqual(state, self.signed_head())

    def test_reconciliation_does_not_write_any_database_fields(self):
        before, reason = read_disposable_local_state(self.path)
        self.assertIsNone(reason)
        for _ in range(3):
            self.assert_hold(self.call())
        after, reason = read_disposable_local_state(self.path)
        self.assertIsNone(reason)
        self.assertEqual(after, before)
        with closing(sqlite3.connect(str(self.path))) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM a323_recovery_state"
                ).fetchone()[0],
                1,
            )

    def test_missing_genesis_package_freezes_without_local_write(self):
        self.assert_veto(
            self.call(genesis_package=None),
            "A322_GENESIS_PACKAGE_MISSING",
            status="LAB_RECOVERY_MISSING_EVIDENCE",
        )

    def test_missing_history_package_freezes(self):
        self.assert_veto(
            self.call(history_package=None),
            "A321_HISTORY_PACKAGE_MISSING",
            status="LAB_RECOVERY_MISSING_EVIDENCE",
        )

    def test_untrusted_go_field_cannot_be_added_to_evidence(self):
        self.assert_veto(
            self.call(genesis_package=dict(self.genesis, can_resume=True)),
            "A322_GENESIS_PACKAGE_MISSING",
        )

    def test_untrusted_history_success_claim_does_not_replace_checks(self):
        self.assert_veto(
            self.call(history_package={"status": "success"}),
            "A321_HISTORY_PACKAGE_MISSING",
        )

    def test_one_declared_custodian_is_not_enough(self):
        package = copy.deepcopy(self.genesis)
        package["custody_copies"] = package["custody_copies"][:1]
        self.assert_veto(self.call(genesis_package=package), "A322_GENESIS_VETO")

    def test_old_card_cannot_be_used_after_rewriting_genesis(self):
        package = copy.deepcopy(self.genesis)
        package["public_manifest"]["high_water_sequence"] = 0
        self.assert_veto(self.call(genesis_package=package), "A322_GENESIS_VETO")

    def test_valid_other_genesis_does_not_match_signed_history_origin(self):
        package = copy.deepcopy(self.genesis)
        package["public_manifest"]["high_water_sequence"] = 0
        package["public_manifest"]["high_water_sha256"] = "0" * 64
        package["genesis_card"] = generate_genesis_card(
            public_manifest=package["public_manifest"],
            ceremony_id="alternate-ceremony",
        )
        new_digest = sha(encode(package["genesis_card"]))
        for copy_record in package["custody_copies"]:
            copy_record["card_sha256"] = new_digest
        self.assert_veto(
            self.call(genesis_package=package),
            "GENESIS_NOT_BOUND_TO_RECOVERY_HISTORY",
            status="LAB_RECOVERY_CONFLICT_VETO",
        )

    def test_signature_tamper_in_history_still_blocks_recovery(self):
        package = copy.deepcopy(self.history)
        package["checkpoints"][-1][1]["signature_hex"] = "0" * 128
        self.assert_veto(
            self.call(history_package=package), "A321_SIGNED_HISTORY_VETO",
        )

    def test_signed_witness_fork_blocks_recovery(self):
        package = copy.deepcopy(self.history)
        witness = package["checkpoints"][-1][1]
        witness["head_sha256"] = "e" * 64
        witness["signature_hex"] = self.f.witnesses[
            witness["custodian_id"]
        ].sign(a321_signing_bytes(witness)).hex()
        self.assert_veto(self.call(history_package=package),
                         "A321_SIGNED_HISTORY_VETO")

    def test_signed_checkpoint_missing_blocks_recovery(self):
        package = copy.deepcopy(self.history)
        package["checkpoints"] = []
        package["expected_challenges"] = []
        self.assert_veto(self.call(history_package=package),
                         "A321_SIGNED_HISTORY_VETO")

    def test_reopened_incident_is_hard_freeze_even_when_all_matched(self):
        self.assert_veto(
            self.call(incident_reopened=True),
            "INCIDENT_REOPENED_FREEZE", status="LAB_RECOVERY_DENIED",
        )

    def test_wrong_incident_flag_type_is_denied(self):
        for value in (1, 0, "false", None, [], {}):
            with self.subTest(value=repr(value)):
                self.assert_veto(
                    self.call(incident_reopened=value),
                    "CONTROL_INPUT_INVALID",
                )

    def test_restore_request_is_unconditionally_forbidden(self):
        for op in ("RESTORE", "RESEND", "RESTART_WORKER", "DEPLOY", ""):
            with self.subTest(operation=op):
                self.assert_veto(
                    self.call(operation=op),
                    "RECOVERY_OPERATION_NOT_ALLOWED",
                )

    def test_boolean_operation_is_not_accepted(self):
        self.assert_veto(
            self.call(operation=True), "CONTROL_INPUT_INVALID",
        )

    def test_missing_local_db_never_falls_back_to_creating_new_state(self):
        missing = self.path.parent / "other.db"
        self.assertFalse(missing.exists())
        self.assert_veto(
            self.call(local_db_path=missing), "LOCAL_FIXTURE_REFUSED",
            status="LAB_RECOVERY_MISSING_EVIDENCE",
        )
        self.assertFalse(missing.exists())

    def test_wrong_marker_blocks_local_read(self):
        marker = self.path.parent / FIXTURE_MARKER
        marker.write_text("not a legitimate LAB marker", encoding="utf-8")
        self.assert_veto(
            self.call(), "LOCAL_FIXTURE_REFUSED",
            status="LAB_RECOVERY_MISSING_EVIDENCE",
        )

    def test_local_db_stored_in_another_unmarked_folder_is_denied(self):
        with TemporaryDirectory(prefix="a323-unmarked-") as tmp:
            path = Path(tmp) / DB_NAME
            with closing(sqlite3.connect(str(path))) as db:
                db.execute("CREATE TABLE mock (id INTEGER)")
                db.commit()
            self.assert_veto(
                self.call(local_db_path=path), "LOCAL_FIXTURE_REFUSED",
            )

    def test_absent_local_state_row_freezes(self):
        with closing(sqlite3.connect(str(self.path))) as db:
            db.execute("DELETE FROM a323_recovery_state")
            db.commit()
        self.assert_veto(
            self.call(), "LOCAL_SNAPSHOT_MISSING_OR_AMBIGUOUS",
            status="LAB_RECOVERY_MISSING_EVIDENCE",
        )

    def test_two_local_state_rows_are_ambiguous_and_veto(self):
        with closing(sqlite3.connect(str(self.path))) as db:
            db.execute(
                "INSERT INTO a323_recovery_state VALUES (?,?,?,?,?)",
                tuple(self.signed_head()[k] for k in (
                    "root_generation", "incident_epoch", "sequence",
                    "head_sha256", "intent_digest",
                )),
            )
            db.commit()
        self.assert_veto(
            self.call(), "LOCAL_SNAPSHOT_MISSING_OR_AMBIGUOUS",
        )

    def test_malformed_local_digest_fails_closed(self):
        self.write_local_state(intent_digest="not-sha256")
        self.assert_veto(self.call(), "LOCAL_SNAPSHOT_MALFORMED")

    def test_wrong_integer_type_from_local_db_fails_closed(self):
        self.write_local_state(sequence="invalid")
        self.assert_veto(self.call(), "LOCAL_SNAPSHOT_MALFORMED")

    def test_local_sequence_rollback_is_detected(self):
        self.write_local_state(sequence=21)
        self.assert_veto(
            self.call(), "LOCAL_ROLLBACK_SEQUENCE",
            status="LAB_RECOVERY_CONFLICT_VETO",
        )

    def test_local_sequence_ahead_without_witness_receipt_is_denied(self):
        self.write_local_state(sequence=23)
        self.assert_veto(
            self.call(), "LOCAL_AHEAD_OF_CLAIMED_WITNESSES",
            status="LAB_RECOVERY_CONFLICT_VETO",
        )

    def test_local_head_hash_conflict_veto(self):
        self.write_local_state(head_sha256="f" * 64)
        self.assert_veto(
            self.call(), "LOCAL_HEAD_SHA256_CONFLICT",
            status="LAB_RECOVERY_CONFLICT_VETO",
        )

    def test_local_intent_digest_conflict_veto(self):
        self.write_local_state(intent_digest="0" * 64)
        self.assert_veto(
            self.call(), "LOCAL_INTENT_DIGEST_CONFLICT",
            status="LAB_RECOVERY_CONFLICT_VETO",
        )

    def test_local_root_generation_mismatch_veto(self):
        self.write_local_state(root_generation=5)
        self.assert_veto(self.call(), "LOCAL_ROOT_GENERATION_CONFLICT")

    def test_local_incident_epoch_mismatch_veto(self):
        self.write_local_state(incident_epoch=4)
        self.assert_veto(self.call(), "LOCAL_INCIDENT_EPOCH_CONFLICT")

    def test_corrupt_local_sqlite_is_not_silently_rebuilt(self):
        self.path.write_bytes(b"not-a-sqlite-database")
        self.assert_veto(
            self.call(), "LOCAL_SNAPSHOT_UNREADABLE",
            status="LAB_RECOVERY_MISSING_EVIDENCE",
        )

    def test_custodian_and_head_can_be_entirely_reminted_by_same_host(self):
        """Crucial P0-3/4 counterexample: entire history can be forged."""
        self.f.old["high_water_sequence"] = 0
        self.f.old["high_water_sha256"] = "0" * 64
        self.f.candidate["high_water_sequence"] = 0
        self.f.candidate["high_water_sha256"] = "0" * 64
        self.f.candidate["previous_manifest_sha256"] = sha(encode(self.f.old))
        self.f.recreate_ceremony()
        self.f.base["sequence"] = 0
        self.f.base["head_sha256"] = "0" * 64
        self.f.checkpoints = self.f.mint_checkpoints()
        self.genesis = self.make_genesis_package()
        self.history = self.make_history_package()
        self.write_local_state()
        observed = self.call()
        self.assertEqual(
            observed["status"],
            "LAB_RECOVERY_CONSISTENT_HOLD_NO_EXTERNAL_AUTHORITY",
        )
        self.assertTrue(observed["local_snapshot_matches_latest_claimed_head"])
        self.assertFalse(observed["high_water_off_host_authenticated"])
        self.assertFalse(observed["recovery_authorized"])
        self.assert_hold(observed)

    def test_malformed_local_path_types_never_open_operational_db(self):
        for bad in (None, [], {}, True, 1):
            with self.subTest(path=repr(bad)):
                self.assert_veto(
                    self.call(local_db_path=bad),
                    "LOCAL_FIXTURE_PATH_INVALID",
                )


if __name__ == "__main__":
    unittest.main()
