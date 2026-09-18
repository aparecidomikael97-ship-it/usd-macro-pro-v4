from atlasquant_macro_briefing import build_macro_briefing


def test_macro_briefing_fail_closed_without_currency_data():
    out = build_macro_briefing([], events=[{"event": "CPI", "impact": "high"}])
    assert out["state"] == "DADOS INSUFICIENTES"
    assert out["data_sufficient"] is False
    assert "não possui dados macro frescos" in out["summary"]


def test_macro_briefing_ranks_only_fresh_rows():
    rows = [
        {"currency": "USD", "score": 82, "quality": "ok"},
        {"currency": "EUR", "score": 41, "quality": "ok"},
        {"currency": "GBP", "score": 95, "stale": True},
    ]
    out = build_macro_briefing(rows)
    assert out["data_sufficient"] is True
    assert out["strongest"][0]["currency"] == "USD"
    assert all(x["currency"] != "GBP" for x in out["strongest"])


def test_macro_briefing_week_and_speech_are_presentation_only():
    out = build_macro_briefing(
        [{"currency": "USD", "score": 70}, {"currency": "EUR", "score": 30}],
        events=[{"event": "FOMC", "currency": "USD", "impact": "high", "time": "18:00"}],
        central_banks=[{"bank": "Fed", "tone": "hawkish"}],
        horizon="semana",
    )
    assert out["horizon"] == "week"
    assert out["title"] == "Briefing macro da semana"
    assert "Fed: tom hawkish" in out["speech_text"]
    assert "FOMC USD, 18:00" in out["speech_text"]
    assert "não constitui sinal" in out["disclaimer"]
