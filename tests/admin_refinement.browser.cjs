// Presentation QA only. Every HTTP request is intercepted; no live app or DB.
// node tests/admin_refinement.browser.cjs <existing-playwright-core-module>
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.argv[2]);
const root = path.resolve(__dirname, '..');
const output = path.join(root, 'test-results', process.env.ADMIN_VISUAL_OUTPUT || 'admin-multiplatform-20261019-final4');
fs.mkdirSync(output, { recursive: true });
const user = { id: 'admin-fixture', name: 'Admin kiểm thử', role: 'admin', active: 1, email: 'admin@example.test', allowed: ['seo', 'facebook-content'] };
const types = [{ id: 'seo', label: 'Website Traffic & SEO', can_generate: true }, { id: 'facebook-content', label: 'Facebook Content', can_generate: false }];
const params = { source: 'facebook_content', report_type: 'facebook-content', start: '2026-10-15', end: '2026-10-15', compare: false };
const data = {
    id: 'dataset-fixture', client_id: 'client_meta_sandbox', params,
    dataset_kind: 'marketing_internal_preview_v1',
    marketing: { preview: {
        asset_id: 'page-fixture',
        meta_snapshot: { external_id: '123456', snapshot_id: 'snapshot-fixture', sync_run_ids: ['sync-fixture'], timezone: 'UTC', fetched_at: '2026-10-19T02:00:00Z' },
        widgets: [
            { label: 'Bài đăng mới trong kỳ', value: 1, status: 'available' },
            { label: 'Tương tác phát sinh trong kỳ', value: null, status: 'no_data' },
            { label: 'Reactions lifetime', value: 2, status: 'available' },
            { label: 'Comments lifetime', value: 0, status: 'available' },
            { label: 'Shares lifetime', value: null, status: 'partial' }
        ].map(item => ({ ...item, unit: 'count', comparison: null })),
        evidence_cards: [], opportunity_candidates: []
    } }
};
const overview = { types, reports: [{ id: 'primary-report', name: 'Primary-only report fixture', report_type: 'seo', version: 1, created_at: '2026-10-18T00:00:00Z', valid: true }], report_count: 1, jobs: [{ id: 'primary-job', kind: 'analysis', status: 'succeeded', params: { report_type: 'seo' } }], running: 1, failed: 0, sources: {}, google_connected: false, dashboard_url: '', job_mode: 'request', client_context: { client_id: 'client_meta_sandbox', environment: 'sandbox' }, organization: { name: 'Khách hàng kiểm thử', author: '' } };
const google = { configured: false, connected: false, sources: {}, assets: {} };
const meta = { configured: true, connected: true, has_connection: true, status: 'connected', client_id: 'client_meta_sandbox', account_name: 'Tài khoản kiểm thử', scopes: ['pages_show_list'], expires_at_unbounded: true };
const sourceState = (state, label, extras = {}) => ({ state, label, asset: null, latest_run: null, verification: 'not_checked', ...extras });
const platformStatus = { client_context: { client_id: 'client_meta_sandbox', environment: 'sandbox' }, platforms: [
    { id: 'seo_website', label: 'SEO & Website', group: 'Google', integration: 'adapter_present', source_status: { ga4: sourceState('not_configured', 'Chưa cấu hình'), gsc: sourceState('not_configured', 'Chưa cấu hình'), keywords: sourceState('not_configured', 'Chưa cấu hình') } },
    { id: 'facebook_content', label: 'Facebook Content', group: 'Meta', integration: 'adapter_present', source_status: { facebook_content: sourceState('sync_succeeded', 'Đồng bộ thành công · có dữ liệu', { asset: { name: 'VIO Agency' }, latest_run: { requested_start: '2026-10-15', requested_end: '2026-10-15', record_count: 1 }, verification: 'unverified' }) } },
    { id: 'facebook_ads', label: 'Facebook Ads', group: 'Meta', integration: 'adapter_present', source_status: { facebook_ads: sourceState('sync_empty', 'Đồng bộ thành công · không có bản ghi', { asset: { name: 'Ad account fixture' }, latest_run: { requested_start: '2026-10-15', requested_end: '2026-10-17', record_count: 0 } }) } },
    { id: 'tiktok_ads', label: 'TikTok Ads', group: 'TikTok', integration: 'planned', source_status: { tiktok_ads: sourceState('unavailable', 'Chưa cấu hình tích hợp') } }
], sources: {}, assets: [{ id: 'page-fixture', client_id: 'client_meta_sandbox', provider: 'meta', asset_type: 'facebook_page', external_id: '123456', name: 'Page kiểm thử' }] };
const syncHistory = { client_id: 'client_meta_sandbox', runs: [], assets: [], truncated: false };
const failures = [], measurements = [], blocked = [], mutations = [];

