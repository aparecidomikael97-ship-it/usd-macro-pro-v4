"""Fed H.10 weekly release lag and offline EUR/USD quotation integrity."""
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import unittest

from atlasquant_trader_fed_h10_euro_history_lab import (
    SCHEMA, inspect_fed_h10_euro_history_lab as inspect,
)

CAPTURE = datetime(2026, 11, 5, 2, 40, tzinfo=timezone.utc)
AS_OF = datetime(2026, 11, 5, 3, 0, tzinfo=timezone.utc)
EVENT = datetime(2026, 10, 28, 18, 0, tzinfo=timezone.utc)


def html(*, rows=(("28-OCT-26", "1.1140"), ("29-OCT-26", "1.1165"),
                  ("30-OCT-26", "1.1163")),
         heading="Release Date: Monday, November 02, 2026",
         table_title="Historical Rates for the EU Euro") -> bytes:
    tr = "".join(f'<tr><th id="r1" headers="a1">{d} </th>'
                 f'<td headers="a2 a1 r1"> {v} </td></tr>' for d, v in rows)
    return (f'<!DOCTYPE html><html lang="en"><body><div class="dates">{heading}</div>'
            f'<h5 class="tablehead">Historical Rates for the EU Euro</h5>'
            f'<span class="tableunit">(Rates in U.S. dollars per EU euro)</span>'
            f'<table class="pubtables" title="{table_title}"><thead>'
            f'<th scope="col">Date</th><th scope="col">Rate</th></thead>{tr}'
            f'</table></body></html>').encode()


_UNSET = object()


def run(raw=_UNSET, **kwargs):
    args = dict(captured_at_utc=CAPTURE, as_of_utc=AS_OF,
                requested_start_date="2026-10-28", requested_end_date="2026-10-30",
                event_at_utc=EVENT)
    args.update(kwargs)
    return inspect(html() if raw is _UNSET else raw, **args)


