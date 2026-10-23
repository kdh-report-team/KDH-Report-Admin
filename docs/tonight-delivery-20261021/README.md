# Facebook Content — bàn giao kỹ thuật, cập nhật 22/10/2026

**CODE READY / DEPLOYED. PERMISSION NOT READY / LIVE INSIGHTS NOT RUN.**
Đã nghiệm thu trình duyệt cho báo cáo cũ revision 1. Chưa nghiệm thu báo cáo mới
chứa Insights vì grant thực tế vẫn thiếu `read_insights`; chưa sync hoặc tạo Dataset mới.

## Runtime

| Dịch vụ | URL | Image | Kết quả |
| --- | --- | --- | --- |
| Admin VIO | http://localhost:8191/marketing | `kdh-admin-meta:insights-20261021-cf97123433e7` | Healthy, preview 7 mục PASS |
| New chung | http://127.0.0.1:8080 | `kdh-new:tonight-content-20261021-80351dfaa44b` | Healthy, VIO handoff PASS |
| Admin chính | http://localhost:8090 | Giữ image trước | Docker tự bật lại; relay chính đang restart loop |
| Mock tham chiếu | http://127.0.0.1:8082/report/social | Giữ image trước | Không dùng làm nguồn dữ liệu |

Container Admin: `kdh-meta-2b-admin-20261016-132836-5c512a53`.
Container New: `kdh-report-new-app-1`.
ID/image/mount/network: [deployment.json](deployment.json).
Đối chiếu source hiện hành: [source-verification.json](source-verification.json).
12 file runtime Admin và 19 file New khớp hash source local được build.

Ngày 22/10, Docker Engine đang tắt; đã mở Docker Desktop. Các container tự bật theo
restart policy. Admin chính chuyển từ stopped sang running, không đổi image/config.
Relay chính `kdh-shared-viewer-primary-relay` restart loop; thử stop/start chính relay
không khắc phục. Chưa xác định lỗi nội bộ vì container không lưu log; không nới isolation
hoặc sửa listener. Nhánh chính 8090 → New chưa được xác nhận. Nhánh VIO vẫn PASS.
Default Docker bridge đổi ID sau Engine restart, policy không đổi; các mạng dự án giữ nguyên.

## Phần hoàn thiện

- Giữ 7 mục, bổ sung chart bài theo ngày và nội dung/link có bằng chứng trong Admin preview.
- Collector tách Posts/Insights; thiếu Insights không chặn đọc Content cơ bản.
- Một job Content bị giới hạn 100 provider requests, gồm retry/phân trang.
- Chuỗi partial giữ zero thật và null; không tạo tổng kỳ từ dữ liệu thiếu.
- New kiểm tra raw/projection identity, Page, kỳ, timezone, metric, permission/task
  và provenance trước khi ánh xạ. Không tính lại KPI nghiệp vụ.
- New nhận trạng thái/lý do thiếu, biểu đồ và chỉ nhận xét đã được duyệt từ Admin.
  Giữ giao diện sẵn có và đường đọc tương thích revision cũ.
- Nhận xét/chủ đề mới cần Dataset mới và quyết định duyệt của người dùng.

Collector hiện có: `page_media_view`, `page_total_media_view_unique`,
`page_post_engagements`, `page_follows` (day); `post_media_view`,
`post_total_media_view_unique` (lifetime). Unique không cộng qua ngày/bài;
follows stock không diễn giải thành follower mới; whole-Page engagement không
đồng nghĩa tương tác phát sinh riêng trên nhóm bài trong kỳ.
Reach/ER/new followers/link clicks/paid-organic còn thiếu contract hoặc metric được
xác minh; không thay bằng views, Ads hay dữ liệu giả. Catalog và giới hạn tài liệu:
[Insights](../FACEBOOK_CONTENT_INSIGHTS_20261021.md).

## Kiểm thử

| Nhóm | PASS | FAIL cuối | SKIP | Phạm vi |
| --- | ---: | ---: | ---: | --- |
| Admin offline | 419 | 0 | 146 | Các test PostgreSQL tách sang DB disposable |
| PostgreSQL disposable | 146 | 0 | 0 | Bao gồm 141 test trước đây SKIP và 5 test mới |
| Admin UI | 102 | 0 | 0 | JSDOM, preview và quyền |
| Admin exact image | 78 | 0 | 0 | Nhóm offline liên quan, network none |
| New exact image | 317 | 0 | 0 | Contract, mapper, ACL/handoff, revision cũ |
| Browser fixture | 10 viewport | 0 | 0 | Admin/New tại 1440,1024,768,390,360; fixture không vào runtime nghiệp vụ |
| Browser VIO thật | PASS | 0 | — | Preview đã lưu → revision 1, desktop/mobile |
| Insights diagnostic/sync | NOT RUN | — | — | Thiếu read_insights |

