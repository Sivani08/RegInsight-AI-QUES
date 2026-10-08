from pathlib import Path
from playwright.sync_api import sync_playwright
import json
ROOT=Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True,args=['--enable-unsafe-swiftshader'])
    errors=[];results=[]
    page=browser.new_page(viewport={'width':1440,'height':1000})
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8021/#workspace',wait_until='domcontentloaded')
    page.get_by_role('button',name='AI chatbot',exact=True).wait_for(timeout=60000)
    page.get_by_text('Local model ready',exact=True).wait_for(timeout=15000)
    page.get_by_role('button',name='What does OAI mean?',exact=True).click()
    page.locator('.chat-sources').first.wait_for(timeout=15000)
    page.get_by_text('LOCAL MODEL · SOURCE-LINKED',exact=True).wait_for(timeout=60000)
    assert 'Official Action Indicated' in page.locator('.chat-answer-text').inner_text()
    font=page.locator('.chat-answer-text p').first.evaluate('(e)=>({size:getComputedStyle(e).fontSize,weight:getComputedStyle(e).fontWeight,line:getComputedStyle(e).lineHeight})')
    assert float(font['size'].replace('px',''))>=17 and int(font['weight'])>=650,font
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(ROOT/'docs/screenshots/chatbot-desktop.png'),full_page=True)
    results.append({'desktop':'passed','font':font,'timing':page.locator('.chat-timing').inner_text(),'answer':page.locator('.chat-answer-text').inner_text()})
    page.get_by_role('button',name='Graph analytics',exact=True).click()
    page.get_by_role('heading',name='Analytics copilot').wait_for()
    page.get_by_role('button',name='AI chatbot',exact=True).click()
    page.get_by_role('button',name='How does RegInsight detect recurring risks?',exact=True).click()
    page.locator('.chat-sources').wait_for(timeout=15000)
    page.get_by_role('button',name='Stop answer').click()
    page.get_by_text('Stopped. Retrieved evidence remains available.',exact=True).wait_for(timeout=10000)
    results.append({'switching_and_cancellation':'passed'})
    page.close()
    page=browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8021/#workspace',wait_until='domcontentloaded')
    page.get_by_role('button',name='Ask copilot',exact=True).click()
    page.get_by_role('button',name='AI chatbot',exact=True).click()
    page.get_by_role('button',name='What does OAI mean?',exact=True).click()
    page.get_by_text('LOCAL MODEL · SOURCE-LINKED',exact=True).wait_for(timeout=60000)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(ROOT/'docs/screenshots/chatbot-mobile.png'),full_page=True)
    results.append({'mobile':'passed','timing':page.locator('.chat-timing').inner_text()})
    assert not errors,errors
    browser.close()
    (ROOT/'docs/chatbot-browser-check.json').write_text(json.dumps({'results':results,'errors':errors},indent=2),encoding='utf-8')
    print(json.dumps(results))
