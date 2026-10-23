# VioAgencyAnalytics Admin

**VIO Agency phát triển, sở hữu và vận hành VioAgencyAnalytics**, hướng tới nền tảng Self-service Multi-platform Marketing Analytics & Reporting SaaS cho doanh nghiệp và Agency. Sản phẩm phát triển độc lập; việc tham khảo mô hình AgencyAnalytics không hàm ý quan hệ sở hữu hoặc hợp tác.

Hiện tại đây là backend và giao diện quản trị nội bộ, chưa phải SaaS self-service production. Google Sign-in cho người dùng là kế hoạch; Google/Meta OAuth hiện có dùng để cấp quyền nguồn dữ liệu, không thay thế đăng nhập ứng dụng. Organization Admin và Customer Viewer trong SaaS tương lai khác vai trò admin nội bộ hiện tại.

- [Product Vision và MVP](docs/VIOAGENCYANALYTICS_PRODUCT_VISION.md)
- [Kiến trúc hiện tại, đích SaaS và trạng thái provider](docs/VIOAGENCYANALYTICS_ARCHITECTURE.md)
- [Roadmap và acceptance criteria](docs/SAAS_MIGRATION_ROADMAP.md)
- [Audit, file map và kết quả kiểm thử rebrand](docs/REBRAND_FILE_MAP.md)

Tên package `kdh`, client ID, cookie/header, database và Docker hiện có là định danh tương thích, không phải tên thương hiệu mới. Rebrand source không cập nhật container/image đang chạy. Các ghi nhận triển khai bên dưới cần đối chiếu cấu hình thực tế trước khi vận hành.

Tài liệu dự án được tập trung tại **[docs/README.md — Mục lục chung](docs/README.md)**: kiến trúc, hướng dẫn vận hành, Facebook Content, hợp đồng Admin → New và lịch sử triển khai.

Ứng dụng quản trị báo cáo của VIO Agency, kế thừa luồng KinderHealth và phạm vi VIO sandbox, xây từ thiết kế Stitch trong `stitch_kdh_report_admin_frontend/`. Flask phục vụ cả API và frontend tiếng Việt. Compose cấu hình ứng dụng cùng worker nền và PostgreSQL 16 trong volume bền vững. SQLite vẫn được hỗ trợ cho môi trường local không cấu hình `DATABASE_URL`. Không cần chạy một Node backend hay MongoDB riêng.

Đọc [bối cảnh toàn hệ thống Admin ↔ Web](docs/SYSTEM_CONTEXT.md) trước khi tiếp tục phát triển: trách nhiệm hai dự án, hợp đồng dữ liệu, trạng thái đã kiểm tra và phần đang dở. Code working tree và container đang chạy có thể khác phiên bản.

## Chạy bằng Docker

Làm theo [hướng dẫn Docker](docs/DEPLOY_DOCKER.md): cấu hình `.env`, build container và mở **http://localhost:8090**. Tài khoản, kết nối Google và dữ liệu database nằm trong volume `postgres-data`; file ứng dụng vẫn nằm trong `admin-data`. Khóa mã hóa lấy từ `ENCRYPTION_KEY` cố định. Lịch tự động do worker xử lý khi container đang chạy. Admin có thể thêm dữ liệu mẫu riêng trong **Cài đặt**.

## Report Bundle cho VioAgencyAnalytics-Web

Admin có thể tạo report bundle từ các dataset đã lưu qua `POST /api/report-bundles`, tạo revision mới và xuất bản `provisional`/`final`. VioAgencyAnalytics-Web đọc snapshot qua internal API; service token chỉ giữ ở backend. Viewer production dùng `GET /api/internal/v1/viewer/report-bundles/{report_id}` với phiên người xem và quyền report/revision. Endpoint dịch vụ `GET /api/internal/v1/report-bundles/{report_id}` vẫn giữ nguyên contract, không thay thế kiểm tra quyền Viewer. GET không gọi provider, tính lại KPI hay phụ thuộc dữ liệu live. ID `rpt_...` giữ nguyên qua các revision; nội dung đã xuất bản không được sửa.

Xem [endpoint, JSON contract, ví dụ request/response và migration 2](docs/report-bundles.md). Không thay thế luồng HTML/Excel hiện tại và không cần database thứ hai. Report Builder hỗ trợ tạo bản nháp, lưu cấu hình section và xem trước nội dung snapshot đã lưu trong Admin. Preview chỉ đọc bản DRAFT, không gọi provider hoặc xuất bản báo cáo.

