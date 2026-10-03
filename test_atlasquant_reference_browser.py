"""Chromium validation of the actual same-session Streamlit V2 component."""
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
import pytest
pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright, expect
from atlasquant_reference_ui import NAV, REGIONS


@pytest.fixture(scope="module")
def preview_url():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        port=sock.getsockname()[1]
    proc=subprocess.Popen([sys.executable,"-m","streamlit","run","tools/reference_ui_preview.py",
        "--server.address","127.0.0.1","--server.port",str(port),"--server.headless","true",
        "--browser.gatherUsageStats","false"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    url=f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                urlopen(url+"/_stcore/health",timeout=.5).read()
                break
            except OSError:
                time.sleep(.1)
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_all_screens_real_clicks_desktop_mobile(preview_url):
    artifacts=Path("visual_review")
    artifacts.mkdir(exist_ok=True)
    timings={}
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True)
        page=b.new_page(viewport={"width":1440,"height":1000})
        errors=[]
        page.on("pageerror",lambda e:errors.append(str(e)))
        start=time.perf_counter()
        page.goto(preview_url)
        expect(page.locator(".ref-canvas")).to_be_visible(timeout=30000)
        expect(page.locator('.ref-component-root[data-art-ready="true"]')).to_be_visible(timeout=30000)
        timings["central_cold_ms"]=round((time.perf_counter()-start)*1000)
        page.mouse.move(0,0)
        page.screenshot(path=str(artifacts/"central-desktop.png"),full_page=True)
        for area in ("trader","negocios","investimentos","aion"):
            start=time.perf_counter()
            page.locator(f'.ref-canvas [data-route="area:{area}"]').click()
            expect(page.locator(f'.ref-workspace[data-workspace="{area}"]')).to_be_visible(timeout=20000)
            expect(page.locator('.ref-component-root[data-art-ready="true"]')).to_be_visible(timeout=30000)
            timings[area+"_open_ms"]=round((time.perf_counter()-start)*1000)
            expect(page.locator('[data-testid="stException"]')).to_have_count(0)
            page.mouse.move(0,0)
            page.screenshot(path=str(artifacts/(area+"-desktop.png")),full_page=True)
            # Hover/focus cannot change the physical rectangle of any card.
            for button in page.locator('.ref-hit,.cq-card,.cq-panel,.cq-globe').all():
                if not button.is_visible(): continue
                button.scroll_into_view_if_needed()
                before=button.bounding_box()
                button.hover()
                after=button.bounding_box()
                assert all(abs(before[k]-after[k]) < .1 for k in ('x','y','width','height'))
                assert button.evaluate('(e)=>getComputedStyle(e).transform') == 'none'
                if area == 'investimentos' and button.get_attribute('data-route') == 'crypto':
                    page.screenshot(path=str(artifacts/'investimentos-crypto-hover.png'),full_page=True)
                button.focus()
                if area == 'investimentos' and button.get_attribute('data-route') == 'crypto':
                    page.screenshot(path=str(artifacts/'investimentos-crypto-focus.png'),full_page=True)
                focused=button.bounding_box()
                assert all(abs(before[k]-focused[k]) < .1 for k in ('x','y','width','height'))
            if area in ('trader','investimentos'):
                ticker=page.locator('.cq-ticker')
                assert ticker.evaluate('(e)=>e.scrollWidth > e.clientWidth')
                page.locator('[data-ticker-step="1"]').click()
                page.wait_for_function('el=>el.scrollLeft > 20',arg=ticker.element_handle())
                page.locator('[data-ticker-step="-1"]').click()
            if area=='negocios':
                expect(page.locator('.cq-market,.cq-tick')).to_have_count(0)
            for width,height in ((1280,720),(1024,768),(768,1024)):
                page.set_viewport_size({'width':width,'height':height})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.screenshot(path=str(artifacts/(area+f'-{width}.png')),full_page=True)
            page.set_viewport_size({'width':1440,'height':1000})
            # Every visual card/tab/panel region opens a detail at the first fold.
            routes=list(dict.fromkeys(page.locator(".ref-canvas [data-route]").evaluate_all("els=>els.map(e=>e.dataset.route)")))
            routes=[route for route in routes if route != "home"]
            for route in routes:
                button=page.locator(f'.ref-canvas [data-route="{route}"]').first
                if route.startswith("extended:"):
                    page.locator(".ref-sidebar details summary").click()
                button.click()
                expect(page.locator(".ref-detail")).to_be_visible(timeout=10000)
                assert page.locator(".ref-detail h1").bounding_box()["y"] < 300
                page.locator('.ref-detail [data-route="home"]').click()
                expect(page.locator(".ref-detail")).to_have_count(0,timeout=10000)
                expect(page.locator(".ref-canvas")).to_be_visible(timeout=10000)
            # Every side-menu entry has a functioning handler, not a decorative span.
            for route,_ in NAV[area]:
                if route=="home":
                    continue
                page.locator(f'.ref-sidebar [data-route="{route}"]').click()
                expect(page.locator(".ref-detail")).to_be_visible(timeout=10000)
                page.locator('.ref-detail [data-route="home"]').click()
                expect(page.locator(".ref-detail")).to_have_count(0,timeout=10000)
                expect(page.locator(".ref-canvas")).to_be_visible(timeout=10000)
            if area=="trader":
                page.locator('.ref-sidebar [data-route="master"]').click()
                expect(page.locator(".ref-detail h1")).to_have_text("Painel Mestre")
                expect(page.locator(".ref-pair")).to_have_count(28)
                assert page.locator(".ref-detail h1").bounding_box()["y"] < 300
                page.screenshot(path=str(artifacts/"master-desktop.png"),full_page=True)
                page.locator('.ref-detail [data-route="home"]').click()
                expect(page.locator(".ref-detail")).to_have_count(0)
            elif area=="investimentos":
                page.locator('.ref-sidebar [data-route="stocks"]').click()
                expect(page.locator(".ref-detail h1")).to_have_text("Ações Globais")
                expect(page.locator(".ref-preview-grid")).to_be_visible()
                page.screenshot(path=str(artifacts/"investimentos-preview-desktop.png"),full_page=True)
                page.locator('.ref-detail [data-route="home"]').click()
                expect(page.locator(".ref-detail")).to_have_count(0)
            elif area=="aion":
                page.locator('.ref-sidebar [data-route="models"]').click()
                expect(page.locator(".ref-detail h1")).to_have_text("Modelos de IA")
                expect(page.locator(".ref-preview-grid")).to_be_visible()
                page.screenshot(path=str(artifacts/"aion-preview-desktop.png"),full_page=True)
                page.locator('.ref-detail [data-route="home"]').click()
                expect(page.locator(".ref-detail")).to_have_count(0)
            page.set_viewport_size({"width":390,"height":844})
            page.emulate_media(reduced_motion="reduce")
            expect(page.locator(".ref-drawer")).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            expect(page.locator('.ref-component-root[data-art-ready="true"]')).to_be_visible()
            if area == 'trader':
                mobile_art=page.locator('.cq-card img').first
                expect(mobile_art).to_be_visible()
                assert mobile_art.evaluate('(e)=>e.complete && e.naturalWidth>0')
            else:
                mobile_art=page.locator(".ref-mobile-art").first
                expect(mobile_art).to_be_visible()
                assert mobile_art.evaluate("(e)=>getComputedStyle(e).backgroundImage")!="none"
            workspace=page.locator(".ref-workspace").first
            if area == 'trader':
                assert workspace.evaluate('(e)=>getComputedStyle(e).backgroundImage') == 'none'
            else:
                assert workspace.evaluate("(e)=>getComputedStyle(e).backgroundSize")=="0px 0px"
            page.mouse.move(0,0)
            page.screenshot(path=str(artifacts/(area+"-mobile.png")),full_page=True)
            expect(page.locator(".ref-detail")).to_have_count(0)
            if area in ('trader','investimentos'):
                ticker=page.locator('.cq-ticker')
                ticker.focus();ticker.press('ArrowRight')
                page.wait_for_function('el=>el.scrollLeft > 20',arg=ticker.element_handle())
            page.locator(".ref-drawer summary").first.click()
            expect(page.locator(".ref-drawer")).to_have_attribute("open", "")
            page.locator('.ref-drawer [data-route="profile"]').click()
            expect(page.locator(".ref-detail")).to_be_visible()
            assert page.locator(".ref-detail h1").bounding_box()["y"] < 300
            page.locator('.ref-detail [data-route="home"]').click()
            assert page.locator(".ref-mobile-card").first.evaluate("(e)=>getComputedStyle(e).transitionDuration")=="0s"
            page.locator('.ref-toolbar [data-route="central"]').click()
            expect(page.locator('[data-workspace="central"]')).to_be_visible()
            page.screenshot(path=str(artifacts/"central-mobile.png"),full_page=True)
            page.set_viewport_size({"width":1440,"height":1000})
            page.emulate_media(reduced_motion="no-preference")
        assert not errors
        import json
        (artifacts/"timings.json").write_text(json.dumps(timings,indent=2),encoding="utf-8")
        print(timings)
        b.close()


def test_central_and_legacy_cards_keep_exact_hover_and_keyboard_geometry(preview_url):
    from atlasquant_ecosystem_workspace_ui import WORKSPACE_CSS
    from atlasquant_premium_shell import PREMIUM_CSS
    artifacts=Path('visual_review');artifacts.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1280,'height':720})
        page.goto(preview_url)
        expect(page.locator('.ref-component-root[data-art-ready="true"]')).to_be_visible(timeout=30000)
        for button in page.locator('.ref-hit[data-route^="area:"]').all():
            button.scroll_into_view_if_needed()
            before=button.bounding_box();button.hover()
            after=button.bounding_box()
            assert all(abs(before[k]-after[k]) < .1 for k in ('x','y','width','height'))
            page.keyboard.press('Tab');button.focus()
            assert button.evaluate('(e)=>getComputedStyle(e).outlineStyle')=='none'
            focused=button.bounding_box()
            assert all(abs(before[k]-focused[k]) < .1 for k in ('x','y','width','height'))
        page.screenshot(path=str(artifacts/'central-focus.png'),full_page=True)
        page.set_content(WORKSPACE_CSS+PREMIUM_CSS+'<main class="stApp" style="display:grid;grid-template-columns:repeat(3,280px);gap:20px;padding:20px"><a href="#" class="aq-ws-card">Módulo</a><a href="#" class="aq-central-reference-card">Ambiente</a><a href="#" class="aq-premium-card">Cartão</a></main>')
        for button in page.locator('.aq-ws-card,.aq-central-reference-card,.aq-premium-card').all():
            button.scroll_into_view_if_needed();button.hover()
            before=button.bounding_box()
            assert button.evaluate('(e)=>getComputedStyle(e).transform')=='none'
            page.keyboard.press('Tab');button.focus()
            focused=button.bounding_box()
            assert all(abs(before[k]-focused[k]) < .1 for k in ('x','y','width','height'))
            assert button.evaluate('(e)=>getComputedStyle(e).outlineStyle')=='none'
            assert button.evaluate('(e)=>getComputedStyle(e).boxShadow')!='none'
        page.screenshot(path=str(artifacts/'legacy-cards-focus.png'),full_page=True)
        browser.close()


