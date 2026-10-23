"""Browser QA of the new pending Dataset; no provider/review/publication calls."""
import json
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
import vio_content_sync_20261022 as s

def main():
    n=s.night;values=n.u.env(n.u.inspect(n.d.ADMIN))
    dataset=json.loads((s.OUT/'new-dataset.json').read_text())['dataset_id']
    executable=next((Path.home()/'AppData/Local/ms-playwright/chromium-1228').rglob('chrome.exe'))
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=str(executable),headless=True)
        context=browser.new_context(viewport={'width':1440,'height':1000})
        rejected=[];errors=[]
        def guard(route):
            r=route.request;u=urlsplit(r.url)
            allowed=u.hostname=='localhost' and u.port==8191 and (r.method in ('GET','HEAD') or u.path in ('/api/auth/login','/api/auth/logout','/api/marketing/preview'))
            if allowed:route.continue_()
            else:rejected.append({'path':u.path,'method':r.method});route.abort()
        context.route('**/*',guard)
        login=context.request.post(s.BASE+'/api/auth/login',headers={'Origin':s.BASE,'X-KDH-Request':'1'},data={'email':values['INITIAL_ADMIN_EMAIL'],'password':values['INITIAL_ADMIN_PASSWORD']})
        assert login.status==200
        csrf=login.json()['csrf']
        try:
            page=context.new_page();page.on('pageerror',lambda e:errors.append(type(e).__name__))
            page.goto(s.BASE+'/marketing')
            page.locator('#snapshot-id option[value="'+dataset+'"]').wait_for(state='attached')
            page.locator('#snapshot-id').select_option(dataset)
            page.locator('#resume-form button[type=submit], #resume-form button:not([type])').click()
            page.locator('#dataset-state').get_by_text('Dataset '+dataset,exact=True).wait_for()
            review=context.request.get(s.BASE+'/api/marketing/datasets/'+dataset+'/review')
            assert review.status==200
            state=review.json();assert state.get('latest_review') is None
            s.save('pending-review-check',state)
            page.locator('#source').select_option('facebook_content')
            page.locator('#asset').select_option(s.ASSET)
            page.locator('#start').fill('2026-09-21');page.locator('#end').fill('2026-10-18')
            with page.expect_response(lambda r:urlsplit(r.url).path=='/api/marketing/preview') as response:
                page.locator('#content-plan-preview').click()
            assert response.value.status==200
            content=response.value.json()['content_report'];assert content['insights']['requests_used']==36
            assert len(content['insights']['measurements'])==34
            for width in (1440,390):
                page.set_viewport_size({'width':width,'height':1000})
                # Open native details without mutating data or bypassing CSP.
                for detail in page.locator('#content-report-preview > details').all():
                    if detail.get_attribute('open') is None:detail.locator('summary').first.click()
                page.wait_for_timeout(200)
                page.locator('#content-report-preview').screenshot(path=str(s.OUT/f'new-admin-preview-{width}.png'))
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2')
            assert not errors and not rejected
            result={'dataset_id':dataset,'preview_sections':7,'insights_measurements':34,'viewports':[1440,390],
                    'javascript_errors':errors,'blocked_requests':rejected,'review_submitted':False,'provider_calls':False}
            s.save('new-preview-browser',result);print(json.dumps(result))
        finally:
            context.request.post(s.BASE+'/api/auth/logout',headers={'Origin':s.BASE,'X-KDH-Request':'1','X-CSRF-Token':csrf},data={})
            browser.close()

if __name__=='__main__':
    try:main()
    except Exception as exc:
        import traceback
        result={'type':type(exc).__name__,'frames':[{'file':Path(f.filename).name,'line':f.lineno} for f in traceback.extract_tb(exc.__traceback__)]}
        s.save('preview-browser-interruption',result)
        raise SystemExit(json.dumps(result))
