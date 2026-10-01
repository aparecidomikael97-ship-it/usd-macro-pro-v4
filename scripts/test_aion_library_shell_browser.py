"""Playwright desktop/mobile smoke of the exact sandbox shell renderer.

This exercises a minimal synthetic Streamlit host, NOT the entire AtlasQuant
admin app and NOT actual customer login or data. Never touches production.
"""
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PORT=8593


def serve(scenario):
    env=dict(os.environ,AION_LIBRARY_BROWSER_FIXTURE='CI_SYNTHETIC_ONLY',
             AION_LIBRARY_TEST_SCENARIO=scenario,STREAMLIT_BROWSER_GATHER_USAGE_STATS='false',
             PYTHONPATH=str(ROOT))
    command=[sys.executable,'-m','streamlit','run',
             str(ROOT/'scripts/aion_library_shell_browser_fixture.py'),
             '--server.headless','true','--server.address','127.0.0.1',
             '--server.port',str(PORT),'--browser.gatherUsageStats','false']
    proc=subprocess.Popen(command,cwd=ROOT,env=env,stdout=subprocess.DEVNULL,
                          stderr=subprocess.STDOUT)
    try:
        for _ in range(90):
            if proc.poll() is not None:raise RuntimeError('synthetic Streamlit fixture exited early')
            try:
                with urlopen(f'http://127.0.0.1:{PORT}/_stcore/health',timeout=1) as r:
                    if r.status==200:break
            except Exception:time.sleep(.5)
        else:raise RuntimeError('synthetic Streamlit fixture failed health check')
        return proc
    except Exception:
        proc.kill();proc.wait(timeout=6)
        raise


def browser_case(browser,scenario,width,height,mobile):
    context=browser.new_context(viewport={'width':width,'height':height},
                                is_mobile=mobile,device_scale_factor=1,locale='pt-BR')
    page=context.new_page()
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    try:
        response=page.goto(f'http://127.0.0.1:{PORT}',wait_until='domcontentloaded',timeout=35_000)
        assert response and response.status==200, (scenario,width,'HTTP response')
        page.get_by_text('Ensaio visual isolado',exact=False).wait_for(timeout=30_000)
        visible=scenario=='allowed'
        # Streamlit streams deltas: the caption and title can appear before
        # metrics and warnings. Wait for the last semantic element instead of
        # asserting against a partially rendered page.
        if visible:
            page.locator('[data-testid="stMetric"]').first.wait_for(timeout=30_000)
            page.get_by_text('Nenhum PDF pode ser enviado',exact=False).wait_for(timeout=30_000)
        else:
            page.get_by_text('Biblioteca indisponível neste cenário de acesso.',exact=False).wait_for(timeout=30_000)
        body=page.locator('[data-testid="stMain"]').inner_text(timeout=20_000)
        assert ('📚 Biblioteca AION' in body)==visible,(scenario,width,'visibility')
        if visible:
            assert 'Ingestão e indexação' in body,(scenario,width,'status')
            assert 'Nenhum PDF pode ser enviado' in body,(scenario,width,'safe warning')
            metrics=page.locator('[data-testid="stMetric"]')
            assert metrics.count()==2,(scenario,width,'two metrics')
            assert page.locator('[data-testid="stFileUploader"]').count()==0
            assert page.locator('[data-testid="stButton"]').count()==0
            # Measure actual metrics; stacked mobile columns may narrow but must
            # remain within the viewport without page-wide horizontal scrolling.
            for rect in metrics.evaluate_all('nodes=>nodes.map(n=>n.getBoundingClientRect().toJSON())'):
                assert rect['left']>=-8 and rect['right']<=width+8,(scenario,width,'metric clipped',rect)
        else:
            assert 'Biblioteca indisponível' in body,(scenario,width,'closed gate')
            assert page.locator('[data-testid="stMetric"]').count()==0
        viewport_w=page.evaluate('window.innerWidth')
        document_w=page.evaluate('document.documentElement.scrollWidth')
        assert document_w<=viewport_w+8,(scenario,width,'horizontal overflow',document_w,viewport_w)
        assert not errors,(scenario,width,'JavaScript errors',errors)
        print(f'PASS scenario={scenario} viewport={width}x{height} metrics={2 if visible else 0} overflow={document_w-viewport_w}',flush=True)
    finally:
        context.close()


def main():
    if os.environ.get('CI','').lower()!='true':
        raise RuntimeError('browser smoke limited to CI')
    scenarios=(
      ('allowed',((360,800,True),(390,844,True),(412,915,True),(1440,900,False))),
      ('disabled',((390,844,True),)),
      ('expired',((390,844,True),)),
      ('user',((390,844,True),)),
      ('production',((390,844,True),)),
    )
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            for scenario,sizes in scenarios:
                proc=serve(scenario)
                try:
                    for w,h,m in sizes:
                        browser_case(browser,scenario,w,h,m)
                finally:
                    proc.terminate()
                    try:proc.wait(timeout=8)
                    except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=8)
                    time.sleep(.6)
        finally:browser.close()

if __name__=='__main__':main()
