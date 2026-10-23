# Facebook Content — biểu đồ và căn bảng, 21/10/2026

Đã cập nhật New 8080; giữ sườn hiện tại và dữ liệu Published Bundle revision 1.

- Panel biểu đồ duy nhất chiếm trọn hàng bằng class bố cục rõ ràng.
- Ba thẻ KPI phủ đều chiều ngang cả màn hình 1920px; sửa CSS bị quy tắc chung lấn.
- Số bài theo ngày dùng biểu đồ cột tím, giữ nguyên 28 nhãn/ngày và toàn bộ giá trị
  trong Bundle. Không cộng lại hoặc tạo KPI. Không có thanh cuộn ngang ở biểu đồ.
- Bỏ bộ chọn khi chỉ có một chuỗi; tiêu đề “Nhịp đăng bài”, giữ timezone UTC.
- Bảng bỏ tiêu đề lặp; cột số, nút sắp xếp và số liệu căn cùng mép phải.
- Link Facebook giữ nguyên; số 0 và ô thiếu dữ liệu không thay đổi.
- CSS có version URL mới để không tiếp tục dùng stylesheet cũ đã cache.

## Files

New: `app/mappers/dashboard.py`, `templates/pages/facebook_content/index.html`,
`templates/pages/facebook_content/partials/formats.html`,
`templates/pages/facebook_content/partials/posts.html`,
`static/css/pages/facebook-content.css`, `tests/test_vio_content.py`,
`compose.shared.yaml` (image tag).

Admin: công cụ QA `ops/check_content_polish.py`, hồ sơ trong thư mục này,
`docs/SYSTEM_CONTEXT.md`, manifest khởi động shared Viewer.
Không sửa backend nghiệp vụ Admin hoặc tạo dữ liệu báo cáo.

## Validation / runtime

- New Python: 292 PASS, 0 SKIP. JS syntax và git diff --check PASS.
- Immutable image render smoke không mạng: PASS.
- Browser đăng nhập VIO → handoff → report thật revision 1: PASS.
- 1920 / 1536 / 1440 / 1024 / 768 / 390 / 360: PASS.
- Đo panel full width, không overflow biểu đồ, đủ 28 cột; đo mép chữ “Cảm xúc”
  và giá trị ở hàng đầu lệch dưới 2px. Ảnh `report-{width}.png`.
- 15 / 80 / 10, engagements null/no_data, shares null/partial 7/15 và UTC giữ nguyên.
- Sai origin, revision, report không grant, khác môi trường: bị chặn đúng.
- Business hashes cả hai Admin không đổi; phiên QA đã logout.

Container: `kdh-report-new-app-1`.
Image cuối: `kdh-new:content-shell-20261021-3c0130851869`.
Hash: `sha256:fb1089d786b5b3f5a9d383b77e2c13024fb32435a0eff505395a1416943228db`.
Manifest `final/deployment.json`; image nền và 5 file overlay trong `build.json`.
Không thay mạng, relay, OAuth, grants hoặc DB trong lượt chỉnh giao diện này.
Giữ backup container stopped/restart=no và cấu hình mã hóa ngoài Git để rollback.
Start-KDH đã xác nhận identity hiện hành. Không commit, push hoặc đổi branch.

Mở lại từ Admin VIO hoặc dùng URL:
http://127.0.0.1:8080/reports/rpt_4909119771c69125897d8bca84444abe?revision=1
