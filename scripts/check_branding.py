from pathlib import Path
from playwright.sync_api import sync_playwright
import json

root=Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True,args=['--enable-unsafe-swiftshader'])
    errors=[]
    for width in (1440,390):
        page=browser.new_page(viewport={'width':width,'height':960})
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto('http://127.0.0.1:8021/',wait_until='networkidle')
        logo=page.locator('.rx-nav .primary-logo')
        assert logo.evaluate('(e)=>e.complete&&e.naturalWidth>0')
        credit=page.get_by_role('link',name='1nb-nt')
        assert credit.get_attribute('href')=='https://github.com/1nb-nt'
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(root/f'docs/screenshots/branding-{width}.png'),full_page=True)
        page.get_by_role('button',name='Explore your workspace').click()
        page.locator('.app-header .primary-logo').wait_for()
        assert page.get_by_role('link',name='1nb-nt').count()==1
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.close()
    browser.close()
    assert not errors,errors
    print(json.dumps({'desktop_mobile_branding':'passed','console_errors':errors}))
