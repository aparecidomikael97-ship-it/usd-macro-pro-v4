"""CI smoke for the reference-first AtlasQuant production entry.

Targets the already-running local Streamlit app. It validates the new reference
surface, real click handlers, the Trader->legacy-analysis bridge, mobile
responsiveness and build identity without contacting external providers.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time

from playwright.sync_api import sync_playwright, expect

from atlasquant_build_identity import short_source_fingerprint


def _assert_clean(page, failures: list[str], label: str) -> None:
    exc = page.locator('[data-testid="stException"]').count()
    if exc:
        failures.append(f"{label}: {exc} stException")
    width = int(page.evaluate("document.documentElement.scrollWidth"))
    viewport = int(page.evaluate("window.innerWidth"))
    if width - viewport > 8:
        failures.append(f"{label}: overflow horizontal {width-viewport}px")


def _open_reference(
    page,
    url: str,
    failures: list[str],
    label: str,
    *,
    mobile: bool = False,
) -> None:
    response = page.goto(url, wait_until="domcontentloaded", timeout=180_000)
    if not response or response.status >= 400:
        failures.append(f"{label}: HTTP {response.status if response else None}")
        return
    page.locator('[data-testid="stAppViewContainer"]').wait_for(timeout=90_000)
    page.locator('.ref-workspace[data-workspace="trader"]').wait_for(
        state="visible", timeout=90_000
    )
    if mobile:
        # In the production entry the responsive card layer is the authoritative
        # mobile readiness signal. The custom component's image preload marker
        # can lag behind the already-painted mobile cards on slower CI runners.
        page.locator(".ref-mobile-grid .ref-mobile-card").first.wait_for(
            state="visible", timeout=90_000
        )
        root = page.locator(".ref-component-root").first
        if root.count():
            art_state = str(root.get_attribute("data-art-ready") or "").strip()
            if art_state == "error":
                failures.append(f"{label}: arte de referência sinalizou erro de carregamento")
    else:
        # Desktop uses the full raster canvas, so image readiness remains a hard gate.
        page.locator('.ref-component-root[data-art-ready="true"]').wait_for(
            state="visible", timeout=90_000
        )
    _assert_clean(page, failures, label)


def _check_build(page, expected: str, failures: list[str], label: str) -> str:
    marker = page.locator("#atlasquant-source-build-marker")
    if not marker.count():
        failures.append(f"{label}: marcador de build ausente")
        return ""
    observed = str(marker.first.get_attribute("data-build") or "").strip().lower()
    if observed != expected:
        failures.append(
            f"{label}: build divergente atual={observed or 'AUSENTE'} esperado={expected}"
        )
    return observed


def _desktop(page, failures: list[str], trace: list[dict]) -> None:
    expect(page.locator(".ref-canvas")).to_be_visible(timeout=30_000)
    expect(page.locator(".ref-sidebar")).to_be_visible(timeout=30_000)
    for route in ("radar", "master", "macro", "calendar", "aion_specialist", "profile"):
        if page.locator(f'.ref-sidebar [data-route="{route}"]').count() < 1:
            failures.append(f"desktop: rota principal ausente: {route}")

    start = time.perf_counter()
    page.locator('.ref-sidebar [data-route="master"]').click()
    expect(page.locator('.ref-detail[data-module="master"]')).to_be_visible(timeout=30_000)
    pairs = page.locator(".ref-detail .ref-pair").count()
    if pairs != 28:
        failures.append(f"desktop: Painel Mestre exibiu {pairs} pares; esperado=28")
    top_text = " ".join(
        page.locator(".ref-detail .ref-pair").nth(i).inner_text()
        for i in range(min(10, pairs))
    )
    if top_text.count("TOP 10") < min(10, pairs):
        failures.append("desktop: TOP 10 não está marcado nos dez primeiros pares")
    trace.append({"action": "master", "pairs": pairs, "ms": round((time.perf_counter()-start)*1000)})

    bridge = page.locator('.ref-detail [data-route="connected:master"]')
    if not bridge.count():
        failures.append("desktop: ponte para análise existente ausente no Painel Mestre")
    else:
        # The state transition into the legacy analytical pipeline is covered by
        # ProductionAdminFlowTests. This browser smoke remains provider-free and
        # validates that the bridge is visibly available from the new cockpit.
        trace.append({"action": "connected-master-bridge-present", "ok": True})

    mode = page.locator(".ref-mode")
    if not mode.count():
        failures.append("desktop: controle de modo da referência ausente")
    else:
        before = mode.first.inner_text()
        mode.first.click()
        page.locator(".ref-canvas").wait_for(state="visible", timeout=90_000)
        after = page.locator(".ref-mode").first.inner_text()
        if before == after:
            failures.append("desktop: alternância Iniciante/Avançado não mudou o modo")
        trace.append({"action": "mode-toggle", "before": before, "after": after})
    _assert_clean(page, failures, "desktop-final")


def _mobile(page, failures: list[str], trace: list[dict], stress: bool) -> None:
    expect(page.locator(".ref-drawer")).to_be_visible(timeout=30_000)
    cards = page.locator(".ref-mobile-card").count()
    if cards < 8:
        failures.append(f"mobile: apenas {cards} cartões responsivos")
    if page.locator(".ref-sidebar").is_visible():
        failures.append("mobile: sidebar desktop permaneceu visível")

    page.locator(".ref-drawer summary").first.click()
    expect(page.locator(".ref-drawer")).to_have_attribute("open", "")
    page.locator('.ref-drawer [data-route="profile"]').click()
    expect(page.locator(".ref-detail")).to_be_visible(timeout=30_000)
    page.locator('.ref-detail [data-route="home"]').click()
    expect(page.locator(".ref-detail")).to_have_count(0, timeout=30_000)
    trace.append({"action": "mobile-profile", "ok": True})

    if stress:
        for route in ("radar", "macro", "master", "academy", "journal", "radar"):
            locator = page.locator(f'.ref-mobile-card[data-route="{route}"]').first
            if not locator.count():
                failures.append(f"mobile-stress: cartão ausente: {route}")
                continue
            locator.click()
            expect(page.locator(".ref-detail")).to_be_visible(timeout=30_000)
            _assert_clean(page, failures, f"mobile-stress-{route}")
            page.locator('.ref-detail [data-route="home"]').click()
            expect(page.locator(".ref-detail")).to_have_count(0, timeout=30_000)
        trace.append({"action": "mobile-stress", "ok": True})
    _assert_clean(page, failures, "mobile-final")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.getenv("ATLASQUANT_SMOKE_URL", "http://127.0.0.1:8501"))
    parser.add_argument("--output", default="ui-smoke")
    parser.add_argument("--profile", choices=("desktop", "mobile", "both"), default="both")
    parser.add_argument("--stress", action="store_true")
    args = parser.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    expected = short_source_fingerprint(Path.cwd(), 16)
    failures: list[str] = []
    report = {"url": args.url, "expected_source_build": expected, "profiles": {}, "failures": failures}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        profiles = []
        if args.profile in {"desktop", "both"}:
            profiles.append(("desktop", {"viewport": {"width": 1440, "height": 1000}, "is_mobile": False}))
        if args.profile in {"mobile", "both"}:
            profiles.append(("mobile", {"viewport": {"width": 390, "height": 844}, "is_mobile": True}))

        for name, cfg in profiles:
            context = browser.new_context(
                viewport=cfg["viewport"],
                is_mobile=cfg["is_mobile"],
                device_scale_factor=1,
                locale="pt-BR",
            )
            page = context.new_page()
            page_errors: list[str] = []
            console_errors: list[str] = []
            page.on("pageerror", lambda exc, bucket=page_errors: bucket.append(str(exc)))
            page.on("console", lambda msg, bucket=console_errors: bucket.append(msg.text) if msg.type == "error" else None)
            trace: list[dict] = []
            try:
                _open_reference(
                    page,
                    args.url,
                    failures,
                    name,
                    mobile=(name == "mobile"),
                )
                observed = _check_build(page, expected, failures, name)
                if name == "desktop":
                    _desktop(page, failures, trace)
                else:
                    _mobile(page, failures, trace, args.stress)
                if page_errors:
                    failures.append(f"{name}: {len(page_errors)} pageerror")
                if any("NotFoundError" in x or "removeChild" in x for x in console_errors):
                    failures.append(f"{name}: console contém NotFoundError/removeChild")
                page.screenshot(path=str(out / f"{name}.png"), full_page=True)
                report["profiles"][name] = {
                    "source_build": observed,
                    "trace": trace,
                    "page_errors": page_errors[-10:],
                    "console_errors": console_errors[-10:],
                    "document_width": int(page.evaluate("document.documentElement.scrollWidth")),
                    "viewport_width": int(page.evaluate("window.innerWidth")),
                }
            except Exception as exc:
                failures.append(f"{name}: {type(exc).__name__}: {exc}")
                try:
                    page.screenshot(path=str(out / f"{name}-failure.png"), full_page=True)
                except Exception:
                    pass
            finally:
                context.close()
        browser.close()

    (out / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
