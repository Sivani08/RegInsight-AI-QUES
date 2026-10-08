from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote
from playwright.sync_api import sync_playwright
import json

out=Path(__file__).resolve().parents[3]/'outputs'
class Links(HTMLParser):
    def __init__(self): super().__init__(); self.ids=set(); self.links=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if 'id' in d: self.ids.add(d['id'])
        if tag=='a' and 'href' in d: self.links.append(d['href'])
parsed={}
for path in out.glob('RegInsight-*.html'):
    parser=Links(); parser.feed(path.read_text(encoding='utf-8')); parsed[path.name]=parser
checked=0
for name in ('RegInsight-Requirement-Audit.html','RegInsight-Function-Connections.html'):
    for href in parsed[name].links:
        if '://' in href: continue
        target,_,fragment=href.partition('#'); target=target or name
        assert target in parsed,(name,href)
        if fragment: assert unquote(fragment) in parsed[target].ids,(name,href)
        checked+=1
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000}); errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto((out/'RegInsight-Function-Connections.html').as_uri())
    assert page.locator('section.file').count()==143
    page.locator('#search').fill('backend/services/observations.py')
    assert page.locator('section.file:visible').count()<143
    section=page.locator('section.file').filter(has=page.get_by_role('heading',name='backend/services/observations.py',exact=True))
    detail=section.locator('details').filter(has=page.locator('summary').filter(has_text='run_batch ·'))
    detail.locator('summary').click()
    detail.get_by_role('link',name='Open definition',exact=True).click()
    page.locator(page.url.split('#')[-1].join(['#',''])).wait_for(state='visible')
    page.goto((out/'RegInsight-Requirement-Audit.html').as_uri())
    assert page.get_by_role('heading',name='Verdict',exact=True).is_visible()
    page.screenshot(path=str(out/'RegInsight-Requirement-Audit-preview.png'),full_page=True)
    assert not errors,errors
    browser.close()
print(json.dumps({'local_links_verified':checked,'browser_search_and_source_navigation':'passed','console_errors':errors}))
