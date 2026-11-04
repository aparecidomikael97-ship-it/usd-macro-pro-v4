"""Two actual official daily reference anchors, 32 days apart. Ex-post LAB only.

The anchor on 2026-10-01 is transcribed from EU Official Journal (published
2026-10-02); 2026-11-02 is from Banque de France, with a separately archived
ECB SDMX CSV available in the repository. This is NOT a 32-day price series,
a forecast, tradable spot, historical capture proof or an OOS test.
"""
from __future__ import annotations

from datetime import datetime, date, timezone
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
from typing import Any, Mapping
import re

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair

SCHEMA = 'ATLASQUANT_TRADER_ECB_MN1_TWO_OFFICIAL_ANCHORS_LAB_V1'
STATE = 'LAB_OFFICIAL_DAILY_REFERENCE_MN1_EXPOST_ONLY'
DENIED = 'LAB_OFFICIAL_DAILY_REFERENCE_MN1_REFUSED'
SOURCE_UNIT = 'CURRENCY_UNITS_PER_EUR'
RESEARCH_DATE = date(2026, 11, 3)
ANCHOR = '2026-10-01'
SETTLEMENT = '2026-11-02'
EXPECTED = (
    {
        'reference_date': ANCHOR,
        'publication_date': '2026-10-02',
        'source_kind': 'EU_OFFICIAL_JOURNAL_REPUBLISHING_ECB_REFERENCES',
        'source_url': 'https://eur-lex.europa.eu/eli/C/2026/5148/oj',
        'eur_quotes': {
            'USD': '1.1298', 'JPY': '178.49', 'GBP': '0.85373',
            'CHF': '0.9437', 'AUD': '1.6255', 'CAD': '1.6095',
            'NZD': '2.0121',
        },
    },
    {
        'reference_date': SETTLEMENT,
        'publication_date': '2026-11-02',
        'source_kind': 'BANQUE_DE_FRANCE_DAILY_ECB_REFERENCES',
        'source_url': ('https://www.banque-france.fr/en/statistics/rates-and-prices/'
                       'exchange-rates-daily-parities-2026-11-02'),
        'eur_quotes': {
            'USD': '1.1216', 'JPY': '177.1000', 'GBP': '0.8358',
            'CHF': '0.9193', 'AUD': '1.6004', 'CAD': '1.5673',
            'NZD': '1.9934',
        },
    },
)

DEADBAND_BP = Decimal('5')
EXTREME_BP = Decimal('2500')
ROUND_BP = Decimal('0.01')


def _refuse(reason: str) -> dict[str, Any]:
    return {
        'schema': SCHEMA, 'state': DENIED, 'reason': reason,
        'rows': [], 'observed_pairs': 0,
        'reference_original_eur_legs_per_date': 0,
        'derived_crosses_not_independent': 21,
        'independent_broker_spot_quotes_verified': 0,
        'original_october_source_bytes_archived': False,
        'historical_data_known_before_anchor_proven': False,
        'forecast_issued_before_move': False,
        'real_predictive_accuracy_proven': False,
        'probability_calibrated': None,
        'can_feed_live_radar': False, 'can_feed_real_oos': False,
        'trade_authorized': False, 'worker_enabled': False,
        'scheduler_enabled': False,
    }


def _decimal(value: Any) -> Decimal | None:
    if (not isinstance(value, str) or
            re.fullmatch(r'[0-9]{1,6}(?:\.[0-9]{1,10})?', value) is None):
        return None
    number = Decimal(value)
    return number if Decimal('0.0001') <= number <= Decimal('100000') else None


