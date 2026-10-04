"""Chromium validation of the actual same-session Streamlit V2 component."""
from pathlib import Path
import socket
import subprocess
import sys
import time
import json
import os
from datetime import timedelta
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
                if route.startswith("extended:") and button.locator('xpath=ancestor::details').count():
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
            if area in ('trader','aion'):
                mobile_art=page.locator('.cq-card img' if area == 'trader' else '.final-aion-banner img').first
                expect(mobile_art).to_be_visible()
                assert mobile_art.evaluate('(e)=>e.complete && e.naturalWidth>0')
            else:
                mobile_art=page.locator(".ref-mobile-art").first
                expect(mobile_art).to_be_visible()
                assert mobile_art.evaluate("(e)=>getComputedStyle(e).backgroundImage")!="none"
            workspace=page.locator(".ref-workspace").first
            if area in ('trader','aion'):
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
            expect(page.locator('[data-workspace="central"]')).to_be_visible(timeout=20000)
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
                        if width == 1280 and mode == 'Avançado' and route in ('radar','scanner','master','macro','market_news','news','lab','paper'):
                            page.screenshot(path=str(artifacts/f'final-trader-{route}-1280.png'), full_page=True)
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


def test_login_and_existing_offline_backtest_matrix(preview_url):
    artifacts = Path('visual_review'); artifacts.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(reduced_motion='reduce')
        for review in ('login','backtest'):
            page.goto(preview_url + '?review=' + review)
            expect(page.locator('[data-testid="stForm"]' if review == 'login' else 'h3').first).to_be_visible(timeout=30000)
            expect(page.locator('[data-testid="stException"]')).to_have_count(0)
            if review == 'backtest':
                page.get_by_text('Histórico de Validação AtlasQuant · snapshots locais',exact=False).click()
                expect(page.get_by_text('Nenhum snapshot',exact=False).first).to_be_visible()
            for width,height in ((1280,720),(1024,768),(768,1024),(390,844)):
                page.set_viewport_size({'width':width,'height':height})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                if review == 'backtest':
                    page.get_by_text('Histórico de Validação AtlasQuant · snapshots locais',exact=False).scroll_into_view_if_needed()
                    page.screenshot(path=str(artifacts/f'final-backtest-history-{width}.png'),full_page=True)
                    page.locator('h3').first.scroll_into_view_if_needed()
                page.screenshot(path=str(artifacts/f'final-{review}-{width}.png'),full_page=True)
            if review == 'login':
                inputs = page.locator('[data-testid="stForm"] input')
                expect(inputs).to_have_count(2)
                inputs.nth(0).focus()
                expect(inputs.nth(0)).to_be_focused()
                inputs.nth(0).press('Tab')
                expect(inputs.nth(1)).to_be_focused()
        browser.close()


def test_validated_top_ten_fixture_layout_matrix():
    from atlasquant_reference_ui import CSS, reference_html
    from test_atlasquant_reference_population import resident_fixture
    resident,_ = resident_fixture()
    artifacts = Path('visual_review'); artifacts.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(reduced_motion='reduce')
        page.set_content('<style>'+CSS.read_text(encoding='utf-8')+'</style><p style="color:white;background:#17334a">FIXTURE DE TESTE · SEM DADOS DE MERCADO</p>'+reference_html('trader',selected='master',fx_population=resident))
        expect(page.locator('.final-featured')).to_have_count(10)
        expect(page.locator('.final-secondary')).to_have_count(18)
        for width,height in ((1280,720),(1024,768),(768,1024),(390,844)):
            page.set_viewport_size({'width':width,'height':height})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert page.locator('.final-top-grid').evaluate('(e)=>getComputedStyle(e).gridTemplateColumns.split(" ").length') == 2
            for button in page.locator('.final-featured button').all():
                button.scroll_into_view_if_needed(); before=button.bounding_box()
                button.hover();button.focus()
                assert all(abs(before[k]-button.bounding_box()[k]) < .1 for k in before)
                assert button.evaluate('(e)=>getComputedStyle(e).transform') == 'none'
            assert page.locator('.final-ring').first.evaluate('(e)=>getComputedStyle(e).animationName') == 'none'
            page.screenshot(path=str(artifacts/f'final-top10-test-fixture-{width}.png'),full_page=True)
        browser.close()


