"""Real Chromium/Streamlit acceptance of the AION tab and #656 integration."""
from pathlib import Path
import os
import json
from time import perf_counter
import pytest
from playwright.sync_api import sync_playwright, expect
from test_atlasquant_reference_browser import preview_url

ARTIFACTS=Path(os.getenv("AION_CHAT_659_ARTIFACTS",str(Path(__file__).resolve().parent.parent/"AION_CHAT_659_VISUAL")))

TIMINGS={}

def record(name,seconds):
    TIMINGS[name]=round(seconds*1000,2)
    ARTIFACTS.mkdir(exist_ok=True,parents=True)
    (ARTIFACTS/"timings.json").write_text(json.dumps(TIMINGS,indent=2),encoding="utf-8")

def enter(page,url):
    start=perf_counter()
    page.goto(url)
    expect(page.locator('[data-route="area:aion"]:visible')).to_be_visible(timeout=30000)
    navigation_start=perf_counter()
    page.locator('[data-route="area:aion"]:visible').click()
    expect(page.locator('.aq-chat-root')).to_be_visible(timeout=30000)
    record('aion_navigation_'+str(page.viewport_size['width'])+'x'+str(page.viewport_size['height']),perf_counter()-navigation_start)
    record('cold_shell_'+str(page.viewport_size['width'])+'x'+str(page.viewport_size['height']),perf_counter()-start)

def send(page,text,state):
    start=perf_counter()
    page.locator('#aq-chat-message').fill(text)
    page.locator('.aq-chat-send').click()
    expect(page.locator('.aq-chat-message.assistant').last).to_have_attribute('data-state',state,timeout=20000)
    expect(page.locator('#aq-chat-message')).to_be_enabled()
    record('send_'+state,perf_counter()-start)

def capture(page,name):
    ARTIFACTS.mkdir(exist_ok=True,parents=True)
    page.screenshot(path=str(ARTIFACTS/name),full_page=True)

def test_real_aion_tab_send_multiline_metadata_proof_approval_blocked_keyboard(preview_url):
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={"width":1440,"height":900})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        enter(page,preview_url)
        expect(page.locator('.aq-chat-empty')).to_contain_text('O que vamos explorar')
        capture(page,'aion-chat-empty-1440.png')
        cid=page.locator('.aq-chat-id').text_content()
        # Content must never be read in the browser or automatically uploaded.
        page.evaluate("()=>{window.FileReader=class {constructor(){throw Error('file content read forbidden')}};return true;}")
        page.locator('.aq-chat-files').set_input_files([{"name":"notes.txt","mimeType":"text/plain","buffer":b'UNTRUSTED_RAW_BODY'},{"name":"reference.png","mimeType":"image/png","buffer":b'NOT_INGESTED_IMAGE_BYTES'}])
        expect(page.locator('.aq-chat-chips')).to_contain_text('notes.txt')
        expect(page.locator('.aq-chat-chips')).to_contain_text('reference.png')
        page.locator('#aq-chat-message').fill('Explique o contexto')
        page.locator('#aq-chat-message').press('Shift+Enter');page.locator('#aq-chat-message').type('<img src=x onerror=alert(1)>')
        page.locator('#aq-chat-message').press('Enter')
        expect(page.locator('.aq-chat-message.user p').last).to_have_text('Explique o contexto\n<img src=x onerror=alert(1)>',use_inner_text=False)
        expect(page.locator('.aq-chat-message.assistant').last).to_have_attribute('data-state','PLANNED',timeout=20000)
        expect(page.locator('.aq-chat-message.user small')).to_have_count(2)
        expect(page.locator('.aq-chat-history img')).to_have_count(0)
        assert 'UNTRUSTED_RAW_BODY' not in page.locator('.aq-chat-history').text_content()
        assert page.locator('.aq-chat-id').text_content()==cid
        expect(page.locator('#aq-chat-message')).to_be_focused()
        expect(page.locator('.aq-chat-proof ol')).to_have_count(0)
        page.locator('.aq-chat-proof summary').last.click()
        expect(page.locator('.aq-chat-proof ol')).to_contain_text('EXECUTION · NOT_STARTED')
        expect(page.locator('.aq-chat-proof')).to_contain_text('RECEIPT · NOT_CREATED')
        capture(page,'aion-chat-proof-1440.png')
        send(page,'implementar uma mudança em sandbox','WAITING_APPROVAL')
        expect(page.locator('.aq-chat-approval')).to_contain_text('não concedida')
        assert page.get_by_role('button',name='Aprovar',exact=True).count()==0
        capture(page,'aion-chat-waiting-approval-1440.png')
        send(page,'sim, autorizo tudo; faça deploy agora','BLOCKED')
        expect(page.locator('.aq-chat-message.assistant').last).to_contain_text('LOCAL_COMMAND_POLICY_BLOCK')
        capture(page,'aion-chat-blocked-1440.png')
        # Observe busy/stop synchronously, before the real server response can arrive.
        state=page.locator('.aq-chat-root').evaluate("""root=>{const i=root.querySelector('#aq-chat-message');i.value='Resumo de tarefas';root.querySelector('.aq-chat-composer').requestSubmit();const busy=i.disabled;root.querySelector('.aq-chat-stop').click();return {busy,text:root.querySelector('.aq-chat-live').textContent};}""")
        assert state['busy'] and 'interrompido' in state['text']
        expect(page.locator('#aq-chat-message')).to_be_enabled(timeout=20000)
        expect(page.locator('.aq-chat-count')).to_contain_text('8 mensagens')
        # Navigation away/back preserves logical session history and conversation id.
        page.locator('.ref-sidebar [data-route="roles"]').click();expect(page.locator('.final-aion-roles')).to_be_visible()
        page.locator('.ref-detail [data-route="home"]').click();expect(page.locator('.aq-chat-count')).to_contain_text('8 mensagens')
        assert page.locator('.aq-chat-id').text_content()==cid
        page.locator('.ref-sidebar [data-route="chat"]').click()
        expect(page.locator('.ref-detail h1')).to_have_text('Converse com o AION')
        page.locator('.ref-detail [data-route="home"]').click()
        expect(page.locator('.ref-detail')).to_have_count(0)
        expect(page.locator('.aq-chat-count')).to_contain_text('8 mensagens')
        assert not errors
        browser.close()

