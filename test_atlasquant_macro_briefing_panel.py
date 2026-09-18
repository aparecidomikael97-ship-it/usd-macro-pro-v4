import atlasquant_macro_briefing_panel as panel


def test_macro_briefing_panel_exposes_renderer():
    assert callable(panel.render_macro_briefing_panel)


def test_panel_source_does_not_embed_tts_network_provider():
    import inspect
    source = inspect.getsource(panel)
    forbidden = ("requests.", "httpx.", "urllib.", "openai.", "elevenlabs.")
    assert not any(token in source.lower() for token in forbidden)
    assert "VoiceRequest" in source
