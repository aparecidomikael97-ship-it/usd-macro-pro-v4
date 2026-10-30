"""A278: hash-chain integrity is not independent timestamp attestation."""
from datetime import datetime, timedelta, timezone
import copy
import unittest

from atlasquant_aion_plan_journal_lab import (
    SCHEMA, GENESIS, empty_plan_journal, append_manual_plan,
    verify_plan_journal, research_backtest_journal_csv,
)
from labs.test_a277_csv_backtest_holdout import (
    NOW, BASE, PLANS, csv_data, plan, stamp,
)


def filled(symbol="EURUSD"):
    journal = empty_plan_journal(symbol=symbol, timeframe="M15")
    for item in PLANS:
        observed = datetime.fromisoformat(item["signal_time"]) + timedelta(minutes=1)
        receipt = append_manual_plan(journal, plan=item, captured_at=observed)
        if not receipt["accepted"]:
            raise AssertionError("bad fixture " + str(receipt["error"]))
        journal = receipt["journal"]
    return journal


def evaluate(journal=None, **overrides):
    archive = filled() if journal is None else journal
    args = {
        "csv_text": csv_data(),
        "journal": archive, "expected_head": archive["head_sha256"],
        "symbol": "EURUSD", "timeframe": "M15",
        "timestamp_basis": "CLOSE", "now": NOW,
        "validation_start": stamp(8),
        "cost_r": 0.1, "slippage_r": 0.05,
        "max_wait_bars": 2, "max_hold_bars": 3,
    }
    args.update(overrides)
    return research_backtest_journal_csv(**args)


