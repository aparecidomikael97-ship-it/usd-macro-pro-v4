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
    assert len(nav)==24
    assert {"scanner","master","radar","fed","market_news","market_map","autopilot","performance","ict","academy","journal","video","profile"}<=nav.keys()
    assert "radar_master" not in nav
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



@pytest.mark.parametrize(("route","target"), [
    ("scanner","🧭 Painel mestre"),
    ("fed","🏦 Fed"),
    ("market_news","📰 Notícias"),
    ("market_map","🗺️ Market Map"),
    ("autopilot","🤖 Autopilot"),
    ("performance","🛠️ Melhorias"),
    ("calendar","🇺🇸 EUA"),
    ("paper","🧪 Backtest"),
])
def test_restored_legacy_trader_routes_open_existing_functional_pages(route, target):
    state={}
    apply_event(state,ADMIN,"trader",f"connected:{route}")
    assert state["aq_reference_connected"]
    assert state["aq_beginner_page"]==target
    assert state["atlasquant_advanced_area"]==target


def test_return_home_resets_legacy_selection_without_changing_auth():
    state={"aq_reference_connected":True,"atlasquant_advanced_area":"master", "atlasquant_access_session":{"username":"same"}}
    apply_event(state,USER,"trader","home")
    assert not state["aq_reference_connected"]
    assert state["atlasquant_advanced_area"]=="🎯 Radar"
    assert state["atlasquant_access_session"]=={"username":"same"}


def test_mode_preserves_all_functions_and_changes_only_visible_depth():
    advanced=reference_html("trader",mode="Avançado")
    beginner=reference_html("trader",mode="Iniciante")
    assert "Funções do Trader · 24" in beginner
    assert "inclusive avançadas, continuam disponíveis" in beginner
    for route,_ in NAV["trader"]:
        assert f'data-route="{route}"' in advanced and f'data-route="{route}"' in beginner


@pytest.mark.parametrize("mode", ["Iniciante", "Avançado"])
def test_exact_trader_navigation_contract_without_nested_hidden_modules(mode):
    from html.parser import HTMLParser
    from atlasquant_reference_ui import nav_html
    expected = ('home', 'radar', 'scanner', 'master', 'macro', 'fed', 'micro',
        'geo', 'market_news', 'fundamental', 'ict', 'calendar', 'news', 'market_map',
        'lab', 'paper', 'guardian', 'autopilot', 'performance', 'academy', 'journal', 'video',
        'aion_specialist', 'profile')
    class Routes(HTMLParser):
        def __init__(self):
            super().__init__(); self.routes = []; self.details = 0
        def handle_starttag(self, tag, attrs):
            if tag == 'details': self.details += 1
            if tag == 'button': self.routes.append(dict(attrs).get('data-route'))
    parser = Routes(); parser.feed(nav_html('trader', mode))
    assert tuple(route for route, _ in NAV['trader']) == expected
    assert tuple(parser.routes) == expected
    assert len(set(parser.routes)) == 24
    assert parser.details == 0


def test_master_first_fold_and_radar_truth():
    html=reference_html("trader",selected="master")
    assert "ref-detail-layout" in html
    assert "ref-canvas" not in html
    assert html.count('class="ref-pair final-fx-card')==28
    assert html.count('data-ranked="false"')==28
    assert "TOP 10" not in html
    assert "Ranking aguardando dados validados" in html
    assert "Sem leitura elegível para ranking" in html
    assert "Compra" not in html and "Venda" not in html
    assert "connected:master" in html
    assert html.index("<h1>") < html.index('class="final-fx-board')
    state={}
    apply_event(state,USER,"trader","why:EUR/USD")
    assert state["aq_reference_module"][1]=="why:EUR/USD"
    with pytest.raises(ValueError):
        apply_event(state,USER,"trader","why:fake")




