"""Authenticated browser smoke; never sync, reconnect, review or publish."""
import json
import re
from pathlib import Path
import sys
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
import deploy_content_insights as d


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
                    '/api/auth/login', '/api/auth/logout', '/auth/handoff/callback', '/logout'):
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
            page.get_by_text('Page/Post Insights: Chưa được cấp read_insights', exact=True).wait_for()
            assert page.get_by_role('button', name='Cấp lại quyền qua Meta', exact=True).is_visible()
            result['insights_permission_ui'] = 'MISSING_READ_INSIGHTS_CORRECTLY_SHOWN'
            page.screenshot(path=str(d.OUT / 'insights-permission-1440.png'), full_page=True)
            page.goto('http://localhost:8191/marketing')
            assert context.request.get('http://localhost:8191/static/facebook-content-report.js').status == 200
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
            page.screenshot(path=str(d.OUT / 'existing-report-1440.png'), full_page=True)
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
    d.verify_protected()
    result.update(business_data='UNCHANGED', new_and_other_containers='UNCHANGED', provider_calls='NOT RUN')
    d.save('browser', result)
    print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        import traceback
        last = traceback.extract_tb(exc.__traceback__)[-1]
        d.save('browser', {'status': 'FAIL', 'type': type(exc).__name__, 'line': last.lineno})
        print(json.dumps({'status': 'FAIL', 'type': type(exc).__name__, 'line': last.lineno}))
        sys.exit(1)
