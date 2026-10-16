"""Offline UI smoke and contract assertions. Chromium/Playwright required; no production integrations."""
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE=Path(__file__).parent
HTML=(BASE/'index.html').read_text(encoding='utf-8')

def assert_clean(page):
    assert page.locator('.risk-banner').is_visible()
    assert 'HARD NO-GO' in page.locator('.risk-banner').inner_text()
    assert page.get_by_text('Recebimentos reais').is_visible()
    assert page.get_by_text('00',exact=True).count() >= 1


def desktop(browser):
    page=browser.new_page(viewport={'width':1440,'height':900},device_scale_factor=1,offline=True)
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(HTML,wait_until="load")
    assert_clean(page)
    assert page.locator('#view-triagem').is_visible()
    page.screenshot(path=str(BASE/'desktop-triagem.png'),full_page=True)
    page.locator('#triage-advance').click()
    assert 'Ainda não é oportunidade' in page.locator('#triage-result').inner_text()
    assert 'CONSULTA' == page.locator('#triage-stage').inner_text()
    for id in ['need','fit','interest','path']: page.locator('#check-'+id).check()
    page.locator('#triage-evaluate').click()
    assert 'Critérios do cenário preenchidos' in page.locator('#triage-result').inner_text()
    page.locator('#triage-advance').click()
    assert 'OPORTUNIDADE (SIMULADA)' in page.locator('#triage-stage').inner_text()
    page.locator('#triage-reset').click()
    assert 'CONSULTA' == page.locator('#triage-stage').inner_text()
    page.locator('.sidebar [data-tab="oportunidades"]').click()
    assert '2 / 4' in page.locator('#stock-ratio').inner_text()
    assert 'INSUFICIENTE' in page.locator('#stock-badge').inner_text()
    assert 'R$ 450,00' in page.locator('#payment-remaining').inner_text().replace('\xa0',' ')
    page.locator('#qty-observed').fill('4')
    assert 'SUFICIENTE NO EXEMPLO' in page.locator('#stock-badge').inner_text()
    assert 'Não há confirmação externa' in page.locator('#stock-text').inner_text()
    page.locator('#amount-received').fill('800')
    assert 'NÃO VERIFICADO' in page.locator('#payment-badge').inner_text()
    assert 'sem prova externa' in page.locator('#payment-text').inner_text()
    page.locator('#amount-received').fill('900')
    assert 'INCONSISTENTES' in page.locator('#payment-badge').inner_text()
    page.locator('#amount-received').fill('350')
    page.locator('#qty-observed').fill('2')
    page.screenshot(path=str(BASE/'desktop-oportunidades.png'),full_page=True)
    page.locator('.sidebar [data-tab="rotina"]').click()
    assert '03' in page.locator('#routine-remaining').inner_text()
    page.locator('[data-routine="0"]').check()
    assert '02' in page.locator('#routine-remaining').inner_text()
    page.locator('#routine-reset').click()
    assert '03' in page.locator('#routine-remaining').inner_text()
    page.locator('.sidebar [data-tab="propostas"]').click()
    assert page.locator('button[disabled]').count()==1
    page.locator('#proposal-text').fill('Garantimos dobrar suas vendas em 30 dias.')
    page.locator('#proposal-review').click()
    assert 'ALERTA' in page.locator('#proposal-result').inner_text()
    page.locator('#proposal-text').fill('Vamos organizar a rotina e medir pendências.')
    page.locator('#proposal-review').click()
    assert 'exige revisão humana' in page.locator('#proposal-result').inner_text()
    page.locator('.sidebar [data-tab="privacidade"]').click()
    for checkbox in page.locator('#privacy-items input').all(): checkbox.check()
    assert 'SEM HOMOLOGAÇÃO' in page.locator('#privacy-status-title').inner_text()
    page.locator('#privacy-incident').click()
    assert 'Nenhuma notificação foi enviada' in page.locator('#notice').inner_text()
    page.screenshot(path=str(BASE/'desktop-privacidade.png'),full_page=True)
    assert not errors,errors
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'), 'horizontal overflow desktop'
    page.close()
    return 19

def mobile(browser):
    page=browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1,is_mobile=True,has_touch=True,offline=True)
    errors=[]; out=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda request: out.append(request.url) if request.url.startswith(('http:','https:')) else None)
    page.set_content(HTML,wait_until="load")
    assert_clean(page)
    assert page.locator('.bottom-nav').is_visible()
    assert not page.locator('.sidebar').is_visible()
    page.screenshot(path=str(BASE/'mobile-triagem.png'),full_page=True)
    navs=['triagem','oportunidades','rotina','propostas','privacidade']
    for nav in navs:
        page.locator('.bottom-nav [data-tab="'+nav+'"]').click()
        assert page.locator('#view-'+nav).is_visible()
        for other in navs:
            if other!=nav: assert not page.locator('#view-'+other).is_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'), f'horizontal overflow {nav}'
    page.locator('.bottom-nav [data-tab="oportunidades"]').click()
    page.screenshot(path=str(BASE/'mobile-oportunidades.png'),full_page=True)
    page.locator('.bottom-nav [data-tab="propostas"]').click()
    page.screenshot(path=str(BASE/'mobile-propostas.png'),full_page=True)
    assert not errors, errors
    assert not out, f'Unexpected network requests: {out}'
    page.close()
    return 15

if __name__=='__main__':
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--disable-dev-shm-usage','--no-sandbox'])
        print('DESKTOP:',desktop(browser),'checks PASS')
        print('MOBILE:',mobile(browser),'checks PASS')
        browser.close()
        print('TOTAL: 34 functional/assertion groups passed in offline browser smoke.')
