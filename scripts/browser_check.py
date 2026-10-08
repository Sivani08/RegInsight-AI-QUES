from pathlib import Path
from playwright.sync_api import sync_playwright
import json
ROOT=Path(__file__).resolve().parents[1]
shots=ROOT/'docs/screenshots';shots.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True,args=['--enable-unsafe-swiftshader'])
    page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8020',wait_until='networkidle')
    page.screenshot(path=str(shots/'landing-desktop.png'),full_page=True)
    assert page.locator('canvas').count()==1
    first=page.locator('canvas').screenshot()
    page.evaluate('() => new Promise(resolve => {let n=0; function step(){if(++n===30)resolve();else requestAnimationFrame(step)} requestAnimationFrame(step)})')
    assert first!=page.locator('canvas').screenshot(), 'Animation must start without interaction'
    page.get_by_role('button',name='Pause animation').click()
    assert page.get_by_role('button',name='Play animation').count()==1
    page.get_by_role('button',name='Explore your workspace').click()
    page.get_by_text('Sites to investigate',exact=True).first.wait_for(timeout=180000)
    page.locator('.graph-insight').first.wait_for()
    assert page.locator('.graph-insight').count()==4
    assert page.locator('.graph-insight').filter(has_text='Citation rate is unavailable').count()==1
    assert float(page.locator('.kpi>span').first.evaluate('e=>parseFloat(getComputedStyle(e).fontSize)'))>=14
    assert 'Segoe UI' in page.locator('body').evaluate('e=>getComputedStyle(e).fontFamily')
    page.screenshot(path=str(shots/'workspace-desktop.png'),full_page=True)
    page.get_by_role('button',name='Which sites have the highest risk?',exact=True).click()
    page.get_by_text('Sites ranked by the existing deterministic risk score.',exact=True).wait_for(timeout=180000)
    page.get_by_role('button',name='Why is the first one high?',exact=True).click()
    page.get_by_text('The selected scope has a',exact=False).wait_for(timeout=60000)
    page.screenshot(path=str(shots/'copilot-desktop.png'),full_page=False)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    mobile=browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1,reduced_motion='reduce',is_mobile=True,has_touch=True)
    mobile.goto('http://127.0.0.1:8020',wait_until='networkidle')
    mobile.screenshot(path=str(shots/'landing-mobile.png'),full_page=True)
    assert mobile.get_by_role('button',name='Pause animation').count()==1
    assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth')
    mobile.get_by_role('button',name='Explore your workspace').click()
    mobile.get_by_text('Sites to investigate',exact=True).first.wait_for(timeout=180000)
    mobile.screenshot(path=str(shots/'workspace-mobile.png'),full_page=True)
    assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth')
    print(json.dumps({'browser_errors':errors,'screenshots':str(shots),'desktop_and_mobile_overflow':False}),flush=True)
    assert not errors
    browser.close()
