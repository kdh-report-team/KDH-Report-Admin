"""Browser verification using existing sandbox credentials; never record secrets."""
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

import fix_sandbox_origin as f
from playwright.sync_api import sync_playwright


def main():
    assert f.read('deployment')['status'] == 'PASS'
    values = f.u.env(f.u.inspect(f.ADMIN))
    result = {'login': 'NOT RUN', 'report': 'NOT RUN'}
    matches = json.loads(f.u.code(f.ADMIN, """import os,json,psycopg
from werkzeug.security import check_password_hash
with psycopg.connect(os.environ['DATABASE_URL'],options='-c default_transaction_read_only=on') as db:
 row=db.execute("SELECT password FROM users WHERE email=%s AND active=1 AND role='admin'",(os.environ.get('INITIAL_ADMIN_EMAIL',''),)).fetchone()
 print(json.dumps(bool(row and os.environ.get('INITIAL_ADMIN_PASSWORD') and check_password_hash(row[0],os.environ['INITIAL_ADMIN_PASSWORD']))))
"""))
    executable = next((Path.home() / 'AppData/Local/ms-playwright/chromium-1228').rglob('chrome.exe'))
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=str(executable), headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 1000})
        blocked = []
        def guard(route):
            r = route.request
            url = urlsplit(r.url)
            allowed = url.hostname in ('localhost', '127.0.0.1') and url.port in (8191, 8193)
            if r.method not in ('GET', 'HEAD') and url.path not in (
                    '/api/auth/login', '/api/auth/logout', '/auth/handoff/callback', '/logout'):
                allowed = False
            if allowed:
                route.continue_()
            else:
                blocked.append(r.method)
                route.abort()
        context.route('**/*', guard)
        page = context.new_page()
        csrf = None
        try:
            page.goto('http://127.0.0.1:8191/')
            assert page.url == 'http://localhost:8191/'
            page.locator('#auth-form').wait_for()
            result['docker_entry'] = 'PASS'
            page.goto('http://127.0.0.1:8191/#connections/facebook')
            assert page.url == 'http://localhost:8191/#connections/facebook'
            result['fragment_preserved'] = 'PASS'
            r = context.request.post('http://localhost:8191/api/auth/login',
                headers={'Origin': 'http://127.0.0.1:8191', 'X-KDH-Request': '1'}, data={})
            assert r.status == 403
            result['wrong_origin_denied'] = 403
            for url in ('http://localhost:8191/health', 'http://127.0.0.1:8191/health',
                        'http://127.0.0.1:8193/api/v1/health'):
                assert context.request.get(url).status == 200
            result['health'] = 'PASS'
            if matches:
                page.goto('http://127.0.0.1:8191/')
                page.locator('#auth-form [name=email]').fill(values['INITIAL_ADMIN_EMAIL'])
                page.locator('#auth-form [name=password]').fill(values['INITIAL_ADMIN_PASSWORD'])
                with page.expect_response(lambda r: urlsplit(r.url).path == '/api/auth/login') as login:
                    page.locator('#auth-form button[type=submit]').click()
                assert login.value.status == 200
                csrf = login.value.json()['csrf']
                result['login'] = 'PASS'
                page.goto('http://127.0.0.1:8191/marketing')
                assert page.url == 'http://localhost:8191/marketing'
                report = 'rpt_4909119771c69125897d8bca84444abe'
                page.locator('#existing-report option[value="' + report + ':1"]').wait_for(state='attached')
                page.locator('#existing-report').select_option(report + ':1')
                link = page.locator('#selected-report-open')
                assert link.is_visible()
                link.click()
                page.wait_for_url('http://127.0.0.1:8193/reports/' + report + '?revision=1')
                payload = json.loads(page.locator('#snapshot-data').inner_text())
                metrics = {m['key'].split('.')[-1]: m for m in payload['dashboard']['all_metrics']}
                assert [metrics[k]['value'] for k in ('posts_published', 'reactions_lifetime', 'comments_lifetime')] == [15, 80, 10]
                assert metrics['engagements']['value'] is None and metrics['engagements']['status'] == 'no_data'
                assert metrics['shares_lifetime']['value'] is None and metrics['shares_lifetime']['status'] == 'partial'
                assert metrics['shares_lifetime']['coverage'] == {'available': 7, 'expected': 15, 'unit': 'posts'}
                assert payload['dashboard']['timezone'] == 'UTC'
                result['report'] = 'PASS'
                page.screenshot(path=str(f.OUT / 'report-after-docker-login.png'))
                new_csrf = next(c['value'] for c in context.cookies() if c['name'] == 'kdh_vio_viewer_csrf')
                r = context.request.post('http://127.0.0.1:8193/logout',
                    headers={'Origin': 'http://127.0.0.1:8193'}, form={'csrf': new_csrf}, max_redirects=0)
                assert r.status == 303
            assert not blocked
        finally:
            if csrf:
                context.request.post('http://localhost:8191/api/auth/logout',
                    headers={'Origin': 'http://localhost:8191', 'X-KDH-Request': '1', 'X-CSRF-Token': csrf}, data={})
            context.close()
            browser.close()
    assert f.data() == f.read('prepared')['data']
    f.verify_protected()
    result.update(business_data='UNCHANGED', protected_services='UNCHANGED')
    f.save('browser', result)
    print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        import traceback
        last = traceback.extract_tb(exc.__traceback__)[-1]
        print(json.dumps({'status': 'FAIL', 'type': type(exc).__name__, 'line': last.lineno}))
        sys.exit(1)
