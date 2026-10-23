# Facebook Page Insights — chỉnh biểu đồ 22/10/2026

Đã deploy New 8080: `kdh-new:insights-chart-20261022-fed378fa5436`.

## Thay đổi

- Lề trục Y theo độ dài nhãn số, không còn cắt số hàng nghìn.
- Ngày trục X hiển thị dd/mm, không chuyển timezone; tooltip giữ nguyên end_time và nguồn.
- Tự co giãn biểu đồ Cartesian khi đổi chiều rộng hoặc chọn chuỗi đang ẩn; giảm số nhãn trên màn hình nhỏ.
- Select Insights dùng tên chỉ số ngắn; nguồn/định nghĩa vẫn trong dữ liệu, tooltip và phạm vi thu thập.
- Màu cột, khoảng cách và kiểu chữ phù hợp sườn Facebook Content hiện có.

Files New: `static/js/shared/charts.js`, `static/js/pages/snapshot.js`, `static/css/pages/facebook-content.css`, `templates/pages/snapshot/components.html`, `templates/pages/facebook_content/partials/engagement.html`, `templates/pages/facebook_content/index.html`, `tests/test_vio_content.py`; `compose.shared.yaml` cập nhật tag đã kiểm thử.

## Kiểm chứng

- Exact image: 317 tests PASS. Lượt đầu 316 PASS/1 FAIL do test ghim cache version CSS cũ; đã cập nhật expected version và chạy lại toàn bộ. Log ban đầu được giữ nguyên.
- Browser hợp lệ Admin → New, report `rpt_795f2c05f18e6eed68b2bb247e731317`, revision 1: PASS.
- 4 chuỗi Insights × 5 viewport 1440/1024/768/390/360: 20 PASS. Kiểm tra SVG text nằm trong viewBox, nhãn ngày không chồng, đủ điểm không-null, tooltip có thời gian 07:00, trang không overflow.
- JS syntax và git diff --check PASS. Sai revision DENIED. Đã logout phiên QA.
- Hash dữ liệu nghiệp vụ Admin trước/sau không đổi; không provider call, sync, sửa Dataset/Bundle hoặc grant.
- Config/secrets/mounts/security options giữ nguyên; Admin, PostgreSQL, relay, gateway và mock không đổi identity/config/state trong deployment.

Ảnh: [desktop](deployed-1440.png), [mobile](deployed-390.png). Kết quả: [browser](deployed.json), [deployment](deployment.json), [tests](tests.json).

Rollback container: `kdh-report-new-app-1-before-insights-chart-20261022`, giữ image cũ và dừng với restart=no. Full runtime config backup mã hóa DPAPI tại LocalAppData/KDH-Insights-Chart-20261022; không ghi secrets vào repository. Startup manifest dùng bởi Start-KDH đã cập nhật container mới.