def build_ecb_mn1_two_official_anchors_lab(
    record: Any, *, evaluated_at: datetime,
) -> dict[str, Any]:
    """Compute 28 *retrospective* observed reference changes, no forecasts.

    Pinned source transcription prevents accidental replacement with different
    dates/rates that look more favorable in hindsight. It does NOT certify
    original source bytes or future pricing availability.
    """
    if (not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None
            or evaluated_at.utcoffset() is None):
        raise ValueError('Evaluation instant must have timezone')
    if evaluated_at.astimezone(timezone.utc).date() < RESEARCH_DATE:
        return _refuse('Cannot backdate document comparison before research day')
    if not isinstance(record, Mapping) or set(record) != {
        'schema', 'state', 'research_date_utc', 'source_unit', 'documents',
    }:
        return _refuse('Missing or unexpected documentary fields')
    if (record['schema'] != SCHEMA or record['state'] != STATE
            or record['research_date_utc'] != RESEARCH_DATE.isoformat()
            or record['source_unit'] != SOURCE_UNIT):
        return _refuse('Wrong documentary contract identity or units')
    docs = record['documents']
    if not isinstance(docs, list) or len(docs) != 2:
        return _refuse('Exactly two fixed documentary snapshots required')
    for actual, expected in zip(docs, EXPECTED):
        if not isinstance(actual, Mapping) or set(actual) != set(expected):
            return _refuse('Snapshot structure changed')
        for field in ('reference_date', 'publication_date', 'source_kind', 'source_url'):
            if actual[field] != expected[field]:
                return _refuse(f'Pinned source metadata changed: {field}')
        quotes = actual['eur_quotes']
        if (not isinstance(quotes, Mapping)
                or set(quotes) != set(CURRENCIES) - {'EUR'}):
            return _refuse('Incomplete or unexpected G8 EUR quotations')
        for currency, expected_text in expected['eur_quotes'].items():
            number = _decimal(quotes.get(currency))
            if number is None or number != Decimal(expected_text):
                return _refuse(f'Official documentary quotation unverified: {currency}')
    first, last = docs[0]['eur_quotes'], docs[1]['eur_quotes']
    elapsed = (date.fromisoformat(SETTLEMENT) - date.fromisoformat(ANCHOR)).days
    if not 30 <= elapsed <= 42:
        return _refuse('MN1 fixed ex-post window was not respected')
    rows: list[dict[str, Any]] = []
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        def rate(snap: Mapping[str, str], currency: str) -> Decimal:
            return Decimal('1') if currency == 'EUR' else Decimal(snap[currency])
        with localcontext() as ctx:
            ctx.prec = 40
            initial = rate(first, quote) / rate(first, base)
            final = rate(last, quote) / rate(last, base)
            movement_bp = (final / initial - 1) * Decimal('10000')
            label = ('REVIEW_EXTREME' if abs(movement_bp) > EXTREME_BP
                     else ('ALTA' if movement_bp > DEADBAND_BP
                           else ('BAIXA' if movement_bp < -DEADBAND_BP else 'NEUTRO')))
            rows.append({
                'pair': pair, 'horizon': 'MN1',
                'reference_date': ANCHOR, 'settlement_date': SETTLEMENT,
                'target_calendar_days': 30, 'elapsed_calendar_days': elapsed,
                'reference_return_bp': str(movement_bp.quantize(
                    ROUND_BP, rounding=ROUND_HALF_EVEN)),
                'realized_reference_side': None if label == 'REVIEW_EXTREME' else label,
                'state': 'EXPOST_EXTREME_MOVE_REVIEW_REQUIRED' if label == 'REVIEW_EXTREME'
                         else 'EXPOST_REFERENCE_ONLY',
                'direction_is_forecast': False,
                'source_type': 'ECB_REFERENCES_REPRINTED_BY_OFFICIAL_INSTITUTIONS',
                'spot_price_independently_verified': False,
            })
    return {
        **_refuse(''), 'state': STATE, 'reason': None,
        'source_unit': SOURCE_UNIT, 'research_date_utc': RESEARCH_DATE.isoformat(),
        'reference_date': ANCHOR, 'settlement_date': SETTLEMENT,
        'elapsed_calendar_days': elapsed,
        'rows': rows, 'observed_pairs': len(rows),
        'reference_original_eur_legs_per_date': 7,
        'research_note': ('Retrospective daily reference endpoints only; October anchor '
                          'was transcribed from EU Official Journal, November endpoint '
                          'from Banque de France, matching prior archived ECB CSV. '
                          'No complete historical time series was downloaded; no '
                          'prospective forecast was made for 2026-10-01.'),
    }


__all__ = ['SCHEMA', 'STATE', 'DENIED', 'SOURCE_UNIT', 'EXPECTED',
           'build_ecb_mn1_two_official_anchors_lab']
