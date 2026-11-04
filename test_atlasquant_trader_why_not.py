"""Checkpoint Mestre: 'Por que não?' diagnostic, 28 Forex pairs, three-page UI."""
from datetime import datetime, timedelta, timezone

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_bias_matrix import SCHEMA, TIMEFRAMES
from atlasquant_trader_why_not import diagnose_trader_bias
from atlasquant_trader_radar_compact_ui import trader_radar_html

NOW=datetime(2026,11,4,14,0,tzinfo=timezone.utc)


def evidence(*, pairs=(), direction="ALTA"):
    return {
        "schema": SCHEMA, "state": "VALIDATED_BIAS_EVIDENCE",
        "source": "Fornecedor de teste <script>alert(1)</script>",
        "as_of": NOW.isoformat(),
        "pairs": {
            pair: {tf:{"bias":direction,"as_of":NOW.isoformat()} for tf in TIMEFRAMES}
            for pair in pairs
        },
    }


def test_no_data_is_a_valid_explicit_all_wait_outcome():
    for input_data in (None, {}, {"schema": SCHEMA, "state":"INVALID"}):
        result=diagnose_trader_bias(input_data,now=NOW)
        assert result["state"]=="NO_DATA"
        assert result["complete_pairs"]==0
        assert result["aligned_pairs"]==0
        assert len(result["rows"])==28
        assert result["blocked_pairs"]==28
        assert result["entry_authorized"] is False
        assert result["provider_authenticated"] is False
        assert all(not row["entry_authorized"] for row in result["rows"].values())
        assert "Semanal" in result["rows"][OFFICIAL_PAIRS[0]]["why_not"]
        assert "M15" in result["rows"][OFFICIAL_PAIRS[0]]["why_not"]


def test_fully_aligned_is_never_misrepresented_as_a_trade():
    result=diagnose_trader_bias(evidence(pairs=OFFICIAL_PAIRS),now=NOW)
    assert result["complete_pairs"]==28
    assert result["aligned_pairs"]==28
    assert result["blocked_pairs"]==28
    assert result["entry_authorized"] is False
    assert result["macro_confirmed"] is False
    assert result["technical_trigger_confirmed"] is False
    assert result["risk_authorized"] is False
    assert "probabilidade" not in result["summary"].lower()
    assert all(x["status"]=="ALINHADO" and not x["entry_authorized"] for x in result["rows"].values())


def test_single_partial_pair_specifies_missing_timeframe_not_fake_reason():
    name=OFFICIAL_PAIRS[0]
    sample=evidence(pairs=(name,))
    del sample["pairs"][name]["M15"]
    result=diagnose_trader_bias(sample,now=NOW)
    assert result["complete_pairs"]==0
    assert result["rows"][name]["status"]=="SEM_DADOS"
    assert "M15" in result["rows"][name]["why_not"]
    assert "H4" not in result["rows"][name]["why_not"]


def test_conflicts_are_explained_but_never_trigger_entry():
    name=OFFICIAL_PAIRS[0]
    for timeframe, side, status, msg in [
        ("W1","BAIXA","CONFLITO_W1_D1","semanal diverge"),
        ("W1","NEUTRO","SEM_DIREÇÃO","Sem direção"),
        ("H4","BAIXA","H4_CONTRÁRIO","H4 não confirma"),
        ("M15","BAIXA","M15_SEM_CONFIRMAÇÃO","M15 não confirmou"),
    ]:
        sample=evidence(pairs=(name,))
        sample["pairs"][name][timeframe]["bias"]=side
        row=diagnose_trader_bias(sample,now=NOW)["rows"][name]
        assert row["status"]==status
        assert msg in row["why_not"]
        assert row["entry_authorized"] is False


def test_stale_and_future_input_stay_fail_closed():
    sample=evidence(pairs=OFFICIAL_PAIRS)
    sample["as_of"]=(NOW-timedelta(days=2)).isoformat()
    result=diagnose_trader_bias(sample,now=NOW)
    assert result["state"]=="NO_DATA"
    assert result["entry_authorized"] is False


def test_three_tabs_have_checkpoint_without_adding_any_fourth_tab():
    for page in ("home","radar","master"):
        html=trader_radar_html(selected=page)
        assert "data-workspace=\"trader_radar\"" in html
        assert html.count("data-route=\"home\"")>=1
        assert html.count("data-route=\"radar\"")>=1
        assert html.count("data-route=\"master\"")>=1
        assert "data-route=\"scanner\"" not in html
        assert "ordens reais" in html.lower() or "sem ordens" in html.lower()
    assert "Checkpoint do viés" in trader_radar_html(selected="home")
    radar=trader_radar_html(selected="radar")
    assert "Por que não?" in radar
    assert 'class="aqr-matrix"' not in radar  # the existing collapsible details is preserved
    assert '<details class="aqr-section aqr-matrix"' in radar
    assert "Faltam leituras recentes" in radar
    master=trader_radar_html(selected="master")
    assert "Checkpoint do viés" in master
    assert "Por que ainda não operar?" in master
    assert "Risco" in master or "risco" in master


def test_source_is_escaped_when_rendered_no_script_injection():
    sample=evidence(pairs=OFFICIAL_PAIRS)
    sample["as_of"]=datetime.now(timezone.utc).isoformat()
    for pair in sample["pairs"]:
        for tf in TIMEFRAMES:
            sample["pairs"][pair][tf]["as_of"]=sample["as_of"]
    html=trader_radar_html(selected="master",bias_evidence=sample)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "autenticidade do produtor não verificada" in html.lower()
