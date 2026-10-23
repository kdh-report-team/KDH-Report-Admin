# Facebook Content / Insights — deployment 21/10/2026

Admin VIO đã cập nhật và healthy tại http://localhost:8191.

| Thành phần | Trạng thái |
| --- | --- |
| Admin collector + 7 mục + preview/editorial | CODE READY / DEPLOYED |
| Page/Post Insights permission | NOT READY: grant chưa có read_insights |
| Insights live diagnostic hoặc sync | NOT RUN |
| New Insights mapper mới | Chưa triển khai, giữ nguyên theo yêu cầu |
| Báo cáo VIO revision 1 hiện hữu qua New 8080 | Browser E2E PASS |
| Admin chính 8090, mock 8082, New 8080 | Không thay container/image/config/trạng thái |

## Image và scope

- Admin HEAD: `6b52ee2f3ef29ebb5820e95e88ba318a7599667d`, branch main với local changes được giữ.
- Image: `kdh-admin-meta:insights-20261021-cd9a3b495991`.
- Image ID: `sha256:6eab0f453566cd574acc6072ed83fbbda2a05540a2affc6c2ccd1774a30bf77b`.
- Container: `kdh-meta-2b-admin-20261016-132836-5c512a53`.
- 12 file runtime trong `build.json`; SHA256 của source đang chạy khớp image và source đã test (`source-verification.json`).
- Không thay dependencies hoặc migrations. Giữ env/OAuth, volume, static IP, không publish host port Admin; relay vẫn publish loopback8191.
- `JOB_MODE=request`; trước deploy không có job queued/running hoặc schedule enabled.
- New HEAD đọc lại `1e3df3c7f4a93576ad2599ceee99c1958e7cc636`; không chỉnh source/runtime New trong lượt này.

## Kiểm thử và bằng chứng

- `image-tests.log`: 78 backend PASS, 0 SKIP, chạy đúng image với network none và không mount DB nghiệp vụ.
- `ui-tests.log`: 102 UI PASS, 0 FAIL/SKIP.
- JS syntax và `git diff --check`: PASS.
- PostgreSQL integration đã PASS trước build trên disposable DB: 141 test từng skip và 5 test Insights/OAuth mới; xem báo cáo Insights chính. Không chạy các test ghi DB trên sandbox.
- `browser.json`: login/canonical host, Insights permission UI, handoff report revision1, wrong revision/no grant/wrong origin và logout PASS.
- Metrics giữ 15 posts, 80 reactions lifetime, 10 comments lifetime; engagements null/no_data, shares null/partial coverage7/15; UTC.
- `insights-permission-1440.png`, `existing-report-1440.png`: ảnh browser thật.
- Browser cuối không có request bị chặn hoặc lỗi JS. Lượt QA đầu đổi hash trước khi login bootstrap xong, gây lỗi null client_context; đã sửa automation để đợi sidebar/overview rồi chuyển trang. Không sửa ứng dụng nhằm che lỗi này. Bằng chứng lần đầu được giữ tại `browser-before-bootstrap-wait.json`.
- Hash toàn bộ bảng nghiệp vụ (gồm jobs, Dataset, grant, Bundle) không đổi; loại trừ bảng phiên/event/handoff phục vụ đăng nhập hợp lệ. Không gọi provider hoặc tạo dữ liệu báo cáo.

## Backup và rollback

- Fresh pg_dump custom + appdata tar mã hóa Fernet; key bảo vệ Windows DPAPI tại `%LOCALAPPDATA%/KDH-Content-Insights-Deploy-20261021`.
- Đã đọc lại/decrypt đối chiếu backup và chạy pg_restore --list. Không rehearsal restore mới trong lượt deploy này; không có migration. Thông tin hash trong `prepared.json`.
- Container rollback: `kdh-meta-2b-admin-20261016-132836-5c512a53-before-insights-20261021`, dừng và restart=no.
- Hai lần thử đầu tự rollback do script đối chiếu Docker: thuộc tính tùy chọn vắng mặt và DNS []/null tương đương. Chưa khởi động image mới ở hai lần đó; thông tin giữ trong first/second-attempt-rollback.json. Lần cuối PASS.
- Rollback app-only qua `python ops/deploy_content_insights.py rollback`, chỉ sau khi xác minh không có deploy mới hơn; không restore/reset database. Khôi phục startup manifest cũ cùng identity container.
- Script `ops/check_content_insights_deploy.py` kiểm tra read-only/phiên, không sync/reconnect/review/publish.

## Bước tiếp theo

Mở Admin → Kết nối nền tảng → Facebook. Quản trị ứng dụng Meta cần kiểm tra
Facebook Login for Business cho phép yêu cầu `read_insights`, sau đó người dùng
tự bấm **Cấp lại quyền qua Meta** và chấp thuận. Không dùng nút Ngắt kết nối.
Chưa có quyền mới thì đọc bài viết cơ bản vẫn hoạt động, Insights không giả thành 0.

Sau khi quyền và Page task hợp lệ mới chạy diagnostic đã giới hạn theo yêu cầu
trước; chưa tự sync đầy đủ. Revision1 không được bổ sung dữ liệu âm thầm. Dữ liệu
mới cần snapshot/Dataset và human review mới. New mapper Insights cần bàn giao
riêng sau khi chủ phiên đang làm New cho phép tiếp tục.
