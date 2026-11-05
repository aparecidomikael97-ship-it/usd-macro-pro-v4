"""Tiny in-memory XML ZIP fixtures; no licensed research data in the repo."""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import unittest
from zipfile import ZipFile, ZIP_DEFLATED

from atlasquant_trader_us_mpt_history_lab import inspect_atlantafed_mpt_history_lab as inspect

UTC = timezone.utc
NOW = datetime(2026, 11, 5, 1, 30, tzinfo=UTC)
NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
STRINGS = ['date', 'reference_start', 'target_range', 'field', 'value',
           '2026-10-27', '2026-10-28', '375bps - 400bps',
           'Rate: mean', 'Rate: mode', 'Rate: 25th percentile',
           'Rate: 75th percentile', 'Prob: cut', 'Prob: hike',
           '385.12', '384.25', '378.00', '390.00', '28.4', '30.1', '3000.01']


def sheet_row(number: int, indexes: tuple[int, int, int, int, int],
              *, serial: int = 46386) -> str:
    cells = []
    for col, index in zip('ABCDE', indexes):
        kind = 'n' if col == 'B' and number > 1 else 's'
        value = str(serial) if col == 'B' and number > 1 else str(index)
        cells.append(f'<c r="{col}{number}" t="{kind}"><v>{value}</v></c>')
    return f'<row r="{number}">{"".join(cells)}</row>'


def fixture(*, license_present=True, malformed=False, dup=False,
            outlier=False, future=False, missing_mean=False,
            mixed_target=False) -> bytes:
    rows = [sheet_row(1, (0, 1, 2, 3, 4))]
    # 46386 = 2026-12-30 in Excel; it is a *future contract window*, not
    # a future observation. The exact reference date is verified below.
    date_id = 6 if future else 5
    fields = [(8, 14), (9, 15), (10, 16), (11, 17), (12, 18), (13, 19)]
    if missing_mean:
        fields = fields[1:]
    for field, value in fields:
        rows.append(sheet_row(len(rows) + 1, (date_id, 0, 7, field, 20 if outlier and field == 8 else value)))
    if dup:
        rows.append(sheet_row(len(rows) + 1, (date_id, 0, 7, 8, 14)))
    if mixed_target:
        rows.append(sheet_row(len(rows) + 1, (date_id, 0, 21, 8, 14)))
    if malformed:
        rows.append('<row r="99"><c r="A99" t="s"><v>999999</v></c></row>')
    strings = STRINGS + (['400bps - 425bps'] if mixed_target else [])
    shared = (f'<sst xmlns="{NS}">' + ''.join(f'<si><t>{s}</t></si>' for s in strings) + '</sst>')
    wb = (f'<workbook xmlns="{NS}"><sheets>'
          '<sheet name="LICENSE"/><sheet name="DICTIONARY"/>'
          '<sheet name="DATA"/></sheets></workbook>')
    data = f'<worksheet xmlns="{NS}"><sheetData>{"".join(rows)}</sheetData></worksheet>'
    license_text = ('Use of this data is permitted for personal and educational purposes only.'
                    if license_present else 'unrestricted mock document')
    drawing = ('<drawing xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
               f'<a:t>{license_text}</a:t></drawing>')
    mem = BytesIO()
    with ZipFile(mem, 'w', compression=ZIP_DEFLATED) as z:
        z.writestr('xl/workbook.xml', wb)
        z.writestr('xl/sharedStrings.xml', shared)
        z.writestr('xl/worksheets/sheet3.xml', data)
        z.writestr('xl/drawings/drawing1.xml', drawing)
    return mem.getvalue()


def run(raw: bytes, **extra):
    kwargs = dict(observed_at_utc=NOW,
                  requested_observation_date='2026-10-27',
                  requested_reference_start='2026-12-30')
    kwargs.update(extra)
    return inspect(raw, **kwargs)


class AtlantaFedMptLabTests(unittest.TestCase):
    def test_valid_research_never_becomes_fomc_surprise_or_commercial_data(self):
        r = run(fixture())
        self.assertEqual(r['state'], 'LAB_MPT_QUARTERLY_SOFR_RESEARCH_ONLY')
        self.assertEqual(r['quarterly_sofr_implied_statistics']['Rate: mean'], '385.12')
        self.assertEqual(r['quarterly_sofr_implied_statistics']['Prob: cut'], '28.4')
        self.assertEqual(len(r['source_raw_sha256']), 64)
        for key in ('trade_authorized', 'pre_event_consensus_verified',
                    'historical_public_availability_witnessed',
                    'metric_is_fomc_target_consensus',
                    'commercial_reuse_authorized', 'can_feed_live_radar'):
            self.assertFalse(r[key])
        self.assertIsNone(r['fx_bias'])
        self.assertIsNone(r['market_surprise_bps'])

    def test_denies_missing_license(self):
        r = run(fixture(license_present=False))
        self.assertEqual(r['reason'], 'LICENSE_RESTRICTION_NOT_READABLE')

    def test_denies_malformed_row(self):
        self.assertEqual(run(fixture(malformed=True))['state'], 'LAB_BLOCKED')

    def test_denies_duplicate_selected_field(self):
        self.assertEqual(run(fixture(dup=True))['state'], 'LAB_BLOCKED')

    def test_denies_out_of_unit_rate_and_mixed_contract_range(self):
        for payload in (fixture(outlier=True), fixture(mixed_target=True)):
            with self.subTest(size=len(payload)):
                self.assertEqual(run(payload)['state'], 'LAB_BLOCKED')

    def test_denies_missing_mean(self):
        self.assertEqual(run(fixture(missing_mean=True))['reason'],
                         'REQUESTED_SOFR_RESEARCH_WINDOW_UNAVAILABLE')

    def test_denies_wrong_contract_window_without_backfilling(self):
        r = run(fixture(), requested_reference_start='2027-03-30')
        self.assertEqual(r['reason'], 'REQUESTED_SOFR_RESEARCH_WINDOW_UNAVAILABLE')

    def test_denies_bad_zip_bytes(self):
        for raw in (None, b'', b'not a zip', b'PK' + b'0' * 1000):
            with self.subTest(raw=raw):
                self.assertEqual(run(raw)['state'], 'LAB_BLOCKED')

    def test_denies_observation_in_future_of_capture(self):
        r = run(fixture(), requested_observation_date='2026-11-06')
        self.assertEqual(r['state'], 'LAB_BLOCKED')

    def test_denies_naive_local_clock(self):
        r = run(fixture(), observed_at_utc=NOW.replace(tzinfo=None))
        self.assertEqual(r['state'], 'LAB_BLOCKED')

    def test_does_not_mislabel_selected_other_date_as_current(self):
        r = run(fixture(future=True))
        self.assertEqual(r['reason'], 'REQUESTED_SOFR_RESEARCH_WINDOW_UNAVAILABLE')


if __name__ == '__main__':
    unittest.main()