class H10EuroHistoryTests(unittest.TestCase):
    def test_unchanged_h10_rows_and_five_day_publication_lag(self):
        raw = html()
        r = run(raw)
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["state"], "LAB_H10_WEEKLY_RELEASE_DAILY_OBSERVATIONS_ONLY")
        self.assertEqual(r["source_release_date"], "2026-11-02")
        self.assertEqual(r["source_raw_sha256"], sha256(raw).hexdigest())
        self.assertEqual(r["start_observed_rate"], "1.1140")
        self.assertEqual(r["end_observed_rate"], "1.1163")
        self.assertEqual(r["numeric_observations"], 3)
        self.assertEqual(r["missing_nd_observations"], 0)
        self.assertTrue(r["source_publication_after_event_date"])
        self.assertTrue(r["source_unavailable_on_event_day"])
        self.assertEqual(r["reason"], "H10_RELEASE_AFTER_EVENT_NO_PRE_EVENT_ACCESS")

    def test_post_release_event_does_not_imply_point_in_time_vintage(self):
        r = run(event_at_utc=datetime(2026, 11, 4, 19, tzinfo=timezone.utc))
        self.assertIs(r["source_publication_after_event_date"], False)
        self.assertIsNone(r["source_unavailable_on_event_day"])
        self.assertEqual(r["reason"], "NO_INDEPENDENT_HISTORICAL_VINTAGE_OR_M15_QUOTE")

    def test_no_signal_in_success_and_failure_branches(self):
        for r in (run(), run(b"not a table")):
            for flag in ("trade_authorized", "can_feed_live_radar", "publishable",
                         "worker_enabled", "scheduler_enabled",
                         "historical_point_in_time_eligible",
                         "independent_executable_m15_price_verified",
                         "source_release_instant_independently_verified",
                         "historical_vintage_independently_verified"):
                self.assertIs(r[flag], False, flag)
            self.assertIsNone(r["fx_bias"])
            self.assertIsNone(r["market_surprise_bps"])
            self.assertEqual(r["operational_bias"], "AGUARDAR")
            self.assertEqual(r["new_cost_brl"], 0)

    def test_nd_preserved_as_missing_not_zero(self):
        raw = html(rows=(("28-OCT-26", "1.1140"), ("29-OCT-26", "ND"),
                         ("30-OCT-26", "1.1163")))
        r = run(raw)
        self.assertEqual(r["missing_nd_observations"], 1)
        self.assertEqual(r["numeric_observations"], 2)
        self.assertEqual(run(raw, requested_end_date="2026-10-29")["reason"],
                         "H10_DAY_MISSING_OR_ND_NO_INTERPOLATION")

    def test_missing_day_is_not_forward_filled(self):
        self.assertEqual(run(requested_start_date="2026-10-27")["reason"],
                         "H10_DAY_MISSING_OR_ND_NO_INTERPOLATION")

    def test_reject_future_release_as_of_or_capture(self):
        self.assertEqual(run(html(heading="Release Date: Monday, November 09, 2026"))["state"],
                         "LAB_BLOCKED")

    def test_reject_observation_same_day_as_release(self):
        self.assertEqual(run(html(rows=(("28-OCT-26", "1.1140"),
                                        ("2-NOV-26", "1.1163"))))["state"],
                         "LAB_BLOCKED")

    def test_reject_duplicate_or_descending_observations(self):
        for rows in ((("28-OCT-26", "1.11"), ("28-OCT-26", "1.12")),
                     (("30-OCT-26", "1.11"), ("28-OCT-26", "1.12"))):
            self.assertEqual(run(html(rows=rows))["state"], "LAB_BLOCKED")

    def test_reject_invalid_numeric_strings(self):
        for value in ("-", "NaN", "Inf", "-1", "0.0000", "1,2", "1e2",
                      "999.00", "", "1.2.3", "+1.12"):
            with self.subTest(value=value):
                self.assertEqual(run(html(rows=(("28-OCT-26", value),
                                                 ("30-OCT-26", "1.1163"))))["state"],
                                 "LAB_BLOCKED")

    def test_reject_malformed_release_or_wrong_weekday(self):
        for heading in ("Release Date: Sunday, November 02, 2026",
                        "Release Date: Monday, October 32, 2026",
                        "Release Date: Thursday, November 02, 2026",
                        "Release Date: Monday, November 02, 2028"):
            self.assertEqual(run(html(heading=heading))["state"], "LAB_BLOCKED")

    def test_reject_table_title_drift_or_duplicate_tables(self):
        self.assertEqual(run(html(table_title="New Buy Signals"))["state"], "LAB_BLOCKED")
        raw = html()
        duplicated = raw.replace(b"</body>",
                                 b'<table class="pubtables" title="Historical Rates for the EU Euro">'
                                 b'<tr><th>29-OCT-26</th><td>1.1165</td></tr></table></body>')
        self.assertEqual(run(duplicated)["state"], "LAB_BLOCKED")

    def test_reject_wrong_currency_unit(self):
        self.assertEqual(run(html(table_title="Historic USD per JPY"))["state"],
                         "LAB_BLOCKED")
        changed = html().replace(b'(Rates in U.S. dollars per EU euro)',
                                 b'(Rates in Japanese yen per EU euro)')
        self.assertEqual(run(changed)["state"], "LAB_BLOCKED")
        changed_heading = html().replace(b'<h5 class="tablehead">Historical Rates for the EU Euro',
                                         b'<h5 class="tablehead">Historical Rates for the EU Yen')
        self.assertEqual(run(changed_heading)["state"], "LAB_BLOCKED")

    def test_reject_invalid_capture_and_event_clock(self):
        for args in (dict(as_of_utc=CAPTURE - timedelta(seconds=1)),
                     dict(captured_at_utc=datetime(2026, 11, 5)),
                     dict(event_at_utc=datetime(2026, 11, 6, tzinfo=timezone.utc)),
                     dict(as_of_utc=None)):
            self.assertEqual(run(**args)["state"], "LAB_BLOCKED")

    def test_reject_requested_future_or_reversed_window(self):
        for args in (dict(requested_end_date="2026-11-06"),
                     dict(requested_start_date="2026-10-30",
                          requested_end_date="2026-10-28"),
                     dict(requested_start_date="2026-10-28",
                          requested_end_date="2026-10-28"),
                     dict(requested_start_date="2026-10-3")):
            self.assertEqual(run(**args)["state"], "LAB_BLOCKED")

    def test_reject_invalid_raw_or_wrong_html_encoding(self):
        for raw in (None, "<table>", b"", b"x" * (2 * 1024 * 1024 + 1),
                    html() + b"\xff"):
            self.assertEqual(run(raw)["state"], "LAB_BLOCKED")

    def test_reject_weekend_or_invalid_observation_date(self):
        for day in ("31-OCT-26", "32-OCT-26", "2-NOO-26"):
            self.assertEqual(run(html(rows=(("28-OCT-26", "1.1140"),
                                             (day, "1.1163"))))["state"], "LAB_BLOCKED")


if __name__ == "__main__":
    unittest.main()
