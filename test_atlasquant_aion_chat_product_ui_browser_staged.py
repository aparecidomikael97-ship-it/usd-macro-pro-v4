"""Chromium proof of the feature-flagged staged durable AION Chat host."""
from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect, sync_playwright


@pytest.fixture(scope="module")
def staged_preview():
    with tempfile.TemporaryDirectory() as raw:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

        env = dict(os.environ)
        env.update(
            {
                "ATLASQUANT_AION_CHAT_STAGED_PRODUCT": "true",
                "ATLASQUANT_AION_CHAT_STAGED_TENANT_ID": "tenant-browser-qa",
                "ATLASQUANT_AION_CHAT_STAGED_WORKSPACE_ID": "aion-browser-qa",
                "ATLASQUANT_AION_CHAT_STAGED_DIR": str(Path(raw).resolve()),
            }
        )
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "tools/aion_chat_product_staged_preview.py",
                "--server.address",
                "127.0.0.1",
                "--server.port",
                str(port),
                "--server.headless",
                "true",
                "--browser.gatherUsageStats",
                "false",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        url = f"http://127.0.0.1:{port}"
        try:
            for _ in range(120):
                try:
                    urlopen(url + "/_stcore/health", timeout=0.5).read()
                    break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("staged AION chat preview did not become healthy")
            yield url, Path(raw)
        finally:
            proc.terminate()
            proc.wait(timeout=10)


def _send(page, text):
    composer = page.locator("#aq-chat-message")
    expect(composer).to_be_enabled(timeout=20000)
    composer.fill(text)
    page.locator(".aq-chat-send").click()


def test_real_browser_persists_remounts_and_continues(staged_preview):
    url, root = staged_preview
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url)

        marker = page.locator("#aq-staged-host-marker")
        expect(marker).to_have_attribute("data-state", "STAGED_BOUND", timeout=30000)
        expect(marker).to_have_attribute("data-production", "false")
        expect(marker).to_have_attribute("data-provider", "false")
        expect(marker).to_have_attribute("data-network", "false")
        expect(page.locator(".aq-chat-root")).to_be_visible(timeout=30000)
        expect(page.locator('[data-testid="stException"]')).to_have_count(0)

        _send(page, "status geral")
        assistant = page.locator(
            '.aq-chat-message.assistant[data-state="UNKNOWN"]'
        )
        try:
            expect(assistant).to_have_count(1, timeout=30000)
        except AssertionError:
            # Diagnostic-only: preserve the failing assertion and report
            # QA-host state without dumping message bodies or credentials.
            snapshot = page.evaluate("""() => {
                const one = selector => document.querySelector(selector);
                const all = selector => [...document.querySelectorAll(selector)];
                return {
                    root_count: all('.aq-chat-root').length,
                    total_message_cards: all('.aq-chat-message').length,
                    assistant_states: all('.aq-chat-message.assistant')
                        .map(e => e.dataset.state ?? ''),
                    live_status: one('.aq-chat-live')?.textContent ?? 'NOT_MOUNTED',
                    workspace_routes: all('[data-workspace]')
                        .map(e => e.getAttribute('data-workspace')),
                    host_marker_count: all('#aq-staged-host-marker').length,
                    st_exception_count: all('[data-testid="stException"]').length,
                    // QA-only synthetic fixture: display just the error heading,
                    // never the full traceback, transcript or runtime secrets.
                    st_exception_heading: (one('[data-testid="stException"]')
                        ?.innerText ?? 'NONE').split('\\n')[0].slice(0, 240),
                    page_title: document.title,
                };
            }""")
            snapshot["browser_error_count"] = len(errors)
            snapshot["sqlite_file_count"] = len(list(root.glob("aion-chat-*.sqlite3")))
            print("AION_STAGED_FIRST_TURN_DIAGNOSTIC", snapshot)
            raise
        expect(assistant).to_contain_text("AION · histórico local")
        expect(assistant).to_contain_text("Não reverificado · UNKNOWN")
        expect(assistant).not_to_contain_text("leitura local verificada")
        expect(page.locator(".aq-chat-message")).to_have_count(2)
        assistant.locator(".aq-chat-proof summary").click()
        expect(assistant.locator(".aq-chat-proof")).to_contain_text("NOT_REVERIFIED")
        expect(assistant.locator(".aq-chat-proof")).to_contain_text("LOCAL_PRESENT")
        expect(assistant.locator(".aq-chat-proof")).to_contain_text("não foi reverificado")
        expect(assistant.locator(".aq-chat-proof")).not_to_contain_text("Receipt verificado")
        conversation_id = page.locator(".aq-chat-id").inner_text().strip()
        assert conversation_id
        assert list(root.glob("aion-chat-*.sqlite3"))

        # Close the actual SQLite handle and let the host construct a new one
        # against the same explicitly configured staging path.
        page.get_by_role(
            "button",
            name="QA · remontar store durável",
        ).click()
        expect(page.get_by_text("remounts=1", exact=False)).to_be_visible(
            timeout=30000
        )
        expect(page.locator(".aq-chat-root")).to_be_visible(timeout=30000)
        expect(page.locator(".aq-chat-id")).to_have_text(
            conversation_id,
            timeout=30000,
        )
        expect(page.locator(".aq-chat-message")).to_have_count(2)
        expect(assistant).to_have_count(1)
        expect(assistant).to_contain_text("AION · histórico local")

        _send(page, "status geral")
        expect(page.locator(".aq-chat-message")).to_have_count(4, timeout=30000)
        expect(assistant).to_have_count(2)
        # Multiple assistant turns exist here; test the newest turn explicitly.
        expect(assistant.last).to_contain_text("Não reverificado · UNKNOWN")
        expect(page.locator(".aq-chat-id")).to_have_text(conversation_id)
        expect(page.locator('[data-testid="stException"]')).to_have_count(0)

        # Unmount the AION workspace, return to Central, then mount AION again.
        page.locator('.ref-toolbar [data-route="central"]').click()
        expect(
            page.locator('[data-workspace="central"]')
        ).to_be_visible(timeout=30000)
        page.locator(
            '.ref-canvas [data-route="area:aion"]'
        ).click()
        expect(page.locator(".aq-chat-root")).to_be_visible(timeout=30000)
        expect(page.locator(".aq-chat-id")).to_have_text(conversation_id)
        expect(page.locator(".aq-chat-message")).to_have_count(4)
        expect(assistant).to_have_count(2)
        expect(page.locator('[data-testid="stException"]')).to_have_count(0)
        assert not errors
        browser.close()
