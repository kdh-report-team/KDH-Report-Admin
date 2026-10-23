# Sửa đăng nhập từ liên kết Docker — 21/10/2026

PASS: Chromium mở http://127.0.0.1:8191/, chuyển về http://localhost:8191/,
đăng nhập bằng tài khoản sandbox hiện hữu và mở Report Bundle revision 1 trên New 8193.

Nguyên nhân: Docker mở IP loopback trong khi APP_URL là localhost.
Origin của POST đăng nhập không khớp nên guard trả 403.

## Thay đổi và phạm vi

- kdh/app.py: chuẩn hóa GET/HEAD của / và /marketing giữa localhost và 127.0.0.1,
  cùng cổng HTTP, theo APP_URL. Giữ query và fragment trình duyệt.
- Giữ API writes, OAuth callbacks, health, Origin guard, CSRF và ACL.
- tests/test_loopback_entry.py: 5 regression tests.
- ops/fix_sandbox_origin.py và ops/check_sandbox_origin.py: backup/build/deploy/QA.
- Image mới chỉ overlay app.py lên image sandbox cũ; identity trong deployment.json.
- Chỉ thay Admin sandbox. Primary 8090/8080, New 8193, PostgreSQL, gateway và
  relay giữ nguyên identity/config. Container cũ được giữ stopped để rollback.
- Backup PostgreSQL/appdata mã hóa ngoài repo, checksum/giải mã roundtrip PASS,
  pg_restore --list PASS. Không restore đè DB.

Lần deploy đầu đã rollback do protected signature khác. Khi kiểm tra lại,
identity/config khớp. Helper đã chuẩn hóa thứ tự mount/network trước so sánh;
không xác nhận được trường khác biệt lần đầu vì chưa lưu chi tiết lúc đó.
Lần deploy cuối PASS; helper hiện ghi metadata nếu kiểm tra tương tự thất bại.

## Kiểm thử

- Python trong image, network none, SQLite disposable: 64 PASS, không skip.
- UI: 100 PASS, không skip. Node syntax và git diff --check: PASS.
- Browser Docker entry, canonical URL, hash fragment: PASS.
- Đăng nhập thật bằng credentials sandbox hiện hữu: PASS.
- Wrong Origin: vẫn 403.
- Handoff/report rpt_4909119771c69125897d8bca84444abe revision 1: PASS.
- KPI 15/80/10; engagements null/no_data; shares null/partial, coverage 7/15; UTC: PASS.
- Chỉ logout các phiên do kiểm thử tạo.
- Hash các bảng nghiệp vụ không đổi; loại trừ session/audit vận hành do login,
  handoff/logout. Không sửa report, grant, review hoặc job.
- Git HEAD giữ nguyên 6b52ee2f3ef29ebb5820e95e88ba318a7599667d; giữ thay đổi cũ.

New health dùng /api/v1/health. Lần QA đầu gọi nhầm /health (404), đã sửa
script QA và chạy lại PASS, không sửa New.

Ảnh: report-after-docker-login.png. Kết quả: browser.json và deployment.json.

## Sử dụng

Bấm link Docker hoặc mở http://localhost:8191/. Tải lại tab IP cũ trước khi
đăng nhập. Mở /marketing để chọn báo cáo VIO revision 1 và mở New.
