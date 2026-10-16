"""Deliberate RED tests for LAB-only CRM V1.1 prototype (offline Chromium)."""
from pathlib import Path
import unittest
from playwright.sync_api import sync_playwright

BASE=Path(__file__).parent
HTML=(BASE/'index.html').read_text(encoding='utf-8')

class AdversarialUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=sync_playwright().start()
        cls.browser=cls.p.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--disable-dev-shm-usage', '--no-sandbox'])
    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.p.stop()
    def setUp(self):
        self.page=self.browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,offline=True)
        self.page.set_content(HTML,wait_until='load')
    def tearDown(self):self.page.close()
    def tab(self,name):self.page.locator(f'.bottom-nav [data-tab="{name}"]').click()
    def test_01_qualification_revoked_after_changed_evidence(self):
        p=self.page
        for i in ['need','fit','interest','path']:p.locator('#check-'+i).check()
        p.locator('#triage-advance').click()
        self.assertIn('OPORTUNIDADE',p.locator('#triage-stage').inner_text())
        p.locator('#check-need').uncheck()
        self.assertNotIn('OPORTUNIDADE',p.locator('#triage-stage').inner_text(), 'stale qualification cannot survive withdrawn evidence')
    def test_02_qualified_metric_tracks_simulated_stage(self):
        p=self.page
        initial=p.locator('#metric-qualified').inner_text()
        for i in ['need','fit','interest','path']:p.locator('#check-'+i).check()
        p.locator('#triage-advance').click()
        self.assertNotEqual(initial,p.locator('#metric-qualified').inner_text())
        p.locator('#triage-reset').click()
        self.assertEqual(initial,p.locator('#metric-qualified').inner_text())
    def test_03_payment_third_decimal_not_silently_rounded(self):
        self.tab('oportunidades')
        p=self.page;p.locator('#amount-received').fill('0.005')
        self.assertIn('INVÁLIDO',p.locator('#payment-badge').inner_text())
    def test_04_payment_exponent_not_silently_accepted(self):
        self.tab('oportunidades')
        p=self.page;p.locator('#amount-received').fill('1e2')
        self.assertIn('INVÁLIDO',p.locator('#payment-badge').inner_text())
    def test_05_quantity_exponent_not_silently_accepted(self):
        self.tab('oportunidades')
        p=self.page;p.locator('#qty-observed').fill('1e1')
        self.assertIn('INVÁLIDO',p.locator('#stock-badge').inner_text())
    def test_06_missed_reverse_guarantee_phrase(self):
        self.tab('propostas');p=self.page
        p.locator('#proposal-text').fill('Lucro garantido em cada contrato.')
        p.locator('#proposal-review').click()
        self.assertIn('ALERTA',p.locator('#proposal-result').inner_text())
    def test_07_missed_sales_percentage_phrase(self):
        self.tab('propostas');p=self.page
        p.locator('#proposal-text').fill('Aumentaremos suas vendas em 50%.')
        p.locator('#proposal-review').click()
        self.assertIn('ALERTA',p.locator('#proposal-result').inner_text())
    def test_09_negative_disclaimer_does_not_trigger_false_alert(self):
        self.tab('propostas');p=self.page
        p.locator('#proposal-text').fill('Não garantimos aumento de vendas nem lucro.')
        p.locator('#proposal-review').click()
        self.assertNotIn('ALERTA',p.locator('#proposal-result').inner_text())
        self.assertIn('NÃO É APROVAÇÃO',p.locator('#proposal-result').inner_text())
    def test_10_invalid_quantity_fraction_rejected(self):
        self.tab('oportunidades');p=self.page
        p.locator('#qty-observed').fill('2.5')
        self.assertIn('INVÁLIDO',p.locator('#stock-badge').inner_text())
    def test_11_invalid_negative_value_rejected(self):
        self.tab('oportunidades');p=self.page
        p.locator('#amount-received').fill('-1')
        self.assertIn('INVÁLIDO',p.locator('#payment-badge').inner_text())
    def test_12_no_network_even_with_untrusted_proposal(self):
        self.tab('propostas');p=self.page
        requests=[]
        p.on('request',lambda request:requests.append(request.url))
        p.locator('#proposal-text').fill('<img src="https://test.invalid/steal"><script>alert(1)</script>')
        p.locator('#proposal-review').click()
        self.assertEqual(requests, [])
        self.assertIn('NÃO É APROVAÇÃO',p.locator('#proposal-result').inner_text())

    def test_08_mobile_navigation_exposes_active_page(self):
        p=self.page
        self.assertEqual(p.locator('.bottom-nav [data-tab="triagem"]').get_attribute('aria-current'),'page')
        self.tab('privacidade')
        self.assertEqual(p.locator('.bottom-nav [data-tab="privacidade"]').get_attribute('aria-current'),'page')
        self.assertNotEqual(p.locator('.bottom-nav [data-tab="triagem"]').get_attribute('aria-current'),'page')

if __name__=='__main__': unittest.main(verbosity=2)