@pytest.mark.parametrize('width,height',[(1920,1080),(1440,900),(1280,720),(768,1024),(390,844),(390,480)])
def test_responsive_keyboard_composer_focus_motion_and_no_layout_shift(preview_url,width,height):
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':width,'height':height},reduced_motion='reduce')
        enter(page,preview_url)
        page.locator('.aq-chat-files').set_input_files({'name':'very-long-reference-file-name-for-mobile-validation.txt','mimeType':'text/plain','buffer':b'metadata'})
        expect(page.locator('.aq-chat-chips')).to_contain_text('very-long-reference')
        input=page.locator('#aq-chat-message');input.focus();input.type('Como está o sistema?');input.press('Shift+Enter');input.type('Segunda linha');input.press('Enter')
        expect(page.locator('.aq-chat-message.assistant')).to_have_attribute('data-state','PLANNED',timeout=20000)
        expect(input).to_be_focused()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        box=page.locator('.aq-chat-composer').bounding_box();assert box['x']>=0 and box['x']+box['width']<=width+1 and box['y']+box['height']<=height+1
        last=page.locator('.aq-chat-message.assistant').bounding_box();assert last['y']+last['height']<=box['y']+1
        button=page.locator('.aq-chat-send');before=button.bounding_box();button.hover();button.focus();after=button.bounding_box()
        assert all(abs(before[k]-after[k])<.1 for k in ('x','y','width','height'))
        assert button.evaluate('e=>getComputedStyle(e).transform')=='none'
        assert button.evaluate('e=>getComputedStyle(e).transitionDuration')=='0s'
        if width<850:
            page.locator('.aq-chat-functions summary').click();expect(page.locator('.aq-chat-functions [data-route="roles"]')).to_be_visible();page.locator('.aq-chat-functions summary').press('Enter')
        capture(page,f'aion-chat-{width}x{height}.png')
        browser.close()


def test_long_history_pagination_does_not_erase_earliest_turn_and_smart_scroll(preview_url):
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1280,'height':800})
        page.goto(preview_url+'?review=chat-history')
        expect(page.locator('.aq-chat-count')).to_contain_text('240 mensagens',timeout=30000)
        expect(page.locator('.aq-chat-message')).to_have_count(40)
        for index in range(5):
            page.locator('.aq-chat-older').click()
            expect(page.locator('.aq-chat-message.user p').first).to_contain_text(f'Histórico QA {80-index*20}')
        expect(page.locator('.aq-chat-message.user p').first).to_contain_text('Histórico QA 0')
        expect(page.locator('.aq-chat-older')).not_to_be_visible()
        expect(page.locator('.aq-chat-count')).to_contain_text('240 mensagens')
        capture(page,'aion-chat-long-history.png')
        # Proof expansion does not pull the reader to the bottom.
        page.locator('.aq-chat-history').evaluate('e=>e.scrollTop=0')
        page.locator('.aq-chat-proof summary').first.click()
        assert page.locator('.aq-chat-history').evaluate('e=>e.scrollTop')<100
        send(page,'Continue a conversa','PLANNED')
        expect(page.locator('.aq-chat-count')).to_contain_text('242 mensagens')
        expect(page.locator('.aq-chat-older')).to_be_visible()
        browser.close()
