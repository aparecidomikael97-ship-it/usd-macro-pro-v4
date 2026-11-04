"""LAB: contrato de viés W1/D1/H4/M15, sem cotação ou ordem real."""
from datetime import datetime, timedelta, timezone
from html import escape

import pytest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_bias_matrix import SCHEMA, TIMEFRAMES, read_bias_matrix
from atlasquant_trader_radar_compact_ui import trader_radar_html

NOW = datetime(2026, 11, 3, 16, 0, tzinfo=timezone.utc)
SIDES = ("ALTA", "BAIXA", "NEUTRO")


def sample(*, side="ALTA", pairs=None):
    names = OFFICIAL_PAIRS if pairs is None else pairs
    return {
        "schema": SCHEMA,
        "state": "VALIDATED_BIAS_EVIDENCE",
        "source": "Fixture LAB",
        "as_of": NOW.isoformat(),
        "pairs": {
            pair: {
                tf: {"bias": side, "as_of": (NOW - timedelta(minutes=10)).isoformat()}
                for tf in TIMEFRAMES
            } for pair in names
        },
    }


def test_empty_returns_28_explicit_waits_without_inventing_direction():
    for value in (None, {}, {"state": "VALIDATED_BIAS_EVIDENCE"}):
        model = read_bias_matrix(value, now=NOW)
        assert model["state"] == "NO_DATA"
        assert model["validated_pairs"] == 0
        assert len(model["rows"]) == 28
        assert all(r["bias"] == "AGUARDAR" for r in model["rows"].values())
    html = trader_radar_html(selected="radar")
    assert "MATRIZ DE VIÉS · Semanal / Diário / H4 / M15" in html
    assert "Clique aqui para abrir as 28 linhas" in html
    assert html.index("MATRIZ DE VIÉS") < html.index("Força relativa das 8 moedas")
    assert html.index("MATRIZ DE VIÉS") < html.index("Os 28 pares Forex")
    assert "Ainda não recebemos leituras válidas" in html
    assert "0 de 28" in html
    assert "Scanner Técnico" not in html


def test_all_28_valid_readings_align_only_as_a_filter_not_probability():
    data = sample()
    model = read_bias_matrix(data, now=NOW)
    assert model["state"] == "READY"
    assert (model["validated_pairs"], model["aligned_pairs"]) == (28, 28)
    assert len(model["rows"]) == len(OFFICIAL_PAIRS)
    assert set(r["bias"] for r in model["rows"].values()) == {"ALTA"}
    html = trader_radar_html(selected="radar", bias_evidence=data)
    # The UI uses real-world current time: a frozen fixture is not current.
    assert "Ainda não recebemos leituras válidas" in html
    assert "28 de 28" not in html


def test_conflicts_do_not_claim_market_direction():
    pair = OFFICIAL_PAIRS[0]
    data = sample(pairs=(pair,))
    data["pairs"][pair]["W1"]["bias"] = "BAIXA"
    model = read_bias_matrix(data, now=NOW)
    assert model["state"] == "PARTIAL"
    assert model["rows"][pair]["status"] == "CONFLITO_W1_D1"
    assert model["rows"][pair]["bias"] == "AGUARDAR"
    for tf, expected in (("W1", "SEM_DIREÇÃO"), ("H4", "H4_CONTRÁRIO"),
                         ("M15", "M15_SEM_CONFIRMAÇÃO")):
        d = sample(pairs=(pair,))
        d["pairs"][pair][tf]["bias"] = "NEUTRO" if tf == "W1" else "BAIXA"
        item = read_bias_matrix(d, now=NOW)["rows"][pair]
        assert item["status"] == expected
        assert item["bias"] == "AGUARDAR"


def test_missing_stale_and_future_horizon_never_carries_old_signal():
    pair = OFFICIAL_PAIRS[0]
    for bad in (None, "not-a-date", NOW - timedelta(hours=11),
                NOW + timedelta(seconds=2)):
        d = sample(pairs=(pair,))
        d["pairs"][pair]["H4"]["as_of"] = bad.isoformat() if isinstance(bad, datetime) else bad
        row = read_bias_matrix(d, now=NOW)["rows"][pair]
        assert row["timeframes"]["H4"] is None
        assert row["status"] == "SEM_DADOS"
        assert row["bias"] == "AGUARDAR"
    d = sample(pairs=(pair,))
    d["pairs"][pair].pop("M15")
    assert read_bias_matrix(d, now=NOW)["validated_pairs"] == 0


