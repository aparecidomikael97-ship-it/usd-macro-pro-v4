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
            page.set_viewport_size({"width":390,"height":844})
            page.emulate_media(reduced_motion="reduce")
            expect(page.locator(".ref-drawer")).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            expect(page.locator('.ref-component-root[data-art-ready="true"]')).to_be_visible()
            page.mouse.move(0,0)
            page.screenshot(path=str(artifacts/(area+"-mobile.png")),full_page=True)
            expect(page.locator(".ref-detail")).to_have_count(0)
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
