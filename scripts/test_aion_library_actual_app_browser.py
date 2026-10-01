"""CI-only Playwright smoke through the ACTUAL AtlasQuant application and login.

Uses ephemeral synthetic local accounts and no user data, API tokens, real DB or
real deployment. Exercises the genuine app entry, login, AION workspace selector
and Library's noninteractive sandbox shell at mobile and desktop widths.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PORT = 8594
URL = f"http://127.0.0.1:{PORT}/?aion=1"
CI_ADMIN = "admin.ci"
CI_USER = "reader.ci"
CI_PASSWORD = "SyntheticBrowserOnly2026!"
OUT = ROOT / "aion-library-real-app-smoke"


def synthetic_env(*, library_enabled: bool) -> dict[str, str]:
    from atlasquant_access_control import hash_password
    # Never load an existing user account; CI supplies the complete registry.
    password_hash = hash_password(CI_PASSWORD, salt=b"sandbox-tests-2026", iterations=200_000)
    users = {name: {"role": role, "active": True, "password_hash": password_hash}
             for name, role in ((CI_ADMIN, "ADMIN"), (CI_USER, "USER"))}
    env = dict(os.environ)
    for key in list(env):
        if key.startswith(("CHAVE_", "GITHUB_TOKEN_", "OPENAI_", "NEWSAPI_", "EODHD_", "TWELVE_")):
            env.pop(key, None)
    env.update({
        "CI": "true", "ATLASQUANT_ENV": "SANDBOX",
        "ATLASQUANT_AUTH_REQUIRED": "true",
        "ATLASQUANT_BOOTSTRAP_PREVIEW": "false",
        "ATLASQUANT_OFFLINE_SMOKE": "true",
        "ATLASQUANT_USERS_JSON": json.dumps({"users": users}, separators=(",", ":")),
        "AION_LIBRARY_SHELL_PREVIEW": "true" if library_enabled else "false",
        "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
        "AION_MODEL_PROVIDER": "LOCAL",
        "GITHUB_REPO_HISTORICO": "", "GITHUB_BRANCH_HISTORICO": "",
        "GITHUB_DATA_BRANCH": "", "GITHUB_TOKEN_HISTORICO": "",
        "CHAVE_FRED": "", "CHAVE_NEWSAPI": "", "CHAVE_EODHD": "",
        "CHAVE_TWELVE_DATA": "", "OPENAI_API_KEY": "",
        "PYTHONPATH": str(ROOT),
    })
    return env


def start_app(*, library_enabled: bool):
    OUT.mkdir(exist_ok=True)
    log_path = OUT / ("sandbox-on.log" if library_enabled else "sandbox-off.log")
    log = log_path.open("w", encoding="utf-8")
    cmd = [sys.executable, "-m", "streamlit", "run", str(ROOT / "usd_macro_pro_v4_cloud.py"),
           "--server.headless", "true", "--server.address", "127.0.0.1",
           "--server.port", str(PORT), "--browser.gatherUsageStats", "false"]
    proc = subprocess.Popen(cmd, cwd=ROOT, env=synthetic_env(library_enabled=library_enabled),
                            stdout=log, stderr=subprocess.STDOUT)
    try:
        for _ in range(100):
            if proc.poll() is not None:
                raise RuntimeError("synthetic full app exited before health check")
            try:
                with urlopen(f"http://127.0.0.1:{PORT}/_stcore/health", timeout=2) as res:
                    if res.status == 200:
                        return proc, log
            except Exception:
                pass
            time.sleep(.6)
        raise RuntimeError("full AtlasQuant CI app health check timed out")
    except Exception:
        proc.kill()
        proc.wait(timeout=10)
        log.close()
        raise


def stop_app(proc, log):
    proc.terminate()
    try:
        proc.wait(timeout=12)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=12)
    log.close()
    time.sleep(1)


def login(page, username: str):
    page.goto(URL, wait_until="domcontentloaded", timeout=90_000)
    page.get_by_text("Acesso privado. Use sua conta autorizada.", exact=False).wait_for(timeout=90_000)
    page.get_by_label("Usuário", exact=True).fill(username)
    page.get_by_label("Senha", exact=True).fill(CI_PASSWORD)
    page.get_by_role("button", name="Entrar", exact=True).click()
    # Streamlit first completes login and then loads the full application.
    page.get_by_text("🔐 AtlasQuant", exact=False).wait_for(state="hidden", timeout=120_000)


def enter_aion(page):
    # Preserve the authenticated Streamlit websocket. A fresh page.goto() after
    # login can RESET Streamlit session_state, including its local login!
    # The initial login page already used ?aion=1, consumed on its rerun.
    page.locator('[data-testid="stSelectbox"]').filter(has_text="Área AION").first.wait_for(
        state="visible", timeout=160_000)
    return page.locator('[data-testid="stSelectbox"]').filter(has_text="Área AION").first


def assert_no_document_controls(page):
    # Page contains controls outside the Library; check only the Library
    # section by its bounded semantic text and explicit file uploader count.
    body = page.locator('[data-testid="stMain"]').inner_text(timeout=30_000)
    assert "Nenhum PDF pode ser enviado, consultado ou aprovado" in body
    assert page.locator('[data-testid="stFileUploader"]').count() == 0
    assert page.locator('[data-testid="stException"]').count() == 0


def choose_library(page, area):
    combo = area.get_by_role("combobox")
    combo.click()
    # A real Streamlit selectbox, not a spoofed session state or fixture.
    page.get_by_role("option", name="📚 Biblioteca").click(timeout=20_000)
    page.get_by_text("Nenhum PDF pode ser enviado, consultado ou aprovado", exact=False).wait_for(
        timeout=120_000)


def record_layout(page, label, width):
    view_w = page.evaluate("window.innerWidth")
    doc_w = page.evaluate("document.documentElement.scrollWidth")
    assert doc_w <= view_w + 8, f"{label}: page overflow at {width}: {doc_w}>{view_w}"
    assert page.locator('[data-testid="stException"]').count() == 0
    page.screenshot(path=str(OUT / (label + ".png")), full_page=False)
    print(f"PASS {label} viewport={width} document_width={doc_w}", flush=True)


def full_app_case(browser, *, username: str, width: int, height: int,
                  mobile: bool, library_enabled: bool):
    label = ("enabled" if library_enabled else "disabled") + "-" + username + "-" + str(width)
    context = browser.new_context(viewport={"width": width, "height": height},
                                  is_mobile=mobile, device_scale_factor=1, locale="pt-BR")
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda err: errors.append(str(err)))
    try:
        login(page, username)
        if username == CI_ADMIN:
            area = enter_aion(page)
            combo = area.get_by_role("combobox")
            if library_enabled:
                choose_library(page, area)
                assert_no_document_controls(page)
                assert "BLOQUEADO" in page.locator('[data-testid="stMain"]').inner_text()
            else:
                combo.click()
                assert page.get_by_role("option", name="📚 Biblioteca").count() == 0
                combo.press("Escape")
        else:
            # AION admin is not exposed at all to ordinary users, even via
            # its direct query route. Never probe or synthesize private access.
            page.wait_for_timeout(1800)
            assert page.locator('[data-testid="stSelectbox"]').filter(has_text="Área AION").count() == 0
            assert page.get_by_text("📚 Biblioteca AION", exact=True).count() == 0
        record_layout(page, label, width)
        assert not errors, (label, errors[-5:])
    finally:
        context.close()


def main():
    if os.getenv("CI", "").lower() != "true" or os.getenv("ATLASQUANT_REAL_APP_SYNTHETIC", "") != "1":
        raise RuntimeError("this full-app browser test is restricted to explicitly opted-in synthetic CI")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for preview, cases in [
                (True, [(CI_ADMIN, 390, 844, True), (CI_ADMIN, 1440, 900, False),
                        (CI_USER, 390, 844, True)]),
                (False, [(CI_ADMIN, 390, 844, True)]),
            ]:
                proc, log = start_app(library_enabled=preview)
                try:
                    for username, width, height, mobile in cases:
                        full_app_case(browser, username=username, width=width,
                                      height=height, mobile=mobile, library_enabled=preview)
                finally:
                    stop_app(proc, log)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
