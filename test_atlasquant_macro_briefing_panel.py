import atlasquant_macro_briefing_panel as panel


def test_macro_briefing_panel_exposes_renderer():
    assert callable(panel.render_macro_briefing_panel)


def test_panel_source_does_not_embed_tts_network_provider():
    import inspect
    source=inspect.getsource(panel)
    forbidden=("requests.","httpx.","urllib.","openai.","elevenlabs.")
    assert not any(token in source.lower() for token in forbidden)
    assert "render_neural_voice_player" in source


def test_panel_uses_explicit_neural_generate_action_via_shared_player():
    import inspect
    source=inspect.getsource(panel)
    assert "render_neural_voice_player" in source
    assert "Ouvir briefing com a voz AtlasQuant" in source
    assert "delivery_mode" in source
    assert "server_neural_tts" in source


def test_panel_labels_context_without_buy_sell_signal():
    import inspect
    source=inspect.getsource(panel)
    assert '"Divergência macro"' in source
    assert "não é sinal de compra ou venda" in source


def test_cloud_integration_does_not_fetch_calendar_for_briefing():
    source=open("usd_macro_pro_v4_cloud.py",encoding="utf-8").read()
    start=source.index("# MACRO BRIEFING")
    end=source.index("# ABA 2",start)
    block=source[start:end]
    assert "_eventos_macro_v65(" not in block
    assert 'st.session_state.get("atlasquant_macro_events")' in block
    assert "_td_series(" not in block


def test_briefing_status_is_fail_closed_and_not_a_trade_signal():
    assert panel.briefing_status({})["label"]=="DADOS INSUFICIENTES"
    out=panel.briefing_status({"data_sufficient":True,"context_bias":"divergência macro"})
    assert out["label"]=="DIVERGÊNCIA MACRO"
    assert "não é sinal de trade" in out["detail"]


def test_macro_briefing_has_no_device_voice_fallback():
    import inspect
    source=inspect.getsource(panel)
    assert "browser_speech_html" not in source
    assert "speechSynthesis" not in source
    assert "voz do Google/aparelho não é usada como fallback" in source


def test_macro_briefing_locks_official_voice_profile_without_style_picker():
    import inspect
    source=inspect.getsource(panel)
    assert "VOICE_PROFILE_ID" in source
    assert "server_neural_tts" in source
    assert 'st.selectbox(\n        "Estilo da voz"' not in source
