"""Admin-owned Facebook presentation contract, built only from saved observations.

Missing Insights are explicit requirements, never inferred from Ads or lifetime
counters. Editorial content is frozen with the Dataset and reviewed with it.
"""
import copy
from collections import Counter
from urllib.parse import parse_qs, urlencode, urlsplit

from .core import Problem
from .meta_contract import metrics

VERSION = 'facebook-content-report-v1'
SECTIONS = {
    'overview': 'Kết quả tổng quan', 'formats': 'Phân bổ định dạng nội dung',
    'topics': 'Hiệu quả theo chủ đề', 'posts': 'Hiệu quả bài đăng',
    'engagement': 'Cấu trúc tương tác trong kỳ', 'reach': 'Tiếp cận tự nhiên và trả phí',
    'insights': 'Nhận định và đề xuất',
}
FORMAT_LABELS = {'photo': 'Ảnh', 'album': 'Album ảnh', 'video': 'Video',
                 'link': 'Liên kết', 'unknown': 'Chưa xác định'}


def canonical_post_url(value, post_id):
    """Accept a canonical Facebook URL for this exact Page/Post; strip trackers."""
    if not isinstance(value, str) or '_' not in post_id:
        return None
    page, post = post_id.split('_', 1)
    try:
        url = urlsplit(value)
        if (url.scheme != 'https' or url.hostname not in ('facebook.com', 'www.facebook.com', 'm.facebook.com')
                or url.username or url.password or url.port not in (None, 443)):
            return None
        if url.path.rstrip('/') == f'/{page}/posts/{post}':
            return f'https://www.facebook.com/{page}/posts/{post}'
        query = parse_qs(url.query)
        if url.path == '/permalink.php' and query.get('id') == [page] and query.get('story_fbid') == [post]:
            return 'https://www.facebook.com/permalink.php?' + urlencode({'story_fbid': post, 'id': page})
    except ValueError:
        pass
    return None


def post_metadata(item, post_id):
    """Copy bounded text and explicit attachment types; never guess Reels/topics."""
    message = item.get('message')
    message = message[:10000] if isinstance(message, str) and message.strip() else None
    attachments = item.get('attachments')
    rows = attachments.get('data', []) if isinstance(attachments, dict) else []
    types = {r.get('type') for r in rows if isinstance(r, dict) and isinstance(r.get('type'), str)}
    kind = next(iter(types)) if len(types) == 1 else None
    formats = {'photo': 'photo', 'album': 'album', 'video_inline': 'video',
               'video_autoplay': 'video', 'video': 'video', 'share': 'link'}
    return {'message': message, 'title': message[:180] if message else None,
            'permalink_url': canonical_post_url(item.get('permalink_url'), post_id),
            'format': formats.get(kind), 'format_source': kind,
            'title_source': 'message_excerpt' if message else None}


def editorial_input(value, entries):
    if value is None:
        return {'notes': {}, 'topics': {}}
    if not isinstance(value, dict) or set(value) - {'notes', 'topics'}:
        raise Problem('Nội dung biên tập không hợp lệ.', 400, 'content_editorial_invalid')
    notes, topics = value.get('notes', {}), value.get('topics', {})
    ids = {r['post_id'] for r in entries}
    if (not isinstance(notes, dict) or set(notes) - set(SECTIONS)
            or not isinstance(topics, dict) or set(topics) - ids
            or len(topics) > 2000):
        raise Problem('Chủ đề/nhận xét không thuộc báo cáo này.', 400, 'content_editorial_scope')
    for values, limit in ((notes, 2000), (topics, 120)):
        if any(not isinstance(v, str) or not v.strip() or len(v) > limit for v in values.values()):
            raise Problem('Nội dung biên tập trống hoặc quá dài.', 400, 'content_editorial_invalid')
    return {'notes': {k: v.strip() for k, v in notes.items()},
            'topics': {k: v.strip() for k, v in topics.items()}}


