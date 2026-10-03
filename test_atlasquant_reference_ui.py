"""Reference fidelity, scoped navigation and lazy-entry contracts."""
from pathlib import Path
from unittest.mock import patch
import hashlib
import json
import re
import pytest
from PIL import Image, ImageChops
from atlasquant_reference_ui import (TRADER_MOBILE_CARDS, NAV, REGIONS, SURFACES, ASSET_ROOT, CSS, action_labels,
    apply_event, asset_uri, reference_html, render_trader_entry)


ADMIN = {"allowed":True,"role":"ADMIN","session":{"username":"review"}}
USER = {"allowed":True,"role":"USER","session":{"username":"client"}}


def test_asset_manifest_hashes_and_dimensions():
    manifest=json.loads((ASSET_ROOT/"manifest.json").read_text(encoding="utf-8"))
    for filename,item in manifest.items():
        data=(ASSET_ROOT/filename).read_bytes()
        assert hashlib.sha256(data).hexdigest()==item["asset_sha256"]
        assert len(data)==item["size_bytes"]
        assert list(Image.open(ASSET_ROOT/filename).size)==item["dimensions"]
        if item.get("unchanged_original"):
            assert item["source_sha256"]==item["asset_sha256"]


def test_reference_pixels_are_preserved_losslessly():
    source_root = Path("C:/Users/apare/Downloads")
    files = {"central.webp":"atlasquant_central.png","negocios.webp":"atlasquant_negocios.png",
             "investimentos.webp":"AtlasQuant_ Investimentos e AION.png", "aion.webp":"AtlasQuant_ Investimentos e AION.png"}
    for encoded, source in files.items():
        # Repo stores approved hashes. Pixel equality can also be reviewed locally
        # when the original user attachments are available.
        manifest=json.loads((ASSET_ROOT/"manifest.json").read_text(encoding="utf-8"))[encoded]
        assert manifest["lossless"]
        original=source_root/source
        if original.exists():
            assert hashlib.sha256(original.read_bytes()).hexdigest()==manifest["source_sha256"]
            approved=Image.open(original).convert("RGB")
            if "crop" in manifest:
                approved=approved.crop(manifest["crop"])
            assert ImageChops.difference(approved,
                Image.open(ASSET_ROOT/encoded).convert("RGB")).getbbox() is None
    assert (ASSET_ROOT/"trader.jpg").stat().st_size < 300000


@pytest.mark.parametrize("area",SURFACES)
def test_reference_has_accessible_routes_and_no_duplicate_strip(area):
    html=reference_html(area,mode="Avançado",name="<script>steal()</script>")
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "Acessar ambiente" not in html
    assert "data-route=" in html and "aria-label=" in html
    if area != "central":
        assert "dados da imagem ilustrativos" in html
    for route, label, _ in REGIONS[area]:
        assert f'data-route="{route}"' in html


def test_separation_and_complete_trader_menu():
    nav=dict(NAV["trader"])
    assert len(nav)==19
    assert {"radar_master","master","radar","ict","academy","journal","video","profile"}<=nav.keys()
    assert "Negócios" not in nav.values() and "Investimentos" not in nav.values()
    for area in ("negocios","investimentos"):
        assert not any(v in {"Trader","Negócios","Investimentos"} for v in dict(NAV[area]).values())


@pytest.mark.parametrize("area",SURFACES)
def test_every_rendered_route_opens_only_its_workspace(area):
    html=reference_html(area)
    routes=set(re.findall(r'data-route="([^"]+)"',html))
    for route in routes:
        session={}
        apply_event(session,ADMIN,area,route)
        if route.startswith("area:"):
            assert session["atlasquant_central_choice"]==route[5:]
        elif route=="central":
            assert session["atlasquant_central_choice"]=="central_root"
        elif route in {"mode","home"}:
            pass
        else:
            assert session["aq_reference_module"]==(area,route)


def test_user_cannot_expand_authority_or_switch_private_sectors():
    for area in ("central","negocios","investimentos","aion"):
        with pytest.raises(ValueError):
            apply_event({},USER,area,"home")
    for event in ("area:aion","area:negocios","area:investimentos","central","connected:business","connected:invest","exec:trade"):
        with pytest.raises(ValueError):
            apply_event({},USER,"trader",event)
    state={}
    apply_event(state,USER,"trader","aion_specialist")
    assert state["aq_reference_module"]==("trader","aion_specialist")
    assert "atlasquant_access_session" not in state


def test_connected_master_uses_existing_navigation_and_no_auth_mutation():
    state={"atlasquant_access_session":{"username":"same","authenticated_at":123}}
    before=dict(state["atlasquant_access_session"])
    apply_event(state,ADMIN,"trader","connected:master")
    assert state["atlasquant_advanced_area"]=="🧭 Painel mestre"
    assert state["atlasquant_experience_mode"]=="Avançado"
    assert state["aq_reference_connected"]
    assert state["atlasquant_access_session"]==before


def test_return_home_resets_legacy_selection_without_changing_auth():
    state={"aq_reference_connected":True,"atlasquant_advanced_area":"master", "atlasquant_access_session":{"username":"same"}}
    apply_event(state,USER,"trader","home")
    assert not state["aq_reference_connected"]
    assert state["atlasquant_advanced_area"]=="🎯 Radar"
    assert state["atlasquant_access_session"]=={"username":"same"}


def test_mode_preserves_all_functions_and_changes_only_visible_depth():
    advanced=reference_html("trader",mode="Avançado")
    beginner=reference_html("trader",mode="Iniciante")
    assert "Todas as funções · Avançado" in beginner
    for route,_ in NAV["trader"]:
        assert f'data-route="{route}"' in advanced and f'data-route="{route}"' in beginner