def test_resident_sidebar_and_bias_hotfix_at_requested_sizes():
    from atlasquant_reference_ui import CSS, reference_html
    from atlasquant_trader_resident import resident_trader_state
    from test_atlasquant_reference_resident import fresh_snapshot
    value, now = fresh_snapshot()
    state = resident_trader_state(value, now=now)
    artifacts = Path('visual_review'); artifacts.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(reduced_motion='reduce')
        for available in (False, True):
            html = reference_html('trader', mode='Iniciante',
                market_items=state['atlasquant_validated_market_items'] if available else None,
                fx_population=state['atlasquant_reference_fx_population'] if available else None)
            page.set_content('<style>'+CSS.read_text(encoding='utf-8')+'</style><p style="color:white;background:#17334a">QA LOCAL · FIXTURE SINTÉTICA · SEM DADOS DE MERCADO</p>'+html)
            for width,height in ((1280,720),(1440,900),(1024,768),(390,844)):
                page.set_viewport_size({'width':width,'height':height})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                if width > 700:
                    nav = page.locator('.cq-nav')
                    expect(nav.locator('.ref-nav-item')).to_have_count(24)
                    assert nav.bounding_box()['width'] >= 160
                    for button in nav.locator('.ref-nav-item').all():
                        button.scroll_into_view_if_needed()
                        assert button.evaluate('(e)=>getComputedStyle(e).overflowWrap') == 'normal'
                        assert button.evaluate('''(e)=>{
                            const icon=e.querySelector('.ref-nav-icon').getBoundingClientRect();
                            const text=Array.from(e.childNodes).find(n=>n.nodeType===3&&n.textContent.trim());
                            const range=document.createRange();range.selectNodeContents(text);
                            return Array.from(range.getClientRects()).every(r=>r.x >= icon.right-0.5 && r.right <= e.getBoundingClientRect().right+0.5);
                        }''')
                        before=button.bounding_box();button.hover();button.focus()
                        assert all(abs(before[k]-button.bounding_box()[k]) < .1 for k in before)
                    page.locator('.cq-nav .ref-nav-item').first.scroll_into_view_if_needed()
                else:
                    summary=page.locator('.cq-functions summary')
                    expect(summary).to_be_visible()
                    summary.click()
                    expect(page.locator('.cq-functions .ref-nav-item')).to_have_count(24)
                    page.screenshot(path=str(artifacts/f'hotfix-functions-{width}-{available}.png'),full_page=True)
                    summary.click()
                if available:
                    expect(page.locator('.cq-market-state')).to_contain_text('DADOS ATUAIS VALIDADOS')
                    expect(page.locator('.cq-engine-bias')).to_have_count(2)
                else:
                    expect(page.locator('.cq-market-state')).to_contain_text('SEM DADOS · SEM FONTE LIVE CONFIGURADA')
                    expect(page.locator('.cq-engine-bias')).to_have_count(0)
                page.screenshot(path=str(artifacts/f'hotfix-trader-{width}-{available}.png'),full_page=True)
        browser.close()