## Demo bằng Docker trên máy này

Image: `kdh-report-admin:demo`. Container: `kdh-report-admin-admin-1`. Truy cập **http://localhost:8090** bằng tài khoản và mật khẩu admin đã tạo trước đó.

Mở Docker Desktop, sau đó nhấp đúp **`demo.cmd`**. Script chờ container khỏe rồi mở trang ứng dụng. Hoặc chạy:

```powershell
cd D:\VioAgencyAnalytics\VioAgencyAnalytics-Admin
docker compose up -d --wait
docker compose ps
```

Compose lưu PostgreSQL trong volume `kdh-report-admin_postgres-data`. Volume `kdh-report-admin_admin-data` vẫn gắn vào `/app/instance` để giữ file và dữ liệu SQLite cũ phục vụ rollback. Đổi kết nối database không tự chuyển dữ liệu SQLite sang PostgreSQL. Thư mục `instance` trên Windows là môi trường local riêng; dữ liệu không tự đồng bộ giữa các nơi.

Các lệnh vận hành:

```powershell
docker compose stop
docker compose up -d --wait
docker compose logs --tail 50 admin
# Khi cập nhật mã nguồn:
docker compose up -d --build --wait
```

`stop`, `restart` và `up` giữ dữ liệu. Không dùng `docker compose down -v` nếu cần giữ tài khoản và báo cáo, vì `-v` xóa volume. Cổng demo chỉ mở trên máy này. Google OAuth vẫn cần cấu hình ở `.env` để trình diễn lấy dữ liệu Google thật; việc chạy Docker không tự cấp quyền Google.

Nếu mang sang máy khác: sao chép mã nguồn, cấu hình riêng của máy đó và chuyển volume nếu cần giữ tài khoản/dữ liệu; có thể tạo image bằng `docker compose build` hoặc xuất image bằng `docker save -o kdh-report-admin-demo.tar kdh-report-admin:demo`. Image không chứa tài khoản, mật khẩu, `.env` hay dữ liệu volume. Mount `/legacy` cần trỏ đúng thư mục báo cáo cũ trên máy đích.

## Bộ dữ liệu demo

Sau khi đã tạo tài khoản admin, thêm dữ liệu bằng lệnh sau (chạy lại không sinh bản trùng):

```powershell
docker compose exec -T admin python run.py seed-demo
```

Bộ mẫu gồm 28 ngày và kỳ so sánh trước đó: GA4, GSC, 48 từ khóa, 2 CSV cho 3 cơ sở GMB giả định, 6 báo cáo HTML, 9 tác vụ minh họa và một file Excel tải được. Dữ liệu lưu trong volume Docker, giữ nguyên qua khởi động lại. Không thay đổi tài khoản, mật khẩu, kết nối Google hay bản xuất bản hiện có.

Mở **Tổng quan → Khám phá báo cáo demo**. Trong **Phân tích & Xuất Excel**, giữ chọn **Dữ liệu demo** để đổi kỳ, chạy lại, so sánh, xuất Excel và lưu HTML mà không cần OAuth. Mỗi kết quả và file xuất đều có nhãn DEMO. CSV demo phải dùng chế độ demo và đúng kỳ ngày ghi trên file. Báo cáo demo không thay thế bản xuất bản chính thức.

Để lấy dữ liệu thật, bỏ chọn **Dữ liệu demo** rồi chạy lại với kết nối Google đã cấu hình hoặc CSV thật. Lỗi nguồn thật vẫn hiển thị lỗi; không tự chuyển sang số liệu mẫu. Các trạng thái kết nối Google trên Tổng quan và Kết nối Google luôn phản ánh kết nối thật. Lịch sử tạo sẵn được đánh dấu mô phỏng; nút Thử lại chạy một tác vụ demo mới.

## Chạy trên Windows

Yêu cầu Python 3.12 trở lên.

```powershell
cd D:\VioAgencyAnalytics\VioAgencyAnalytics-Admin
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe run.py
```

