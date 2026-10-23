import { chart } from './ui.js';

const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const status = value => ({ available: 'Có dữ liệu', partial: 'Thiếu một phần', no_data: 'Chưa có dữ liệu', unsupported: 'Chưa hỗ trợ', pending_review: 'Chờ duyệt' })[value] || value;

export const contentSections = { overview: 'Kết quả tổng quan', formats: 'Phân bổ định dạng', topics: 'Chủ đề nội dung', posts: 'Hiệu quả bài đăng', engagement: 'Tương tác trong kỳ', reach: 'Tiếp cận tự nhiên và trả phí', insights: 'Nhận định & đề xuất' };

export function contentReportHtml(report) {
    if (!report || report.schema_version !== 'facebook-content-report-v1') return '';
    const cell = value => esc(value == null ? 'Chưa có dữ liệu' : value);
    const postLink = row => {
        try {
            const url = new URL(row.permalink_url);
            const [page, post] = row.post_id.split('_');
            if (page !== report.identity?.external_id || url.protocol !== 'https:' || url.hostname !== 'www.facebook.com' || url.username || url.password) return '';
            if (url.pathname !== `/${page}/posts/${post}` && !(url.pathname === '/permalink.php' && url.searchParams.get('id') === page && url.searchParams.get('story_fbid') === post)) return '';
            return `<a href="${esc(url.href)}" target="_blank" rel="noopener noreferrer">Xem bài trên Facebook ↗</a>`;
        } catch { return ''; }
    };
    const postDetails = (report.sections.posts?.rows || []).filter(r => r.message || r.permalink_url);
    return `<h2>Phạm vi báo cáo Facebook Content</h2><p>${esc(report.period.start)} → ${esc(report.period.end)} · ${esc(report.timezone)}</p>
        ${report.daily_posts?.length ? `<h3>Nhịp đăng bài · UTC</h3>${chart(report.daily_posts, 'posts_published', 'blue', report.period.start, report.period.end)}` : ''}
        <div class="workflow-table"><table><thead><tr><th>Chỉ số</th><th>Giá trị</th><th>Trạng thái và điều kiện còn thiếu</th></tr></thead><tbody>${report.metrics.map(m => `<tr><td>${esc(m.label)}</td><td>${cell(m.value)}</td><td>${esc(status(m.status))}${m.reason ? `<br>${esc(m.reason)}` : ''}</td></tr>`).join('')}</tbody></table></div>
        ${Object.values(report.sections).map(s => `<details class="review-provenance"><summary>${esc(s.label)} · ${esc(status(s.status))}</summary><p>${esc(s.reason)}</p>${s.commentary ? `<p><strong>Nhận xét của người phụ trách:</strong> ${esc(s.commentary.text)}</p>` : '<p>Chưa nhập nhận xét cho mục này.</p>'}${s.rows.length ? `<div class="workflow-table"><table><thead><tr>${(s.key === 'posts' ? ['Bài đăng', 'Ngày (UTC)', 'Định dạng', 'Chủ đề', 'Cảm xúc tích lũy', 'Bình luận tích lũy', 'Chia sẻ tích lũy'] : ['Nhóm', 'Số bài', 'Tỷ trọng (%)']).map(c => `<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${s.rows.map(r => `<tr>${(s.key === 'posts' ? [r.title || r.post_id, r.date, r.format, r.topic, r.reactions_lifetime, r.comments_lifetime, r.shares_lifetime] : [r.label, r.count, r.percent]).map(v => `<td>${cell(v)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>` : ''}</details>`).join('')}
        ${report.insights ? `<details class="review-provenance"><summary>Page/Post Insights · ${esc(status(report.insights.status))}</summary><p>Số đo giữ nguyên mốc end_time của Meta. Chỉ công bố tổng kỳ khi ranh giới ngày khớp UTC.</p><div class="workflow-table"><table><thead><tr><th>Metric / tài sản</th><th>Kỳ đo</th><th>Giá trị tổng hợp</th><th>Trạng thái</th></tr></thead><tbody>${report.insights.measurements.map(m => `<tr><td>${esc(m.label)}<br>${esc(m.object_id)}</td><td>${esc(m.period)}</td><td>${cell(m.value)}</td><td>${esc(m.report_status)}<br>${esc(m.reason)}</td></tr><tr><td colspan="4">${m.values.map(p => `${esc(p.end_time || 'Tại thời điểm lấy dữ liệu')}: ${cell(p.value)}`).join(' · ')}</td></tr>`).join('')}</tbody></table></div></details>` : ''}
        ${postDetails.length ? `<details class="review-provenance"><summary>Nội dung và liên kết bài đăng</summary>${postDetails.map(r => `<article><h3>${esc(r.title || r.post_id)}</h3><p>${esc(r.message || 'Bài đăng không có nội dung văn bản trong nguồn.')}</p>${postLink(r)}</article>`).join('')}</details>` : ''}
        <p>${esc(report.comparison.reason)}</p>`;
}

export function editorialFields() {
    return Object.entries(contentSections).map(([key, title]) => `<label>${esc(title)}<textarea data-content-note="${key}" maxlength="2000" rows="2" placeholder="Nhận xét và hướng triển khai cho khách hàng"></textarea></label>`).join('');
}

export function topicFields(report) {
    return report.sections.posts.rows.map(row => `<label>${esc(row.title || row.post_id)}<input data-content-topic="${esc(row.post_id)}" maxlength="120" placeholder="Chủ đề do agency phân loại"></label>`).join('');
}

export function readEditorial(root) {
    const collect = (selector, key) => Object.fromEntries([...root.querySelectorAll(selector)].filter(el => el.value.trim()).map(el => [el.dataset[key], el.value.trim()]));
    return { notes: collect('[data-content-note]', 'contentNote'), topics: collect('[data-content-topic]', 'contentTopic') };
}
