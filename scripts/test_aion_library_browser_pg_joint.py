"""One CI-only cycle: real AtlasQuant login+browser and ephemeral PostgreSQL read.

No production app files are changed. The browser gets a strictly ephemeral
in-memory test overlay, never a deployable route or document bytes. Adversarial
DB mid-read cases remain in the independent real PostgreSQL suites.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import test_aion_library_actual_app_browser as actual
from aion_library_ci_joint_host import (
    OWNER_DSN, approve_fixture, assert_read_only_roles,
    initialize_fixture, require_synthetic, revoke_admin,
)
from playwright.sync_api import sync_playwright

OUT = ROOT / "aion-library-browser-pg-evidence"
PORT = actual.PORT


def child_env(entry_id, *, shell_enabled):
    """Allowlist only synthetic configuration; do not inherit developer secrets."""
    base = actual.synthetic_env(library_enabled=shell_enabled)
    keep = {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "VIRTUAL_ENV",
            "PYTHONPATH", "CI", "ATLASQUANT_ENV", "ATLASQUANT_AUTH_REQUIRED",
            "ATLASQUANT_BOOTSTRAP_PREVIEW", "ATLASQUANT_OFFLINE_SMOKE",
            "ATLASQUANT_USERS_JSON", "AION_LIBRARY_SHELL_PREVIEW",
            "STREAMLIT_BROWSER_GATHER_USAGE_STATS", "AION_MODEL_PROVIDER",
            "GITHUB_REPO_HISTORICO", "GITHUB_BRANCH_HISTORICO",
            "GITHUB_DATA_BRANCH", "GITHUB_TOKEN_HISTORICO",
            "CHAVE_FRED", "CHAVE_NEWSAPI", "CHAVE_EODHD",
            "CHAVE_TWELVE_DATA", "OPENAI_API_KEY"}
    env = {k: v for k, v in base.items() if k in keep}
    env.update({
        "CI": "true",
        "ATLASQUANT_ENV": "SANDBOX",
        "ATLASQUANT_REAL_APP_SYNTHETIC": "1",
        "AION_LIB_BROWSER_PG_E2E": "1",
        "AION_CI_TRUSTED_ENTRY": entry_id,
        "PYTHONPATH": str(ROOT),
    })
    # In particular, OWNER_DSN / AION_LIB_TEST_PG_DSN is NEVER in app environment.
    assert "AION_LIB_TEST_PG_DSN" not in env
    return env


def start_actual_app(entry_id, *, shell_enabled):
    OUT.mkdir(exist_ok=True)
    actual.OUT.mkdir(exist_ok=True)
    logfile = (OUT / "private-local-only.log").open("w", encoding="utf-8")
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(ROOT / "scripts" / "aion_library_ci_instrumented_app.py"),
        "--server.headless", "true", "--server.address", "127.0.0.1",
        "--server.port", str(PORT), "--browser.gatherUsageStats", "false",
    ]
    proc = subprocess.Popen(
        cmd, env=child_env(entry_id, shell_enabled=shell_enabled),
        cwd=ROOT, stdout=logfile, stderr=subprocess.STDOUT,
    )
    try:
        for _ in range(125):
            if proc.poll() is not None:
                raise RuntimeError("isolated instrumented actual app exited")
            try:
                with urlopen(f"http://127.0.0.1:{PORT}/_stcore/health", timeout=2) as response:
                    if response.status == 200:
                        return proc, logfile
            except Exception:
                pass
            time.sleep(0.6)
        raise RuntimeError("actual app sandbox health timeout")
    except Exception:
        actual.stop_app(proc, logfile)
        raise


def choose_library_checked(page, area):
    # Streamlit can rerender the selectbox just as Playwright opens the
    # dropdown. Reacquire the REAL element and retry only the UI gesture;
    # never inject session state or select a Library scope from the browser.
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    option = page.get_by_role("option", name="📚 Biblioteca", exact=True)
    for attempt in range(3):
        area = actual.enter_aion(page)
        combo = area.get_by_role("combobox")
        combo.click(timeout=15_000)
        try:
            option.wait_for(state="visible", timeout=5_000)
            option.click(timeout=15_000)
            page.get_by_text(
                "Nenhum PDF pode ser enviado, consultado ou aprovado",
                exact=False,
            ).wait_for(timeout=120_000)
            return
        except PlaywrightTimeout:
            # A vanished option can mean a Streamlit rerender closed the
            # dropdown. Retrying does not grant any new permission.
            if page.get_by_text(
                "Nenhum PDF pode ser enviado, consultado ou aprovado",
                exact=False,
            ).count():
                return
            page.keyboard.press("Escape")
            if attempt < 2:
                page.wait_for_timeout(650)

    # Fail closed after bounded retries, with only static policy telemetry.
    labels = page.get_by_role("option").all_inner_texts()
    print("CI_WORKSPACE_OPTIONS=" + repr(labels[:12]), flush=True)
    logfile = OUT / "private-local-only.log"
    if logfile.exists():
        lines = [line.strip() for line in logfile.read_text(
            encoding="utf-8", errors="replace").splitlines()
            if "AION_CI_GATE_REASON=" in line]
        print("CI_GATE_DIAG=" + repr(lines[-4:]), flush=True)
    raise AssertionError("real Streamlit Library option not stable after bounded retries")


def browser_case(browser, *, username, width, height, mobile, expected):
    context = browser.new_context(
        viewport={"width": width, "height": height},
        is_mobile=mobile, device_scale_factor=1, locale="pt-BR",
    )
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    try:
        actual.login(page, username)
        if username == actual.CI_ADMIN and expected != "FLAG_OFF":
            area = actual.enter_aion(page)
            choose_library_checked(page, area)
            actual.assert_no_document_controls(page)
            assert_state(page, expected)
        elif username == actual.CI_ADMIN:
            area = actual.enter_aion(page)
            area.get_by_role("combobox").click()
            assert page.get_by_role("option", name="📚 Biblioteca").count() == 0
            area.get_by_role("combobox").press("Escape")
        else:
            page.wait_for_timeout(1700)
            assert page.locator('[data-testid="stSelectbox"]').filter(has_text="Área AION").count() == 0
            assert "Estado sintético:" not in page.locator('[data-testid="stMain"]').inner_text()
        actual.record_layout(page, f"pg-{username}-{width}-{expected}", width)
        assert not errors, ("browser JavaScript errors", errors[-3:])
        return context, page
    except Exception:
        context.close()
        raise


def assert_state(page, expected):
    main = page.locator('[data-testid="stMain"]')
    if expected in ("METADATA_REVIEW", "APPROVED_FOR_INDEXING"):
        try:
            # Streamlit may briefly retain several identically labeled
            # text spans across rerenders. Require at least one visible
            # matching state AND recheck the bounded main-panel contents.
            main.get_by_text("Estado sintético: " + expected,
                             exact=True).first.wait_for(timeout=30_000)
        except Exception:
            body = main.inner_text()
            print("CI_READ_STATE_DIAG=" + repr({
                "generic_denial_visible": "Consulta sintética indisponível" in body,
                "static_shell_visible": "Nenhum PDF pode ser enviado" in body,
                "streamlit_exception_count": page.locator('[data-testid="stException"]').count(),
            }), flush=True)
            logfile = OUT / "private-local-only.log"
            if logfile.exists():
                allowed = ("AION_CI_GATE_REASON=", "AION_CI_READ_EXCEPTION_TYPES=", "AION_CI_DENIAL_STAGES=")
                diagnostic = [line.strip() for line in logfile.read_text(
                    encoding="utf-8", errors="replace").splitlines()
                    if any(marker in line for marker in allowed)]
                print("CI_HOST_DIAG=" + repr(diagnostic[-8:]), flush=True)
            page.screenshot(path=str(actual.OUT / "pg-synthetic-diagnostic.png"),
                            full_page=False)
            raise
        body = main.inner_text()
        assert "Estado sintético: " + expected in body
        assert "Integridade sintética: CONFIRMADA" in body
        assert "Versão sintética: 1" in body
        assert "DOC-1" not in body and "synthetic-publisher" not in body
        assert "a" * 64 not in body
        assert "Consulta sintética indisponível" not in body
    elif expected == "DENIED":
        main.get_by_text("Consulta sintética indisponível",
                         exact=True).first.wait_for(timeout=90_000)
        assert "Estado sintético:" not in main.inner_text()
    else:
        raise AssertionError("unknown expected synthetic state")


def rerender_library(page):
    area = actual.enter_aion(page)
    combo = area.get_by_role("combobox")
    combo.click()
    page.get_by_role("option", name="🧠 Central").click(timeout=30_000)
    area = actual.enter_aion(page)
    choose_library_checked(page, area)


def main():
    require_synthetic(writer=True)
    if os.getenv("AION_LIB_TEST_PG_DSN") != OWNER_DSN:
        raise RuntimeError("CI PostgreSQL must use the exact ephemeral DSN")

    entry, writer, approvals = initialize_fixture()
    assert_read_only_roles()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            proc, log = start_actual_app(entry.entry_id, shell_enabled=True)
            opened = []
            try:
                for user, width, height, mobile, wanted in (
                    (actual.CI_ADMIN, 390, 844, True, "METADATA_REVIEW"),
                    (actual.CI_USER, 390, 844, True, "NO_ADMIN"),
                    (actual.CI_ADMIN, 1440, 900, False, "METADATA_REVIEW"),
                ):
                    ctx, page = browser_case(
                        browser, username=user, width=width, height=height,
                        mobile=mobile, expected=wanted,
                    )
                    opened.append(ctx)
                    if user == actual.CI_ADMIN and width == 1440:
                        desktop_page = page

                # Writer is held by the CI runner, never app/browser.
                approve_fixture(entry, writer, approvals)
                rerender_library(desktop_page)
                assert_state(desktop_page, "APPROVED_FOR_INDEXING")
                actual.assert_no_document_controls(desktop_page)
                actual.record_layout(desktop_page, "pg-admin-after-approval", 1440)
                print("PASS real AtlasQuant browser -> trusted host -> PostgreSQL approved metadata", flush=True)

                # PostgreSQL committed revocation must deny the NEXT browser-driven read.
                revoke_admin()
                rerender_library(desktop_page)
                assert_state(desktop_page, "DENIED")
                actual.record_layout(desktop_page, "pg-admin-after-revocation", 1440)
                print("PASS browser-driven read denied after persistent ACL revocation", flush=True)
            finally:
                for ctx in opened:
                    ctx.close()
                actual.stop_app(proc, log)

            proc, log = start_actual_app(entry.entry_id, shell_enabled=False)
            try:
                context, _ = browser_case(
                    browser, username=actual.CI_ADMIN, width=390, height=844,
                    mobile=True, expected="FLAG_OFF",
                )
                context.close()
                print("PASS actual AtlasQuant admin with Library shell disabled", flush=True)
            finally:
                actual.stop_app(proc, log)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
