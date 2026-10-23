"""Read-only report browser QA; optional local asset overlay before deployment."""
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
import shared_viewer as s

OUT = s.u.ROOT / 'docs/insights-chart-20261022'
FILES = ['static/js/shared/charts.js', 'static/js/pages/snapshot.js',
         'static/css/pages/facebook-content.css']
REPORT = 'rpt_795f2c05f18e6eed68b2bb247e731317'


def main():
    OUT.mkdir(exist_ok=True)
    overlay = '--local' in sys.argv
    values = s.u.env(s.u.inspect(s.VIO))
    result = {'mode': 'local-assets' if overlay else 'deployed', 'checks': []}
    before = s.data(s.VIO)
    with sync_playwright() as p:
        exe = next((Path.home() / 'AppData/Local/ms-playwright/chromium-1228').rglob('chrome.exe'))
        browser = p.chromium.launch(executable_path=str(exe), headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 1000})
        errors = []

        def route(request):
            url = urlsplit(request.request.url)
            allowed = url.hostname in ('localhost', '127.0.0.1') and url.port in (8191, 8080)
            if request.request.method not in ('GET', 'HEAD'):
                allowed = allowed and url.path in ('/auth/handoff/callback', '/api/auth/login', '/api/auth/logout', '/logout')
            if not allowed:
                errors.append('unexpected_request')
                return request.abort()
            if overlay and url.path.lstrip('/') in FILES:
                file = s.u.NEW / url.path.lstrip('/')
                return request.fulfill(body=file.read_bytes(), content_type='text/css' if file.suffix == '.css' else 'application/javascript')
            request.continue_()

        context.route('**/*', route)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(type(error).__name__))
        base = 'http://localhost:8191'
        origin = 'http://127.0.0.1:8080'
        csrf = None
        try:
            login = context.request.post(base + '/api/auth/login', headers={'Origin': base, 'X-KDH-Request': '1'},
                                         data={'email': values['INITIAL_ADMIN_EMAIL'], 'password': values['INITIAL_ADMIN_PASSWORD']})
            assert login.status == 200
            csrf = login.json()['csrf']
            page.goto(origin + '/auth/handoff/start?mode=published&target_id=' + REPORT + '&revision=1')
            page.wait_for_url(origin + '/reports/' + REPORT + '?revision=1')
            payload = json.loads(page.locator('#snapshot-data').inner_text())
            result['metrics'] = {m['key']: m['value'] for m in payload['dashboard']['all_metrics']}
            chart_panel = page.locator('#fc-engagement')
            for width in (1440, 1024, 768, 390, 360):
                page.set_viewport_size({'width': width, 'height': 1000})
                chart_panel.scroll_into_view_if_needed()
                select = chart_panel.locator('[data-snapshot-series]')
                for i in range(select.locator('option').count()):
                    select.select_option(str(i))
                    page.wait_for_timeout(180)
                    chart = chart_panel.locator('[data-bundle-chart]:not([hidden])')
                    check = chart.evaluate('''element => {
                      const svg = element.querySelector('.pb-chart-surface>svg');
                      const box = svg.viewBox.baseVal;
                      const ticks = [...svg.querySelectorAll('text')].map(t => ({text:t.textContent, x:t.getBBox().x, y:t.getBBox().y, width:t.getBBox().width, height:t.getBBox().height}));
                      const outside = ticks.filter(t => t.x < -1 || t.x+t.width>box.width+1 || t.y<0 || t.y+t.height>box.height+1);
                      const dates = ticks.filter(t => t.y>230);
                      const overlap = dates.some((t,i) => i && t.x < dates[i-1].x+dates[i-1].width+2);
                      const data = JSON.parse(element.querySelector('script').textContent);
                      return {outside, overlap, dates:dates.map(t=>t.text), points:svg.querySelectorAll('[tabindex]').length, expected:data.values.filter(v=>v!==null).length};
                    }''')
                    assert not check['outside'] and not check['overlap'], check
                    assert check['points'] == check['expected']
                    assert all(len(d) == 5 and '/' in d for d in check['dates'])
                    chart.locator('svg [tabindex]').first.focus()
                    assert chart.locator('.pb-chart-tooltip').is_visible()
                    assert '07:00' in chart.locator('.pb-chart-tooltip').inner_text()
                    result['checks'].append({'width': width, 'series': i, 'status': 'PASS', **check})
                select.select_option('0')
                page.wait_for_timeout(180)
                page.locator('h1').click()
                chart_panel.scroll_into_view_if_needed()
                if width in (1440, 390):
                    chart_panel.screenshot(path=str(OUT / f'{result["mode"]}-{width}.png'))
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 2')
            assert not errors, errors
            assert context.request.get(origin + '/reports/' + REPORT + '?revision=2', max_redirects=0).status == 404
            result['wrong_revision'] = 'DENIED'
            token = next(c['value'] for c in context.cookies() if c['name'] == 'kdh_viewer_csrf')
            assert context.request.post(origin + '/logout', headers={'Origin': origin}, form={'csrf': token}, max_redirects=0).status == 303
            result['status'] = 'PASS'
        finally:
            if csrf:
                context.request.post(base + '/api/auth/logout', headers={'Origin': base, 'X-KDH-Request': '1', 'X-CSRF-Token': csrf}, data={})
            context.close()
            browser.close()
            result['business_unchanged'] = before == s.data(s.VIO)
            (OUT / (result['mode'] + '.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'chart_checks': len(result['checks']), 'business_unchanged': result['business_unchanged']}))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        import traceback
        print(json.dumps({'status': 'FAIL', 'type': type(exc).__name__, 'line': traceback.extract_tb(exc.__traceback__)[-1].lineno}))
        sys.exit(1)
