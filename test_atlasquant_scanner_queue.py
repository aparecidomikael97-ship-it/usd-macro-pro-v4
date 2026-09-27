import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_scanner_queue import next_batch, scanner_queue, technical_result_state


def complete_result(ts=1_000.0, source="Twelve Data"):
    return {
        "processado_em": ts,
        "source": source,
        "tecnico": {
            "disponivel": True,
            "h4": {"status": "BUY"},
            "h1": {"status": "BUY"},
            "m15": {"status": "WAIT"},
        },
    }


class ScannerQueueTests(unittest.TestCase):
    def test_queue_always_contains_exactly_the_28_unique_official_pairs(self):
        snapshot = scanner_queue({}, now_ts=2_000)
        self.assertEqual(snapshot["population"], 28)
        self.assertEqual(len(snapshot["pairs"]), 28)
        self.assertEqual(len(snapshot["queue"]), 28)
        self.assertEqual(set(snapshot["queue"]), set(OFFICIAL_PAIRS))
        self.assertEqual(len(set(snapshot["queue"])), 28)
        self.assertFalse(snapshot["selected_pair_required"])
        self.assertFalse(snapshot["real_orders_enabled"])

    def test_missing_stale_and_unverified_are_ahead_of_fresh(self):
        results = {
            OFFICIAL_PAIRS[0]: complete_result(ts=9_900),
            OFFICIAL_PAIRS[1]: complete_result(ts=1_000),
            OFFICIAL_PAIRS[2]: complete_result(ts=9_900, source=""),
        }
        snapshot = scanner_queue(results, now_ts=10_000, stale_after_minutes=45)
        by_pair = {row["pair"]: row for row in snapshot["pairs"]}
        self.assertEqual(by_pair[OFFICIAL_PAIRS[0]]["status"], "FRESH")
        self.assertTrue(by_pair[OFFICIAL_PAIRS[0]]["eligible_for_score"])
        self.assertEqual(by_pair[OFFICIAL_PAIRS[1]]["status"], "STALE")
        self.assertFalse(by_pair[OFFICIAL_PAIRS[1]]["eligible_for_score"])
        self.assertEqual(by_pair[OFFICIAL_PAIRS[2]]["status"], "UNVERIFIED")
        self.assertFalse(by_pair[OFFICIAL_PAIRS[2]]["eligible_for_score"])
        self.assertNotIn(OFFICIAL_PAIRS[0], next_batch(snapshot, 2))

    def test_incomplete_timeframes_fail_closed(self):
        raw = complete_result()
        raw["tecnico"]["m15"] = {}
        state = technical_result_state(raw)
        self.assertFalse(state["complete"])
        self.assertFalse(state["eligible_for_score"])
        snapshot = scanner_queue({OFFICIAL_PAIRS[0]: raw}, now_ts=2_000)
        first = next(row for row in snapshot["pairs"] if row["pair"] == OFFICIAL_PAIRS[0])
        self.assertEqual(first["status"], "MISSING")
        self.assertFalse(first["eligible_for_score"])

    def test_unknown_and_duplicate_storage_keys_cannot_change_population(self):
        results = {"EUR/USD": complete_result(), "eur/usd": complete_result(), "USD/XXX": complete_result()}
        snapshot = scanner_queue(results, now_ts=1_001)
        self.assertEqual(snapshot["population"], 28)
        self.assertEqual(len(set(snapshot["queue"])), 28)

    def test_batch_size_is_bounded_and_invalid_size_is_empty(self):
        snapshot = scanner_queue({}, now_ts=1)
        self.assertEqual(next_batch(snapshot, 100), list(OFFICIAL_PAIRS))
        self.assertEqual(next_batch(snapshot, "x"), [])


if __name__ == "__main__":
    unittest.main()