def build_content_report(payload, editorial=None):
    """Deterministic projection. This function performs no I/O and no approval."""
    entries = payload.get('entries', [])
    edit = editorial_input(editorial, entries)
    measured = metrics(payload)
    scopes = payload.get('provenance', {}).get('permissions', [])
    insights_reason = ('Thiếu quyền read_insights trong lần thu thập; adapter chưa thu thập Page/Post Insights.'
                       if 'read_insights' not in scopes else
                       'Adapter chưa thu thập Page/Post Insights; cần nghiệm thu metric và kỳ trên Graph API hiện hành.')
    if payload.get('insights'):
        from .meta_content_insights import REASONS
        observed_status = payload['insights'].get('status')
        insights_reason = (REASONS.get(observed_status) or
                           'Đã thu thập Insights riêng; chỉ số này chưa có equivalent cùng định nghĩa và phạm vi.')
    def block(key, reason, rows=None, status='unsupported'):
        return {'key': key, 'label': SECTIONS[key], 'status': status, 'reason': reason, 'rows': rows or []}

    def distribution(field, labels=None):
        counts = Counter(r.get(field) or 'unknown' for r in posts)
        return [{'key': key, 'label': (labels or {}).get(key, key) if key != 'unknown' else 'Chưa phân loại',
                 'count': count, 'percent': round(100 * count / len(posts), 2),
                 'reach': None, 'engagement_rate': None}
                for key, count in sorted(counts.items())]

    posts = [{k: copy.deepcopy(r.get(k)) for k in ('post_id', 'date', 'title', 'message',
              'permalink_url', 'format', 'reactions_lifetime', 'comments_lifetime', 'shares_lifetime')}
             for r in entries]
    for row in posts:
        row.update(topic=edit['topics'].get(row['post_id']), reach=None, engagements=None,
                   engagement_rate=None, link_clicks=None)
        row['permalink_url'] = canonical_post_url(row['permalink_url'], row['post_id'])
    sections = {
        'overview': block('overview', 'Chỉ số lifetime được tách riêng; không thay thế tương tác trong kỳ.', status='partial'),
        'formats': block('formats', 'Chưa có định dạng trong snapshot; không suy đoán Reels từ video.'),
        'topics': block('topics', 'Chưa phân loại chủ đề. Meta không cung cấp taxonomy nghiệp vụ của agency.'),
        'posts': block('posts', 'Reach, ER và click chưa được thu thập; ô thiếu giữ nguyên null.', posts,
                       'partial' if posts else 'no_data'),
        'engagement': block('engagement', insights_reason + ' Không cộng lifetime thành tương tác trong kỳ.'),
        'reach': block('reach', 'Chưa có bộ metric reach organic/paid tương đương được xác minh trên v26; không thay bằng impressions hoặc Ads.'),
        'insights': block('insights', 'Chưa có nhận xét do người phụ trách nhập và duyệt.'),
    }
    for key, field, labels in (('formats', 'format', FORMAT_LABELS), ('topics', 'topic', None)):
        known = sum(bool(r.get(field)) for r in posts)
        if known:
            sections[key].update(status='available' if known == len(posts) else 'partial', rows=distribution(field, labels),
                                 reason='Phân bố số bài; chưa có reach/ER theo nhóm.',
                                 coverage={'available': known, 'expected': len(posts), 'unit': 'posts'})
    for key, note in edit['notes'].items():
        sections[key]['commentary'] = {'text': note, 'origin': 'editorial', 'status': 'pending_review'}
    if edit['notes']:
        sections['insights'].update(status='pending_review', reason='Nhận xét đang chờ duyệt cùng Dataset.')
    requirements = [dict(m, reason='' if m['value'] is not None else
                        'Chưa có đủ bộ đếm từng bài.' if m['key'].endswith('_lifetime') else insights_reason)
                    for m in measured]
    if payload.get('insights'):
        for m in requirements:
            if m['key'] == 'engagements' and m['value'] is None:
                m['reason'] = ('Chưa có tương tác phát sinh theo ngày UTC của nhóm bài trong kỳ. '
                               'Page Insights đo toàn Page, không thay thế chỉ số này.')
    for key, label, reason in (
        ('reach', 'Lượt tiếp cận', insights_reason + ' Unique viewers mới cần xác minh tương đương và kỳ; không cộng unique theo ngày.'),
        ('engagement_rate', 'Tỷ lệ tương tác (ER)', 'Cần tương tác và reach cùng phạm vi, kỳ, định nghĩa; Admin chưa đủ đầu vào để tính.'),
        ('followers_gained', 'Người theo dõi mới', insights_reason + ' Phân biệt follows mới, unfollows và tổng followers.'),
        ('link_clicks', 'Lượt nhấp liên kết', insights_reason + ' Cần xác minh click loại link trên v26.'),
        ('ctr', 'CTR', 'Chưa đủ click và mẫu số đã thống nhất; không tự lấy CTR quảng cáo.'),
        ('response_rate', 'Tỷ lệ phản hồi tin nhắn', 'Ngoài contract Content hiện tại; chưa có nguồn và định nghĩa được nghiệm thu.')):
        requirements.append({'key': key, 'label': label, 'value': None, 'status': 'unsupported', 'reason': reason})
    result = {'schema_version': VERSION, 'source': 'facebook_content',
            'identity': copy.deepcopy(payload.get('identity', {})),
            'period': {'start': payload['requested_start'], 'end': payload['requested_end']},
            'timezone': payload.get('timezone'), 'fetched_at': payload.get('fetched_at'),
            'comparison': {'status': 'unsupported', 'reason': 'Meta contract hiện chỉ hỗ trợ một kỳ; chưa có snapshot kỳ so sánh.'},
            'metrics': requirements, 'sections': sections, 'editorial': edit,
            'daily_posts': [{'date': r['date'], 'posts_published': r.get('posts_published')} for r in payload.get('daily', [])],
            'review_status': 'pending_review'}
    if 'insights' in payload:
        from .meta_content_insights import project
        result['insights'] = project(payload['insights'])
        for row in result['sections']['posts']['rows']:
            for metric in ('post_media_view', 'post_total_media_view_unique'):
                found = next((m for m in result['insights'].get('measurements', [])
                              if m['object_id'] == row['post_id'] and m['metric'] == metric), None)
                row[metric + '_lifetime'] = found['value'] if found else None
    return result


def approved_content_report(report):
    """Called only inside the existing authorized release transaction."""
    result = copy.deepcopy(report)
    result['review_status'] = 'approved'
    for section in result['sections'].values():
        if section.get('commentary'):
            section['commentary']['status'] = 'approved'
    if result['sections']['insights']['status'] == 'pending_review':
        result['sections']['insights'].update(status='available', reason='Nhận xét đã duyệt cùng bản phát hành.')
    return result