Mở **http://localhost:8090**. Lần đầu, trên chính máy chủ, giao diện cho phép tạo **một tài khoản admin đầu tiên**, sau đó đăng nhập. Không có tài khoản mặc định, mật khẩu cứng hoặc đăng ký công khai. Các lần sau chỉ cần chạy `run.py`. Có thể dùng `powershell -File .\start.ps1` nếu chính sách PowerShell của máy cho phép chạy script.

Sau khi thiết lập, có thể tạo Admin / Người vận hành / Người xem ở màn hình Người dùng. Tài khoản đăng nhập admin và tài khoản Google cấp quyền nguồn là hai loại riêng.

Đặt lại mật khẩu từ máy chủ (mật khẩu nhập ẩn, không truyền trong dòng lệnh):

```powershell
.\.venv\Scripts\python.exe run.py reset-password --email ten@kinderhealth.vn
```

## Kết nối Google thật

Ứng dụng có adapter API thật, bộ dữ liệu demo được chọn riêng và không lấy credential từ dự án cũ. Cần cấu hình OAuth Web client một lần ở backend:

1. Trong Google Cloud project của đơn vị, bật **Google Analytics Data API**, **Google Search Console API**, **Google Sheets API**.
2. Thiết lập màn hình OAuth consent và tài khoản thử nghiệm nếu ứng dụng đang ở chế độ Testing.
3. Tạo OAuth client loại **Web application**, thêm đúng redirect URI `http://localhost:8090/api/google/callback`.
4. Chép `.env.example` thành `.env`, đặt `GOOGLE_CLIENT_ID` và `GOOGLE_CLIENT_SECRET`. Không gửi secret qua chat, không đưa vào frontend hoặc Git.
5. Khởi động lại ứng dụng, đăng nhập admin, mở **Kết nối Google → Kết nối Google**, cấp các quyền chỉ đọc.

Tài sản mặc định đã được đưa vào cấu hình:

- GA4 property: `484358741`.
- Search Console: `https://kinderhealth.vn/`.
- Google Sheet keyword: ID được đối chiếu từ script cũ, tab `Ranking`.
- Múi giờ báo cáo: `Asia/Ho_Chi_Minh`.

Tài khoản Google cần được chia sẻ quyền riêng trên cả ba tài sản. Trạng thái thiếu quyền / lỗi API / không có dữ liệu được ghi riêng. Kết nối có thể cần cấp lại khi hết hạn hoặc bị thu hồi.

Backend giữ access token và refresh token mã hóa bằng Fernet trong database. Compose PostgreSQL dùng biến `ENCRYPTION_KEY` cố định; local SQLite có thể dùng khóa ở `instance/encryption.key`. Cookie đăng nhập là mã phiên ngẫu nhiên HttpOnly; token Google không được gửi xuống trình duyệt, không lưu trong localStorage. Khi ngắt kết nối, backend cố gắng thu hồi ở Google rồi xóa kết nối cục bộ; giao diện báo rõ nếu Google chưa xác nhận.

