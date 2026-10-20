"""Real sandbox browser handoff. No traces, cookies, passwords or raw responses saved."""
import json
import secrets
import base64
import hashlib
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.dont_write_bytecode=True
from operations import ROOT, HERE, ADMIN, read, save, inspect, env, private_dir, dpapi, integrity, protected_services
from playwright.sync_api import sync_playwright

REPORT='rpt_4909119771c69125897d8bca84444abe'
OTHER='rpt_9f8e96cd09ef21bcace6d18aa7a31970'
ADMIN_URL='http://localhost:8191'


def main():
    deployed=read('deployment');assert deployed['status']=='PASS'
    baseline=read('preflight');new_url=deployed['new_url']
    target=new_url+'/reports/'+REPORT+'?revision=1'
    new_origin=urlsplit(new_url)
    values=env(inspect(ADMIN))
    token=dpapi((private_dir()/'service-token.dpapi').read_bytes(),decrypt=True).decode()
    assert values['REPORT_SERVICE_TOKEN']==token
    from werkzeug.security import check_password_hash
    from runtime_common import rows
    user=rows("SELECT id,email,password FROM users WHERE id='bbd01124919791b9e6bbde683e2f433c' AND active=1")[0]
    assert user['email']==values['INITIAL_ADMIN_EMAIL']
    assert check_password_hash(user['password'],values['INITIAL_ADMIN_PASSWORD'])
    screenshots=HERE/'screenshots';screenshots.mkdir(exist_ok=True)
    results={'target':target,'report_id':REPORT,'revision':1,'provider_calls':0,'screenshots':[],'negative':{},'widths':[]}
    executable=next((Path.home()/'AppData/Local/ms-playwright/chromium-1228').rglob('chrome.exe'))
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=str(executable),headless=True)
        context=browser.new_context(viewport={'width':1440,'height':1000})
        blocked=[];page_errors=[]
        def guard(route):
            request=route.request;u=urlsplit(request.url)
            allowed=u.hostname in ('localhost','127.0.0.1') and u.port in (8191,new_origin.port)
            if request.method not in ('GET','HEAD') and u.path not in ('/api/auth/login','/api/auth/logout','/auth/handoff/callback','/logout'):
                allowed=False
            if not allowed:
                blocked.append({'host':u.hostname,'path':u.path,'method':request.method});route.abort()
            else:route.continue_()
        context.route('**/*',guard)
        page=context.new_page();page.on('pageerror',lambda e:page_errors.append(type(e).__name__))
        csrf=None
        try:
            assert page.goto(ADMIN_URL+'/health').status==200
            page.goto(ADMIN_URL)
            page.locator('#auth-form [name=email]').fill(user['email'])
            page.locator('#auth-form [name=password]').fill(values['INITIAL_ADMIN_PASSWORD'])
            with page.expect_response(lambda r:urlsplit(r.url).path=='/api/auth/login') as login:
                page.locator('#auth-form button[type=submit]').click()
            login_response=login.value;assert login_response.status==200
            csrf=login_response.json()['csrf']
            page.goto(ADMIN_URL+'/marketing')
            option=REPORT+':1'
            page.locator('#existing-report option[value="'+option+'"]').wait_for(state='attached')
            page.locator('#existing-report').select_option(option)
            link=page.locator('#selected-report-open');assert link.is_visible()
            href=link.get_attribute('href');assert href.startswith(new_url+'/auth/handoff/start?') and REPORT in href and 'revision=1' in href
            page.screenshot(path=str(screenshots/'admin-report-selection.png'),full_page=False)
            with page.expect_response(lambda r:urlsplit(r.url).path=='/auth/handoff/callback' and r.request.method=='POST') as callback:
                link.click()
            assert callback.value.status==200
            page.wait_for_url(target)
            page.locator('[data-snapshot-kpi="facebook_content.posts_published"]').wait_for()
            payload=json.loads(page.locator('#snapshot-data').inner_text())
            assert payload['report_id']==REPORT and payload['revision']==1
            d=payload['dashboard'];metrics={m['key'].split('.')[-1]:m for m in d['all_metrics']}
            assert [metrics[k]['value'] for k in ('posts_published','reactions_lifetime','comments_lifetime')]==[15,80,10]
            assert metrics['engagements']['value'] is None and metrics['engagements']['status']=='no_data'
            assert metrics['shares_lifetime']['value'] is None and metrics['shares_lifetime']['status']=='partial'
            assert metrics['posts_published']['coverage']=={'available':28,'expected':28,'unit':'days'}
            assert metrics['reactions_lifetime']['coverage']=={'available':15,'expected':15,'unit':'posts'}
            assert metrics['comments_lifetime']['coverage']=={'available':15,'expected':15,'unit':'posts'}
            assert metrics['engagements']['coverage']=={'available':0,'expected':28,'unit':'days'}
            assert metrics['shares_lifetime']['coverage']=={'available':7,'expected':15,'unit':'posts'}
            assert d['preview'] is False
            assert 'Tạm thời' in page.locator('body').inner_text()
            assert d['timezone']=='UTC' and d['source_identity']['external_id']=='2188688654687066'
            assert d['source_identity']['client_id']=='client_meta_sandbox'
            assert payload['period']=={'start':'2026-09-21','end':'2026-10-18'}
            assert 'Dữ liệu mẫu KinderHealth' not in page.locator('body').inner_text()
            assert '7/15 bài' in page.locator('body').inner_text()
            html=page.content()
            assert token not in html and values['INITIAL_ADMIN_PASSWORD'] not in html
            cookies=context.cookies()
            viewer=next(c['value'] for c in cookies if c['name']=='kdh_vio_viewer_session')
            assert all(c['name'] not in ('kdh_viewer_session','kdh_viewer_csrf','kdh_handoff') for c in cookies)
            assert viewer not in html
            results.update(handoff='PASS',viewer_cookie_namespace='PASS',kpis='PASS',coverage='PASS',
                           timezone='UTC',status='provisional')
            for width in (1440,1024,768,390,360):
                page.set_viewport_size({'width':width,'height':1000});page.evaluate('document.fonts.ready')
                measurement=page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})')
                results['widths'].append(measurement)
                assert measurement['scroll']<=width+1,'responsive overflow'
                name='vio-content-'+str(width)+'.png';page.screenshot(path=str(screenshots/name),full_page=True)
                results['screenshots'].append('screenshots/'+name)
            # Protected read endpoints: never grant access or alter published rows.
            headers={'Authorization':'Bearer '+token,'X-KDH-Viewer-Session':viewer}
            for name,path in [('no_grant','/api/internal/v1/viewer/report-bundles/'+OTHER+'?revision=1'),
                              ('wrong_revision','/api/internal/v1/viewer/report-bundles/'+REPORT+'?revision=2'),
                              ('wrong_report','/api/internal/v1/viewer/report-bundles/rpt_'+'f'*32+'?revision=1')]:
                r=context.request.get(ADMIN_URL+path,headers=headers);assert r.status==404
                results['negative'][name]=r.status
            r=context.request.get(ADMIN_URL+'/api/internal/v1/viewer/report-bundles/'+REPORT+'?revision=1',
                                   headers={**headers,'X-KDH-Viewer-Session':secrets.token_urlsafe(48)})
            assert r.status==401;results['negative']['invalid_or_expired_session']=401
            verifier=secrets.token_urlsafe(48)
            body={'mode':'published','target_id':REPORT,'revision':1,'state':secrets.token_urlsafe(32),
                  'challenge':base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='),
                  'audience':new_url,'callback':new_url+'/auth/handoff/callback','client_id':'client_kinderhealth'}
            r=context.request.post(ADMIN_URL+'/api/internal/v1/handoffs',headers={'Authorization':'Bearer '+token},data=body)
            assert r.status==400;results['negative']['wrong_client']=400
            for path in ('/demo-bundle','/overview','/report/facebook-content','/api/v1/reports/facebook-content'):
                r=context.request.get(new_url+path,max_redirects=0);assert r.status==404
            results['demo_routes']='DENIED'
            # Revoke ONLY our own delegated Viewer session via supported logout.
            new_csrf=next(c['value'] for c in context.cookies() if c['name']=='kdh_vio_viewer_csrf')
            r=context.request.post(new_url+'/logout',headers={'Origin':new_url},form={'csrf':new_csrf},max_redirects=0)
            assert r.status==303
            r=context.request.get(ADMIN_URL+'/api/internal/v1/viewer/report-bundles/'+REPORT+'?revision=1',headers=headers)
            assert r.status==401;results['negative']['logout_revocation']=401
            r=context.request.get(target,max_redirects=0)
            assert r.status==303 and r.headers['location'].startswith('/auth/handoff/start?')
            results['expired_session_resume']='PASS'
            assert not page_errors and not blocked
            results['browser_errors']=0;results['unexpected_requests']=0
        finally:
            if csrf:
                context.request.post(ADMIN_URL+'/api/auth/logout',headers={'Origin':ADMIN_URL,'X-KDH-Request':'1','X-CSRF-Token':csrf},data={})
            context.close();browser.close()
    after=integrity()
    allowed={'viewer_handoffs','delegated_viewer_sessions'}
    differences=[k for k in baseline['data'] if k not in allowed and baseline['data'][k]!=after[k]]
    assert not differences,'business data changed'
    protected_services(baseline)
    results['business_data']='UNCHANGED';results['result']='PASS';save('browser-e2e',results)
    print(json.dumps(results))


if __name__=='__main__':
    try:main()
    except Exception as e:
        import traceback
        last=traceback.extract_tb(e.__traceback__)[-1]
        result={'result':'FAIL','type':type(e).__name__,'file':Path(last.filename).name,'line':last.lineno}
        save('browser-e2e-failure',result);print(json.dumps(result));sys.exit(1)
