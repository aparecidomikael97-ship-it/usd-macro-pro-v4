import atlasquant_macro_briefing_panel as panel


def test_macro_briefing_panel_exposes_renderer():
    assert callable(panel.render_macro_briefing_panel)
