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
