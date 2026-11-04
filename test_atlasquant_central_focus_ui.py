"""Focused central landing, secure navigation and client-only profile avatar."""
import re
import sys
from types import ModuleType
from unittest.mock import patch

import pytest

from atlasquant_central_focus_ui import focused_central_html
from atlasquant_reference_ui import JS, apply_event, reference_html


ADMIN = {"allowed": True, "role": "ADMIN"}
USER = {"allowed": True, "role": "USER"}


def test_priority_and_secondary_workspace_cards():
    html = reference_html("central", name="M")
    assert 'class="aqc-hero"' in html
    assert "ATLASQUANT TRADER" in html and "Forex &amp; Índices" in html
    assert 'data-route="area:trader_radar"' in html
    for route in ("trader", "negocios", "investimentos", "aion"):
        assert f'data-route="area:{route}"' in html
    assert html.count('class="aqc-other"') == 1
    assert html.count("data-route=\"open:") == 3


def test_direct_navigation_and_no_scanner():
    html = reference_html("central")
    for key in ("home", "radar", "master"):
        assert f'data-route="open:{key}"' in html
    assert "Scanner Técnico" not in html
    assert 'data-route="open:scanner"' not in html


def test_avatar_edit_is_private_browser_only():
    html = reference_html("central", name='</section><script>alert(1)</script>')
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert 'data-avatar-input' in html
    assert 'data-avatar-editor' in html
    assert 'data-avatar-clear' in html
    assert 'data-profile-avatar' in html
    assert "localStorage.setItem" in JS
    assert "canvas.toDataURL('image/jpeg'" in JS
    assert "file.size>8*1024*1024" in JS
    assert "URL.createObjectURL" in JS


def test_trader_subpages_still_exist_and_share_avatar():
    for key in ("home", "radar", "master"):
        html = reference_html("trader_radar", selected=key, name="M")
        assert "data-avatar-key=" in html
        assert "data-profile-avatar" in html
        assert "Scanner Técnico" not in html


def test_direct_routes_are_access_controlled_and_scoped():
    fake = ModuleType("atlasquant_central_hub_ui")
    def assert_area_access(access, area):
        if access.get("allowed") is not True:
            raise ValueError("unauthorized")
    def request_central_destination(session, access, area):
        if access.get("role") != "ADMIN":
            raise ValueError("unauthorized")
        session["atlasquant_central_choice"] = area
    fake.assert_area_access = assert_area_access
    fake.request_central_destination = request_central_destination
    with patch.dict(sys.modules, {"atlasquant_central_hub_ui": fake}):
        for key in ("home", "radar", "master"):
            session = {"atlasquant_access_session": "unchanged"}
            apply_event(session, ADMIN, "central", f"open:{key}")
            assert session["atlasquant_central_choice"] == "trader_radar"
            assert session["aq_reference_module"] == ("trader_radar", key)
            assert session["atlasquant_access_session"] == "unchanged"
        for role in (USER, {"allowed": False, "role": "ADMIN"}):
            with pytest.raises(ValueError):
                apply_event({}, role, "central", "open:radar")
        with pytest.raises(ValueError):
            apply_event({}, ADMIN, "central", "open:scanner")
