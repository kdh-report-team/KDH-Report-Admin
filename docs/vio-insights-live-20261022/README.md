# VIO Insights — kiểm tra sau khi người dùng báo đã cấp quyền

## Kết quả cuối — đã sync, Dataset chờ human review

Người dùng đã chọn lại Page. Job đầu `b1589509581f925ed3a325f320ea3ef2` bị gián đoạn
khi runtime dừng, không có snapshot. Sau khi người dùng cho phép thêm đúng một lượt,
retry job `5e320fe5250726ec421829fceedcb94f` **succeeded**, 36/100 provider requests.
Sync run `d1cec7997ce5bbd67b693a2eca5ad16e`, 43 records = 28 ngày + 15 bài.
Snapshot `0dd5107c80ab72342a4889d2f59b033f`; receipt hợp lệ, daily rows khớp snapshot.
Không có provider call nào để xem preview, tạo Dataset hoặc browser QA.

Đã chuẩn bị đúng một Dataset mới `a036be96e3977c32cd61541afe37b329`, trạng thái
**awaiting_review**, `can_approve_internal=true`, chưa có latest_review.
Không Candidate, approval, release, publication hoặc grant mới. Hash Bundle
`rpt_4909119771c69125897d8bca84444abe` revision 1 và grants không đổi.

Dữ liệu mới: 15 bài, 81 reactions lifetime, 10 comments lifetime; shares vẫn partial.
Nội dung/tiêu đề/định dạng đủ 15/15 bài: 13 ảnh, 2 album. Bốn metric Page có đủ
28 điểm, hai metric Post có đủ 15/15 bài, tất cả raw measurements available.
Có 4 chuỗi biểu đồ Insights trong contract. Tổng lượt xem/tương tác theo kỳ UTC
vẫn null do ngày Meta kết thúc lúc 07:00 UTC. Unique/follows không cộng.

Các phần còn thiếu: reach/ER/link clicks/CTR/new followers/organic-paid chưa có
contract được nghiệm thu; chủ đề và nhận xét chưa được agency nhập/duyệt.
Permalink chuẩn hóa còn 0/15: bộ lọc URL hiện chỉ chấp nhận đường dẫn khớp Page/Post
số hoặc permalink.php; snapshot không giữ URL raw bị từ chối nên chưa xác định
được dạng URL Meta đã trả. Không gọi lại provider hoặc tạo URL giả để lấp thiếu.
New revision 1 vẫn là dữ liệu cũ 15/80/10; Dataset mới chưa được xuất sang New.

Browser Admin preview + mở đúng Dataset PASS ở 1440 và 390, không JS error/overflow.
Ảnh: `new-admin-preview-1440.png`, `new-admin-preview-390.png`.
Evidence: `retry-result.json`, `retry-persistence.json`, `new-dataset.json`,
`pending-review-check.json`, `new-preview-browser.json`, `final-integrity.json`.

Khôi phục runtime: sau Docker restart, relay lấy động địa chỉ 192.168.0.3 của
Admin, PostgreSQL chuyển từ .2 sang .4. Đã dừng hai relay VIO, khởi động đúng
Admin hiện hữu ở .3 rồi mở lại relay; không recreate database/gateway/ứng dụng.
Relay host lấy .2 nên phép thử pg_ip cũ trỏ chính nó và fail closed. Đã backup
config và cập nhật duy nhất pg_ip kiểm tra cách ly sang địa chỉ PG thực tế .4
ở hai relay VIO, giữ listener/upstream và firewall. PostgreSQL/Internet đều bị
chặn ENETUNREACH, không default route; HTTP8191/8080 healthy. Đây là khôi phục
runtime hiện hữu, không build/deploy image mới. Cấp IP động vẫn có rủi ro lặp khi
Docker restart; chưa thay cấu hình IP cố định của PostgreSQL hoặc stack chính.

Người dùng tiếp tục: vào `/marketing` → Làm mới → Hồ sơ báo cáo → chọn kỳ
21/09–18/10 và mã `a036be96` → Mở, xem dữ liệu/giới hạn rồi quyết định duyệt nội bộ.
Nếu muốn bổ sung chủ đề/nhận xét, phải chuẩn bị Dataset khác chứa nội dung đó,
không sửa Dataset này. Sau human review mới tiếp tục Candidate/source-check/
approval/publication và xác nhận quyền revision mới theo workflow.

