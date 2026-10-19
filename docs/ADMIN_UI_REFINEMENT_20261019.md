# Admin UI refinement — 2026-10-19

## Phạm vi

Chỉnh lớp trình bày trong KDH-Report-Admin: bố cục, typography, màu sắc, câu chữ và chỉ dẫn chuyển bước. Giữ Flask/Vanilla JS, route/action hiện có và các điều kiện review/publication. Chưa triển khai lên sandbox 8191.

## Thay đổi

- Sidebar, tiêu đề, bảng, input và nút dùng cùng hệ màu xanh/trung tính; giảm bóng đổ và nhãn trang trí lặp lại.
- Rút gọn mô tả trên các trang Admin; bỏ câu chữ kỹ thuật không cần thiết ở luồng thao tác chính.
- Marketing có bốn liên kết bước, khu vực tiếp tục công việc và bố cục thích ứng desktop/mobile.
- Truy vết snapshot/receipt nằm trong mục mở rộng. Cảnh báo dữ liệu chưa xác minh và lỗi bằng chứng vẫn hiển thị trực tiếp.
- Giữ nguyên giá trị null/zero, lifetime/period, partial và các giới hạn phát hành. Nhãn trạng thái KPI Marketing được Việt hóa.
- Không hiển thị liên kết Dashboard khi chưa cấu hình URL; liên kết New bị ẩn vẫn không chiếm chỗ hoặc có thể nhấn.
- Khi mở snapshot phát hành, hướng dẫn tiếp tục mục Xuất bản thay cho thông báo chưa có Candidate.

## Files thuộc lượt UI

- `static/admin-refinement.css` (mới).
- `static/views.js`, `static/app.js`, `static/marketing.js`.
- `templates/index.html`, `templates/marketing.html`.
- `tests/ui.test.js`, `tests/admin_refinement.browser.cjs` (mới).

Working tree đã có nhiều thay đổi Meta/SEO trước lượt này. Diff so với HEAD bao gồm cả những thay đổi đó; không coi toàn bộ diff là kết quả của lượt UI.

## Validation

| Kiểm tra | Kết quả |
| --- | --- |
| `npm.cmd test` | 94 PASS, 0 FAIL |
| `.\.venv\Scripts\python.exe -B tests/run_offline.py` | 490 ca: 372 PASS, 118 SKIP, 0 FAIL |
| `node --check` cho toàn bộ `static/*.js` và browser QA script | PASS |
| `git diff --check` | PASS |
| Browser QA: 15 màn hình × 3 viewport (1440/768/390) | 45 PASS |

Python sử dụng runner offline hiện có: chặn network/PostgreSQL runtime và không đọc `.env` local. Các ca PostgreSQL không được tính là PASS trong lượt này.

Browser QA dùng fixture riêng và chặn toàn bộ request tới môi trường thật. Không có request provider, mutation, dữ liệu VIO hoặc DB runtime. Kiểm tra không tràn ngang, không có lỗi JavaScript, liên kết bước hợp lệ và các nút phát hành bị khóa đúng trạng thái fixture. Đây không phải nghiệm thu nghiệp vụ runtime hoặc Admin-to-New E2E.

Chạy browser QA với bản Playwright Core đã cài:

```powershell
node tests/admin_refinement.browser.cjs <duong-dan-module-playwright-core>
```

Ảnh và kết quả nằm trong `test-results/admin-refinement/` (không đưa vào image):

- `overview-1440.png`
- `connections-facebook-1440.png`
- `marketing-1440.png`
- `marketing-390.png`
- `result.json`

## Ranh giới triển khai

Không thay backend, database, OAuth, Docker hay KDH-Report-New trong lượt UI. Không sync, review, approve hoặc publish dữ liệu thật; không commit/reset/stash.

Trước triển khai sandbox, manifest build phải bao gồm `static/admin-refinement.css` cùng các frontend/template đã thay đổi; không đưa fixture/tests vào image. Kiểm tra lại manifest và baseline hiện hành, smoke-test image mới rồi áp dụng quy trình thay riêng Admin đã được duyệt. Không cần migration. Deployment và kiểm tra runtime chưa thực hiện trong lượt này.
