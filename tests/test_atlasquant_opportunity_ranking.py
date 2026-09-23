from atlasquant_opportunity_ranking import build_rankings, quality_band, top10_is_honest

def row(pair,q,*,ready=True,trigger="CONFIRMED",risk="APPROVED",blocks=None,maturity=80,confidence=90):
    return {"pair":pair,"quality_score":q,"data_ready":ready,"trigger":trigger,"risk_gate":risk,
            "hard_blocks":blocks or [],"maturity":maturity,"confidence":confidence}

def test_88_released_ranks_above_94_blocked_in_top_agora():
    out=build_rankings([row("EUR/USD",94,blocks=["NEWS_LOCK"]),row("GBP/USD",88)])
    assert out["TOP_AGORA"][0]["pair"]=="GBP/USD"
    assert out["TOP_AGORA"][0]["executable"] is True
    assert out["TOP_GERAL"][0]["pair"]=="EUR/USD"

def test_missing_trigger_never_releases_high_score():
    out=build_rankings([row("EUR/JPY",99,trigger="WAITING")])
    assert out["TOP_AGORA"][0]["executable"] is False
    assert out["TOP_AGORA"][0]["operational_status"]=="AGUARDANDO GATILHO"

def test_stale_or_missing_data_blocks_even_100():
    out=build_rankings([row("GBP/JPY",100,ready=False)])
    assert out["TOP_AGORA"][0]["executable"] is False
    assert out["TOP_AGORA"][0]["operational_status"]=="BLOQUEADO"

def test_quality_bands_and_probability_contract():
    assert quality_band(59)=="OBSERVANDO"
    assert quality_band(60)=="PREPARANDO"
    assert quality_band(75)=="QUASE PRONTO"
    assert quality_band(85)=="ALTA QUALIDADE"
    out=build_rankings([row("AUD/NZD",85)])
    assert out["score_is_probability"] is False
    assert top10_is_honest(out)
