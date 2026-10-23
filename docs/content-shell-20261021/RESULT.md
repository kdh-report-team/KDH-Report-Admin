# Facebook Content dùng chung sườn New — 21/10/2026

Đã triển khai và kiểm tra trên New dùng chung cổng 8080. Báo cáo thật dùng
`pages/facebook_content/index.html` và các partial của sườn gốc, thay vì nhánh
template `partials/bundle.html` riêng cho VIO.

## Kết quả giao diện

- Giữ sidebar, header, kiểu thẻ KPI, bố cục biểu đồ và bảng của sườn.
- Chỉ hiện KPI có giá trị hợp lệ; số 0 hợp lệ vẫn hiển thị.
- Ẩn khối và mục menu chưa có dữ liệu. Không dựng số thay thế hoặc suy diễn KPI.
- VIO revision 1 hiển thị 15 bài, 80 cảm xúc tích lũy, 10 bình luận tích lũy.
- Engagements `null/no_data` và tổng shares `null/partial` được giữ nguyên trong
  dữ liệu, không hiển thị thành thẻ tổng. Shares từng bài vẫn hiện khi có giá trị;
  ô thiếu trong cột có dữ liệu một phần tiếp tục ghi “Chưa có dữ liệu”.
- Biểu đồ dùng chuỗi bài đăng đã lưu; bảng giữ link Facebook của đúng bài đăng.
- Phạm vi lifetime, timezone UTC và chất lượng dữ liệu vẫn xem được.
- Sườn preview rỗng vẫn giữ đầy đủ các vị trí để xem thiết kế.

## File của New được sửa trong lượt này

- `app/mappers/dashboard.py`
- `templates/pages/facebook_content/index.html`
- `templates/pages/facebook_content/partials/kpis.html`
- `templates/pages/facebook_content/partials/formats.html`
- `templates/pages/facebook_content/partials/topics.html`
- `templates/pages/facebook_content/partials/posts.html`
- `templates/pages/facebook_content/partials/reach_mix.html`
- `templates/pages/facebook_content/partials/insights.html`
- `templates/components/dashboard/navigation.html`
- `static/css/pages/facebook-content.css`
- `tests/test_vio_content.py`
- `compose.shared.yaml` — image hiện hành và IP Viewer cố định trên hai mạng đã có.

Không thay mapper tính KPI chính thức, dữ liệu Bundle, grants hoặc API xác thực.

## Validation

| Kiểm tra | Kết quả |
|---|---|
| New Python suite | 292 PASS, không SKIP |
| Focused Content/dashboard sau điều chỉnh | 38 PASS |
| Admin npm UI suite | 100 PASS, không SKIP |
| JS syntax snapshot.js / charts.js | PASS |
| git diff --check cả hai repository | PASS |
| Render image offline, không mạng | PASS |
| Admin VIO login → handoff → New report revision 1 | PASS |
| Sai origin / revision / không grant / khác môi trường | DENIED đúng |
| Responsive 1440, 1024, 768, 390, 360 | PASS |
| Hash bảng nghiệp vụ của hai Admin | Không đổi |

Ảnh: `report-1440.png`, `report-1024.png`, `report-768.png`, `report-390.png`,
`report-360.png`. Kết quả máy: `browser.json`, `final-health.json`.
Không truy cập provider hoặc tạo Dataset/Bundle/review/approval/grant.
Các phiên đăng nhập kiểm thử đã logout.

## Deployment và sự cố đã xử lý

Container hiện hành: `kdh-report-new-app-1`.
Image: `kdh-new:content-shell-20261021-0c7aaa9bea7c`.
ID image/container chính xác xem `responsive-release/deployment.json`.
Image chỉ overlay các file giao diện được liệt kê trong manifest; không chứa secrets.

Lần cập nhật mobile đầu đã rollback khi relay Admin chính dừng. Kiểm tra cho thấy
New dùng IP động, nhận IP dành cho relay khi relay không chạy. Đồng thời phép thử
chặn DB của relay còn dùng địa chỉ DB cũ, trùng IP interface hiện tại của relay.

Đã giữ nguyên hai mạng nội bộ và giới hạn egress, cố định New ở
`192.168.144.3` / `192.168.96.3`; relay chính vẫn nghe `192.168.144.2:8090`
và chỉ forward `172.26.0.3:8090`. Cập nhật duy nhất `pg_ip` của phép thử từ
địa chỉ cũ sang DB đã inspect: `172.26.0.4`. Không đổi container/volume/config DB.
Cấu hình relay cũ đã lưu mã hóa DPAPI ngoài Git. Nếu topology DB thay đổi về sau,
cần revalidate phép thử theo IP thực tế; không tắt guard để relay khởi động.

Các lượt kiểm tra sau còn phát hiện việc Docker trả danh sách mount khác thứ tự.
Đã sửa phép so sánh để sắp theo destination, vẫn so sánh toàn bộ nội dung mount;
không bỏ qua thay đổi mount. Các lượt không đạt đều rollback trước khi thử lại.

Final: hai backend health HTTP 200; New không có default route, không tham gia
mạng DB và truy cập trực tiếp cả hai PostgreSQL bị từ chối. Admin 8090/8191,
gateway, PostgreSQL, dữ liệu và grant giữ nguyên. Relay chính được khởi động lại
với phép thử đúng IP; không mở host port hoặc tạo mạng mới.

Rollback New gần nhất giữ tại
`kdh-report-new-app-1-before-content-responsive-release-20261021`, stopped,
restart=no. Đây là bản cùng sườn trước tinh chỉnh mobile, đã giữ IP Viewer cố định.
Không dùng compose down hoặc phục hồi database để rollback giao diện.

## Công cụ / hồ sơ Admin

`ops/deploy_content_shell.py`, `ops/check_content_shell.py` và bổ sung bảo toàn
log driver trong `ops/shared_viewer.py`; cập nhật manifest khởi động tại
`docs/shared-viewer-20261021/deployment.json`. Backup cấu hình mã hóa nằm ngoài Git.
Không commit, đổi branch hoặc xóa file local. HEAD Admin `6b52ee2`, New `837f655`
giữ nguyên; working-tree changes có trước được giữ lại.

## Mở xem

Từ `http://localhost:8191/marketing`, chọn report
`rpt_4909119771c69125897d8bca84444abe`, revision 1 và mở New.
Đích: `http://127.0.0.1:8080/reports/rpt_4909119771c69125897d8bca84444abe?revision=1`.
Nếu hết phiên, đăng nhập lại Admin VIO và mở từ nút báo cáo. Không dùng URL static
layout-preview để xem dữ liệu thật.