def test_payload_source_and_timestamps_must_be_credible():
    for edit in (
        {"schema": "other"},
        {"state": "UNVERIFIED"},
        {"source": ""},
        {"as_of": NOW.isoformat().replace("+00:00", "")},
        {"as_of": (NOW - timedelta(hours=2)).isoformat()},
        {"as_of": (NOW + timedelta(seconds=1)).isoformat()},
    ):
        data = sample()
        data.update(edit)
        assert read_bias_matrix(data, now=NOW)["state"] == "NO_DATA"


def test_extra_pairs_invalid_sides_and_naive_time_are_not_accepted():
    data = sample(pairs=(OFFICIAL_PAIRS[0], "FAKE/USD"))
    data["pairs"][OFFICIAL_PAIRS[0]]["D1"]["bias"] = "COMPRAR AGORA"
    model = read_bias_matrix(data, now=NOW)
    assert "FAKE/USD" not in model["rows"]
    assert model["rows"][OFFICIAL_PAIRS[0]]["bias"] == "AGUARDAR"
    with pytest.raises(ValueError):
        read_bias_matrix(data, now=NOW.replace(tzinfo=None))


def test_source_cannot_inject_markup_or_present_percentage_of_success():
    data = sample(pairs=(OFFICIAL_PAIRS[0],))
    data["source"] = "<script>alert(1)</script>"
    model = read_bias_matrix(data, now=NOW)
    assert model["source"] == data["source"]
    assert "probability" not in model and "win_rate" not in model
    # No quoted source can appear from a stale fixture in the production view.
    html = trader_radar_html(selected="radar", bias_evidence=data)
    assert "<script>" not in html


def test_timeframe_window_is_independent_and_weekly_not_monthly():
    assert TIMEFRAMES == ("W1", "D1", "H4", "M15")
    pair = OFFICIAL_PAIRS[0]
    d = sample(pairs=(pair,))
    d["pairs"][pair]["W1"]["as_of"] = (NOW - timedelta(days=10)).isoformat()
    assert read_bias_matrix(d, now=NOW)["rows"][pair]["bias"] == "AGUARDAR"


def test_current_upstream_reading_is_visible_without_claiming_probability():
    current = datetime.now(timezone.utc)
    pair = OFFICIAL_PAIRS[0]
    data = sample(pairs=(pair,))
    data["as_of"] = current.isoformat()
    for tf in TIMEFRAMES:
        data["pairs"][pair][tf]["as_of"] = current.isoformat()
    data["source"] = "<script>alert(1)</script>"
    html = trader_radar_html(selected="radar", bias_evidence=data)
    assert "1 de 28 pares com quatro leituras válidas" in html
    assert "Horizontes alinhados" in html
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert '<details class="aqr-section aqr-matrix"' in html
    assert "probabilidade de acerto" in html


def test_stale_daily_changes_are_hidden_even_when_claimed_validated():
    from atlasquant_trader_radar_compact_ui import _daily
    current = datetime.now(timezone.utc)
    data = {
        "state": "VALIDATED_DAILY", "source": "Local LAB",
        "as_of": (current - timedelta(days=4)).isoformat(),
        "pairs": {OFFICIAL_PAIRS[0]: {"change_pct": 3.2, "bias": "ALTA"}},
    }
    assert _daily(data)["pairs"] == {}
    data["as_of"] = (current + timedelta(minutes=2)).isoformat()
    assert _daily(data)["pairs"] == {}
    data["as_of"] = current.astimezone(timezone(timedelta(hours=-3))).isoformat()
    assert _daily(data)["stamp"].endswith("UTC")
    assert _daily(data)["pairs"][OFFICIAL_PAIRS[0]]["change_pct"] == 3.2
