from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
 s=b.new_page();s.goto('http://127.0.0.1:8020/#workspace');s.locator('.rx-table td').first.wait_for(timeout=90000)
 print(s.evaluate("() => Object.fromEntries(['body','.rx-table td','.kpi>span','.workspace-title h1','.copilot h2','.rx-button'].map(k=>{let c=getComputedStyle(document.querySelector(k));return[k,[c.fontFamily,c.fontSize,c.fontWeight]]}))"))
 b.close()
