"""Browser acceptance tests; optional development dependency: playwright + Chromium."""
import base64
from pathlib import Path

import pytest
pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright, expect
from test_atlasquant_aion_chat_foundation import preview


def test_browser_desktop_mobile_send_attachments_history(preview, tmp_path):
    root, token = preview
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(root)
        expect(page.locator("#status")).to_contain_text("não conectado")
        with page.expect_response("**/api/create") as response:
            page.locator("#new").click()
        cid = response.value.json()["id"]
        expect(page.locator("#message")).to_be_enabled()
        page.locator("#file").set_input_files({"name": "notes.txt", "mimeType": "text/plain", "buffer": b"notes"})
        expect(page.locator("#attachment-list")).to_contain_text("notes.txt")
        page.locator("#image").set_input_files({"name": "pixel.png", "mimeType": "image/png",
            "buffer": base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lZkAAAAASUVORK5CYII=")})
        expect(page.locator("#attachment-list")).to_contain_text("pixel.png")
        content = "Decisão: manter o histórico.\n<img src=x onerror=alert(1)>"
        page.locator("#message").fill(content)
        page.locator("#send").click()
        expect(page.locator(".message.user")).to_contain_text(content)
        expect(page.locator(".message.system")).to_contain_text("Modelo indisponível")
        assert page.locator(".message.assistant").count() == 0
        assert page.locator("#history img").count() == 0
        expect(page.locator(".message.user small")).to_contain_text("2")
        page.locator("#action").select_option("publish")
        page.locator("#message").fill("AION, publique o relatório")
        page.locator("#send").click()
        expect(page.locator(".task-state")).to_contain_text("WAITING_APPROVAL")
        page.get_by_role("button", name="Cancelar tarefa").click()
        expect(page.locator(".task-state").last).to_contain_text("CANCELLED")
        assert page.get_by_role("button", name="Cancelar tarefa").count() == 0
        page.get_by_role("button", name="Útil").last.click()
        expect(page.locator("#status")).to_contain_text("Feedback salvo")
        page.locator("#compact").click()
        expect(page.locator("#status")).to_contain_text("Checkpoint local salvo")
        page.screenshot(path=str(tmp_path / "desktop.png"), full_page=True)
        page.reload()
        page.locator(".conversation").first.click()
        expect(page.locator("#history")).to_contain_text("manter o histórico")
        # Seed old history through the same scoped API and exercise UI pagination.
        for i in range(30):
            r = page.request.post(root + "/api/send", headers={"X-Aion-Token": token},
                                  data={"cid": cid, "content": f"Paginação {i}"})
            assert r.ok
        page.locator(".conversation").first.click()
        expect(page.locator("#more-messages")).to_be_visible()
        page.locator("#more-messages").click()
        expect(page.locator("#history")).to_contain_text("manter o histórico")
        page.locator("#search").fill("manter")
        expect(page.locator(".conversation")).to_have_count(1)
        page.locator("#archive").click()
        expect(page.locator(".conversation")).to_have_count(0)
        page.locator("#archived").check()
        expect(page.locator(".conversation")).to_have_count(1)
        page.set_viewport_size({"width": 390, "height": 844})
        page.emulate_media(reduced_motion="reduce")
        page.locator("#drawer-toggle").click()
        expect(page.locator("#sidebar")).to_have_class("open")
        page.locator(".conversation").first.click()
        expect(page.locator("#sidebar")).not_to_have_class("open")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        bounds = page.locator("#composer").bounding_box()
        assert bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= 390
        assert bounds["y"] + bounds["height"] <= 844

        # open() refreshes the conversation list asynchronously via replaceChildren().
        # Re-resolve the locator and let Playwright retry while that DOM replacement
        # settles, preserving the same reduced-motion contract without accepting a
        # detached node's empty computed style.
        assert page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches") is True
        conversation = page.locator(".conversation").first
        expect(conversation).to_be_attached()
        expect(conversation).to_have_css("transition-duration", "0s")
        expect(conversation).to_have_css("transform", "none")

        page.screenshot(path=str(tmp_path / "mobile.png"), full_page=True)
        # Keep reviewable screenshots outside Git.
        qa = Path("chat_preview_artifacts")
        qa.mkdir(exist_ok=True)
        (qa / "desktop.png").write_bytes((tmp_path / "desktop.png").read_bytes())
        (qa / "mobile.png").write_bytes((tmp_path / "mobile.png").read_bytes())
        assert not errors
        browser.close()
