"""Crawl every AtlasQuant area in a running local app and report UI health.

Usage (app already running, e.g. on port 8502 with local test accounts):
    python tools/interface_audit.py --base http://127.0.0.1:8502 \
        --user aparecidomikael --password-env AQ_AUDIT_PASSWORD --out /tmp/aq-audit

Read-only: it logs in, switches areas and measures. It never clicks buttons that
change data. The password is read from an environment variable and is never
printed. Requires Playwright with Chromium.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from pathlib import Path

CONTRAST_JS = r"""
() => {
  function parse(c){const m=c&&c.match(/rgba?\(([^)]+)\)/);if(!m)return null;const p=m[1].split(',').map(x=>parseFloat(x));return {r:p[0],g:p[1],b:p[2],a:p.length>3?p[3]:1};}
  function lum(c){const f=v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)};return 0.2126*f(c.r)+0.7152*f(c.g)+0.0722*f(c.b);}
  function ratio(a,b){const l1=lum(a),l2=lum(b);return (Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05);}
  function bgOf(el){let n=el;while(n&&n.nodeType===1){const s=getComputedStyle(n);const c=parse(s.backgroundColor);if(c&&c.a>0.5)return c;if(s.backgroundImage&&s.backgroundImage!=='none'){const g=parse(s.backgroundImage);if(g&&g.a>0.5)return g;}n=n.parentElement;}return {r:7,g:17,b:31,a:1};}
  const out=[];const seen=new Set();
  const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
  while(w.nextNode()){
    const t=w.currentNode;const txt=(t.textContent||'').trim();if(txt.length<2)continue;
    const el=t.parentElement;if(!el||seen.has(el))continue;seen.add(el);
    if(el.closest('[aria-hidden="true"],script,style,noscript,svg,canvas'))continue;
    const s=getComputedStyle(el);if(s.visibility==='hidden'||s.display==='none')continue;
    const r=el.getBoundingClientRect();if(r.width<2||r.height<2||r.right<0||r.left>innerWidth+5)continue;
    let o=1,n=el;while(n&&n.nodeType===1){o*=parseFloat(getComputedStyle(n).opacity)||1;n=n.parentElement;}if(o<0.2)continue;
    const fg=parse(s.webkitTextFillColor&&s.webkitTextFillColor!=='currentcolor'?s.webkitTextFillColor:s.color)||parse(s.color);if(!fg)continue;
    const cr=ratio(fg,bgOf(el));const size=parseFloat(s.fontSize);const bold=parseInt(s.fontWeight)>=700;
    const need=(size>=24||(size>=18.66&&bold))?3:4.5;
    if(cr<need)out.push({text:txt.slice(0,80),ratio:+cr.toFixed(2),fg:s.color,testid:(el.closest('[data-testid]')||{getAttribute:()=>''}).getAttribute('data-testid')});
  }
  const exc=[...document.querySelectorAll('[data-testid="stException"]')].map(n=>n.innerText.slice(0,300));
  const errors=[...document.querySelectorAll('[data-testid="stAlertContentError"]')].map(n=>n.innerText.slice(0,200));
  return {checked:seen.size,contrast:out,exceptions:exc,errors:errors,overflow:document.documentElement.scrollWidth-innerWidth,
          buttons:document.querySelectorAll('[data-testid="stButton"] button').length};
}
"""


def _wait_idle(page, timeout_s=120.0):
    page.wait_for_timeout(350)
    end = time.time() + timeout_s
    while time.time() < end:
        if not page.locator('[data-testid="stStatusWidget"]').count():
            page.wait_for_timeout(250)
            if not page.locator('[data-testid="stStatusWidget"]').count():
                return True
        page.wait_for_timeout(200)
    return False


def _login(page, base, user, password):
    page.goto(base, wait_until="domcontentloaded")
    page.get_by_label("Usuário").fill(user)
    page.get_by_label("Senha").fill(password)
    page.get_by_role("button", name="Entrar").click()
    page.wait_for_selector("#aq-account-identity", timeout=120000)
    _wait_idle(page)


def _combobox(page, label):
    return page.locator('[data-testid="stSelectbox"]').filter(has_text=label).first.get_by_role("combobox")


def _select_area(page, label, option):
    box = _combobox(page, label)
    box.click()
    box.fill(option)
    page.get_by_role("option", name=option, exact=True).first.click(timeout=15000)


def _advanced_options(page, label="Área avançada"):
    """Streamlit 1.64 renders a virtualized React Aria list; walk it by keyboard."""
    box = _combobox(page, label)
    box.focus()
    page.keyboard.press("ArrowDown")
    page.wait_for_timeout(300)
    names: list[str] = []
    stale = 0
    while stale < 3 and len(names) < 200:
        before = len(names)
        for opt in page.get_by_role("option").all():
            text = opt.inner_text().strip()
            if text and text not in names:
                names.append(text)
        stale = stale + 1 if len(names) == before else 0
        for _ in range(8):
            page.keyboard.press("ArrowDown")
        page.wait_for_timeout(120)
    page.keyboard.press("Escape")
    return names


def run(base, user, password, out_dir, viewports):
    from playwright.sync_api import sync_playwright

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = {"base": base, "user": user, "viewports": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, vp in viewports.items():
            page = browser.new_page(viewport=vp)
            _login(page, base, user, password)
            rows = []
            for area in [o.inner_text().strip() for o in page.locator('[data-testid="stRadio"]').nth(1).locator('[data-testid="stRadioOption"]').all()] or []:
                started = time.perf_counter()
                page.locator('[data-testid="stRadio"]').nth(1).get_by_text(area, exact=True).click()
                idle = _wait_idle(page)
                health = page.evaluate(CONTRAST_JS)
                rows.append({"mode": "Iniciante", "area": area, "ms": round((time.perf_counter() - started) * 1000), "idle": idle,
                             "exceptions": health["exceptions"], "errors": health["errors"], "contrast": health["contrast"][:10],
                             "contrast_count": len(health["contrast"]), "overflow": health["overflow"], "buttons": health["buttons"]})
            started = time.perf_counter()
            page.get_by_text("Avançado", exact=True).first.click()
            page.wait_for_selector(".aq-boot-banner", timeout=120000)
            _wait_idle(page)
            rows.append({"mode": "Avançado", "area": "(abertura)", "ms": round((time.perf_counter() - started) * 1000)})
            for area in _advanced_options(page):
                started = time.perf_counter()
                _select_area(page, "Área avançada", area)
                idle = _wait_idle(page)
                elapsed = round((time.perf_counter() - started) * 1000)
                health = page.evaluate(CONTRAST_JS)
                slug = "".join(ch for ch in area if ch.isalnum()) or "area"
                page.screenshot(path=str(out / f"{name}-{slug}.png"))
                rows.append({"mode": "Avançado", "area": area, "ms": elapsed, "idle": idle,
                             "exceptions": health["exceptions"], "errors": health["errors"], "contrast": health["contrast"][:10],
                             "contrast_count": len(health["contrast"]), "overflow": health["overflow"], "buttons": health["buttons"]})
            report["viewports"][name] = rows
            page.close()
        browser.close()
    for name, rows in report["viewports"].items():
        timed = [r["ms"] for r in rows if r.get("area") != "(abertura)"]
        report[f"{name}_median_ms"] = round(statistics.median(timed)) if timed else None
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8502")
    parser.add_argument("--user", required=True)
    parser.add_argument("--password-env", default="AQ_AUDIT_PASSWORD")
    parser.add_argument("--out", default="/tmp/aq-audit")
    parser.add_argument("--mobile-only", action="store_true")
    parser.add_argument("--desktop-only", action="store_true")
    args = parser.parse_args()
    password = os.environ.get(args.password_env, "")
    if not password:
        raise SystemExit(f"set {args.password_env}")
    viewports = {"desktop": {"width": 1440, "height": 1000}, "mobile": {"width": 390, "height": 844}}
    if args.mobile_only:
        viewports.pop("desktop")
    if args.desktop_only:
        viewports.pop("mobile")
    report = run(args.base, args.user, password, args.out, viewports)
    for name, rows in report["viewports"].items():
        print(f"== {name} (mediana {report.get(name + '_median_ms')} ms)")
        for r in rows:
            flags = []
            if r.get("exceptions"):
                flags.append(f"EXC x{len(r['exceptions'])}")
            if r.get("errors"):
                flags.append(f"ERR x{len(r['errors'])}")
            if r.get("contrast_count"):
                flags.append(f"contraste x{r['contrast_count']}")
            if r.get("overflow", 0) > 8:
                flags.append(f"overflow {r['overflow']}px")
            if r.get("idle") is False:
                flags.append("sem ficar ocioso")
            print(f"  {r['mode']:9} {r['area'][:28]:28} {r['ms']:>6} ms  {' '.join(flags)}")


if __name__ == "__main__":
    main()
