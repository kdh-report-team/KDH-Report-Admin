# VioAgencyAnalytics — Product Vision

Ngày 23/10/2026, bổ sung rà soát **customer-first / self-service** sau rebrand. Đây là định hướng sản phẩm và phạm vi MVP, không phải biên bản nghiệm thu SaaS. Trạng thái source/bằng chứng nằm trong [Architecture](VIOAGENCYANALYTICS_ARCHITECTURE.md); công việc triển khai nằm trong [Roadmap](SAAS_MIGRATION_ROADMAP.md).

## Chủ sở hữu và mục tiêu

VIO Agency là đơn vị phát triển, sở hữu và vận hành VioAgencyAnalytics. Sản phẩm hướng tới **Self-service Multi-platform Marketing Analytics & Reporting SaaS**: doanh nghiệp và Agency tự đăng nhập, tổ chức Workspace, kết nối nguồn được cấp quyền, theo dõi dữ liệu và phát hành báo cáo. Sản phẩm lấy cảm hứng từ mô hình hoạt động của AgencyAnalytics nhưng phát triển độc lập, không mặc định có quan hệ sở hữu hoặc hợp tác.

Mục tiêu kinh doanh là cung cấp phần mềm thuê bao cho nhiều doanh nghiệp và Agency. Giá trị cốt lõi là giảm thao tác tổng hợp báo cáo, duy trì định nghĩa KPI nhất quán và giải thích được nguồn/độ mới/độ phủ của số liệu. Không hứa có dữ liệu cho mọi nền tảng chỉ vì có menu hoặc Metric Catalog.

**Customer Web là điểm bắt đầu của mọi thao tác kết nối nền tảng.** Khách tự onboarding, cấp quyền nguồn, chọn asset, xem dashboard và tạo/chia sẻ báo cáo theo quyền, không phải nhờ nhân viên VIO thao tác. Admin Backend tự xử lý nghiệp vụ; VIO Super Admin vận hành hệ thống và cấu hình Meta App/Google OAuth Client cấp nền tảng. Cấu hình app không phải consent truy cập Page, Ad Account hoặc Property của khách và không cấp VIO quyền mặc định xem dữ liệu nhạy cảm.

## Người dùng và mô hình tổ chức mục tiêu

| Khái niệm | Ý nghĩa |
|---|---|
| VIO Super Admin | Đội vận hành nền tảng của VIO; quản lý Organization thuê phần mềm, tích hợp, worker, cảnh báo và audit. Không tự động có quyền đọc mọi dữ liệu khách hàng. |
| Organization | Đơn vị thuê phần mềm và ranh giới tenant; có thể là doanh nghiệp hoặc Agency. |
| Workspace | Tên trải nghiệm của Organization trong MVP: một Organization tương ứng một Workspace. Nếu thêm nhiều Workspace trong một Organization phải có quyết định kiến trúc riêng. |
| Agency | Một loại Organization có thể quản lý nhiều Client; không phải tên khác của VIO Super Admin. |
| Client | Khách hàng/phạm vi báo cáo thuộc Organization. Doanh nghiệp có thể có Client nội bộ. Không coi client ID cũ là tenant ID mới. |
| Brand | Thương hiệu thuộc Client; liên kết asset phải rõ ràng, không tự nhập chung số liệu của các Brand. |
| User / Membership | Một người có danh tính riêng, có thể là thành viên nhiều Organization; vai trò và quyền gắn với từng membership/phạm vi. |
| Organization Owner/Admin | Quản trị thành viên và cấu hình của chính Organization, không quản trị toàn nền tảng. |
| Customer Viewer | Chỉ xem dashboard/report được cấp quyền; quyền xem Published Report không tự cấp quyền kết nối nguồn, sửa Dataset hoặc phát hành. |

Tên hiển thị KinderHealth và VIO trong dữ liệu hiện tại tiếp tục biểu thị đúng khách hàng. `client_kinderhealth` và `client_meta_sandbox` giữ nguyên; sandbox không được nâng thành production tenant trong task rebrand.

## Hành trình mong muốn