def test_trader_24_functions_discoverable_and_clickable_in_both_modes(preview_url):
    artifacts = Path('visual_review'); artifacts.mkdir(exist_ok=True)
    expected_routes = [route for route, _ in NAV['trader']]
    assert len(expected_routes) == len(set(expected_routes)) == 24
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width':1280, 'height':720}, reduced_motion='reduce')
        errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(preview_url)
        page.locator('.ref-canvas [data-route="area:trader"]').click(timeout=30000)
        expect(page.locator('.cq-main')).to_be_visible(timeout=30000)
        for width, height in ((1280,720), (1024,768), (768,1024), (390,844)):
            page.set_viewport_size({'width':width, 'height':height})
            for mode in ('Avançado', 'Iniciante'):
                mode_button = page.locator('.ref-mode')
                for _ in range(2):
                    if mode_button.inner_text() == 'Modo ' + mode: break
                    mode_button.click()
                    expect(mode_button).not_to_have_attribute('aria-busy', 'true')
                    expect(page.locator('.cq-main')).to_be_visible()
                expect(mode_button).to_have_text('Modo ' + mode)
                expect(page.locator('.ref-detail')).to_have_count(0)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                # Existing home shortcuts remain present in both experience modes.
                for route in ('indexes','commodities','stocks','week','day','close_day',
                        'close_week','radar','master','news','calendar','geo','guardian','aion_specialist'):
                    expect(page.locator(f'.cq-main [data-route="{route}"]').first).to_be_visible()
                if width == 390:
                    summary = page.locator('.cq-functions summary')
                    expect(summary).to_be_visible()
                    expect(summary).to_contain_text('Funções do Trader · 24')
                    expect(summary).to_contain_text('inclui avançadas')
                    summary.scroll_into_view_if_needed()
                    assert summary.bounding_box()['y'] < height
                    before = summary.bounding_box(); summary.hover(); summary.focus()
                    assert all(abs(before[k]-summary.bounding_box()[k]) < .1 for k in before)
                    assert summary.evaluate('(e)=>getComputedStyle(e).transform') == 'none'
                    assert summary.evaluate('(e)=>getComputedStyle(e).animationName') == 'none'
                    assert summary.evaluate('(e)=>getComputedStyle(e).transitionDuration') == '0s'
                    page.screenshot(path=str(artifacts/f'trader-functions-mobile-{mode}.png'), full_page=True)
                    summary.click()
                    expect(page.locator('.cq-functions')).to_have_attribute('open', '')
                    if mode == 'Iniciante':
                        expect(page.locator('.cq-functions-note')).to_contain_text('inclusive avançadas')
                    page.screenshot(path=str(artifacts/f'trader-functions-mobile-open-{mode}.png'), full_page=True)
                    nav_selector = '.cq-functions nav'
                else:
                    expect(page.locator('.cq-nav-title').first).to_have_text('Funções · 24')
                    nav_selector = '.cq-nav'
                    page.screenshot(path=str(artifacts/f'trader-functions-{width}-{mode}.png'), full_page=True)
                # Exact route set, direct buttons; no nested disclosure or CSS hiding.
                buttons = page.locator(nav_selector + ' [data-route]')
                assert buttons.evaluate_all('(els)=>els.map(e=>e.dataset.route)') == expected_routes
                expect(buttons).to_have_count(24)
                expect(page.locator(nav_selector + ' details')).to_have_count(0)
                for route in expected_routes:
                    if width == 390 and page.locator('.cq-functions').get_attribute('open') is None:
                        page.locator('.cq-functions summary').click()
                    button = page.locator(nav_selector + f' [data-route="{route}"]')
                    expect(button).to_be_visible()
                    button.scroll_into_view_if_needed()
                    before = button.bounding_box(); button.hover(); button.focus()
                    assert all(abs(before[k]-button.bounding_box()[k]) < .1 for k in before)
                    assert button.evaluate('(e)=>getComputedStyle(e).transform') == 'none'
                    button.click()
                    if route != 'home':
                        expect(page.locator('.ref-detail')).to_be_visible()
                        if width == 390 and mode == 'Iniciante' and route in ('master','ict'):
                            page.screenshot(path=str(artifacts/f'trader-functions-mobile-{route}.png'), full_page=True)
                        page.locator('.ref-detail [data-route="home"]').click()
                    expect(page.locator('.cq-main')).to_be_visible()
                    expect(page.locator('.ref-detail')).to_have_count(0)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    expect(page.locator('.ref-mode')).to_have_text('Modo ' + mode)
                if width == 390:
                    page.locator('.cq-functions summary').scroll_into_view_if_needed()
                    page.screenshot(path=str(artifacts/f'trader-functions-mobile-return-{mode}.png'), full_page=True)
        assert not errors
        browser.close()
