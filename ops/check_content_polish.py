"""Browser verification using existing sandbox credentials; never record secrets."""
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

import shared_viewer as f
from playwright.sync_api import sync_playwright
OUT = f.u.ROOT / 'docs/content-polish-20261021'


def main():
    assert f.read('deployment')['status'] == 'PASS'
    values = f.u.env(f.u.inspect(f.VIO))
    result = {'login': 'NOT RUN', 'report': 'NOT RUN'}
    matches = json.loads(f.u.code(f.VIO, """import os,json,psycopg
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
            allowed = url.hostname in ('localhost', '127.0.0.1') and url.port in (8191, 8080)
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
                        'http://127.0.0.1:8080/api/v1/health'):
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
                page.wait_for_url('http://127.0.0.1:8080/reports/' + report + '?revision=1')
                payload = json.loads(page.locator('#snapshot-data').inner_text())
                metrics = {m['key'].split('.')[-1]: m for m in payload['dashboard']['all_metrics']}
                assert [metrics[k]['value'] for k in ('posts_published', 'reactions_lifetime', 'comments_lifetime')] == [15, 80, 10]
                assert metrics['engagements']['value'] is None and metrics['engagements']['status'] == 'no_data'
                assert metrics['shares_lifetime']['value'] is None and metrics['shares_lifetime']['status'] == 'partial'
                assert metrics['shares_lifetime']['coverage'] == {'available': 7, 'expected': 15, 'unit': 'posts'}
                assert payload['dashboard']['timezone'] == 'UTC'
                result['report'] = 'PASS'
                r = context.request.get('http://localhost:8080/reports/' + report + '?revision=1', max_redirects=0)
                assert r.status == 303 and r.headers['location'].startswith('/auth/handoff/start?')
                r = context.request.get('http://localhost:8080/auth/handoff/start?mode=published&target_id=' + report + '&revision=1', max_redirects=0)
                assert r.status == 404
                result['cross_environment'] = 'DENIED'
                for target in ('/reports/' + report + '?revision=2', '/reports/rpt_9f8e96cd09ef21bcace6d18aa7a31970?revision=1'):
                    r = context.request.get('http://127.0.0.1:8080' + target, max_redirects=0)
                    assert r.status == 404
                result['wrong_revision_and_no_grant'] = 'DENIED'
                assert page.locator('#facebook-content-dashboard.fc-live-shell').count() == 1
                assert page.locator('.fc-agency').count() == 0
                cards = page.locator('#fc-kpis [data-snapshot-kpi]')
                assert cards.all_text_contents() == ['15', '80', '10']
                for key in ('fc-topics', 'fc-reach', 'fc-engagement', 'fc-insights'):
                    assert page.locator('#' + key).count() == 0
                    assert page.locator('a[href="#' + key + '"]').count() == 0
                assert page.locator('#fc-formats svg').count() > 0
                assert page.locator('#fc-posts .fc-post-external').count() > 0
                page.goto(page.url + '&view=fc-dinh-dang-noi-dung')
                assert page.locator('link[href*="facebook-content.css?v=content-polish-20261021"]').count() == 1
                result['responsive'] = {}
                for width in (1920, 1536, 1440, 1024, 768, 390, 360):
                    page.set_viewport_size({'width': width, 'height': 1000})
                    page.wait_for_timeout(250)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                    assert page.locator('#fc-formats .pb-chart-surface>svg').evaluate(
                        'el => el.getBoundingClientRect().right <= el.parentElement.getBoundingClientRect().right + 1')
                    if width < 640:
                        assert page.locator('#fc-posts [data-row-count]').bounding_box()['width'] > 200
                    if width >= 1024:
                        assert page.locator('#fc-kpis').evaluate('el => Math.abs(el.lastElementChild.getBoundingClientRect().right - el.getBoundingClientRect().right) < 2')
                    assert page.locator('#fc-formats').evaluate("el => Math.abs(el.getBoundingClientRect().width - el.parentElement.getBoundingClientRect().width) < 2")
                    assert page.locator('#fc-formats [data-bundle-chart]').evaluate('el => el.scrollWidth <= el.clientWidth + 1')
                    assert page.locator('#fc-formats rect[role="img"]').count() == 28
                    assert page.locator('#fc-posts table').evaluate("""table => {
                        const edge = node => { const r = document.createRange(); r.selectNodeContents(node); return r.getBoundingClientRect().right; };
                        const th = table.querySelectorAll('th')[2];
                        const td = table.querySelector('tbody tr').children[2];
                        return Math.abs(edge(th.querySelector('button').firstChild) - edge(td.firstChild)) < 2;
                    }""")
                    assert cards.count() == 3
                    page.screenshot(path=str(OUT / ('report-' + str(width) + '.png')), full_page=True)
                    result['responsive'][str(width)] = 'PASS'
                result['shared_layout_and_data_visibility'] = 'PASS'
                result['visible_kpis'] = [15, 80, 10]
                new_csrf = next(c['value'] for c in context.cookies() if c['name'] == 'kdh_viewer_csrf')
                r = context.request.post('http://127.0.0.1:8080/logout',
                    headers={'Origin': 'http://127.0.0.1:8080'}, form={'csrf': new_csrf}, max_redirects=0)
                assert r.status == 303
            assert not blocked
        finally:
            if csrf:
                context.request.post('http://localhost:8191/api/auth/logout',
                    headers={'Origin': 'http://localhost:8191', 'X-KDH-Request': '1', 'X-CSRF-Token': csrf}, data={})
            context.close()
            browser.close()
    assert all(f.data(n) == f.read('baseline')['data'][n] for n in (f.u.A, f.VIO))
    result.update(business_data='UNCHANGED', protected_services='UNCHANGED')
    (OUT / 'browser.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        import traceback
        last = traceback.extract_tb(exc.__traceback__)[-1]
        print(json.dumps({'status': 'FAIL', 'type': type(exc).__name__, 'line': last.lineno}))
        sys.exit(1)
