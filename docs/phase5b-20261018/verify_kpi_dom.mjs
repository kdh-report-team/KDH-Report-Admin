// Render the deployed, hash-matched KPI action with the real read-only response.
// No provider discovery, browser navigation, cookie or network access in this test.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';
import { JSDOM } from 'jsdom';

const here = new URL('./', import.meta.url);
const payload = JSON.parse(await fs.readFile(new URL('content-kpi-response.json', here), 'utf8'));
const source = await fs.readFile(new URL('../../static/app.js', here), 'utf8');
const start = source.indexOf("case 'meta-view-kpis': {");
const end = source.indexOf("case 'connect-facebook':", start);
assert.ok(start > 0 && end > start);
const action = source.slice(start, end);
const dom = new JSDOM('<input id="meta-sync-start" value="2026-09-19"><input id="meta-sync-end" value="2026-10-16"><dialog id="modal"></dialog>', {
  url: 'http://localhost:8191/', runScripts: 'outside-only'
});
dom.window.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
dom.window.HTMLDialogElement.prototype.close = function () { this.open = false; };
const context = dom.getInternalVMContext();
const ui = new vm.SourceTextModule(await fs.readFile(new URL('../../static/ui.js', here), 'utf8'), { context });
const module = new vm.SourceTextModule(`
import { esc, date, time, num, icon, badge, empty, button, notice, modal, toast, table, chart, barChart } from './ui.js';
const $ = selector => document.querySelector(selector);
export async function run(id, data) {
  const api = async path => {
    if (path !== '/meta/reporting/kpis/' + id + '?start=2026-09-19&end=2026-10-16') throw new Error('Unexpected API');
    return data;
  };
  switch ('meta-view-kpis') { ${action} }
}`, { context });
try {
  await module.link(() => ui);
  await module.evaluate();
  await module.namespace.run(payload.asset_id, payload);
  const modal = dom.window.document.querySelector('#modal');
  const [posts, engagement] = modal.querySelectorAll('.meta-kpi-card');
  assert.equal(posts.querySelector('h2').textContent, '14');
  assert.match(posts.textContent, /Số ngày có dữ liệu:\s*28\s*\/\s*28/);
  assert.equal(engagement.querySelector('h2').textContent, '—');
  assert.match(engagement.textContent, /no_data/);
  assert.match(engagement.textContent, /Tương tác phát sinh trong kỳ chưa có dữ liệu theo ngày từ Meta/);
  assert.match(engagement.textContent, /Số ngày có dữ liệu:\s*0\s*\/\s*28/);
  assert.match(modal.textContent, /Dữ liệu Meta chưa được xác minh độc lập/);
  assert.match(modal.textContent, /Không sử dụng làm bằng chứng báo cáo chính thức/);
  assert.doesNotMatch(modal.textContent, /\bVerified\b|\bPublishable\b|Đã xác minh|Đủ điều kiện phát hành/);
  assert.equal(modal.querySelector('.meta-snapshot-kpi'), null);
  const result = { status: 'PASS', input: 'actual sandbox read-only KPI response', renderer: 'deployed hash-matched KPI action in JSDOM',
    displayed_posts: 14, daily_coverage: '28/28', period_engagement: 'no_data / —', engagement_coverage: '0/28',
    unverified_banner: true, historical_lifetime_not_fabricated: true, provider_requests: 0, full_browser_e2e: 'NOT TESTED' };
  await fs.writeFile(new URL('kpi-dom.json', here), JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify(result));
} finally {
  dom.window.close();
}
