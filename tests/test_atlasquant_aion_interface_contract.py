from pathlib import Path

def test_aion_admin_surface_keeps_full_runtime_status_visible():
 s=Path("atlasquant_admin_voice_panel.py").read_text(encoding="utf-8")
 assert "Núcleo geral:" in s and "Pesquisa web:" in s
 assert "YouTube:" in s and "Spotify:" in s
 assert "Pergunte qualquer coisa" in s

def test_aion_external_write_still_requires_confirmation():
 s=Path("atlasquant_admin_voice_panel.py").read_text(encoding="utf-8")
 assert "Confirmar ação externa" in s
 assert "approve_pending_action" in s
 assert "SESSION_PENDING_ACTION_KEY" in s

def test_main_theme_has_explicit_high_contrast_controls():
 s=Path("atlasquant_ui_v1.py").read_text(encoding="utf-8")
 assert "High-contrast controls" in s
 assert "color:#f8fbff !important" in s
 assert 'background:#10233a !important' in s
 assert '[role="option"]' in s

def test_compact_theme_does_not_restore_dark_text_on_dark_inputs():
 s=Path("compact_ui_v1107.py").read_text(encoding="utf-8")
 assert "color:#f8fbff!important" in s
 assert "background:#10233a!important" in s
 assert "color:var(--text-color,#111827)!important" not in s