## Cập nhật sau OAuth hoàn tất 09:29 ngày 22/10

PERMISSION READY. LIMITED LIVE DIAGNOSTIC PASS. FULL SYNC NOT RUN.

Grant mới đã có read_insights và pages_read_engagement. Connection/account/Page
binding đúng VIO. Callback hiện gọi clear_connections và đặt asset enabled=0;
chưa tự bật lại tài sản. Người dùng cần chọn lại VIO qua giao diện trước full sync.

Đã chạy đúng một diagnostic 15–17/10/2026, ba post ID có trong snapshot VIO đã lưu.
11 provider requests trên giới hạn 20, gồm Page token lookup, 4 metric Page và
2 metric × 3 bài. Không Ads/nguồn khác, không ghi database hoặc tạo sync_run.
Meta trả Page task ANALYZE; cả 10 measurements có status available, không lỗi
permission/token/metric/transport. Chứng cứ `diagnostic.json`, thao tác một lần
được đánh dấu bởi `diagnostic-started.json`; không tự chạy lại script.

| Metric Page | Giá trị tại ba mốc kết thúc ngày Meta |
| --- | --- |
| page_media_view | 131 / 484 / 539 |
| page_total_media_view_unique | 46 / 112 / 193 |
| page_post_engagements | 1 / 17 / 78 |
| page_follows | 12642 / 12644 / 12645 |

Ba mốc lần lượt là 16,17,18/10 lúc 07:00 UTC. Không gán chúng thành tổng kỳ
15–17/10 theo ngày UTC 00:00. Views/engagements giữ period_boundary_mismatch
cho tổng kỳ; unique/follower stock không cộng. Post lifetime đều trả số liệu;
chỉ là giá trị tích lũy tại fetch 22/10, không phải cuối kỳ cũ.

Bước tiếp: `http://localhost:8191/#connections/facebook` → **Tải danh sách Page
được cấp quyền** → VIO Agency `2188688654687066` → **Chọn tài sản**. Không bấm
ngắt/kết nối lại. Sau khi asset enabled và binding vẫn hợp lệ mới thực hiện một
job kỳ 21/09–18/10, ≤100 requests, với raw Insights giữ đúng mốc provider và tổng
UTC chưa xác định vẫn null. Không tự duyệt hoặc sửa revision 1.

## Lần kiểm tra trước khi OAuth hoàn tất (lịch sử)

Ngày 22/10/2026. Chỉ đọc cấu hình và metadata OAuth đã lưu, không gọi Graph.

- VIO Admin 8191: đúng container/image đã triển khai, healthy.
- Client `client_meta_sandbox`, Page `2188688654687066` enabled; connection/account binding khớp.
- Graph version cấu hình `v26.0`.
- Grant VIO vẫn là lần kết nối `2026-10-19T12:57:44.266218+00:00`.
- Scopes VIO: `pages_show_list`, `ads_read`, `pages_read_engagement`,
  `pages_read_user_content`, `public_profile`. **Chưa có read_insights.**
- Admin chính 8090 cũng có scope VIO nhưng grant cũ ngày 16/10 chưa có read_insights.
  Không tìm thấy lần kết nối mới được lưu ở cả hai Admin.
- VIO không còn pending OAuth state; điều này không chứng minh người dùng đã/chưa
  chỉnh quyền trong Meta Developer Dashboard, chỉ phản ánh metadata Admin hiện có.

Diagnostic: NOT RUN. Sync: NOT RUN. Không tạo job/Dataset, không đổi grant/asset,
không sửa revision 1 hoặc review/publication. Không xuất credential.

Bước tiếp theo: người dùng mở `http://localhost:8191/#connections/facebook`, bấm
**Cấp lại quyền qua Meta**, tự chấp thuận đúng Page VIO và để trình duyệt quay về Admin.
Kiểm tra nhãn **Đã lưu quyền read_insights**; nếu lỗi, chỉ gửi nội dung thông báo hoặc
ảnh trang kết nối, không gửi URL callback có code/state hoặc token.

Bằng chứng: `preflight.json`, `oauth-check.json`.
