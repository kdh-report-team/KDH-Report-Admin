"""Authenticated browser smoke; never sync, reconnect, review or publish."""
import json
import re
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
import deploy_tonight_content as night
night.configure_admin()
d = night.d


def wait_mobile_drawer_closed(page):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        box = page.locator('#dashboard-sidebar').bounding_box()
        if box and box['x'] + box['width'] <= 1:
            return
        page.wait_for_timeout(100)
    raise AssertionError('Mobile drawer remained visible after closing')


def main():
    assert d.read('deployment')['status'] == 'PASS'
    values = d.u.env(d.u.inspect(d.ADMIN))
    result = {}
    matches = json.loads(d.u.code(d.ADMIN, """import os,json,psycopg
from werkzeug.security import check_password_hash
with psycopg.connect(os.environ['DATABASE_URL'],options='-c default_transaction_read_only=on') as db:
 row=db.execute("SELECT password FROM users WHERE email=%s AND active=1 AND role='admin'",(os.environ.get('INITIAL_ADMIN_EMAIL',''),)).fetchone()
 print(json.dumps(bool(row and os.environ.get('INITIAL_ADMIN_PASSWORD') and check_password_hash(row[0],os.environ['INITIAL_ADMIN_PASSWORD']))))
"""))
    assert matches, 'Valid existing login required'
    executable = next((Path.home() / 'AppData/Local/ms-playwright/chromium-1228').rglob('chrome.exe'))
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=str(executable), headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 1000})
        blocked = []
        def guard(route):
            request = route.request
            url = urlsplit(request.url)
            allowed = url.hostname in ('localhost', '127.0.0.1') and url.port in (8191, 8080)
            if request.method not in ('GET', 'HEAD') and url.path not in (
                    '/api/auth/login', '/api/auth/logout', '/auth/handoff/callback', '/logout', '/api/marketing/preview'):
                allowed = False
            if allowed:
                route.continue_()
            else:
                blocked.append({'method': request.method, 'path': url.path})
                route.abort()
        context.route('**/*', guard)
        page = context.new_page()
        errors = []
        def page_error(error):
            message = re.sub(r'https?://\S+|[A-Za-z0-9_\-]{40,}', '[redacted]', error.message)
            errors.append({'path': urlsplit(page.url).path, 'message': message[:220]})
        page.on('pageerror', page_error)
        csrf = None
        try:
            for url in ('http://localhost:8191/health', 'http://127.0.0.1:8191/health',
                        'http://127.0.0.1:8080/api/v1/health'):
                assert context.request.get(url).status == 200
            result['health'] = 'PASS'
            page.goto('http://127.0.0.1:8191/')
            assert page.url == 'http://localhost:8191/'
            page.locator('#auth-form [name=email]').fill(values['INITIAL_ADMIN_EMAIL'])
            page.locator('#auth-form [name=password]').fill(values['INITIAL_ADMIN_PASSWORD'])
            with page.expect_response(lambda r: urlsplit(r.url).path == '/api/auth/login') as response:
                page.locator('#auth-form button[type=submit]').click()
            assert response.value.status == 200
            csrf = response.value.json()['csrf']
            # The login response precedes the app's overview bootstrap. Wait
            # for its shell before changing the hash in this browser fixture.
            page.locator('#sidebar').wait_for()
            page.locator('#content .spinner').wait_for(state='detached')
            result['login_and_canonical_host'] = 'PASS'
            page.goto('http://localhost:8191/#connections/facebook')
            page.get_by_text('Page/Post Insights:', exact=False).wait_for()
            meta_response = context.request.get('http://localhost:8191/api/meta')
            assert meta_response.status == 200
            meta = meta_response.json()
            result['permissions'] = {'connected': meta.get('connected'), 'insights_permission': meta.get('insights_permission'), 'scopes': meta.get('scopes')}
            page.screenshot(path=str(d.OUT / 'insights-permission-1440.png'), full_page=True)
            page.goto('http://localhost:8191/marketing')
            assert context.request.get('http://localhost:8191/static/facebook-content-report.js').status == 200
            page.locator('#source option[value=facebook_content]').wait_for(state='attached')
            page.locator('#source').select_option('facebook_content')
            workflow = context.request.get('http://localhost:8191/api/marketing/workflow').json()
            asset = next(a['id'] for a in workflow['assets'] if a.get('external_id') == '2188688654687066' and a.get('asset_type') == 'facebook_page')
            page.locator('#asset option[value="' + asset + '"]').wait_for(state='attached')
            page.locator('#asset').select_option(asset)
            page.locator('#start').fill('2026-09-21')
            page.locator('#end').fill('2026-10-18')
            with page.expect_response(lambda r: urlsplit(r.url).path == '/api/marketing/preview') as preview:
                page.locator('#content-plan-preview').click()
            assert preview.value.status == 200
            content = preview.value.json()['content_report']
            assert len(content['sections']) == 7
            assert content['identity']['external_id'] == '2188688654687066'
            assert content['review_status'] == 'pending_review'
            page.wait_for_function("!document.querySelector('[aria-busy=true]')")
            page.locator('#content-report-preview details').evaluate_all('(els)=>els.forEach(e=>e.open=true)')
            for width in (1440, 390):
                page.set_viewport_size({'width': width, 'height': 1000})
                page.screenshot(path=str(d.OUT / f'admin-preview-real-{width}.png'), full_page=True)
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2')
            result['admin_preview'] = {'sections': 7, 'source': 'existing saved snapshot',
                'metrics': {m['key']: m['value'] for m in content['metrics']}, 'new_dataset_created': False}
            page.set_viewport_size({'width':1440, 'height':1000})
            report = 'rpt_4909119771c69125897d8bca84444abe'
            page.locator('#existing-report option[value="' + report + ':1"]').wait_for(state='attached')
            page.locator('#existing-report').select_option(report + ':1')
            page.locator('#selected-report-open').click()
            page.wait_for_url('http://127.0.0.1:8080/reports/' + report + '?revision=1')
            payload = json.loads(page.locator('#snapshot-data').inner_text())
            metrics = {m['key'].split('.')[-1]: m for m in payload['dashboard']['all_metrics']}
            assert [metrics[k]['value'] for k in ('posts_published', 'reactions_lifetime', 'comments_lifetime')] == [15, 80, 10]
            assert metrics['engagements']['value'] is None and metrics['engagements']['status'] == 'no_data'
            assert metrics['shares_lifetime']['value'] is None and metrics['shares_lifetime']['status'] == 'partial'
            assert metrics['shares_lifetime']['coverage'] == {'available': 7, 'expected': 15, 'unit': 'posts'}
            assert payload['dashboard']['timezone'] == 'UTC'
            result['existing_revision_1_handoff'] = 'PASS'
            result['metrics'] = {'posts': 15, 'reactions_lifetime': 80, 'comments_lifetime': 10,
                                 'engagements': 'null/no_data', 'shares': 'null/partial 7/15', 'timezone': 'UTC'}
            for width in (1440, 390):
                page.set_viewport_size({'width': width, 'height': 1000})
                if width == 390:
                    wait_mobile_drawer_closed(page)
                page.wait_for_timeout(300)
                page.screenshot(path=str(d.OUT / f'new-report-real-{width}.png'), full_page=True)
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2')
                if width == 390:
                    wait_mobile_drawer_closed(page)
                    page.locator('#sidebar-toggle').click()
                    assert page.locator('#sidebar-toggle').get_attribute('aria-expanded') == 'true'
                    page.keyboard.press('Escape')
                    wait_mobile_drawer_closed(page)
            result['responsive_1440_390'] = 'PASS; mobile drawer opens and closes'
            for target in ('/reports/' + report + '?revision=2', '/reports/rpt_9f8e96cd09ef21bcace6d18aa7a31970?revision=1'):
                assert context.request.get('http://127.0.0.1:8080' + target, max_redirects=0).status == 404
            result['wrong_revision_and_no_grant'] = 'DENIED'
            response = context.request.post('http://localhost:8191/api/auth/login',
                headers={'Origin': 'http://127.0.0.1:8191', 'X-KDH-Request': '1'}, data={})
            assert response.status == 403
            result['wrong_origin'] = 'DENIED'
            new_csrf = next(c['value'] for c in context.cookies() if c['name'] == 'kdh_viewer_csrf')
            response = context.request.post('http://127.0.0.1:8080/logout',
                headers={'Origin': 'http://127.0.0.1:8080'}, form={'csrf': new_csrf}, max_redirects=0)
            assert response.status == 303
            result['viewer_logout'] = 'PASS'
            d.save('browser-observations', {'blocked_requests': blocked, 'javascript_error_types': errors, 'checks': result})
            assert not blocked and not errors
        finally:
            if csrf:
                context.request.post('http://localhost:8191/api/auth/logout',
                    headers={'Origin': 'http://localhost:8191', 'X-KDH-Request': '1', 'X-CSRF-Token': csrf}, data={})
            context.close()
            browser.close()
    assert d.s.data(d.ADMIN) == d.read('prepared')['data']
    expected = d.read('prepared')['protected']
    actual = {n: d.signature(n) for n in expected if n != d.u.N}
    state_changes = {n: {'before': expected[n]['running'], 'after': v['running']}
                     for n, v in actual.items() if v['running'] != expected[n]['running']}
    # Docker Desktop restart may auto-start existing services. Identity, image,
    # mounts and networks must still match the deployment preflight exactly.
    assert {n: {k: v for k, v in item.items() if k != 'running'} for n, item in actual.items()} == {
        n: {k: v for k, v in item.items() if k != 'running'} for n, item in expected.items() if n != d.u.N}
    result['docker_restart_state_changes'] = state_changes
    assert d.signature(d.u.N) == night.read('deployment')['new']
    result.update(business_data='UNCHANGED', other_container_identity_and_config='UNCHANGED', provider_calls='NOT RUN')
    d.save('browser', result)
    print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        import traceback
        last = traceback.extract_tb(exc.__traceback__)[-1]
        message = re.sub(r'https?://\S+|[A-Za-z0-9_\-]{40,}', '[redacted]', str(exc))[:900]
        failure = {'status': 'FAIL', 'type': type(exc).__name__, 'line': last.lineno, 'message': message}
        d.save('browser', failure)
        print(json.dumps(failure))
        sys.exit(1)