@pytest.mark.parametrize(
    ("area","selected","expected"),
    [
        ("negocios","companies",("ESCOPO B2B","Workspace isolado por empresa","AÇÃO EXTERNA")),
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
    if area == "aion":
        assert "final-aion-banner" in html and "Um único AION Core" in html
        assert html.count("data-internal-role=") == 8
    elif area == "negocios":
        assert 'class="aq-ws-shell"' in html
        assert 'data-business-contract="managed-operations-v1"' in html
        assert "ATLASQUANT · NEGÓCIOS" in html
        assert "Poderoso por dentro. Simples por fora." in html
    else:
        assert f"ref-mobile-header-{area}" in html
        assert "ECOSSISTEMA ATLASQUANT" in html

def test_business_reference_home_uses_current_b2b_contract_and_no_legacy_market_scope():
    html=reference_html("negocios",mode="Avançado",name="Admin")
    expected=(
        "Empresas / Clientes","Automação B2B","Leads","Revenue Ops","CRM","Propostas","Follow-up",
        "Micro-SaaS","Serviços Internacionais","Produtos Digitais","Integrações",
        "Financeiro / FinOps","ROI","Saúde do Cliente","SLA / Suporte","Auditoria / LGPD",
        "Equipe &amp; Acessos","Demo / Sandbox","AION Negócios",
    )
    for label in expected:
        assert label in html
    for legacy in (
        "Oportunidades","Setores","M&amp;A","Mercado Global","Notícias Corporativas",
        "Fluxo Institucional","Calendário de Resultados",
    ):
        assert legacy not in html
    routes=dict(NAV["negocios"])
    assert "b2b" in routes and "finops" in routes and "success" in routes and "sla" in routes
    assert "ma" not in routes and "sectors" not in routes and "global" not in routes
    assert 'data-route="b2b"' in html
    assert 'data-route="finops"' in html
    assert 'data-route="success"' in html
    assert 'data-route="sla"' in html


def test_compact_trader_preserves_routes_and_uses_readable_native_labels():
    html=reference_html("trader")
    for route,label in NAV["trader"]:
        assert f'data-route="{route}"' in html
    assert 'cq-cards' in html and 'cq-tools' in html
    assert 'Fechamento do Dia' in html and 'Fechamento da Semana' in html
    assert 'Notícias em Tempo Real' in html and 'Calendário Econômico' in html
    assert 'Eventos Geopolíticos' in html and 'Mapa de Risco Global' in html
    assert 'data-mobile-crop=' not in html


def test_reference_mobile_chrome_is_hidden_only_when_reference_cockpit_is_active():
    src=Path("atlasquant_reference_ui.py").read_text(encoding="utf-8")
    assert 'id="aq-reference-active"' in src
    assert '.stApp:has(#aq-reference-active) [data-testid="stHeader"]{display:none!important' in src
    assert '.stApp:has(#aq-reference-active) [data-testid="stSidebarCollapsedControl"]{display:none!important}' in src
    assert '.stApp:has(#aq-reference-active) [data-testid="stElementContainer"]:has([data-testid="stRadio"]){display:none!important}' in src
    assert '.stApp:has(#aq-reference-active) .block-container{padding-top:0!important' in src


def test_mobile_v7_collapses_duplicate_production_chrome_before_reference_cockpit():
    src=Path("atlasquant_reference_ui.py").read_text(encoding="utf-8")
    assert '[data-testid="stElementContainer"]:has(.aq-hero)' in src
    assert '[data-testid="stElementContainer"]:has(#aq-account-identity)' in src
    assert '[data-testid="stElementContainer"]:has(.aq-boot-banner)' in src
    assert '[data-testid="stElementContainer"]:has(.aq-voice-dock)' in src
    assert ':has(.aq-voice-dock) + [data-testid="stHorizontalBlock"]{display:none!important}' in src
    assert 'html:has(#aq-reference-active) [data-testid="stAppViewContainer"]' in src
    assert 'html:has(#aq-reference-active) [data-testid="stMain"]' in src
    assert 'html:has(#aq-reference-active) [data-testid="stMainBlockContainer"]' in src
    assert 'margin-top:0!important;top:0!important;padding-top:0!important' in src
    assert '[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"]{gap:0!important}' in src


def test_mobile_v7_equalizes_video_art_and_centers_journal():
    css=CSS.read_text(encoding="utf-8")
    assert "Fidelity polish v7" in css
    assert ".ref-trader .ref-mobile-card-video .ref-mobile-art{" in css
    assert "height:clamp(112px,31vw,132px)" in css
    assert ".ref-trader .ref-mobile-card-journal{" in css
    assert "grid-column:1/-1" in css
    assert "justify-self:center" in css


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
    assert html.count('data-internal-role=')==8


def test_validated_resident_snapshot_precedes_cockpit_without_heavy_loaders():
    source=Path("usd_macro_pro_v4_cloud.py").read_text(encoding="utf-8")
    block=source[source.index("_hold_admin_before_trader_shell()\n"):source.index('st.session_state["_aq_experience_switch_mounted"] = False')]
    assert "render_trader_entry" in block and "st.stop()" in block
    assert source.index("_fast_snapshot = load_home_snapshot(") < source.index("hydrate_trader_resident_state(st.session_state") < source.index("if render_trader_entry")
    for heavy in ("carregar_macro_eua()", "carregar_narrativa_fed()", "carregar_dados_moedas()"):
        assert heavy not in block
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


def test_compact_ticker_data_is_verified_before_any_price_or_order_is_used():
    from atlasquant_compact_cockpit import ticker_html,asset_symbol,normalized_market_items
    from datetime import datetime,timezone
    assert ticker_html('negocios') == ''
    assert 'cq-market' not in reference_html('negocios')
    empty=ticker_html('trader')
    assert 'Preço: —' in empty and 'Variação: —' in empty and 'SEM DADOS' in empty and 'PRÉVIA' not in empty
    assert 'polyline' not in empty and '%' not in empty
    assert 'data-country="US"' in asset_symbol('DXY')
    for pair,country in [('EUR/USD','EU'),('GBP/USD','GB'),('USD/JPY','JP'),('AUD/USD','AU')]:
        assert f'data-country="{country}"' in asset_symbol(pair) and 'data-country="US"' in asset_symbol(pair)
    for asset in ('PETR4','VALE3'):
        assert 'data-country="BR"' in asset_symbol(asset)
    for asset in ('NASDAQ','BTC','OURO'):
        assert 'cq-class-icon' in asset_symbol(asset) and 'cq-flag' not in asset_symbol(asset)
    assert normalized_market_items([{'asset':'DXY','price':123,'validated':False}]) == []
    stamp=datetime.now(timezone.utc).isoformat()
    rows=[{'asset':'USD/JPY','source':'test-fixture','validated':True,'as_of':stamp,'price':150.5,'change_pct':-.3,'score':70,'series':[2,3,2.5]},
          {'asset':'DXY','source':'test-fixture','validated':True,'as_of':stamp,'price':float('nan'),'change_pct':float('inf')}]
    html=ticker_html('trader',rows)
    assert html.index('data-asset="USD/JPY"') < html.index('data-asset="DXY"')
    assert '150,5000' in html and '-0,30%' in html and 'polyline' in html
    assert 'nan' not in html and 'inf' not in html
    assert 'USD/JPY' not in ticker_html('investimentos',rows)


def test_crypto_hit_region_is_aligned_to_source_border():
    assert next(box for route,_,box in REGIONS['investimentos'] if route=='crypto') == (687,317,165,113)
    assert 'translateY(-2px)' not in CSS.read_text(encoding='utf-8')


def test_refined_graphic_crops_are_lossless_from_new_user_reference():
    manifest=json.loads((ASSET_ROOT/'manifest.json').read_text(encoding='utf-8'))
    for filename,entry in manifest.items():
        if not (filename.endswith('-body.webp') or filename.startswith('trader-')):
            continue
        source=Path('C:/Users/apare/Downloads')/entry['source_name']
        if source.exists():
            expected=Image.open(source).convert('RGB').crop(entry['crop'])
            assert ImageChops.difference(expected,Image.open(ASSET_ROOT/filename).convert('RGB')).getbbox() is None
