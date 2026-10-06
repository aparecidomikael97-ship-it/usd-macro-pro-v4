"""Regression lock for the approved AtlasQuant entry flow.

The post-login ADMIN surface must stay simple: exactly four ecosystem doors.
Complexity belongs inside each workspace, never on the Central root.
"""
from atlasquant_central_hub_ui import central_selector_html, central_surface_html
from atlasquant_reference_ui import NAV, reference_html

ADMIN = {"allowed": True, "role": "ADMIN", "permissions": ("app:read", "aion:admin")}
EXPECTED = ("Trader", "Negócios", "Investimentos", "AION")
ROUTES = ("area:trader", "area:negocios", "area:investimentos", "area:aion")


def test_admin_post_login_central_has_exactly_four_primary_doors():
    html = central_selector_html(ADMIN)

    assert 'data-workspace="central"' in html
    assert html.count('data-route="area:') == 4
    for route, label in zip(ROUTES, EXPECTED):
        assert f'data-route="{route}"' in html
        assert label in html

    positions = [html.index(f'data-route="{route}"') for route in ROUTES]
    assert positions == sorted(positions)


def test_central_root_does_not_leak_inner_workspace_complexity():
    html = central_selector_html(ADMIN)

    # Trader's expanded internal capability set stays inside Trader.
    assert len(NAV["trader"]) == 24
    for route, _ in NAV["trader"]:
        if route != "home":
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
    assert html.count('data-route="area:') == 4


def test_each_private_workspace_can_return_to_central_without_cross_sector_strip():
    for area in ("negocios", "investimentos", "aion"):
        html = central_surface_html(ADMIN, area)
        assert f'data-workspace="{area}"' in html
        assert 'data-route="central"' in html
        assert 'data-route="area:' not in html


def test_trader_keeps_complexity_inside_workspace_and_central_return_available():
    html = reference_html("trader", show_central=True)
    assert 'data-workspace="trader"' in html
    assert 'data-route="central"' in html
    assert html.count('data-route="area:') == 0
