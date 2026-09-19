import atlasquant_macro_briefing_panel as panel


def test_macro_briefing_panel_exposes_renderer():
    assert callable(panel.render_macro_briefing_panel)


def test_panel_source_does_not_embed_tts_network_provider():
    import inspect
    source = inspect.getsource(panel)
    forbidden = ("requests.", "httpx.", "urllib.", "openai.", "elevenlabs.")
    assert not any(token in source.lower() for token in forbidden)
    assert "VoiceRequest" in source


def test_panel_requires_explicit_generate_action_before_audio_contract():
    import inspect
    source = inspect.getsource(panel)
    assert 'st.button("🎙️ Gerar narração"' in source
    assert "aq_macro_brief_voice_generate_requested" in source
    assert "st.audio(" in source


def test_panel_labels_context_without_buy_sell_signal():
    import inspect
    source = inspect.getsource(panel)
    assert '"Divergência macro"' in source
    assert "não é sinal de compra ou venda" in source


def test_cloud_integration_does_not_fetch_calendar_for_briefing():
    source = open("usd_macro_pro_v4_cloud.py", encoding="utf-8").read()
    start = source.index("# MACRO BRIEFING")
    end = source.index("# ABA 2", start)
    block = source[start:end]
    assert "_eventos_macro_v65(" not in block
    assert 'st.session_state.get("atlasquant_macro_events")' in block
    assert "_td_series(" not in block


def test_briefing_status_is_fail_closed_and_not_a_trade_signal():
    assert panel.briefing_status({})["label"]=="DADOS INSUFICIENTES"
    out=panel.briefing_status({"data_sufficient":True,"context_bias":"divergência macro"})
    assert out["label"]=="DIVERGÊNCIA MACRO"
    assert "não é sinal de trade" in out["detail"]
