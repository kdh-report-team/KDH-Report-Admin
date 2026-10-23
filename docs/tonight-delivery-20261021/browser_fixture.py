"""Isolated UI QA. Temporary SQLite and synthetic data only; no live backend."""
import json
import mimetypes
import sys
import threading
from pathlib import Path
from urllib.parse import urlsplit

ADMIN = Path('D:/KDH-Report-All/KDH-Report-Admin')
NEW = ADMIN.parent / 'KDH-Report-New'
OUT = Path('D:\\KDH-Report-All\\KDH-Report-Admin\\docs\\tonight-delivery-20261021')
sys.path[:0] = [str(ADMIN), str(ADMIN / 'tests'), str(NEW)]
sys.path.append(str(NEW / '.venv/Lib/site-packages'))
from test_facebook_bundles import FacebookBundleTests
from test_facebook_content_report import source_fixture
from kdh.facebook_content_report import build_content_report, approved_content_report
from werkzeug.serving import make_server, WSGIRequestHandler
from playwright.sync_api import sync_playwright
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.mappers.dashboard import dashboard_context
from app.schemas.bundle_view import BundleView, SectionView, QualityView
from app.mappers.facebook_content import content_report


class Quiet(WSGIRequestHandler):
    def log_request(self, *args, **kwargs):
        pass


fx = FacebookBundleTests()
fx.setUp()
server = None
try:
    asset = fx.fixture.select_asset('facebook_content', '1234')
    fx.fixture.sync_asset(asset)
    calls_before = len(fx.meta.calls)
    datasets_before = fx.store.all('SELECT id,data FROM datasets')
    server = make_server('127.0.0.1', 0, fx.app, request_handler=Quiet)
    origin = f'http://localhost:{server.server_port}'
    fx.app.config['APP_URL'] = origin
    threading.Thread(target=server.serve_forever, daemon=True).start()
    source = json.loads((NEW / 'tests/fixtures/facebook_content_insights_v1.json').read_text(encoding='utf-8'))
    raw = approved_content_report(build_content_report(source, {
        'topics': {'1234_1': 'Sản phẩm'},
        'notes': {'overview': 'Fixture only: approved editorial', 'posts': 'Fixture only: post commentary'}}))
    section = SectionView('facebook_content', 'fb', 'Facebook Content', 'facebook-content', raw['period'],
                          True, 'available', QualityView(), content_report=content_report(raw, source, raw['period'], True),
                          source_identity=raw['identity'], timezone='UTC', fetched_at=raw['fetched_at'])
    bundle = BundleView('fixture-report', 1, 'provisional', 'KIỂM THỬ GIAO DIỆN', 'Fixture', raw['period'],
                       None, None, None, QualityView(), [section], 'facebook_content')
    context = dashboard_context(bundle, 'facebook_content', '/reports/fixture-report')
    html = Environment(loader=FileSystemLoader(str(NEW / 'templates')), autoescape=select_autoescape()).get_template(
        'pages/facebook_content/index.html').render(**context)
    exe = next((Path.home() / 'AppData/Local/ms-playwright/chromium-1228').rglob('chrome.exe'))
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=str(exe), headless=True)
        ctx = browser.new_context(viewport={'width': 1440, 'height': 1000})
        errors = []
        def route(r):
            u = urlsplit(r.request.url)
            if u.netloc == urlsplit(origin).netloc:
                r.continue_()
            elif u.hostname == 'fixture.invalid':
                if u.path == '/report':
                    r.fulfill(status=200, content_type='text/html', body=html)
                elif u.path.startswith('/static/'):
                    path = (NEW / u.path.lstrip('/')).resolve()
                    if path.is_relative_to(NEW / 'static') and path.is_file():
                        r.fulfill(status=200, content_type=mimetypes.guess_type(path)[0] or 'application/octet-stream', body=path.read_bytes())
                    else:
                        r.fulfill(status=404, body='')
                else:
                    r.fulfill(status=404, body='')
            else:
                r.abort()
        ctx.route('**/*', route)
        page = ctx.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(origin)
        page.locator('#auth-form [name=email]').fill(fx.fixture.admin_email)
        page.locator('#auth-form [name=password]').fill(fx.fixture.admin_password)
        with page.expect_response(lambda r: r.url.endswith('/api/auth/login')) as response:
            page.locator('#auth-form button[type=submit]').click()
        assert response.value.status == 200
        page.locator('#sidebar').wait_for()
        page.goto(origin + '/marketing')
        page.locator('#source option[value=facebook_content]').wait_for(state='attached')
        page.locator('#source').select_option('facebook_content')
        page.locator('#asset').select_option(asset)
        page.locator('#start').fill(fx.fixture.START)
        page.locator('#end').fill(fx.fixture.END)
        page.locator('[data-content-note=overview]').evaluate("e => e.value = 'Fixture editorial only'")
        with page.expect_response(lambda r: r.url.endswith('/api/marketing/preview')) as response:
            page.locator('#content-plan-preview').click()
        assert response.value.status == 200, response.value.status
        page.wait_for_function("!document.querySelector('[aria-busy=true]')")
        page.locator('[data-content-topic]').evaluate("e => e.value = 'Fixture topic'")
        with page.expect_response(lambda r: r.url.endswith('/api/marketing/preview')) as response:
            page.locator('#content-plan-preview').click()
        assert response.value.status == 200
        page.wait_for_function("!document.querySelector('[aria-busy=true]')")
        assert 'Fixture editorial only' in page.locator('#content-report-preview').text_content()
        assert 'read_insights' in page.locator('#content-report-preview').inner_text()
        results = []
        for width in (1440, 1024, 768, 390, 360):
            page.set_viewport_size({'width': width, 'height': 1000})
            page.screenshot(path=str(OUT / f'admin-fixture-{width}.png'), full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 2'), ('Admin overflow', width)
            results.append({'page': 'Admin fixture', 'width': width, 'overflow': False})
        page.goto('http://fixture.invalid/report')
        page.wait_for_timeout(300)
        for width in (1440, 1024, 768, 390, 360):
            page.set_viewport_size({'width': width, 'height': 1000})
            page.screenshot(path=str(OUT / f'new-fixture-{width}.png'), full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 2'), ('New overflow', width)
            assert page.locator('#fc-topics').is_visible()
            assert page.locator('#fc-insights').is_visible()
            assert page.locator('#fc-engagement').is_visible()
            assert page.locator('[data-snapshot-kpi="facebook_content.page_media_view"]').inner_text().strip() == '3'
            results.append({'page': 'New fixture', 'width': width, 'overflow': False})
        assert not errors, errors
        ctx.close()
        browser.close()
    assert len(fx.meta.calls) == calls_before
    assert fx.store.all('SELECT id,data FROM datasets') == datasets_before
    (OUT / 'fixture-browser.json').write_text(json.dumps({'results': results, 'page_errors': errors,
        'preview_provider_calls': 0, 'preview_dataset_writes': 0}, indent=2), encoding='utf-8')
    print('Browser fixture PASS: 10 viewports, no preview provider call or Dataset write')
finally:
    if server:
        server.shutdown()
        server.server_close()
    fx.doCleanups()