Tài liệu API đã đối chiếu: [Google OAuth Web Server](https://developers.google.com/identity/protocols/oauth2/web-server), [GA4 runReport](https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/properties/runReport), [Search Analytics](https://developers.google.com/webmaster-tools/v1/searchanalytics/query), [Sheets values.get](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/get).

## Kết nối Meta OAuth

Admin hỗ trợ Meta OAuth, khám phá/chọn Page và Ad Account, sync worker, receipt, Dataset, review và publication trong các phạm vi client được phép. Token chỉ lưu mã hóa ở backend. Facebook Content VIO có bằng chứng nghiệm thu theo ngày và collector Insights mới; không suy ra mọi KPI hoặc mọi tài khoản đã được nghiệm thu. Facebook Ads có adapter nhưng lượt rebrand này không xác nhận dữ liệu live. Xem [ma trận triển khai và bằng chứng](docs/VIOAGENCYANALYTICS_ARCHITECTURE.md) và [cấu hình Meta OAuth](docs/meta-oauth.md).

## Luồng đã triển khai

| Màn hình | Chức năng |
| --- | --- |
| Đăng nhập | Tạo admin đầu tiên tại localhost, phiên 8 giờ, giới hạn đăng nhập sai, đăng xuất, khôi phục mật khẩu bằng CLI |
| Tổng quan | Trạng thái nguồn, ngày dữ liệu, lần thành công trước đó, báo cáo / tác vụ / xuất Excel gần nhất |
| Phân tích & Xuất Excel | SEO tổng hợp hoặc từng nguồn GA4/GSC/Keyword/GMB, chọn kỳ, so sánh kỳ trước, GSC loại trừ `/san-pham/`, biểu đồ và bảng, cảnh báo độ mới |
| Báo cáo đã lưu | Tạo HTML từ kết quả hợp lệ, nhập HTML cũ, xem trước trong sandbox, mở, tải, phiên bản, xuất bản nội bộ và chọn lại bản trước |
| Kết nối Google | OAuth do backend xử lý, kiểm tra riêng từng nguồn, kết nối lại / ngắt kết nối; chỉ admin |
| Lịch sử | Người chạy, tham số, thời gian, trạng thái từng bước, chạy lại lỗi, ngăn tạo trùng tác vụ đang chạy |
| Dữ liệu đầu vào | CSV UTF-8, giới hạn request 5 MB, preview, kiểm tra cột / số liệu / mã cơ sở, file trùng và kỳ chồng lấn |
| Lịch tự động | Ngày/tuần/tháng, giờ Việt Nam, 7/28 ngày đến hôm qua hoặc tháng trước, tạo bản nháp hoặc xuất bản nội bộ khi hợp lệ, bật/tắt |
| Người dùng | Ba vai trò, cấp quyền theo loại báo cáo, vô hiệu hóa, đổi mật khẩu và thu hồi phiên cũ |
| Cài đặt | Tên đơn vị và người lập, hiển thị chính sách múi giờ / phiên bản / xuất bản |

Viewer có thể phân tích và xuất Excel trong phạm vi báo cáo đã cấp; không tải CSV, lưu HTML, xuất bản, đổi nguồn hoặc quản lý người dùng. Operator được tải CSV, lưu và xuất bản báo cáo được cấp. Mọi quyền đều kiểm tra tại API, không chỉ ẩn nút.

## Quy tắc dữ liệu

- Tác vụ hoàn tất không đồng nghĩa tất cả nguồn hợp lệ. Kết quả có thể `partial` hoặc `failed`; nguồn thành công vẫn xem được.
- Mỗi nguồn có `requested_start`, `requested_end`, `latest_available_date`, `fetched_at`, `status`. Ngày có dữ liệu cuối cùng là ngày thực sự được nguồn trả về; không suy đoán ngày trễ cố định.
- GA4 KPI tổng được truy vấn riêng; không cộng active users theo ngày thành tổng kỳ. GSC KPI cũng lấy riêng; tổng hàng truy vấn có thể khác KPI.
- GSC dùng `web`, `dataState=final`, tối đa 25.000 hàng truy vấn đầu; cảnh báo nếu đạt giới hạn. Ngày GSC theo múi giờ nguồn `America/Los_Angeles`, được ghi riêng với múi giờ báo cáo.
- Không lấp khoảng ngày thiếu bằng 0; biểu đồ ngắt đoạn khi thiếu ngày.
- Kỳ so sánh là số ngày bằng kỳ hiện tại, kết thúc trước ngày bắt đầu một ngày. Nếu thiếu kỳ so sánh, vẫn xem được dữ liệu hiện tại nhưng phải bỏ so sánh hoặc sửa nguồn trước khi xuất.
- Đổi bộ lọc chưa bấm Xem báo cáo sẽ khóa xuất Excel / lưu HTML. Khoảng ngày ghi bên kết quả luôn là bộ lọc đã áp dụng.
- Mỗi lần phân tích tạo một dataset bất biến. Excel lấy từ dataset đó, không gọi lại API nguồn.
- Excel có metadata, ngày kiểu Excel, chỉ số dạng số, tỷ lệ 0–1 có nhãn đơn vị. Chuỗi từ nguồn được ép kiểu text để tránh công thức trong ô.
- Nguồn lỗi/thiếu không được xuất Excel hoặc tạo bản HTML hợp lệ; không thay bản đã xuất bản trước đó.

### Google Sheets Ranking

Hỗ trợ bảng dài: `Từ khóa, Vị trí, URL, Ngày` (tên tiếng Anh tương đương cũng được). Ngày có năm: `YYYY-MM-DD`, `DD/MM/YYYY`, hoặc `Jul/16/2026`.

Hỗ trợ bảng rộng, mỗi cột là ngày tracking. Nếu header chỉ có `Jul/16` hoặc `7/16`, quản trị backend cần đặt `KEYWORD_TRACKING_YEAR` bằng **năm dữ liệu thật**; ứng dụng không tự gắn năm hiện tại cho dữ liệu cũ. Cột ngày đầy đủ năm vẫn được ưu tiên giữ nguyên. Giá trị ngày/vị trí sai sẽ báo nguồn không hợp lệ, không chuyển sang dữ liệu mẫu.

### CSV Google Business Profile

Hỗ trợ CSV Performance Report của Google, gồm `Store code`, `Business name`, bốn cột lượt xem Search/Maps mobile/desktop, `Calls`, `Directions`, `Website clicks`. Bỏ đúng dòng mô tả cột của Google nếu có. Mã cơ sở vẫn giữ kiểu text kể cả có số 0 đầu.

Cũng hỗ trợ schema đơn giản trong `static/gmb-template.csv`. File mẫu chỉ có tiêu đề, không có số liệu giả.

Người tải chọn kỳ CSV. Nếu tên file có hai ngày thì phải khớp kỳ đã chọn. Cùng cơ sở không được có kỳ chồng lấn. Khi tạo báo cáo, kỳ phải khớp toàn bộ file CSV; ứng dụng không chia tỷ lệ số tổng thành số liệu ngày. So sánh GMB cần hai file khớp hai kỳ và cùng tập mã cơ sở.

## Tích hợp dự án KDH-Report cũ

`LEGACY_REPORT_DIR` mặc định trỏ đến `D:/KDH-Report/KDH-Report`. Admin bấm **Báo cáo đã lưu → Nhập báo cáo cũ** để sao chép nội dung bảy HTML theo danh sách tên file cố định. Thao tác không chạy script, không chỉnh file hoặc credential ở dự án cũ. Nhập nhiều lần không tạo trùng cùng nội dung.

HTML cũ được ghi **chưa kiểm chứng dữ liệu**, không tự suy luận kỳ dữ liệu từ ngày sửa file. Chúng được xem/tải nhưng không được xuất bản lại qua luồng dữ liệu hợp lệ. Đặc biệt, `generate_seo_report.py` cũ có fallback sang số liệu mẫu khi lỗi nguồn, nên ứng dụng này dùng adapter Google riêng. `creator-backend` là backend Node/MongoDB cho nền tảng nội dung, có phạm vi khác; không được ghép làm backend tài khoản thứ hai.

Thư viện HTML cũ của Facebook Ads, Facebook Content và TikTok vẫn được giữ. Luồng Meta mới có adapter riêng và quy trình kiểm chứng/release; không phải chức năng của Google OAuth. TikTok hiện vẫn là scaffold/planned, chưa có tích hợp production chỉ vì đã có giao diện hoặc Metric Catalog.

Xuất bản HTML cũ là **xuất bản nội bộ trong Admin**. Published Report Bundle có luồng phát hành và cấp quyền Viewer riêng sang Web; không mặc định public và không đẩy GCS. Live Dashboard SaaS, billing và white label chưa triển khai. Không có nút giả báo thao tác đã thành công.

## Vận hành Docker/local

- Một process Waitress và một worker nền. File lock ngăn chạy hai server cùng thư mục dữ liệu. Đây là cấu hình cho một đơn vị, không phải hàng đợi phân tán.
- Tác vụ chờ được lưu trong database đã cấu hình (PostgreSQL ở Compose hiện tại). Tác vụ đang chạy khi server dừng sẽ chuyển `interrupted` ở lần mở lại, có thể thử lại.
- Lịch dùng timezone IANA Việt Nam. Khi mở lại sau thời gian tắt, xử lý một lần bị lỡ rồi tính lần tới; không chạy bù toàn bộ lịch sử.
- Với Compose PostgreSQL: sao lưu database, `admin-data` và khóa `ENCRYPTION_KEY` theo [hướng dẫn Docker](docs/DEPLOY_DOCKER.md). Với local SQLite: database ở `instance/kdh.sqlite3`; nếu dùng khóa file thì giữ cả `instance/encryption.key`. Excel mới lưu trong database; Excel của bản cũ vẫn đọc từ `instance/exports/`. Giữ khóa mã hóa tương ứng cùng bản sao lưu trong kho nội bộ hạn chế quyền đọc.
- Không đưa `instance`, `.env`, credential vào Git, thư mục web hoặc bản chia sẻ frontend. Các thư mục này đã được loại trong `.gitignore` / `.dockerignore`.
- Khi triển khai ngoài localhost, đặt HTTPS reverse proxy, `APP_URL` đúng origin, `COOKIE_SECURE=1`, redirect URI HTTPS đúng trong Google Cloud. Cấp quyền đọc/ghi thư mục dữ liệu cho tài khoản dịch vụ, không cho người dùng không liên quan.
- Chỉ expose cổng admin sau lớp mạng nội bộ theo nhu cầu đơn vị. Các API dữ liệu đều yêu cầu đăng nhập.

### Demo Render Free

Để tạo admin đầu tiên khi không có Shell, đặt `INITIAL_ADMIN_EMAIL` và `INITIAL_ADMIN_PASSWORD` trong Environment của Render. Khi database chưa có user, ứng dụng tạo admin với toàn quyền; mật khẩu phải dài 12–200 ký tự. Nếu database đã có user, các biến này không thay đổi tài khoản hiện có. Không commit các giá trị này vào Git. Render Free không có persistent disk, vì vậy database, tài khoản và báo cáo có thể mất khi service được triển khai lại hoặc khởi động lại; chỉ dùng cho demo tạm thời.

Docker là tùy chọn; chưa cần cho bản local:

```powershell
docker compose up -d --build
docker compose exec admin python run.py create-admin --email ten@kinderhealth.vn
```

Compose mount dự án cũ chỉ đọc và volume riêng cho dữ liệu admin. Tạo admin bằng CLI vì kết nối qua Docker không phải loopback của container.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm.cmd ci --ignore-scripts
npm.cmd test
.\.venv\Scripts\python.exe tests/run_http_smoke.py
```

Chạy toàn bộ test Python bằng `python -m unittest discover -s tests -v`, cùng các test giao diện bằng `npm test`. Python dùng `unittest`, Flask test client, SQLite tạm và schema PostgreSQL riêng cho từng bài; giao diện dùng Node test runner và JSDOM với HTTP API giả lập. Các test dùng cấu hình OAuth riêng, không phụ thuộc Client ID/Secret thật trong `.env`. Xem [hướng dẫn kiểm thử PostgreSQL](docs/DEPLOY_DOCKER.md#kiểm-thử).

Test Python kiểm tra auth/CSRF/phân quyền, queue, dữ liệu thiếu/độ trễ, Excel theo snapshot, công thức độc hại, CSV, phiên bản/xuất bản, OAuth state, lịch chạy và chế độ demo. Test DOM kiểm tra đăng nhập, bộ lọc chưa áp dụng, export, điều hướng, chuyển demo/thật và xóa dữ liệu phiên cũ khi hết hạn. Dữ liệu giả trong kiểm thử và bộ demo được chọn riêng; lỗi nguồn thật không tự dùng dữ liệu mẫu.

`tests/run_http_smoke.py` tự mở Waitress cùng worker ở cổng 8091, chạy chuỗi đăng nhập → upload CSV → phân tích → tải Excel → lưu/xem HTML → xuất bản → đăng xuất, rồi dừng server. Mỗi lần chạy dùng một thư mục dữ liệu mới `test-results/http-smoke-*`, giữ các file kiểm thử để kiểm tra lại; không dùng dữ liệu Docker hoặc `instance`. Nếu cổng 8091 đang được dùng, lệnh dừng trước khi gửi yêu cầu. Có thể chạy lặp lại mà không xóa dữ liệu test cũ.

Unit/DOM tests không thay thế nghiệm thu browser, tải hoặc dữ liệu thật. Repository có script và bằng chứng browser trong các đợt triển khai trước; kết quả rebrand hiện tại được ghi riêng trong [file map](docs/REBRAND_FILE_MAP.md). Luồng cấp quyền OAuth và số liệu Google thật cần kiểm tra với tài khoản được cấp quyền trên các tài sản của đơn vị; JSDOM và adapter giả lập không xác nhận được những quyền đó.

Để mở máy chủ UI test riêng: `.\.venv\Scripts\python.exe tests/serve_ui.py` tại cổng `8091`. Dữ liệu test nằm ở `test-results/ui-state`, không dùng `instance` của ứng dụng thật.