def test_master_first_fold_and_radar_truth():
    html=reference_html("trader",selected="master")
    assert "ref-detail-layout" in html
    assert "ref-canvas" not in html
    assert html.count('class="ref-pair"')==28
    assert html.count("TOP 10")==10
    assert "Direção: aguardando dados" in html
    assert "Compra" not in html and "Venda" not in html
    assert "connected:master" in html
    assert html.index("<h1>") < html.index('class="ref-radar-grid"')
    state={}
    apply_event(state,USER,"trader","why:EUR/USD")
    assert state["aq_reference_module"][1]=="why:EUR/USD"
    with pytest.raises(ValueError):
        apply_event(state,USER,"trader","why:fake")




@pytest.mark.parametrize(
    ("area","selected","expected"),
    [
        ("negocios","opportunities",("ESCOPO B2B","Workspace isolado por empresa","AÇÃO EXTERNA")),
        ("investimentos","stocks",("ESCOPO","Leitura e comparação de investimentos","EXECUÇÃO")),
        ("aion","models",("NÚCLEO","Um único AION Core compartilhado","AUTORIDADE")),
    ],
)
def test_private_preview_panels_have_workspace_specific_identity(area, selected, expected):
    html=reference_html(area,selected=selected)
    assert 'class="ref-preview-grid"' in html
    for text in expected:
        assert text in html
    assert "Nenhum dado validado disponível para exibir." not in html


@pytest.mark.parametrize("area",("negocios","investimentos","aion"))
def test_mobile_hero_has_environment_identity(area):
    html=reference_html(area)
    assert f"ref-mobile-header-{area}" in html
    assert "ECOSSISTEMA ATLASQUANT" in html

def test_trader_mobile_v6_has_explicit_card_identity_without_route_collisions():
    html=reference_html("trader")
    cards={(route,label):(box,kind) for route,label,box,kind in TRADER_MOBILE_CARDS}
    assert cards[("news","Pré-Notícia")] == ((915,332,111,65),"icon")
    assert cards[("news","Notícias em Tempo Real")] == ((163,604,276,111),"panel")
    assert cards[("calendar","Calendário Econômico")] in {
        ((798,332,112,65),"icon"),
        ((1006,464,257,134),"panel"),
    }
    assert cards[("master","Painel Mestre")] == ((1031,332,162,65),"icon")
    assert cards[("journal","Diário")] == ((908,639,96,38),"icon")
    assert 'data-mobile-kind="icon" data-mobile-crop="915,332,111,65"' in html
    assert 'data-mobile-kind="panel" data-mobile-crop="163,604,276,111"' in html
    assert 'data-mobile-kind="icon" data-mobile-crop="1031,332,162,65"' in html
    assert 'data-mobile-kind="icon" data-mobile-crop="908,639,96,38"' in html


def test_reference_mobile_chrome_is_hidden_only_when_reference_cockpit_is_active():
    src=Path("atlasquant_reference_ui.py").read_text(encoding="utf-8")
    assert 'id="aq-reference-active"' in src
    assert '.stApp:has(#aq-reference-active) [data-testid="stHeader"]{display:none!important' in src
    assert '.stApp:has(#aq-reference-active) [data-testid="stSidebarCollapsedControl"]{display:none!important}' in src
    assert '.stApp:has(#aq-reference-active) [data-testid="stElementContainer"]:has([data-testid="stRadio"]){display:none!important}' in src
    assert '.stApp:has(#aq-reference-active) .block-container{padding-top:0!important' in src


def test_mobile_v5_v6_css_compacts_and_stops_card_stretching():
    css=CSS.read_text(encoding="utf-8")
    assert "Fidelity polish v5" in css
    assert "Fidelity polish v6" in css
    assert ".ref-central .ref-mobile-grid{grid-template-columns:repeat(2,minmax(0,1fr))" in css
    assert ".ref-central .ref-mobile-art{aspect-ratio:4/3!important}" in css
    assert ".ref-toolbar{width:calc(100% - 16px);min-width:0;overflow:hidden}" in css
    assert ".ref-mobile-grid{align-items:start}" in css
    assert ".ref-mobile-card{align-self:start;height:auto}" in css
    assert ".ref-trader .ref-mobile-card-icon .ref-mobile-art{" in css


def test_eight_roles_one_shared_aion():
    html=reference_html("aion",selected="roles")
    assert "Não são oito IAs independentes" in html
    assert html.count('class="ref-pair"')==8


def test_no_remote_io_or_heavy_home_load():
    source=Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
    block=source[source.index("_hold_admin_before_trader_shell()\n"):source.index('st.session_state["_aq_experience_switch_mounted"] = False')]
    assert "render_trader_entry" in block and "st.stop()" in block
    assert source.index("if render_trader_entry") < source.index("_fast_snapshot = load_home_snapshot(")
    assert source.index("if render_trader_entry") < source.index("# EXECUÇÃO PRINCIPAL")
    with patch("atlasquant_reference_ui.render_reference_workspace",return_value=True) as renderer:
        fake=type("Fake",(),{"session_state":{}})()
        assert render_trader_entry(fake,USER)
        renderer.assert_called_once()
        fake.session_state["aq_reference_connected"]=True
        with patch("atlasquant_reference_ui._component") as mount:
            mount.return_value.return_value.navigate = None
            assert not render_trader_entry(fake,USER)
            markup = mount.return_value.call_args.kwargs["data"]
            assert 'data-route="home"' in markup
            assert 'data-route="central"' not in markup


def test_reduced_motion_and_drawer_css():
    css=CSS.read_text(encoding="utf-8")
    assert "prefers-reduced-motion:reduce" in css
    assert "@media(max-width:700px)" in css
    assert ".ref-drawer{display:block" in css
    assert "minmax(0,1fr)" in css
