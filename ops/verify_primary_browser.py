"""Anonymous primary browser QA; never use or create an authenticated user."""
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
import unify_primary as deploy


def main():
    assert deploy.read('deployment')['status'] == 'PASS'
    executable = next((Path.home() / 'AppData/Local/ms-playwright/chromium-1228').rglob('chrome.exe'))
    folder = deploy.OUT / 'screenshots'
    folder.mkdir(exist_ok=True)
    result = {'authenticated_browser_e2e': 'NOT RUN: no primary login credential; no VIO Bundle in primary DB',
              'widths': [], 'blocked_requests': [], 'page_errors': []}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=str(executable), headless=True)
        context = browser.new_context()

        def guard(route):
            req = route.request
            parsed = urlsplit(req.url)
            allowed = (parsed.hostname == 'localhost' and parsed.port in (8090, 8080)
                       and req.method in ('GET', 'HEAD')
                       and (parsed.path.startswith('/static/') or parsed.path in
                            ('/', '/api/auth/me', '/viewer/reports', '/api/v1/health', '/health')))
            if allowed:
                route.continue_()
            else:
                result['blocked_requests'].append({'path': parsed.path, 'method': req.method})
                route.abort()

        context.route('**/*', guard)
        page = context.new_page()
        page.on('pageerror', lambda e: result['page_errors'].append(type(e).__name__))
        assert page.goto('http://localhost:8090/health').status == 200
        for width in (1440, 1024, 768, 390, 360):
            page.set_viewport_size({'width': width, 'height': 900})
            page.goto('http://localhost:8090/')
            page.locator('#auth-form [name=email]').wait_for()
            assert page.locator('#auth-form [name=password]').is_visible()
            page.evaluate('document.fonts.ready')
            dimensions = page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})')
            assert dimensions['scroll'] <= width + 1
            result['widths'].append(dimensions)
            page.screenshot(path=str(folder / f'primary-admin-login-{width}.png'), full_page=True)
        page.goto('http://localhost:8080/')
        page.wait_for_url('http://localhost:8090/viewer/reports')
        page.locator('#auth-form [name=email]').wait_for()
        result['new_to_admin_entry'] = 'PASS'
        result['primary_login_render'] = 'PASS'
        assert not result['blocked_requests'] and not result['page_errors']
        context.close()
        browser.close()
    deploy.save('browser-qa', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