@pytest.fixture(scope='module')
def runtime_preview_url():
    from test_atlasquant_runtime_consistency import historical_fixture,scanner_fixture
    from atlasquant_runtime_presentation import compact_market_strip
    value,status,now=historical_fixture()
    value['market_strip']=compact_market_strip(scanner_fixture(now-timedelta(days=1)),now=now)
    contexts={pack['pair']:{'updated_at':pack['technical_timestamp'],'w1_bias':'NEUTRO','d1_bias':'NEUTRO','readiness_score':0,'readiness_grade':'WAIT'} for pack in value['packs']}
    scanner={'resultados':{pack['pair']:{'m15_fetched_at':pack['technical_timestamp'],'tecnico':{'disponivel':True,'h4':{'status':'CONFIRMA'},'h1':{'status':'PULLBACK OK'},'m15':{'status':'AGUARDAR'}}} for pack in value['packs']}}
    artifacts=Path('visual_review');artifacts.mkdir(exist_ok=True)
    path=(artifacts/'runtime-test-fixture.json').resolve()
    path.write_text(json.dumps({'snapshot':value,'status':status,'master_state':{'contexts':contexts},'scanner_state':scanner,'label':'QA LOCAL · FIXTURE SINTÉTICA · HISTÓRICO 107 MIN · SEM DADOS LIVE'},ensure_ascii=False),encoding='utf-8')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    env=dict(os.environ,ATLASQUANT_REVIEW_SNAPSHOT=str(path))
    proc=subprocess.Popen([sys.executable,'-m','streamlit','run','tools/reference_ui_preview.py','--server.address','127.0.0.1','--server.port',str(port),'--server.headless','true','--browser.gatherUsageStats','false'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    url=f'http://127.0.0.1:{port}'
    try:
        for _ in range(100):
            try: urlopen(url+'/_stcore/health',timeout=.5).read();break
            except OSError: time.sleep(.1)
        yield url
    finally:
        proc.terminate();proc.wait(timeout=10)


def test_all_24_runtime_routes_states_content_console_and_overflow(runtime_preview_url):
    from atlasquant_reference_ui import TRADER_NAV,action_labels
    from datetime import timedelta
    audit=[];artifacts=Path('visual_review')
    critical={'scanner','master','macro','fed','ict','market_map','autopilot','paper','lab','news'}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(reduced_motion='reduce',viewport={'width':1280,'height':720})
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('console',lambda message:errors.append(message.text) if message.type=='error' else None)
        page.goto(runtime_preview_url+'?review=runtime')
        expect(page.locator('.cq-workspace')).to_be_visible(timeout=30000)
        for width,height in ((1280,720),(1440,900),(1024,768),(390,844)):
            page.set_viewport_size({'width':width,'height':height})
            for route,label in TRADER_NAV:
                if width!=1280 and route not in critical|{'home'}: continue
                if route!='home':
                    if width==390:
                        page.locator('.cq-functions summary').click()
                        page.locator(f'.cq-functions [data-route="{route}"]').click()
                    else:
                        page.locator(f'.cq-nav [data-route="{route}"]').click()
                    expect(page.locator(f'.ref-detail[data-module="{route}"]')).to_be_visible(timeout=20000)
                expect(page.locator('[data-testid="stException"]')).to_have_count(0)
                state=page.locator('.cq-market-state').inner_text() if route=='home' else page.locator('.ref-detail > .ref-state').inner_text()
                text=page.locator('.cq-workspace').inner_text()
                assert 'PRÉVIA · sem execução automática' not in text
                assert 'VALIDAÇÃO PENDENTE' not in text
                overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth')
                assert not overflow
                connected=page.locator(f'.ref-primary[data-route="connected:{route}"]').count()
                assert connected<=1
                assert page.locator('[title="Fechar"],[aria-label="Fechar"]').count()==0
                if route in {'scanner','master','ict','market_map','autopilot','paper','news'}:
                    assert ('REVALIDAR' in state or 'DEPENDÊNCIA EXTERNA' in state)
                page.mouse.move(0,0)
                page.screenshot(path=str(artifacts/f'consistency-{route}-{width}.png'),full_page=True)
                title=page.locator('.cq-hero h1').inner_text() if route=='home' else page.locator('.ref-detail-head h1').inner_text()
                used=page.locator('.cq-engine-bias').count()>0 if route=='home' else page.locator('.ref-detail').get_attribute('data-resident-used')=='true'
                audit.append({'route':route,'title':title,'width':width,'connected_panel':bool(connected),'state':state,'resident_used':used,'hardcoded_preview':'PRÉVIA' in state,'console_errors':list(errors),'overflow':overflow,'duplicate_connected_button':connected>1})
                if route!='home':
                    page.locator('.ref-detail-head [data-route="home"]').click()
                    expect(page.locator('.cq-hero')).to_be_visible(timeout=20000)
            if width==390:
                page.locator('.cq-functions summary').click()
                expect(page.locator('.cq-functions .ref-nav-item')).to_have_count(24)
                page.screenshot(path=str(artifacts/'consistency-mobile-functions-open.png'),full_page=True)
                page.locator('.cq-functions summary').click()
        assert not errors
        assert len({row['route'] for row in audit if row['width']==1280})==24
        (artifacts/'trader-route-state-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
        browser.close()


def test_legacy_master_is_read_only_without_provider_buttons_at_four_sizes(runtime_preview_url):
    artifacts=Path('visual_review')
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(reduced_motion='reduce')
        page.goto(runtime_preview_url+'?review=legacy')
        expect(page.get_by_text('Painel Mestre de Oportunidades',exact=False)).to_be_visible(timeout=30000)
        expect(page.get_by_text('REVISÃO LEGADA CONCLUÍDA · ZERO CHAMADAS PROVIDER',exact=True)).to_be_visible(timeout=30000)
        expect(page.locator('[data-testid="stException"]')).to_have_count(0)
        for width,height in ((1280,720),(1440,900),(1024,768),(390,844)):
            page.set_viewport_size({'width':width,'height':height})
            expect(page.get_by_text('Atualizar próximo lote',exact=False)).to_have_count(0)
            expect(page.get_by_text('Atualizar scanner técnico',exact=False)).to_have_count(0)
            expect(page.get_by_text('TOP 10 da população de 28',exact=False)).to_have_count(0)
            expect(page.get_by_text('Universo Forex',exact=True)).to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.mouse.move(0,0)
            page.screenshot(path=str(artifacts/f'consistency-legacy-master-{width}.png'),full_page=True)
        page.get_by_role('button',name='Voltar à home Trader',exact=True).click()
        expect(page.locator('.cq-hero')).to_be_visible(timeout=20000)
        browser.close()
