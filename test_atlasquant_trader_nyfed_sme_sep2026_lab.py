"""Synthetic XLSX ZIP/XML tests; not genuine survey history or trading data."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile
import unittest

from atlasquant_trader_nyfed_sme_sep2026_lab import (
    HEADERS, ROW_METADATA, inspect_nyfed_sme_sep2026_oct_meeting_lab as inspect,
)

UTC = timezone.utc
NOW = datetime(2026, 11, 5, 12, tzinfo=UTC)
DEFAULT_RAW = object()


def make_xlsx(*, exclude=None, override=None, panels=True, duplicate=False,
              wrong_header=False, corrupt_formula=False) -> bytes:
    """Create a tiny in-memory OOXML fixture; never export workbook files."""
    exclude = exclude or set()
    override = override or {}
    columns = [chr(c) for c in range(ord("A"), ord("U") + 1)]

    def row_xml(i, fields):
        parts = []
        for col in columns:
            val = fields.get(col, "")
            if col == "U" and i != 1:
                body = f'<v>{escape(str(val))}</v>'
                if corrupt_formula and i == 4:
                    body = '<f>1+1</f>' + body
                parts.append(f'<c r="{col}{i}" t="n">{body}</c>')
            else:
                parts.append(f'<c r="{col}{i}" t="inlineStr"><is><t>{escape(str(val))}</t></is></c>')
        return f'<row r="{i}">' + "".join(parts) + '</row>'

    headers = {c: HEADERS[i] for i, c in enumerate(columns)}
    if wrong_header:
        headers["A"] = "SURVEY_DATE_UNKNOWN"
    rows = [row_xml(1, headers)]
    number = 1
    entries = []
    for panel in (("Combined", "Dealer", "Participant") if panels else ("Combined",)):
        for agg, value in (("count", "62"), ("pctl75", "0.0388"),
                           ("pctl50", "0.0363"), ("pctl25", "0.0363")):
            if agg in exclude and panel == "Combined":
                continue
            fields = dict(ROW_METADATA)
            fields.update({"C": panel, "T": agg, "U": value})
            fields.update(override)
            entries.append(fields)
    if duplicate:
        fields = dict(ROW_METADATA)
        fields.update({"T": "pctl50", "U": "0.0363"})
        entries.append(fields)
    for fields in entries:
        number += 1
        rows.append(row_xml(number, fields))
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    xml = (f'<worksheet xmlns="{main}"><sheetData>' + "".join(rows)
           + '</sheetData></worksheet>').encode("utf-8")
    wb = (f'<workbook xmlns="{main}"><sheets>'
          '<sheet name="Sheet1" sheetId="1"/></sheets></workbook>').encode()
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as z:
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/worksheets/sheet1.xml", xml)
    return buffer.getvalue()


def case(raw=DEFAULT_RAW, **changes):
    args = {"captured_at_utc": NOW, "as_of_utc": NOW,
            "requested_meeting_end_date": "2026-10-28"}
    args.update(changes)
    return inspect(make_xlsx() if raw is DEFAULT_RAW else raw, **args)


class NyFedSmeSep2026Tests(unittest.TestCase):
    def test_valid_combined_only_and_fraction_to_percent(self):
        raw = make_xlsx()
        r = case(raw)
        self.assertEqual(r["state"], "LAB_USD_OCTOBER_MEETING_SURVEY_CONTEXT_UNVERIFIED")
        self.assertEqual(r["median_target_range_midpoint_pct"], "3.63")
        self.assertEqual(r["pctl25_target_range_midpoint_pct"], "3.63")
        self.assertEqual(r["pctl75_target_range_midpoint_pct"], "3.88")
        self.assertEqual(r["respondents_in_question"], 62)
        self.assertEqual(r["source_raw_sha256"], sha256(raw).hexdigest())
        self.assertTrue(r["aggregation_is_median_of_modal_point_forecasts"])
        self.assertEqual(r["survey_meeting_end_date"], "2026-10-28")

    def test_questionnaire_date_cannot_be_results_publication_proof(self):
        r = case()
        self.assertEqual(r["questionnaire_distributed_on"], "2026-09-02")
        self.assertEqual(r["responses_due_on"], "2026-09-08")
        self.assertEqual(r["results_release_date_inferred_from_minutes_rule"], "2026-10-08")
        self.assertFalse(r["results_publication_date_independently_verified"])
        self.assertFalse(r["results_publication_instant_independently_verified"])
        self.assertFalse(r["historical_survey_vintage_independently_verified"])

    def test_other_panels_must_not_triple_count_combined_sample(self):
        r = case(make_xlsx(panels=True))
        self.assertEqual(r["respondents_in_question"], 62)

    def test_combined_alone_can_be_read_without_dealer_and_participant(self):
        self.assertEqual(case(make_xlsx(panels=False))["respondents_in_question"], 62)

    def test_missing_aggregation_fails(self):
        self.assertEqual(case(make_xlsx(exclude={"pctl50"}))["reason"],
                         "EXPECTED_FOMC_MEDIAN_ROWS_MISSING")

    def test_duplicate_combined_percentile_rejected(self):
        self.assertEqual(case(make_xlsx(duplicate=True))["reason"], "XLSX_REJECTED")

    def test_wrong_header_fails_closed(self):
        self.assertEqual(case(make_xlsx(wrong_header=True))["reason"], "XLSX_REJECTED")

    def test_invalid_currency_horizon_or_question_rejected(self):
        for change in ({"A": "2026-10-08"}, {"B": "2026-10-07"},
                       {"G": "SOFR"}, {"P": "2026-09-16"},
                       {"K": "other_question"}):
            with self.subTest(change=change):
                self.assertEqual(case(make_xlsx(override=change))["reason"],
                                 "XLSX_REJECTED")

    def test_out_of_range_percentile_rejected(self):
        self.assertEqual(case(make_xlsx(override={"U": "0.90"}))["reason"], "XLSX_REJECTED")

    def test_formula_value_rejected(self):
        self.assertEqual(case(make_xlsx(corrupt_formula=True))["reason"], "XLSX_REJECTED")

    def test_bad_input_clock_future_or_wrong_meeting_rejected(self):
        for change in ({"captured_at_utc": NOW.replace(tzinfo=None)},
                       {"as_of_utc": NOW.replace(tzinfo=None)},
                       {"as_of_utc": datetime(2026, 11, 4, tzinfo=UTC)},
                       {"requested_meeting_end_date": "2026-09-16"}):
            with self.subTest(change=change):
                self.assertEqual(case(**change)["reason"], "XLSX_REJECTED")

    def test_non_zip_empty_oversized_and_wrong_type_rejected(self):
        for raw in (b"", b"not an xlsx", None, "fake", b"x" * (2 * 1024 * 1024 + 1)):
            with self.subTest(size=len(raw) if raw is not None else -1):
                self.assertEqual(case(raw)["reason"], "XLSX_REJECTED")

    def test_truncated_zip_rejected(self):
        x = make_xlsx()
        self.assertEqual(case(x[:-19])["reason"], "XLSX_REJECTED")

    def test_cannot_authorize_trade_under_any_valid_data(self):
        r = case()
        for key in ("trade_authorized", "can_feed_live_radar", "publishable",
                    "worker_enabled", "scheduler_enabled", "historical_point_in_time_eligible",
                    "meeting_consensus_public_before_event_verified"):
            self.assertFalse(r[key])
        self.assertIsNone(r["market_surprise_bps"])
        self.assertIsNone(r["fx_bias"])
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertEqual(r["new_cost_brl"], 0)


if __name__ == "__main__":
    unittest.main()
