"""Compare a running reference and cleaned application without changing UI source.

Requires the optional requirements-tools.txt dependencies and installed Chrome.
Snapshots mask the animated canvas; byte-identical builds cover its implementation.
"""
import argparse,json
from pathlib import Path
from PIL import Image,ImageChops
from playwright.sync_api import sync_playwright

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before',required=True)
    parser.add_argument('--after',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    results=[];errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
        for width,height in [(1440,1000),(390,844)]:
            for label,url in [('before',args.before),('after',args.after)]:
                page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1,reduced_motion='reduce')
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(url,wait_until='networkidle');page.locator('canvas').wait_for()
                page.evaluate('document.fonts.ready')
                def shot(name):
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(label,width,name,'overflow')
                    page.screenshot(path=str(args.output/f'{label}-{width}-{name}.png'),full_page=True,animations='disabled',mask=[page.locator('canvas')])
                shot('landing')
                page.get_by_role('button',name='Explore your workspace',exact=True).click()
                page.locator('.graph-insight').first.wait_for(timeout=120000)
                page.get_by_text('Local model ready',exact=True).wait_for(timeout=15000)
                assert page.locator('.graph-insight').count()==4
                shot('portfolio')
                page.get_by_role('button',name='Evidence workspace',exact=True).click()
                page.locator('.ri-record-link').first.wait_for(timeout=120000)
                shot('evidence')
                page.locator('.ri-record-link').first.click()
                assert page.locator('.ri-site').get_by_text('Source',exact=True).count()>0
                page.get_by_role('button',name='Documentation',exact=True).first.click()
                page.get_by_role('dialog').wait_for()
                page.keyboard.press('Escape')
                page.close()
            for name in ['landing','portfolio','evidence']:
                before=Image.open(args.output/f'before-{width}-{name}.png').convert('RGB')
                after=Image.open(args.output/f'after-{width}-{name}.png').convert('RGB')
                identical=before.size==after.size and ImageChops.difference(before,after).getbbox() is None
                results.append({'viewport':width,'view':name,'pixel_identical':identical,'before_size':before.size,'after_size':after.size})
        browser.close()
    report={'comparisons':results,'browser_errors':errors,'canvas':'masked animated rendering; implementation checked by build hashes'}
    (args.output/'ui-regression.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)
    assert not errors and all(r['pixel_identical'] for r in results),report

if __name__=='__main__':main()