1. Truy cập Web, đăng ký/đăng nhập bằng Google Sign-in.
2. Tạo hoặc tham gia Organization/Workspace qua lời mời hợp lệ.
3. Tạo hoặc chọn Client/Brand trong Workspace.
4. Vào Data Sources / Integrations, chọn nguồn được hỗ trợ, nhấn Connect.
5. Web yêu cầu backend tạo giao dịch OAuth; trình duyệt chuyển tới trang consent chính thức để khách tự cấp quyền.
6. Backend nhận callback, kiểm tra giao dịch/quyền và lưu token mã hóa theo Organization/Client/Connection. Web chỉ nhận trạng thái an toàn.
7. Khách chọn Page, Ad Account, GA4 Property hoặc asset được cấp; backend xác minh lựa chọn và tự xếp initial sync.
8. Worker gọi API provider, lưu/chuẩn hóa dữ liệu và theo dõi freshness/coverage; khách theo dõi tiến độ trên Web.
9. Web tự hiển thị Live Dashboard theo nguồn có dữ liệu hợp lệ; khách tùy chỉnh dashboard, bộ lọc và kỳ so sánh. Không cần nhân viên VIO duyệt phát hành để xem dashboard.
10. Khách tạo báo cáo từ template/Dataset bất biến, review và publication theo policy của Workspace; xuất hoặc chia sẻ revision cho Client Viewer theo quyền. Reviewer/Publisher là người có quyền trong Workspace, không mặc định là nhân viên VIO.
11. Xem lịch sử và cấp/thu hồi chia sẻ. Gửi theo lịch là giai đoạn sau, chỉ dùng revision đủ điều kiện và quyền.

**Google Sign-in chỉ xác thực người dùng ứng dụng. Provider OAuth là ủy quyền dữ liệu riêng.** Đăng nhập thành công không có nghĩa đã được đọc GA4, GSC, Google Ads, Meta hay TikTok. Không yêu cầu nhập mật khẩu Google/Facebook/TikTok vào form của VioAgencyAnalytics. Provider token chỉ do Admin Backend lưu và sử dụng.

## MVP đề xuất

**MVP đầu tiên:** Google Sign-in → Workspace → Client/Brand → Connect Facebook Content VIO → chọn Page → initial sync tự động → xem dashboard dữ liệu thật. VIO Page là nguồn thử nghiệm có cấp quyền, không phải nguồn mặc định cho mọi khách. Các bước 1–5 của Roadmap phục vụ lát cắt này; Report Builder/Sharing self-service và Billing/White Label mở sau. Tận dụng code Meta và evidence/dữ liệu sandbox để kiểm thử có nhãn sandbox; không sao chép token, cấu hình riêng hoặc số liệu sandbox thành dữ liệu production. Production phải có consent, ownership và sync riêng được nghiệm thu.

Phạm vi mở rộng sau lát cắt đầu tiên:

- Danh tính customer, Organization/Workspace và membership có kiểm tra quyền backend; mời/tham gia Workspace và chọn Client rõ ràng.
- Kết nối tự phục vụ từng provider đã qua acceptance: Facebook Content trước, tiếp theo tái sử dụng Google SEO; Facebook Ads chỉ bật sau nghiệm thu riêng. Platform chưa hỗ trợ phải có trạng thái trung thực.
- Đồng bộ nền có theo dõi tiến độ, retry có giới hạn, độ trễ và coverage; không tạo dữ liệu mẫu khi lỗi nguồn.
- Live Dashboard cho nguồn đủ điều kiện; không gộp currency/timezone hoặc cộng sai unique users/reach.
- Report Builder từ template và Dataset; kế thừa review/source-check/approval/release/Bundle; quyền chia sẻ gắn revision.
- Audit hoạt động và test cách ly tenant cho API, job, cache, export, token và grant trước khi phục vụ nhiều Organization.

MVP chỉ được coi hoàn thành khi hai Organization kiểm thử không đọc/ghi chéo nhau, người xem chỉ mở được revision có quyền, ngắt nguồn không sửa báo cáo cũ, và mọi nền tảng được quảng bá đều có bằng chứng acceptance riêng.

## Hiện có và chưa triển khai

Hiện có Flask Admin, PostgreSQL trong cấu hình Compose, SQLite local/test, tài khoản nội bộ, Google/Meta OAuth, worker, Data Foundation, Daily Metrics/Source Snapshots, Dataset, Data Quality, review/approval, Bundle/revision và Viewer Access. Web dùng FastAPI/Jinja2/Vanilla JS và renderer Bundle; các dashboard mẫu tồn tại riêng ngoài production. Chi tiết khả năng và mức chứng minh từng nguồn trong Architecture.

Chưa triển khai SaaS customer Google Sign-in, tenant runtime tổng quát, onboarding self-service, customer Live Dashboard tổng quát, customer Report Builder, subscription/billing, white label hoặc gửi báo cáo thuê bao theo lịch. Các phiên bản hiện có là nền tảng kế thừa, không phải lời cam kết mọi KPI đã được nghiệm thu dữ liệu thật.

Rebrand đã được thực hiện trước lượt rà soát này. Lượt customer-first chỉ cập nhật năm tài liệu được chỉ định: không sửa application code, migration, OAuth/permissions, schema/API, worker hoặc Docker/Git. Các tài liệu `KDH_*.md`, dữ liệu, fixture và bằng chứng handover giữ nguyên. Chỉ triển khai SaaS sau khi người dùng thống nhất và chấp thuận kiến trúc.
