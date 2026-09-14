from datetime import date
import unittest

from calendar_core import eod_row, parse_fomc, upcoming, value_text


class CalendarTests(unittest.TestCase):
    def test_fed_dates_and_year_sections(self):
        html = "<h4>2026 FOMC Meetings</h4><b>September</b><div>15-16*</div><h4>2025 FOMC Meetings</h4>September 16-17*"
        rows = parse_fomc(html)
        self.assertEqual({r["date"] for r in rows}, {"2026-09-16", "2025-09-17"})
        self.assertTrue(all("projeções" in r["details"] for r in rows))

    def test_fed_cross_month_and_scripts(self):
        rows = parse_fomc("<script>2026 FOMC Meetings December 1-2</script><h4>2026 FOMC Meetings</h4>Apr/May 30-1")
        self.assertEqual([r["date"] for r in rows], ["2026-05-01"])

    def test_alternative_cross_month_text(self):
        rows = parse_fomc("<h4>2026 FOMC Meetings</h4>April 30-May 1*")
        self.assertEqual(rows[0]["date"], "2026-05-01")
        self.assertIn("projeções", rows[0]["details"])

    def test_unknown_structure_not_invented(self):
        self.assertEqual(parse_fomc("<html>Access denied</html>"), [])
        self.assertEqual(parse_fomc(""), [])

    def test_dedup_meeting_dates(self):
        rows = parse_fomc("<h4>2026 FOMC Meetings</h4>September 15-16* September 15-16*")
        self.assertEqual(len(rows), 1)

    def test_filter_sort_dedup_and_today(self):
        def row(dt):
            return {"Data": dt, "Evento": "FOMC", "Fonte": "Fed"}
        rows = upcoming(
            [row("2026-09-16"), row("2026-09-13"), row("2026-09-12"), row("2026-10-01"), row("2026-09-16")],
            date(2026, 9, 13),
            7,
        )
        self.assertEqual([r["Em dias"] for r in rows], [0, 3])

    def test_negative_window_empty(self):
        self.assertEqual(upcoming([], date(2026, 9, 13), -1), [])

    def test_timezone_not_guessed_and_zero_preserved(self):
        row = eod_row({"date": "2026-09-16 14:00:00", "type": "GDP", "estimate": 0}, "America/Cuiaba")
        self.assertEqual(row["Consenso"], "0")
        self.assertIn("fuso não informado", row["Horário"])
        self.assertEqual(row["Realizado"], "—")

    def test_explicit_timezone_converts_day(self):
        row = eod_row({"date": "2026-09-16T02:00:00Z", "type": "Event"}, "America/Cuiaba")
        self.assertEqual(row["Data"], date(2026, 9, 15))
        self.assertEqual(row["Horário"], "22:00")

    def test_invalid_date_or_timezone_ignored(self):
        self.assertIsNone(eod_row({"date": "invalid"}, "UTC"))
        self.assertIsNone(eod_row({"date": "2026-09-16T02:00:00Z"}, "Bad/Zone"))

    def test_value_text_preserves_zero(self):
        self.assertEqual(value_text(0), "0")
        self.assertEqual(value_text("0.0"), "0.0")
        self.assertEqual(value_text(None), "—")
        self.assertEqual(value_text("nan"), "—")


if __name__ == "__main__":
    unittest.main()