class A278LocalJournalTests(unittest.TestCase):
    def test_01_empty_scaffold_exposes_no_custody_claim(self):
        journal = empty_plan_journal(symbol="WIN", timeframe="M5")
        self.assertEqual(journal["schema"], SCHEMA)
        self.assertEqual(journal["head_sha256"], GENESIS)
        self.assertEqual(journal["entries"], [])
        self.assertIs(journal["externally_attested"], False)
        self.assertFalse(journal["authorizes_send"])
        self.assertEqual(journal["p0_homologated"], 0)
        self.assertTrue(verify_plan_journal(journal, expected_head=GENESIS)["valid"])

    def test_02_append_pins_ordered_local_plan_chain_without_mutation(self):
        original = empty_plan_journal(symbol="EURUSD", timeframe="M15")
        snapshot = copy.deepcopy(original)
        item = plan(0)
        receipt = append_manual_plan(
            original, plan=item, captured_at=BASE + timedelta(minutes=1),
        )
        self.assertTrue(receipt["accepted"])
        self.assertEqual(original, snapshot)
        next_journal = receipt["journal"]
        self.assertEqual(len(next_journal["entries"]), 1)
        entry = next_journal["entries"][0]
        self.assertEqual(entry["sequence"], 1)
        self.assertEqual(entry["previous_sha256"], GENESIS)
        self.assertEqual(entry["sha256"], next_journal["head_sha256"])
        self.assertEqual(len(entry["sha256"]), 64)
        self.assertFalse(receipt["externally_attested"])

    def test_03_full_chained_journal_is_repeatably_verifiable(self):
        archive = filled()
        verdict = verify_plan_journal(archive, expected_head=archive["head_sha256"])
        self.assertTrue(verdict["valid"])
        self.assertEqual(verdict["entry_count"], 4)
        self.assertEqual(verdict["plans"], [
            {**p, "entry": float(p["entry"]), "stop": float(p["stop"]),
             "target": float(p["target"])} for p in PLANS
        ])
        self.assertEqual(verdict["time_provenance"], "CALLER_DECLARED_LOCAL_ONLY")

    def test_04_valid_journal_runs_a277_without_signal_generation(self):
        report = evaluate()
        self.assertTrue(report["valid"])
        self.assertEqual(report["train"]["summary"]["net_r"], 3.7)
        self.assertEqual(report["holdout"]["summary"]["net_r"], 0.7)
        self.assertEqual(report["plan_journal_entry_count"], 4)
        self.assertFalse(report["signal_generation"])
        self.assertFalse(report["externally_attested"])
        self.assertFalse(report["authorizes_send"])
        self.assertTrue(report["no_orders"])
        self.assertEqual(report["p0_homologated"], 0)

    def test_05_tampered_plan_is_rejected_even_if_original_head_retained(self):
        archive = filled()
        pinned = archive["head_sha256"]
        fake = copy.deepcopy(archive)
        fake["entries"][0]["plan"]["entry"] = 10.5
        self.assertFalse(verify_plan_journal(fake, expected_head=pinned)["valid"])
        self.assertFalse(evaluate(fake, expected_head=pinned)["valid"])

    def test_06_rebuilt_or_changed_head_refused_by_separate_pinned_digest(self):
        archive = filled()
        pinned = archive["head_sha256"]
        fake = copy.deepcopy(archive)
        fake["head_sha256"] = "a" * 64
        verdict = verify_plan_journal(fake, expected_head=pinned)
        self.assertFalse(verdict["valid"])
        self.assertEqual(verdict["error"], "UNPINNED_OR_MISMATCHED_HEAD")
        self.assertFalse(evaluate(fake, expected_head=pinned)["valid"])

    def test_07_broken_sequence_previous_or_digest_is_refused(self):
        archive = filled()
        for mutation in (
            lambda item: item.__setitem__("sequence", 2),
            lambda item: item.__setitem__("previous_sha256", "a" * 64),
            lambda item: item.__setitem__("sha256", "b" * 64),
        ):
            with self.subTest(mutation=mutation.__code__.co_firstlineno):
                fake = copy.deepcopy(archive)
                mutation(fake["entries"][0])
                self.assertFalse(verify_plan_journal(
                    fake, expected_head=archive["head_sha256"]
                )["valid"])

    def test_08_capture_after_first_executable_candle_close_is_rejected(self):
        original = empty_plan_journal(symbol="EURUSD", timeframe="M15")
        receipt = append_manual_plan(original, plan=plan(0),
                                     captured_at=BASE + timedelta(minutes=15))
        self.assertFalse(receipt["accepted"])
        self.assertEqual(receipt["error"], "INVALID_CAPTURE_ORDER_OR_DUPLICATE")
        self.assertIsNone(receipt["journal"])

    def test_09_capture_near_but_before_next_close_is_allowed_as_claim(self):
        original = empty_plan_journal(symbol="EURUSD", timeframe="M15")
        receipt = append_manual_plan(original, plan=plan(0),
                                     captured_at=BASE + timedelta(minutes=14))
        self.assertTrue(receipt["accepted"])
        self.assertFalse(verify_plan_journal(
            receipt["journal"], expected_head=receipt["head_sha256"]
        )["externally_attested"])

    def test_10_backward_capture_time_and_duplicate_plan_blocked(self):
        archive = empty_plan_journal(symbol="EURUSD", timeframe="M15")
        first = append_manual_plan(archive, plan=plan(0),
                                   captured_at=BASE + timedelta(minutes=5))
        duplicate = append_manual_plan(first["journal"], plan=plan(0),
                                       captured_at=BASE + timedelta(minutes=6))
        self.assertFalse(duplicate["accepted"])
        second = append_manual_plan(
            first["journal"], plan=plan(4, "OB", "SELL", 11, 12, 9),
            captured_at=BASE + timedelta(minutes=4),
        )
        self.assertFalse(second["accepted"])

    def test_11_timestamps_are_timezone_aware_and_native(self):
        original = empty_plan_journal(symbol="EURUSD", timeframe="M15")
        for timestamp in (None, "2026-09-30T22:01:00Z",
                          datetime(2026, 9, 30, 22, 1),
                          BASE.replace(tzinfo=None)):
            self.assertFalse(append_manual_plan(original, plan=plan(0),
                                                captured_at=timestamp)["accepted"])
        offset_time = (BASE + timedelta(minutes=1)).astimezone(
            timezone(timedelta(hours=-4))
        )
        self.assertTrue(append_manual_plan(original, plan=plan(0),
                                           captured_at=offset_time)["accepted"])

    def test_12_unknown_symbol_timeframe_and_mismatch_refused(self):
        with self.assertRaises(ValueError):
            empty_plan_journal(symbol="US100", timeframe="M15")
        with self.assertRaises(ValueError):
            empty_plan_journal(symbol="EURUSD", timeframe="M1")
        self.assertFalse(evaluate(symbol="WIN")["valid"])
        self.assertEqual(evaluate(symbol="WIN")["error"],
                         "JOURNAL_ASSET_TIMEFRAME_MISMATCH")

    def test_13_invalid_plan_native_types_or_levels_fail_closed(self):
        original = empty_plan_journal(symbol="EURUSD", timeframe="M15")
        class Hostile(dict):
            def items(self):
                raise AssertionError("hostile callback")
        for bad in (Hostile(plan(0)), plan(0, target=9), plan(0, entry=True),
                    plan(0, entry=10**1000), {**plan(0), "side": "LONG"},
                    {**plan(0), "unknown": 1}):
            with self.subTest(bad_type=type(bad).__name__):
                self.assertFalse(append_manual_plan(
                    original, plan=bad, captured_at=BASE
                )["accepted"])

    def test_14_invalid_journal_and_malicious_subclasses_are_refused(self):
        archive = filled()
        class Hostile(dict):
            def get(self, *_):
                raise AssertionError("hostile mapping callback")
        self.assertFalse(verify_plan_journal(
            Hostile(archive), expected_head=archive["head_sha256"]
        )["valid"])
        self.assertFalse(verify_plan_journal(
            archive, expected_head=None
        )["valid"])
        self.assertFalse(append_manual_plan(
            Hostile(archive), plan=plan(0), captured_at=BASE
        )["accepted"])

    def test_15_fake_attestation_authority_is_rejected(self):
        archive = filled()
        for name, value in (
            ("externally_attested", True),
            ("authorizes_send", True),
            ("p0_homologated", 1),
        ):
            fake = copy.deepcopy(archive)
            fake[name] = value
            self.assertFalse(verify_plan_journal(
                fake, expected_head=archive["head_sha256"]
            )["valid"])

    def test_16_corrupt_capture_timestamp_is_refused(self):
        archive = filled()
        fake = copy.deepcopy(archive)
        fake["entries"][0]["captured_at"] = "2026-09-30T22:01:00"
        self.assertFalse(verify_plan_journal(
            fake, expected_head=archive["head_sha256"]
        )["valid"])

    def test_17_too_many_entries_are_rejected_before_hashing(self):
        archive = filled()
        fake = copy.deepcopy(archive)
        fake["entries"] = [fake["entries"][0]] * 201
        self.assertFalse(verify_plan_journal(
            fake, expected_head=archive["head_sha256"]
        )["valid"])

    def test_18_bad_csv_or_changed_commitment_does_not_produce_trades(self):
        archive = filled()
        bad = evaluate(csv_text="closed_at,open,high,low,close\n")
        self.assertFalse(bad["valid"])
        self.assertIsNone(bad["train"])
        self.assertIsNone(bad["holdout"])
        bad = evaluate(expected_head="c" * 64)
        self.assertFalse(bad["valid"])
        self.assertIsNone(bad["train"])
        self.assertIsNone(bad["holdout"])

    def test_19_futures_root_remains_readonly_and_unattested(self):
        archive = filled(symbol="WIN")
        report = evaluate(archive, symbol="WIN")
        self.assertTrue(report["valid"])
        self.assertFalse(report["externally_attested"])
        self.assertFalse(report["authorizes_send"])
        self.assertEqual(report["p0_homologated"], 0)

    def test_20_local_hash_chain_is_not_independent_timestamp_proof(self):
        archive = filled()
        verdict = verify_plan_journal(
            archive, expected_head=archive["head_sha256"]
        )
        self.assertTrue(verdict["valid"])
        self.assertEqual(verdict["time_provenance"], "CALLER_DECLARED_LOCAL_ONLY")
        self.assertFalse(verdict["externally_attested"])
        self.assertFalse(evaluate(archive)["holdout_is_independently_attested"])


if __name__ == "__main__":
    unittest.main()
