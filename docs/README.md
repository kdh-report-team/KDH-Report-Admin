# Tài liệu KDH Report Admin

Đây là mục lục chung của dự án. Bắt đầu từ [SYSTEM_CONTEXT.md](SYSTEM_CONTEXT.md) để nắm bối cảnh và công việc đang dở. Các thông tin runtime, quyền và kết quả nghiệm thu trong tài liệu phản ánh thời điểm ghi nhận; cần đối chiếu source/container hiện tại trước khi thao tác.

## Kiến trúc và luồng báo cáo

- [Kiến trúc hệ thống](KDH_ARCHITECTURE.md)
- [Kiến trúc database](DATABASE_ARCHITECTURE.md)
- [Luồng dữ liệu, Dataset và duyệt báo cáo](KDH_DATA_FLOW.md)
- [API tích hợp và phân quyền](KDH_API_INTEGRATION.md)
- [Report Bundle API](report-bundles.md) và [contract Admin → New](KDH_REPORT_BUNDLE_CONTRACT.md)
- [Mở báo cáo từ Admin sang New](ADMIN_NEW_HANDOFF.md)
- [Bàn giao nền tảng](KDH_HANDOVER.md), [trạng thái provider](KDH_PROVIDER_STATUS.md) và [kế hoạch còn lại](marketing-remaining-implementation.md)

Admin thu thập, tính toán, kiểm tra và phát hành; New chỉ đọc Bundle đã phát hành. Dataset và revision đã phát hành không được sửa để bổ sung dữ liệu mới.

## Facebook Content và các nền tảng

- [Yêu cầu 7 mục Facebook Content](FACEBOOK_CONTENT_REQUIREMENTS_20261021.md)
- [Collector Page/Post Insights và giới hạn chỉ số](FACEBOOK_CONTENT_INSIGHTS_20261021.md)
- [Meta OAuth](meta-oauth.md)
- [Facebook Content/Ads: bàn giao triển khai ban đầu](KDH_FACEBOOK_REPORTS_HANDOFF.md)
- [TikTok Ads scaffold](TIKTOK_ADS_SCAFFOLD.md)
- [Bằng chứng diagnostic, sync và Dataset VIO ngày 22/10](vio-insights-live-20261022/README.md)

Không dùng kết quả fixture để khẳng định dữ liệu thật đầy đủ. Quyền đọc Insights, dữ liệu đã thu thập, duyệt Dataset và quyền xem revision là các trạng thái riêng.

## Vận hành và kiểm thử

- [Docker: cấu hình, dữ liệu bền vững, backup và kiểm thử](DEPLOY_DOCKER.md)
- [Hướng dẫn triển khai nền tảng](KDH_DEPLOYMENT_GUIDE.md)
- [Kết quả kiểm thử nền tảng](KDH_TEST_RESULTS.md)
- [Triển khai Admin/Insights ngày 21/10](content-insights-deploy-20261021/README.md)
- [Triển khai tích hợp Admin/New và nghiệm thu](tonight-delivery-20261021/README.md)
- [New dùng chung](shared-viewer-20261021/RESULT.md) và [sửa origin loopback](origin-fix-20261021/RESULT.md)

Các lệnh trong tài liệu được chạy từ thư mục gốc repository, trừ khi có chỉ dẫn khác. Không chạy lại script triển khai/nghiệm thu cũ chỉ vì tài liệu được sắp xếp lại.

## Giao diện

- [Audit UX và workflow Admin](KDH_ADMIN_UX_WORKFLOW_AUDIT_20261019.md)
- [Tinh chỉnh Admin UI](ADMIN_UI_REFINEMENT_20261019.md)
- [Nhận diện nền tảng](PLATFORM_BRAND_ASSETS.md) và [tinh chỉnh giao diện đa nền tảng](PLATFORM_UI_POLISH_20261019.md)
- [Đưa dữ liệu thật vào sườn New](content-shell-20261021/RESULT.md)
- [Tinh chỉnh Facebook Content](content-polish-20261021/RESULT.md)
- [Sửa nhãn và responsive biểu đồ Insights](insights-chart-20261022/README.md)

## Lịch sử triển khai và nghiệm thu

Giữ các tài liệu sau để tra cứu quyết định, bằng chứng và phương án rollback. Không xem địa chỉ IP, image, cổng hoặc trạng thái PASS trong báo cáo cũ là trạng thái runtime hiện tại.

| Giai đoạn | Tài liệu |
|---|---|
| Phase 4 — PostgreSQL | [Nghiệm thu](KDH_PHASE4_POSTGRES_ACCEPTANCE.md) |
| Phase 5 — Chuẩn bị sandbox | [Kế hoạch](KDH_PHASE5_SANDBOX_DEPLOYMENT_PLAN.md) |
| Phase 5B — Triển khai sandbox | [Kết quả](KDH_PHASE5B_SANDBOX_DEPLOYMENT_RESULT.md) |
| Multi-platform — 19/10 | [Triển khai](MULTIPLATFORM_SANDBOX_DEPLOYMENT_20261019.md) |
| Phase 9 — VIO Admin → New | [Kết quả](KDH_PHASE9_IMPLEMENTATION_RESULT.md) |
| Admin chính — 20/10 | [Hợp nhất](KDH_PRIMARY_UNIFICATION_RESULT.md) |

## Quy ước lưu tài liệu

- Thư mục gốc giữ [README.md](../README.md) và [AGENTS.md](../AGENTS.md); tài liệu hướng dẫn, audit và bàn giao nằm trong `docs/`.
- Thêm liên kết ở mục lục này khi thêm tài liệu chủ đề mới; không chép toàn bộ báo cáo lịch sử vào một file dài.
- Các thư mục bằng chứng theo ngày giữ nguyên JSON, ảnh, log và baseline để đối chiếu. Đường dẫn trong baseline, bảng liệt kê thay đổi lịch sử và file `t` có thể phản ánh vị trí trước khi chuyển tài liệu.
- Tám tài liệu ở thư mục gốc đã được chuyển vào `docs/` ngày 22/10/2026, giữ nguyên tên. Liên kết Markdown và hai đường dẫn đọc báo cáo trong script kiểm tra lịch sử đã được cập nhật; baseline/manifest gốc không được viết lại.
- Chưa xác định tài liệu nào trùng hoàn toàn hoặc chắc chắn không còn cần dùng để xóa. Giữ nguyên source, cấu hình, script khởi động, file `t` và bằng chứng nghiệp vụ.
