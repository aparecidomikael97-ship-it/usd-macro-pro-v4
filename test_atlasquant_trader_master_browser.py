"""Chromium contracts for the approved Painel Mestre visual layout.

Runs in the existing Quality browser stage; no live URLs, credentials or API.
Synthetic fixture is explicitly identified as LAB evidence.
"""
from datetime import datetime, timedelta, timezone
import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright, expect

from atlasquant_trader_economic_calendar import normalize_events
from atlasquant_trader_radar_compact_ui import trader_radar_html


def _markup() -> str:
    brt = timezone(timedelta(hours=-3))
    now = datetime.now(brt)
    release_today = now.replace(hour=9, minute=30, second=0, microsecond=0)
    release_tomorrow = (now + timedelta(days=1)).replace(
        hour=9, minute=30, second=0, microsecond=0
    )
    def event(name, moment, estimate=3.2):
        return {
            "country": "US", "type": name,
            "date": moment.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "period": "LAB", "comparison": "yoy",
            "previous": 3.1, "estimate": estimate, "actual": None,
        }
    snapshot = normalize_events(
        {"ok": True, "fetched_at": now.isoformat(),
         "data": [event("Consumer Price Index CPI", release_today),
                  event("GDP Growth Rate", release_tomorrow)]},
        at=now
    )
    snapshot["source"] = "EXEMPLO FICTÍCIO · LAB"
    for entry in snapshot["events"] + snapshot["week_events"]:
        entry["source"] = "EXEMPLO FICTÍCIO · LAB"
        entry["consensus_source"] = "EXEMPLO SINTÉTICO · NÃO REAL"
    news_time = now.astimezone(timezone.utc).isoformat()
    existing_news = {
        "updated_at": news_time,
        "currencies": {"USD": {"articles": [{
            "title": "Trade tariffs discussed in Washington",
            "source": "LAB Financial Press",
            "published_at": news_time,
            "link": "https://example.com/lab-news",
            "provider": "Google News RSS",
        }]}}
    }
    content = trader_radar_html(
        selected="master", name="M", show_central=False,
        calendar_data=snapshot, news_data=existing_news
    )
    return (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<style>body{margin:0;background:#080e1b}</style></head>'
        '<body>' + content + '</body></html>'
    )


@pytest.mark.parametrize("width,height", [(1440, 900), (768, 1024), (390, 844)])
def test_master_browser_does_not_overflow_and_expands_calendar(width, height):
    markup = _markup()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": height},
                                device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda exception: errors.append(str(exception)))
        page.set_content(markup, wait_until="load")
        expect(page.locator('.aqr-app')).to_be_visible()
        expect(page.locator('.aqr-hero h1')).to_contain_text("Entenda")
        expect(page.locator('main .aqr-card').first).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        for selector in (".aqr-app", ".aqr-hero", ".aqr-hero h1", ".aqr-aside"):
            rect = page.locator(selector).bounding_box()
            assert rect is not None
            assert rect["x"] >= -2, selector
            assert rect["x"] + rect["width"] <= width + 2, selector
        expect(page.locator(".aqr-master-week details")).to_have_count(1)
        weekly = page.locator(".aqr-master-week details").first
        weekly.locator("summary").click()
        expect(weekly).to_have_attribute("open", "")
        expect(weekly).to_contain_text("Acima do consenso")
        expect(page.locator(".aqr-cal-item")).to_have_count(1)
        daily = page.locator(".aqr-cal-item").first
        daily.locator("summary").click()
        expect(daily).to_have_attribute("open", "")
        expect(daily).to_contain_text("Se vier abaixo do consenso")
        expect(page.locator(".aqr-news-item")).to_have_count(1)
        headline = page.locator(".aqr-news-item").first
        headline.locator("summary").click()
        expect(headline).to_have_attribute("open", "")
        expect(headline).to_contain_text("não foi verificado independentemente")
        expect(page.locator(".aqr-news-item a")).to_have_attribute(
            "rel", "noopener noreferrer nofollow"
        )
        assert not errors
        browser.close()
