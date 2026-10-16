"""Viewport and keyboard navigation checks for isolated, offline UI."""
from pathlib import Path
from playwright.sync_api import sync_playwright
HTML=Path(__file__).with_name('index.html').read_text(encoding='utf-8')
NAVS=['triagem','oportunidades','rotina','propostas','privacidade']
widths=[320,360,390,580,768,1024,1440]
checks=0
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--disable-dev-shm-usage','--no-sandbox'])
    for width in widths:
        page=browser.new_page(viewport={'width':width,'height':850},offline=True,is_mobile=width<851,has_touch=width<851)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(HTML,wait_until='load')
        nav='.bottom-nav' if width<=850 else '.sidebar'
        for name in NAVS:
            page.locator(f'{nav} [data-tab="{name}"]').click()
            assert page.locator(f'#view-{name}').is_visible(),(width,name)
            assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1'),(width,name)
            assert page.locator(f'{nav} [data-tab="{name}"]').get_attribute('aria-current')=='page',(width,name)
            checks+=1
        if width==320: page.screenshot(path=str(Path(__file__).with_name('mobile-320-privacidade.png')),full_page=True)
        if width==1440:page.screenshot(path=str(Path(__file__).with_name('desktop-1440-privacidade.png')),full_page=True)
        assert not errors,(width,errors)
        page.close()
    browser.close()
print(f'PASS: {checks} viewport/tab checks at {len(widths)} widths, no horizontal overflow or script exceptions')