Các lần test lỗi đã được xử lý, không xóa bằng chứng: chạy unittest trực tiếp từng
nạp `.env` workspace sai fixture scope; bộ chạy offline cô lập đã đạt. UI harness
thiếu dependency chart đã sửa. New image test cần mount thư mục scripts chỉ đọc.
Test PostgreSQL dùng ID bài fixture không đúng dạng số đã sửa fixture. Lần chụp
mobile đầu trúng CSS transition; đã chờ drawer đóng rồi chụp lại, không sửa CSP.
Lần kiểm tra browser dùng wait_for_function gặp CSP đã đổi cách chờ bằng bounding box;
không bật unsafe-eval. JS syntax và git diff --check hai repository PASS.

Gates: [acceptance-gates.json](acceptance-gates.json),
[browser.json](admin/browser.json), [browser observations](admin/browser-observations.json).
Business hash VIO không đổi; không provider calls, migration, Dataset/review/publication/grant mới.

## Báo cáo và ảnh thực tế

Report `rpt_4909119771c69125897d8bca84444abe`, revision **1**, status provisional.
Mở từ Admin qua handoff hợp lệ, sau đó:
http://127.0.0.1:8080/reports/rpt_4909119771c69125897d8bca84444abe?revision=1

Đối chiếu thật: 15 bài, 80 reactions lifetime, 10 comments lifetime;
engagements null/no_data; shares null/partial, 7/15 bài; UTC.
Sai revision/no grant bị chặn, sai origin bị chặn, logout PASS.
Không lấy các số này hardcode cho báo cáo mới.

- [Admin 1440](admin/admin-preview-real-1440.png), [Admin 390](admin/admin-preview-real-390.png).
- [New 1440](admin/new-report-real-1440.png), [New 390](admin/new-report-real-390.png).
- [Quyền Meta hiện hành](admin/insights-permission-1440.png).

## Backup, rollback và Git

Backup database/appdata và cấu hình runtime được mã hóa dưới
`%LOCALAPPDATA%/KDH-Tonight-Delivery-20261021`, khóa được bảo vệ bằng DPAPI.
Dump đã xác minh giải mã, định dạng PGDMP và pg_restore --list; không thực hiện
restore mới vào DB nghiệp vụ. Không có migration. Không in secrets.
Container trước triển khai giữ stopped/restart=no để rollback ứng dụng:

- `kdh-meta-2b-admin-20261016-132836-5c512a53-before-tonight-20261021`.
- `kdh-report-new-app-1-before-tonight-content-20261021`.

Rollback phải khôi phục đúng cấu hình/image ứng dụng và startup manifest; không
restore/reset PostgreSQL hoặc thay Bundle. Không tự chạy rollback khi VIO smoke PASS.
Admin HEAD `6b52ee2f3ef29ebb5820e95e88ba318a7599667d`, New HEAD
`1e3df3c7f4a93576ad2599ceee99c1958e7cc636`, không đổi branch/commit/push.
Working tree và file ngoài phạm vi giữ nguyên. Chi tiết file runtime trong
[Admin manifest](admin/build.json) và [New manifest](new-build.json).

## Bước tiếp theo

1. Người dùng cấu hình quyền read_insights trong Facebook Login for Business nếu cần,
   mở http://localhost:8191/#connections/facebook → **Cấp lại quyền qua Meta**,
   tự đăng nhập/chấp thuận và báo hoàn tất. Không gửi token/secret.
2. Kiểm tra lại grant lưu trữ, Page task và scope VIO. Nếu hợp lệ, diagnostic ≤20 requests,
   1–3 ngày đã kết thúc, tối đa 3 bài. Diagnostic không được coi là sync.
3. Nếu diagnostic PASS và metric hỗ trợ kỳ đã chọn, chạy tối đa một Content job
   2026-09-21 → 2026-10-18, tổng ≤100 requests. Không lặp/backfill/Ads/Page khác.
4. Kiểm tra persistence/receipt, chuẩn bị Dataset phù hợp, để người dùng xem và duyệt.
   Không dùng approval cũ cho dữ liệu mới; quyền revision mới phải được xác nhận riêng.
5. Sau khi có bản phát hành/quyền hợp lệ mới, nghiệm thu Admin → New với chính revision đó.

Chưa tuyên bố hoàn thành báo cáo Insights thật chỉ dựa trên fixture hoặc revision 1 cũ.
