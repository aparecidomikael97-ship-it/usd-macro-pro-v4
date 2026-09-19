import unittest

from atlasquant_setup_journal import (
    journal_template,
    normalize_setup_record,
    setup_forward_summary,
    validate_setup_record,
)


def record(**overrides):
    row={
        "setup_id":"session-liquidity-mss",
        "pair":"EUR/USD",
        "observed_at":"2026-09-19T12:00:00Z",
        "session":"London",
        "regime":"trend",
        "direction":"BUY",
        "entry":1.1000,
        "stop":1.0950,
        "target":1.1100,
        "result_r":1.5,
        "data_quality":88,
        "decision_state":"PAPER",
        "hard_blocks":[],
        "soft_blocks":["evento distante"],
        "invalidation":"perda da mínima",
    }
    row.update(overrides)
    return row


class AtlasQuantSetupJournalTests(unittest.TestCase):
    def test_valid_record_is_paper_only(self):
        out=validate_setup_record(record())
        self.assertTrue(out["valid"])
        self.assertTrue(out["paper_only"])
        self.assertFalse(out["real_order"])
        self.assertTrue(out["record"]["paper_only"])
        self.assertFalse(out["record"]["real_order"])

    def test_direction_is_normalized(self):
        row=normalize_setup_record(record(direction="compra"))
        self.assertEqual(row["direction"],"BUY")
        row=normalize_setup_record(record(direction="venda"))
        self.assertEqual(row["direction"],"SELL")

    def test_invalid_numeric_values_fail_closed(self):
        for field,bad in (
            ("entry","bad"),("stop",float("nan")),("target",None),
            ("result_r",float("inf")),("data_quality",101),
        ):
            with self.subTest(field=field):
                out=validate_setup_record(record(**{field:bad}))
                self.assertFalse(out["valid"])

    def test_entry_stop_target_must_be_distinct(self):
        self.assertFalse(validate_setup_record(record(stop=1.1000))["valid"])
        self.assertFalse(validate_setup_record(record(target=1.1000))["valid"])

    def test_wait_is_not_a_completed_directional_observation(self):
        out=validate_setup_record(record(direction="WAIT"))
        self.assertFalse(out["valid"])

    def test_forward_summary_is_setup_tagged(self):
        rows=[
            record(result_r=1.5,regime="trend",session="London"),
            record(result_r=-1.0,regime="range",session="New York",observed_at="2026-09-20T12:00:00Z"),
            record(result_r=0.5,regime="trend",session="London",observed_at="2026-09-21T12:00:00Z"),
        ]
        summary=setup_forward_summary(rows)["session-liquidity-mss"]
        self.assertEqual(summary["forward_samples"],3)
        self.assertAlmostEqual(summary["forward_expectancy_r"],0.3333,places=4)
        self.assertEqual(summary["regimes"],["range","trend"])
        self.assertEqual(summary["sessions"],["London","New York"])
        self.assertTrue(summary["paper_only"])

    def test_invalid_records_are_excluded_from_summary(self):
        rows=[record(),record(observed_at="bad")]
        summary=setup_forward_summary(rows)["session-liquidity-mss"]
        self.assertEqual(summary["forward_samples"],1)

    def test_template_has_no_filled_trade_result(self):
        df=journal_template()
        self.assertEqual(len(df),1)
        self.assertEqual(df.iloc[0]["result_r"],"")
        self.assertEqual(df.iloc[0]["entry"],"")


if __name__=="__main__":
    unittest.main()
