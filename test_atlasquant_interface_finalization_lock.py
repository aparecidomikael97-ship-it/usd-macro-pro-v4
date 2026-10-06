"""Regression lock for the approved AtlasQuant entry flow.

The post-login ADMIN surface must stay simple: exactly four ecosystem doors.
Desktop and mobile may render the same door more than once in responsive markup;
the product contract is four unique ecosystem routes, in canonical order.
Complexity belongs inside each workspace, never on the Central root.
"""
import re

from atlasquant_central_hub_ui import central_selector_html, central_surface_html
from atlasquant_reference_ui import NAV, reference_html

ADMIN = {"allowed": True, "role": "ADMIN", "permissions": ("app:read", "aion:admin")}
EXPECTED = ("Trader", "Negócios", "Investimentos", "AION")
ROUTES = ("area:trader", "area:negocios", "area:investimentos", "area:aion")
GLOBAL_UTILITY_ROUTES = {"home", "central", "profile", "notifications", "settings", "session"}
AREA_ROUTE_RE = re.compile(r'data-route="(area:[^"]+)"')


def _unique_area_routes(html: str) -> tuple[str, ...]:
    """Return responsive ecosystem routes once, preserving first-seen order."""
    return tuple(dict.fromkeys(AREA_ROUTE_RE.findall(html)))


def test_admin_post_login_central_has_exactly_four_primary_doors():
    html = central_selector_html(ADMIN)
    observed = _unique_area_routes(html)

    assert 'data-workspace="central"' in html
    assert observed == ROUTES
    assert set(AREA_ROUTE_RE.findall(html)) == set(ROUTES)

    for route, label in zip(ROUTES, EXPECTED):
        assert f'data-route="{route}"' in html
        assert label in html


def test_central_root_does_not_leak_inner_workspace_complexity():
    html = central_selector_html(ADMIN)

    # Trader's expanded internal capability set stays inside Trader. A route such
    # as "profile" is intentionally shared with Central as a global utility and
    # therefore is not an inner-workspace leak.
    assert len(NAV["trader"]) == 24
    for route, _ in NAV["trader"]:
        if route not in GLOBAL_UTILITY_ROUTES:
            assert f'data-route="{route}"' not in html

    # AION internal roles/modules and sector-specific actions also stay inside.
    for leaked in (
        'data-route="roles"',
        'data-route="models"',
        'data-route="companies"',
        'data-route="stocks"',
        'data-route="crypto"',
        'data-route="master"',
        'data-route="radar"',
    ):
        assert leaked not in html


def test_central_root_preserves_approved_simplicity_message():
    html = reference_html("central", name="Mikael")
    assert "Poderoso por dentro. Simples por fora." in html
    assert _unique_area_routes(html) == ROUTES
    assert set(AREA_ROUTE_RE.findall(html)) == set(ROUTES)


def test_each_private_workspace_can_return_to_central_without_cross_sector_strip():
    for area in ("negocios", "investimentos", "aion"):
        html = central_surface_html(ADMIN, area)
        assert f'data-workspace="{area}"' in html
        assert 'data-route="central"' in html
        assert not AREA_ROUTE_RE.findall(html)


def test_trader_keeps_complexity_inside_workspace_and_central_return_available():
    html = reference_html("trader", show_central=True)
    assert 'data-workspace="trader"' in html
    assert 'data-route="central"' in html
    assert not AREA_ROUTE_RE.findall(html)
