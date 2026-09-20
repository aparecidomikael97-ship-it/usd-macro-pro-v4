import base64
import unittest
from unittest.mock import Mock, patch

from atlasquant_setup_journal import (
    journal_template,
    normalize_setup_record,
    setup_forward_summary,
    validate_setup_record,
)
from atlasquant_paper_setup_bridge import (
    bridge_paper_audit,
    canonical_setup_id,
    load_paper_audit_runtime,
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

    def test_paper_bridge_accepts_only_explicit_known_setup_tags(self):
        import pandas as pd
        audit=pd.DataFrame([
            {
                "trade_id":"t1","setup_id":"FVG","setup_attribution":"EXPLICIT_INPUT",
                "pair":"EUR/USD","status":"CLOSED","side":"BUY",
                "signal_time":"2026-09-20T12:00:00Z",
                "active_session":"London","d1_regime":"trend",
                "entry_price":1.1,"stop_price":1.09,"target_price":1.12,
                "realized_r":2.0,"data_quality_pct":100,
            },
            {
                "trade_id":"t2","setup_id":"","setup_attribution":"UNATTRIBUTED",
                "pair":"EUR/USD","status":"CLOSED","side":"SELL",
                "signal_time":"2026-09-20T13:00:00Z",
                "active_session":"London","d1_regime":"trend",
                "entry_price":1.1,"stop_price":1.11,"target_price":1.08,
                "realized_r":-1.0,"data_quality_pct":100,
            },
        ])
        out=bridge_paper_audit(audit)
        self.assertEqual(out["closed_rows"],2)
        self.assertEqual(out["explicit_rows"],1)
        self.assertEqual(out["eligible_records"],1)
        self.assertEqual(out["records"][0]["setup_id"],"fvg")
        self.assertEqual(out["summary_by_setup"]["fvg"]["forward_samples"],1)
        self.assertFalse(out["setup_inference_used"])
        self.assertEqual(out["excluded"]["ATTRIBUTION_NOT_EXPLICIT"],1)

    def test_paper_bridge_rejects_unknown_or_incomplete_attribution(self):
        import pandas as pd
        audit=pd.DataFrame([
            {
                "trade_id":"unknown","setup_id":"mystery","setup_attribution":"EXPLICIT_INPUT",
                "pair":"EUR/USD","status":"CLOSED","side":"BUY",
                "signal_time":"2026-09-20T12:00:00Z","active_session":"London",
                "d1_regime":"trend","entry_price":1.1,"stop_price":1.09,
                "target_price":1.12,"realized_r":2.0,"data_quality_pct":100,
            },
            {
                "trade_id":"quality","setup_id":"fvg","setup_attribution":"EXPLICIT_INPUT",
                "pair":"EUR/USD","status":"CLOSED","side":"BUY",
                "signal_time":"2026-09-20T12:15:00Z","active_session":"London",
                "d1_regime":"trend","entry_price":1.1,"stop_price":1.09,
                "target_price":1.12,"realized_r":2.0,"data_quality_pct":None,
            },
        ])
        out=bridge_paper_audit(audit)
        self.assertEqual(out["eligible_records"],0)
        self.assertEqual(out["excluded"]["UNKNOWN_SETUP_ID"],1)
        self.assertEqual(out["excluded"]["MISSING_DATA_QUALITY"],1)

    def test_runtime_loader_rejects_code_branch_before_network(self):
        with patch("atlasquant_paper_setup_bridge.requests.get") as get:
            frame,status=load_paper_audit_runtime(
                repo="owner/repo",branch="main",token="secret"
            )
        self.assertTrue(frame.empty)
        self.assertEqual(status["reason"],"UNSAFE_BRANCH")
        get.assert_not_called()

    def test_runtime_loader_reads_csv_from_safe_runtime_branch(self):
        csv=(
            "trade_id,setup_id,setup_attribution,pair,status,side,signal_time,"
            "active_session,d1_regime,entry_price,stop_price,target_price,"
            "realized_r,data_quality_pct\n"
            "t1,fvg,EXPLICIT_INPUT,EUR/USD,CLOSED,BUY,2026-09-20T12:00:00Z,"
            "London,trend,1.10,1.09,1.12,2.0,100\n"
        )
        response=Mock()
        response.status_code=200
        response.json.return_value={"content":base64.b64encode(csv.encode("utf-8")).decode("ascii")}
        response.raise_for_status.return_value=None
        with patch("atlasquant_paper_setup_bridge.requests.get",return_value=response) as get:
            frame,status=load_paper_audit_runtime(
                repo="owner/repo",branch="atlasquant-runtime",token="secret"
            )
        self.assertTrue(status["ok"])
        self.assertEqual(status["reason"],"LOADED")
        self.assertEqual(len(frame),1)
        self.assertEqual(frame.iloc[0]["setup_id"],"fvg")
        get.assert_called_once()

    def test_setup_aliases_are_canonical_without_guessing_from_components(self):
        self.assertEqual(canonical_setup_id("AMD / PO3"),"amd-po3")
        self.assertEqual(canonical_setup_id("FVG"),"fvg")
        self.assertEqual(canonical_setup_id("FVG / desequilíbrio"),"fvg")
        self.assertEqual(canonical_setup_id("OTE / Fibonacci"),"ote")
        self.assertEqual(canonical_setup_id("Liquidez de sessão + MSS"),"session-liquidity-mss")
        self.assertEqual(canonical_setup_id("random ict state"),"")

    def test_template_has_no_filled_trade_result(self):
        df=journal_template()
        self.assertEqual(len(df),1)
        self.assertEqual(df.iloc[0]["result_r"],"")
        self.assertEqual(df.iloc[0]["entry"],"")


if __name__=="__main__":
    unittest.main()