async function run() {
    const browser = await chromium.launch({ headless: true, executablePath: process.argv[3] || undefined });
    try {
        const context = await browser.newContext({ reducedMotion: 'reduce' });
        await context.route('**/*', async route => {
            const request = route.request();
            const url = new URL(request.url());
            if (url.origin !== 'http://admin-ui.test') return route.abort();
            if (request.method() !== 'GET') {
                mutations.push(url.pathname);
                return route.fulfill({ status: 405, json: { error: 'Read-only fixture' } });
            }
            if (url.pathname === '/' || url.pathname === '/marketing') {
                return route.fulfill({ contentType: 'text/html; charset=utf-8', body: fs.readFileSync(path.join(root, 'templates', url.pathname === '/marketing' ? 'marketing.html' : 'index.html')) });
            }
            if (url.pathname.startsWith('/static/')) {
                const file = path.resolve(root, '.' + url.pathname);
                if (!file.startsWith(path.join(root, 'static') + path.sep) || !fs.existsSync(file)) return route.fulfill({ status: 404 });
                const ext = path.extname(file);
                return route.fulfill({ body: fs.readFileSync(file), contentType: ({ '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml' })[ext] || 'application/octet-stream' });
            }
            const responses = {
                '/api/auth/me': { user, csrf: 'fixture-only', setup_required: false },
                '/api/overview': overview,
                '/api/google': google,
                '/api/meta': meta,
                '/api/platform-status': platformStatus,
                '/api/sync-history': syncHistory,
                '/api/meta/reporting/assets': { client_id: 'client_meta_sandbox', selected: [], discovered: { facebook_content: [{ id: '123456', name: 'Page kiểm thử' }], facebook_ads: [] } },
                '/api/jobs': [], '/api/events': [], '/api/schedules': [], '/api/reports': [], '/api/uploads': [], '/api/report-bundles': [],
                '/api/users': [user],
                '/api/settings': { organization: overview.organization, timezone: 'Asia/Ho_Chi_Minh', versions: 'Giữ toàn bộ phiên bản', oauth_configured: false },
                '/api/marketing/workflow': { client_id: 'client_meta_sandbox', client_name: 'Sandbox kiểm thử giao diện', new_url: '', sources: [{ id: 'facebook_content', label: 'Facebook Content' }], assets: [{ id: 'page-fixture', external_id: '123456', name: 'Page kiểm thử', asset_type: 'facebook_page' }], snapshots: [{ id: data.id, kind: data.dataset_kind, source: params.source, start: params.start, end: params.end }] },
                '/api/datasets/dataset-fixture': data,
                '/api/marketing/datasets/dataset-fixture/review': { dataset_id: data.id, checks: { can_approve_internal: true }, issues: [], review_status: 'awaiting_review', latest_review: null },
                '/api/marketing/datasets/dataset-fixture/source-evidence': { receipt_valid: true, snapshot_hash_matches: true, daily_consistent: true, fresh: true, note: 'Fixture kiểm thử giao diện; không phải dữ liệu khách hàng.', checked_at: '2026-10-19T02:01:00Z' }
            };
            if (url.pathname in responses) return route.fulfill({ json: responses[url.pathname] });
            blocked.push(url.pathname);
            return route.fulfill({ status: 404, json: { error: 'Unknown fixture endpoint' } });
        });
        const page = await context.newPage();
        page.on('pageerror', error => failures.push(error.message));
        const routes = ['overview', 'clients', 'connections', 'assets', 'sync', 'analysis', 'datasets', 'report-builder', 'reports', 'activity', 'schedules', 'users', 'settings', 'connections/facebook'];
        async function measure(name, width, screenshot = false) {
            const size = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth }));
            measurements.push({ name, ...size });
            if (size.scroll > size.width + 1) {
                const wide = await page.locator('body *').evaluateAll(elements => elements.filter(el => el.getBoundingClientRect().right > innerWidth + 1 && getComputedStyle(el).position !== 'fixed').slice(0, 12).map(el => ({ tag: el.tagName, class: el.className, right: el.getBoundingClientRect().right })));
                failures.push(`${name} overflows at ${width}: ${JSON.stringify(wide)}`);
            }
            if (screenshot) await page.screenshot({ path: path.join(output, `${name}-${width}.png`), fullPage: true });
        }
        for (const width of [1440, 1024, 768, 390, 360]) {
            await page.setViewportSize({ width, height: 960 });
            for (const name of routes) {
                await page.goto('http://admin-ui.test/#' + name);
                await page.locator('#content h1').waitFor();
                await page.waitForLoadState('networkidle');
                for (const logo of await page.locator('.brand-mark img').all()) {
                    assert.equal(await logo.getAttribute('alt'), '');
                    assert.equal(await logo.evaluate(img => img.complete && img.naturalWidth > 0), true, 'Local provider logo must load');
                }
                assert.equal(await page.locator('.nav-link').count(), 14);
                if (name === 'overview') {
                    assert.equal(await page.locator('.platform-status-card').count(), 4);
                    assert.equal(await page.locator('.sidebar-status').count(), 0);
                    assert.equal(await page.locator('[data-action="check-google"]').count(), 0);
                    assert.equal(await page.getByText('Primary-only report fixture').count(), 0);
                    assert.equal(await page.locator('#content a[href="#datasets"], #content a[href="#reports"]').count(), 0);
                    assert.equal(await page.locator('.platform-status-card a[href="#connections/facebook?start=2026-10-15&end=2026-10-15"]').count(), 1);
                }
                if (name === 'connections') {
                    assert.equal(await page.locator('.connection-google').count(), 0);
                    assert.equal(await page.locator('.connection-meta').count(), 1);
                    assert.equal(await page.locator('.connection-provider-grid .connection-source').count(), 3);
                    assert.equal(await page.getByText('Google OAuth và tài sản SEO thuộc client Primary; không hiển thị hoặc dùng trong sandbox này.').count(), 1);
                }
                await measure(name.replaceAll('/', '-'), width, ['overview', 'connections', 'connections/facebook'].includes(name));
            }
            await page.goto('http://admin-ui.test/marketing');
            await page.locator('#marketing-console:not([aria-busy]) #snapshot-id option[value="dataset-fixture"]').waitFor({ state: 'attached' });
            await page.selectOption('#snapshot-id', 'dataset-fixture');
            await page.locator('#resume-form button').first().click();
            await page.locator('#snapshot-preview .meta-review-notice').waitFor();
            await page.waitForLoadState('networkidle');
            assert.equal(await page.locator('#selected-report-open').isVisible(), false);
            assert.equal(await page.locator('#approve-release').isDisabled(), true);
            assert.equal(await page.locator('#publish-final').isDisabled(), true);
            assert.equal(await page.locator('.review-provenance').getAttribute('open'), null);
            assert.equal(await page.locator('.meta-review-notice').isVisible(), true);
            for (const link of await page.locator('.workflow-steps a').all()) {
                const href = await link.getAttribute('href');
                assert.equal(await page.locator(href).count(), 1);
            }
            await measure('marketing', width, true);
        }
        assert.deepEqual(mutations, [], 'Visual QA cannot mutate even fixture state');
        assert.deepEqual(blocked, [], 'All app requests must be explicitly mocked');
        assert.deepEqual(failures, []);
    } finally {
        fs.writeFileSync(path.join(output, 'result.json'), JSON.stringify({ measurements, failures, blocked, mutations }, null, 2));
        await browser.close();
    }
    console.log(JSON.stringify({ status: 'PASS', views: measurements.length, widths: [1440, 1024, 768, 390, 360], liveRequests: 0, mutations: 0, output }));
}
run().catch(error => { console.error(error); process.exitCode = 1; });
