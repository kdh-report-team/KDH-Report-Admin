# VioAgencyAnalytics — bối cảnh toàn hệ thống

## Định hướng 23/10/2026 — rebrand source và chuẩn bị SaaS

VIO Agency phát triển, sở hữu và vận hành VioAgencyAnalytics. Xem [Product Vision](VIOAGENCYANALYTICS_PRODUCT_VISION.md), [Architecture](VIOAGENCYANALYTICS_ARCHITECTURE.md), [Roadmap](SAAS_MIGRATION_ROADMAP.md) và [audit/file map](REBRAND_FILE_MAP.md). Các tài liệu này định nghĩa mục tiêu tương lai; không tuyên bố đã triển khai Google Sign-in, Organization, multi-tenant hoặc Live Dashboard customer.

Repository local là `D:/VioAgencyAnalytics/VioAgencyAnalytics-Admin` và `D:/VioAgencyAnalytics/VioAgencyAnalytics-Web`. Remote/worktree cũ giữ nguyên. Audit rebrand chỉ đọc source và bằng chứng đã có, không kiểm tra runtime Docker, không đọc `.env`, không gọi provider hoặc PostgreSQL. Web production tiếp tục đọc Published Bundle theo quyền/revision; internal preview vẫn là luồng riêng có kiểm soát, không phải Live Dashboard.

Các mục có ngày bên dưới được giữ nguyên như lịch sử. Trạng thái PASS, IP, image, grant hoặc permission trong đó không phải kết quả kiểm tra mới ngày 23/10.

## Cập nhật 22/10/2026 — Biểu đồ Page Insights trên New

New chung 8080 đã cập nhật `kdh-new:insights-chart-20261022-fed378fa5436`:
sửa nhãn trục Y bị cắt, ngày dd/mm và resize/selector Insights. 317 tests PASS;
4 chuỗi × 5 viewport browser PASS trên report mới revision 1; dữ liệu/grants không đổi.
Admin, PG, relay/gateway và mock giữ nguyên. Chi tiết và rollback:
[biểu đồ Insights](insights-chart-20261022/README.md).

## Cập nhật 22/10/2026 — Khôi phục mở báo cáo Facebook mới

Đã xác nhận người dùng đã phát hành Bundle `rpt_795f2c05f18e6eed68b2bb247e731317`,
revision 1, provisional, client_meta_sandbox, grant active revision 1–1.
New bị lỗi kết nối do private relay restart sau Docker đổi IP PostgreSQL;
đã cập nhật đúng địa chỉ kiểm tra cách ly và restart riêng relay. Browser handoff
PASS 1440/390; dashboard 15/81/10, UTC, engagements/shares null; sai revision bị chặn.
Bundle/grants không đổi. Còn rủi ro cấu hình kiểm tra IP tĩnh khi Docker đổi IP.
Chi tiết: [khôi phục VIO handoff](vio-handoff-recovery-20261022/README.md).

## Cập nhật 22/10/2026 09:47 — VIO đã đồng bộ Insights, chờ duyệt Dataset mới

User chọn lại Page và cho phép một retry sau job đầu bị gián đoạn. Retry
`5e320fe5250726ec421829fceedcb94f` succeeded, 36/100 requests; sync
`d1cec7997ce5bbd67b693a2eca5ad16e`, snapshot `0dd5107c80ab72342a4889d2f59b033f`.
Receipt/daily rows PASS. Đã tạo một Dataset `a036be96e3977c32cd61541afe37b329`,
awaiting_review, có thể duyệt nội bộ; chưa review/Candidate/release/grant.
15 bài, 81 reactions lifetime, 10 comments, đủ 28 điểm mỗi 4 metric Page và
15/15 bài cho 2 metric Post. Day boundary 07:00 UTC nên tổng kỳ UTC không suy ra.
Revision 1/grants không đổi. Admin browser1440/390 PASS. Chi tiết missing fields,
evidence và khôi phục relay sau Docker restart trong
`docs/vio-insights-live-20261022/README.md` (phần kết quả cuối).

## Cập nhật 22/10/2026 09:32 — Insights VIO đọc thật thành công

Người dùng hoàn tất OAuth 09:29; read_insights đã lưu, Page task ANALYZE được
Meta xác nhận trong diagnostic 11/20 requests, 15–17/10, đúng 3 bài VIO. Cả 4
metric Page và 2 metric Post trả số liệu thật. End_time ngày là 07:00 UTC;
không cộng thành tổng kỳ UTC 00:00, giữ period_boundary_mismatch cho tổng.
Chưa sync: OAuth callback đặt Page enabled=0; cần người dùng chọn lại Page qua
UI, không tự sửa asset. Không tạo Dataset/review/Bundle; revision 1 giữ nguyên.
Chi tiết: `docs/vio-insights-live-20261022/README.md` và `diagnostic.json`.

## Cập nhật 22/10/2026 — Admin/Insights và New đã deploy, chờ quyền Meta

Người dùng đã xác nhận phiên rebase New hoàn tất và cho phép tiếp tục New.
Admin VIO 8191 chạy `kdh-admin-meta:insights-20261021-cf97123433e7`;
New chung 8080 chạy `kdh-new:tonight-content-20261021-80351dfaa44b`.
Hash 12 file Admin và 19 file New trong container khớp source local đã kiểm thử.
Không migration, không sửa revision 1 hoặc grant. Admin 419 offline PASS +
146 PostgreSQL disposable PASS; UI 102 PASS; New 317 PASS trên exact image.

Browser sau Docker restart: Admin preview 7 mục → handoff hợp lệ → VIO revision 1
PASS, số liệu 15/80/10 và null/no_data/partial giữ nguyên. Desktop 1440/mobile 390,
drawer mobile, từ chối sai revision/no grant/origin và logout PASS. Dữ liệu nghiệp vụ
VIO không đổi. Chưa gọi provider, sync, tạo Dataset hoặc duyệt/phát hành mới.
Grant đọc lại ngày 22/10 vẫn thiếu read_insights; người dùng đang tự cấp quyền.

Docker Desktop đã được mở lại ngày 22/10. Các container tự khởi động theo policy,
bao gồm Admin chính 8090 trước đó dừng. Relay `kdh-shared-viewer-primary-relay`
đang restart loop, khởi động lại không khắc phục; nhánh 8090 → New chưa nghiệm thu.
Không đổi cấu hình relay hoặc isolation để né lỗi. Nhánh VIO 8191 → New 8080 PASS.
Docker default bridge đổi ID sau Engine restart; policy và các network dự án không đổi.

Trạng thái hiện hành và bằng chứng: `docs/tonight-delivery-20261021/README.md`.
Các mục bên dưới là lịch sử, không dùng image/status cũ để thay runtime hiện hành.

## Cập nhật 21/10/2026 — Đã deploy Facebook Content/Insights vào VIO 8191

Theo yêu cầu mới, sau các thay đổi đã qua kiểm thử, tiếp tục cập nhật Docker trong
phạm vi thử nghiệm đã xác minh; không tự mở rộng sang production hoặc môi trường
đang được phiên khác xử lý. Lượt này chỉ cập nhật Admin VIO 8191, giữ nguyên New.

Image đang chạy: `kdh-admin-meta:insights-20261021-cd9a3b495991`, container
`kdh-meta-2b-admin-20261016-132836-5c512a53`. Đã deploy 7 mục Facebook Content,
preview/editorial và collector Insights tùy chọn. Exact image: 78 backend PASS;
UI: 102 PASS; browser đăng nhập → handoff → revision 1 trên New 8080 PASS.
Wrong revision/no grant/wrong origin bị chặn; logout PASS. Hash dữ liệu nghiệp vụ,
network policy, New và các container khác không đổi. Không migration/provider/sync.

Grant thực tế vẫn thiếu `read_insights`; PERMISSION NOT READY, LIVE NOT RUN.
New checkout hiện hết rebase (HEAD `1e3df3c7f4a93576ad2599ceee99c1958e7cc636`)
nhưng giữ nguyên theo chỉ dẫn người dùng, chưa triển khai mapper Insights mới.
Admin chính 8090 vẫn dừng như trước lượt này. Không tự start hoặc cập nhật nó.

Backup mã hóa/rollback và bằng chứng: `docs/content-insights-deploy-20261021/README.md`.
Startup manifest dùng bởi Start-KDH đã cập nhật identity của VIO Admin mới.

## Cập nhật 21/10/2026 — Insights collector local, chờ New hết rebase

Admin đã có collector Page/Post Insights v26 tùy chọn: 4 metric Page và 2 metric
Post, tách lỗi/permission khỏi đọc bài, request budget và projection có kiểm tra
ranh giới UTC. Lưu raw measurements an toàn trong snapshot/receipt hiện có; 7 mục
và workflow review/publication giữ nguyên. Không có migration hoặc live sync.
Grant VIO đọc lại vẫn thiếu read_insights. Diagnostic thật NOT RUN.

141 test PostgreSQL từng SKIP đã chạy PASS trên DB disposable; nhóm Insights/OAuth
mới có 5 PostgreSQL PASS. Admin UI 102 PASS; browser fixture 5 viewport PASS.
New đang được phiên khác interactive rebase lên 56a51a0 với nhiều conflict. Người
dùng xác nhận giữ nguyên New; ngừng sửa New và chưa deploy ứng dụng nào. Phải
đối chiếu lại mapper/projection sau rebase, không dùng kết quả test cũ để deploy.
Admin chính 8090 được thấy đang dừng sau Docker restart; không sửa trong lượt này.

Chi tiết catalog, trạng thái CODE/DEPLOY/PERMISSION/LIVE, test evidence và bước
tiếp theo: `docs/FACEBOOK_CONTENT_INSIGHTS_20261021.md`.

## Cập nhật 21/10/2026 — Facebook Content requirements (source local, CHƯA deploy)

Đã audit mock 8082 và report VIO revision 1 trên New 8080 bằng browser/handoff hợp lệ.
Sau yêu cầu tiếp theo, bổ sung contract `facebook-content-report-v1`: Admin lưu metadata
bài, phân bố định dạng, chủ đề do agency nhập, nhận xét theo 7 mục; preview read-only
và đóng băng vào Dataset mới. Review/source-check/release hiện có chốt cùng contract;
New validate/copy và render bằng giao diện sẵn có. Revision cũ giữ nguyên đường đọc.

Chưa có Page/Post Insights collector và grant đang lưu thiếu `read_insights`.
Reach/ER/follower/link clicks/paid-organic/so sánh kỳ chưa được nghiệm thu; Admin hiện
lý do thiếu, không điền mock. Không gọi Graph, tạo Dataset/Bundle thật hoặc deploy.
Test: Admin Python 400 PASS/141 SKIP; UI 101 PASS; New 305 PASS; browser fixture 10
viewport PASS. Hash nghiệp vụ hai DB và HEAD không đổi. Chi tiết, matrix, screenshot
paths và giới hạn trong `docs/FACEBOOK_CONTENT_REQUIREMENTS_20261021.md`.

## Cập nhật 21/10/2026 — polish biểu đồ và bảng Facebook

New 8080 image `kdh-new:content-shell-20261021-3c0130851869`: biểu đồ bài đăng
dạng cột, panel full width, căn phải tiêu đề/số liệu và CSS version URL mới.
Sửa quy tắc grid bị CSS chung lấn trên màn hình rộng. Browser report thật PASS
ở 1920/1536/1440/1024/768/390/360, đo căn cột <2px; Python 292 PASS.
Không đổi dữ liệu, ACL, mạng hoặc hai Admin. Xem `docs/content-polish-20261021/RESULT.md`.

## Cập nhật 21/10/2026 — báo cáo Facebook dùng sườn chung

New 8080 đã dùng sườn Facebook Content gốc cho Published Bundle, ẩn các khối/menu
chưa có dữ liệu; không đổi null/zero/lifetime hoặc Bundle. VIO login/handoff và
responsive 1440/1024/768/390/360 PASS; New 292 tests, Admin UI 100 tests PASS.
Xem `docs/content-shell-20261021/RESULT.md` và manifest `responsive-release`.
Image hiện hành `kdh-new:content-shell-20261021-0c7aaa9bea7c`.

Khi Docker restart trong lượt này, đã khôi phục relay chính và cố định New ở
192.168.144.3 / 192.168.96.3 trên hai mạng Viewer cũ, tránh tranh IP relay .2.
Phép thử chặn DB của relay chính dùng IP PostgreSQL đã inspect là 172.26.0.4;
upstream Admin vẫn 172.26.0.3:8090. Không recreate DB/gateway hoặc mở thêm mạng.
Revalidate IP DB khi topology đổi; giữ nguyên deny guards. Hai DB business hashes
không đổi; manifest Start-KDH đã cập nhật đúng container New cuối.

## Cập nhật 21/10/2026 — hai Admin, một New

Đã triển khai Admin chính 8090, Admin VIO 8191 và một New chung 8080.
Primary giữ client_meta_sandbox theo quyết định người dùng; không chuyển dữ liệu
hoặc grant giữa hai database. New chọn backend theo hai origin được cấu hình:
localhost:8080 → primary; 127.0.0.1:8080 → VIO. Nút mở báo cáo tự chọn origin;
query client_id không chọn backend hoặc cấp quyền. Cookies host-only tách phiên.

VIO login → handoff → báo cáo rpt_4909119771c69125897d8bca84444abe revision 1
đã browser PASS trên 8080, kể cả sau restart app. Primary login page và đường
backend PASS; chưa có Bundle/grant primary để nghiệm thu report E2E primary.
New không nối mạng DB; chỉ qua hai relay cố định, không default route/Internet.
Các report/grant/dataset và hash bảng nghiệp vụ của hai DB giữ nguyên.

Khởi động đúng dịch vụ bằng Start-KDH.cmd hoặc giữ các dịch vụ active chạy với
restart unless-stopped. Không Run toàn bộ container backup/test cũ. Xem
docs/shared-viewer-20261021/RESULT.md; không dùng compose New một-backend cũ.
New 8193 cũ được giữ stopped cho rollback. Bản thiết kế MockDb 8082 riêng không
thuộc luồng báo cáo thật và không bị sửa.

## Cập nhật 20/10/2026 — hợp nhất cải tiến vào cặp ứng dụng chính

Admin `main` HEAD `6b52ee2`, New `main` HEAD `837f655`; không đổi HEAD/branch.
Source Viewer từ working tree VIO đã được đưa vào working tree New chính,
chưa commit. Admin 8090 và New 8080 đã cập nhật image bất biến, healthy.
Người dùng quyết định giữ `client_meta_sandbox` trên Admin chính; VIO sandbox
riêng và mọi dữ liệu/grant của nó không chuyển sang chính.

Database chính chưa có Bundle VIO. Đã kiểm tra anonymous browser và đường
New → Admin, nhưng chưa kiểm tra authenticated E2E báo cáo thật trên cặp chính.
Mọi hash table chính giữ nguyên sau deployment; không sync, publish hay migration.
Chi tiết image, test PASS/SKIP, backup/rollback và giới hạn tại
[`KDH_PRIMARY_UNIFICATION_RESULT.md`](KDH_PRIMARY_UNIFICATION_RESULT.md).
Revalidate runtime trước lần thao tác tiếp theo; các mốc dưới đây là lịch sử.

## Luồng hiện hành 14/10/2026 — chỉ đăng nhập tại Admin

Đăng nhập Admin → chọn report/revision → Mở báo cáo → dashboard New.
New đã bỏ form/API đăng nhập và danh sách riêng. Root và bookmark login/list cũ
chuyển về Admin `/viewer/reports`; phiên xem hết hạn dùng handoff để quay lại đúng
báo cáo. Auth, ACL, CSRF, Publishing Guard và preview riêng vẫn được giữ.
Các điểm vào đều dùng lại trang đăng nhập Admin gốc. Đã bỏ form handoff không có
giao diện; không thay `loginView`, template index, CSS hoặc dashboard đã thiết kế.
Chi tiết và kết quả đợt này trong `ADMIN_NEW_HANDOFF.md` và tài liệu liên repo.

Đã cập nhật container local Admin 8090/New 8080 ngày 14/10, cả hai healthy.
338 Admin Python / 225 New pytest / 69 UI / 1 HTTP E2E đều PASS, không skip;
Chrome fixture PASS. HTTP runtime và hash code trong container đạt, dữ liệu/volume/
`.env`/khóa mã hóa giữ nguyên, backup PostgreSQL đã đọc kiểm tra đầy đủ. Lượt sửa
giao diện đã rebuild riêng Admin; Chrome headless kiểm trực tiếp trang đăng nhập
runtime ở desktop/mobile đạt. Luồng click có đăng nhập được kiểm bằng DB fixture,
không dùng phiên người dùng hoặc sửa báo cáo/quyền trên DB thật.

## Mốc lịch sử 13/10/2026 — Admin → New và dashboard Bundle

Đã bổ sung handoff một lần có state/PKCE và phiên Viewer theo report/revision,
migration 8; New gắn Bundle vào sáu template dashboard hiện có. Xem
[ADMIN_NEW_HANDOFF.md](ADMIN_NEW_HANDOFF.md) để biết cấu hình, chính sách thu hồi,
kiểm thử, ảnh và giới hạn. Chỉ build/kiểm tra môi trường tách biệt; chưa nâng cấp
container runtime hoặc thay `.env`. Working tree có thêm thay đổi Meta ngoài phạm
vi handoff; giữ nguyên khi tiếp tục. Đường dẫn hiện tại ở `D:\KDH-Report-All\`.

## Cập nhật tiếp nối 10/10/2026 — đọc trước các mốc lịch sử bên dưới

Trạng thái code local hiện tại đã đi xa hơn các mục 5–9 viết ngày 07–08/10. Xem [KDH_HANDOVER.md](KDH_HANDOVER.md) và [audit Marketing](marketing-remaining-implementation.md) để tiếp tục đúng việc.

- Admin local HEAD `5c3d657`, New local HEAD `028d317`; có thay đổi chưa commit ở cả hai. Không đồng nhất với GitHub hoặc image đang chạy.
- Đã có Platform Dataset, Marketing Dataset/Review/Candidate, Source Verification/Release Approval, Release Snapshot riêng, guard publication và ACL theo report/revision. Migrations mới là **6, 7**, giữ migrations trước.
- Admin có `/marketing` để mở lại snapshot, kiểm tra, duyệt, tạo release/Bundle, publish và cấp quyền Viewer.
- New có repository/mapper/service/templates Bundle, `/login`, `/reports/{id}?revision=N` và internal preview riêng cho Admin. New gọi HTTP Admin; không đọc DB Admin hay gọi provider. Production đóng dashboard mock cũ.
- Kiểm thử gần nhất: **295 Admin Python đạt trên SQLite/PostgreSQL, không skip; 69 UI đạt; 184 New pytest đạt; 1 HTTP E2E đạt**. Đã build và smoke hai container test; New được rebuild ngày 10/10, không nâng cấp runtime 8090/8080.
- Nguồn thật còn **BLOCKED** do chưa nghiệm thu permission/data KinderHealth. 12 nguồn/211 KPI là Catalog; luồng verification mới hiện cho GA4/GSC/Keyword Sheet có adapter và dữ liệu đủ kỳ. Các adapter khác không được mặc định là đã có.
- Đã chạy Chromium headless qua Playwright có sẵn: toàn bộ workflow, login/chart/menu/grant/revoke, 7 màn hình ở 1440/768/390px đạt. Sửa lỗi browser login do Referrer-Policy, focus nút logout và nhãn trục tỷ lệ; ảnh và log ở `test-results/marketing-browser/`.
- Không tự commit/push, sửa `.env`, đổi khóa mã hóa hoặc ghi fixture vào runtime. Các container test và PostgreSQL test đều tách biệt, không dùng volume khách hàng.

**Các phần phía dưới là bối cảnh/quyết định kiến trúc và mốc lịch sử; các câu “chưa có mapper”, “chưa có Platform Dataset”, migration 4 và số dữ liệu cũ không còn mô tả code mới.**

Đối chiếu kiến trúc hai repository ngày **07/10/2026**; cập nhật phần Data Foundation và Docker Admin ngày **08/10/2026**. Nguồn: yêu cầu của chủ dự án, sơ đồ “KDH-Report System Architecture Flow”, code và trạng thái Docker. Đây là tài liệu tiếp nối công việc; trạng thái triển khai và các điểm đang dở phải được kiểm tra lại khi code thay đổi.

## 1. Mục tiêu và các quyết định đã chốt

Một hệ thống báo cáo marketing cho KinderHealth, gồm hai ứng dụng có trách nhiệm riêng:

| Thành phần | Trách nhiệm | Công nghệ hiện tại |
| --- | --- | --- |
| **KDH-Report-Admin** | Kết nối nguồn, đồng bộ, chuẩn hóa, kiểm tra chất lượng, lưu Dataset, tạo và xuất bản Report Bundle; quản lý vận hành | Flask, Vanilla JS, worker, PostgreSQL trong Docker |
| **Kho dữ liệu do Admin quản lý** | Nguồn dữ liệu chuẩn duy nhất; lưu thông tin kết nối, dữ liệu nguồn, snapshot, phiên bản báo cáo | PostgreSQL; token nằm trong bảng secrets được mã hóa |
| **KDH-Report-New** | Backend đọc Bundle đã xuất bản; frontend trình bày cho khách hàng/sếp/người xem | FastAPI, Jinja2, Vanilla JS; Docker riêng |

- Chạy **Docker**, không tiếp tục triển khai Vercel.
- Giao diện phục vụ một khách hàng KinderHealth; giữ `client_id` trong kiến trúc, chưa mở rộng UI thành SaaS nhiều khách hàng.
- Giữ kiến trúc của từng repository; không gộp hai backend, không chuyển Admin sang React/Vue.
- Luồng HTML/Excel, báo cáo cũ, auth, OAuth và jobs hiện có vẫn phải hoạt động.
- Report Builder và Preview chỉ đọc Dataset snapshot; không gọi provider để lấy số liệu mới.
- Dataset và nội dung revision đã xuất bản phải bất biến. Dữ liệu mới tạo Dataset/revision mới.
- Không điền số liệu mẫu vào báo cáo thật khi nguồn thiếu/lỗi. Số 0 thật khác với không có dữ liệu.
- GA4, GSC và Keywords là nguồn kỹ thuật của SEO, không phải ba mục báo cáo cấp cao.
- Quyết định trước đây về tài khoản: khi triển khai Owner, chọn **admin đang hoạt động được tạo đầu tiên**. Đây là quyết định đã nhận, chưa phải tính năng đã có trong code hiện tại.

## 2. Cách đọc sơ đồ kiến trúc

Luồng mục tiêu:

```text
Google / Meta / TikTok / YouTube / GMB hoặc CSV
  -> Admin: kết nối + sync + chuẩn hóa + kiểm tra chất lượng
  -> Admin DB: daily_metrics + source_snapshots + nhật ký sync
  -> tạo immutable Dataset từ dữ liệu đã lưu
  -> Report Builder: chọn Dataset, kỳ, section, thứ tự
  -> Preview -> publish Report Bundle revision
  -> Admin Internal API (chỉ đọc, service token)
  -> Report-New: AdminBundleRepository
  -> BundleViewMapper + section resolver
  -> giao diện chỉ hiện các section đã xuất bản
```

“Kho dữ liệu chung” là nguồn sự thật chung về nghiệp vụ. **Report-New đọc qua Internal API của Admin**, không được đọc toàn bộ database hay nhận OAuth token. Admin ghi database qua lớp lưu trữ của mình; Internal Report API hiện tại chỉ phục vụ đọc Bundle.

Service token xác thực **backend New với backend Admin**. Nó không thay thế đăng nhập/phân quyền người xem cuối, và không được đưa xuống trình duyệt.

Ví dụ mục tiêu: người vận hành chọn Dataset SEO tháng 9, tạo Bundle gồm `overview` và `seo`, xem trước rồi xuất bản revision 1. Người xem mở New chỉ thấy hai mục đó. Nếu đồng bộ lại có dữ liệu khác, revision 1 giữ nguyên; cần Dataset mới và revision 2. Mở lại revision 1 phải thấy đúng số liệu đã xuất bản trước đó.

## 3. Phân biệt các lớp dữ liệu

| Lớp | Ý nghĩa và giới hạn |
| --- | --- |
| `connections`, `source_assets` | Tài khoản/kết nối và tài sản cụ thể: GA4 property, GSC site, Sheet, Page, Ad Account… Kết nối thành công chưa có nghĩa đã đồng bộ được dữ liệu. |
| `sync_runs`, `sync_watermarks` | Lịch sử chạy, kỳ yêu cầu, lỗi, ngày dữ liệu thật mới nhất; không dùng thời điểm job kết thúc thay cho độ mới dữ liệu. |
| `daily_metrics` | Số liệu chuẩn hóa theo ngày, được upsert khi provider điều chỉnh dữ liệu. Không phải snapshot báo cáo bất biến. |
| `source_snapshots` | Payload nguồn đã chuẩn hóa theo lần sync, giữ chi tiết như channels/pages/queries/keywords mà daily metrics chưa diễn tả đủ. Không phải raw HTTP response chứa credential. Code hiện upsert theo `sync_run_id`; không đồng nhất tính bất biến của lớp này với Dataset. |
| `datasets` | Snapshot dữ liệu phục vụ kiểm tra/phân tích, xuất file và làm đầu vào Builder. |
| `report_bundles`, `report_bundle_sections` | Gói báo cáo: client, kỳ, revision, chất lượng, branding, navigation và dữ liệu section đã chụp lại. |
| View model của New | Chuyển dữ liệu Bundle thành cấu trúc template/chart; không gọi provider, không tạo KPI kinh doanh còn thiếu hoặc áp dụng tỷ lệ mô phỏng từ mock. |

## 4. Code Admin hiện có và phần đang dở

Mốc rà soát ban đầu là branch `feat/postgres-primary-store` trên nền `ea84bb2`. Phần PostgreSQL, Google/source snapshots, kiểm thử và tài liệu đã được lưu trong commit **`8a2888b` — `update migration`**, sau đó gộp fast-forward vào **`main` ngày 08/10/2026** theo yêu cầu của chủ dự án. Tiếp tục làm việc trên `main`, không tự tạo feature branch mới; vẫn chỉ commit/push khi được yêu cầu.

Luôn phân biệt **architecture target**, **local current state** và **GitHub committed state**. Khi kiểm tra GitHub, đối chiếu commit trên `origin/main`; tài liệu/Compose cũ trước `8a2888b` không phản ánh runtime PostgreSQL đang chạy. Việc gộp Admin vào main không thay đổi trạng thái local chưa commit của Report-New ở mục 5.

| Phần | Trạng thái quan sát được |
| --- | --- |
| Auth và quyền | Có session, băm mật khẩu, CSRF, role admin/operator/viewer, giới hạn theo loại báo cáo; cập nhật tài khoản thu hồi phiên. Chưa có Owner, bộ quyền xem/chạy/xuất/publish tách riêng, vòng đời mời/reset/2FA đầy đủ. |
| Google | OAuth và adapter GA4/GSC/Sheets thật; lưu tình trạng nguồn riêng. Quyền tài khoản trên từng tài sản vẫn phải hợp lệ. |
| Meta | Có OAuth và quản lý kết nối; chưa có luồng đồng bộ dữ liệu Page/Ads hoàn chỉnh. |
| TikTok/YouTube | Có vị trí trong kiến trúc/UI; chưa có reporting adapter vận hành trong Admin. |
| GMB | Luồng CSV hiện có; không coi việc có màn hình GMB là đã tích hợp API Business Profile. |
| Data Foundation | Có clients, connections, assets, sync runs, watermarks, daily metrics. Một số màn hình chỉ đọc/tổng hợp từ API hiện có, thao tác chưa có backend được khóa. |
| Google persistence | Đã triển khai daily metrics và source snapshots lên Docker ngày 08/10/2026. Sync thành công/partial lưu kết quả chuẩn hóa; lỗi provider không được biến thành dữ liệu thành công. |
| Tạo Dataset | Luồng analysis hiện vẫn lấy nguồn rồi lưu Dataset. Chưa có `PlatformDatasetRepository` để xây Dataset hoàn toàn từ Data Foundation đã lưu. |
| Builder/Preview | Tạo draft, chọn Dataset, cấu hình section/thứ tự/trang mặc định, preview snapshot. Chưa hoàn thiện publish/revision trong UI Builder. |
| Bundle backend | Có tạo/sửa draft, revision mới, publish provisional/final và Internal API đọc snapshot. |
| HTML/Excel | Luồng xuất file/lưu HTML/xuất bản cũ vẫn tồn tại song song; không xóa khi nối New. |

Phần source snapshots đã hoàn tất ngày **08/10/2026**:

- Migration **4 — source_snapshots** đã áp dụng lên PostgreSQL Docker. Migration 1–3 được đối chiếu bằng AST với HEAD và giữ nguyên; không thay schema Dataset/Report Bundle.
- Đã sửa regression tại `Worker._google_platform_refs`: lấy đúng mapping do cấu hình Google hiện tại trả về, không chọn lẫn tài sản cũ. Chưa có kết nối vẫn tạo kết quả lỗi từng nguồn trong job/Dataset, không tạo tài khoản hoặc số liệu giả.
- Chỉ cấu hình GA4 vẫn chạy được GA4. Khi chạy SEO mà thiếu cấu hình GSC/Sheets, nguồn thiếu được ghi `invalid_data`; các nguồn hợp lệ vẫn được xử lý. Cấu hình nguồn trống bị chặn trước request Google.
- Provider lỗi không ghi daily metrics/source snapshot mới cho nguồn đó. Lỗi persistence ghi `persistence_error`, trả kết quả `invalid_data` với thông báo an toàn. Ghi daily metrics, snapshot và kết thúc sync vẫn qua các thao tác storage riêng; không được mô tả là giao dịch nguyên tử cho toàn bộ sync.
- Kiểm thử: **py_compile đạt; platform data 12/12; Google success/failure 8/8; toàn bộ Python 135/135 (SQLite và PostgreSQL, không skip); UI 65/65; JS syntax, HTTP smoke và git diff --check đều đạt**. Provider được giả lập trong tests; chưa xác nhận lấy số liệu từ tài khoản provider thật.
- Đã sao lưu PostgreSQL trước khi nâng cấp, kiểm tra archive đọc được, rebuild Docker và xác nhận Admin/PostgreSQL healthy. Số tài khoản/Dataset/Bundle giữ nguyên.

Log cục bộ, không đưa vào Git: `test-results/foundation-full-tests.txt`, `foundation-platform-tests.txt`, `foundation-google-tests.txt`, `foundation-readiness-app-tests.txt`, `foundation-readiness-ui-tests.txt`, `foundation-http-smoke.txt`. Backup trước migration: `test-results/backups/postgres-before-source-snapshots-20261008-a3e7a9da.dump` (nội bộ, không đưa vào Git hoặc image).

## 5. GitHub và working tree của Report-New khác nhau

[Repository GitHub](https://github.com/bac2908/KDH-Report-New), main/HEAD đã đối chiếu bằng `git ls-remote`: **837f655525d4ee061c1e1365d1e47b57bba175f4** (`update layout`). Local `D:\KDH-Report-New` có cùng HEAD, branch `feat/admin-bundle-repository`.

**Bản trên GitHub:** các trang Overview/SEO/Facebook Content/Facebook Ads/TikTok/YouTube dùng `ReportService -> ReportRepository -> integrations.mock`. Sidebar liệt kê các kênh cố định. Có scaffold SQLAlchemy nhưng đường báo cáo hiện tại không sử dụng nó; không có database báo cáo thứ hai đang được nối vào luồng này.

**Bản local bổ sung chưa commit:** `.env.example`, `app/config.py`, `app/repositories/admin_bundle.py`, `tests/test_admin_bundle_repository.py`.

- `AdminBundleRepository` dùng HTTP backend, gửi Bearer token, gọi đúng endpoint Internal API, hỗ trợ revision, phân loại lỗi và kiểm tra contract 1.0/published status/report ID. Không fallback sang mock.
- Repository này **chưa được ReportService/routes sử dụng**. Có file không đồng nghĩa UI đã lấy dữ liệu thật.
- Chưa tìm thấy `BundleViewMapper` hoặc section resolver nối với Bundle. JSON Dataset trong Bundle khác cấu trúc mock mà template/JS đang dùng.
- `app/presentation.py` đã có helper render HTML từng phần để cập nhật giao diện; đây chưa phải mapper đọc Bundle. Các CLI trong `scripts/real_data_tests/` chỉ kiểm tra quyền/provider độc lập, chưa cấp dữ liệu cho UI và không được dùng làm đường provider của New trong kiến trúc đích.
- Chưa có luồng trang theo report ID/revision đã xuất bản và quyền người xem hoàn chỉnh.
- Compose của New chưa truyền `REPORT_ADMIN_BASE_URL`/`REPORT_SERVICE_TOKEN` và chưa khai báo network chung với Admin. Giá trị `127.0.0.1:8090` bên trong container New không chỉ đến container Admin.
- Kiểm thử riêng repository đọc Bundle vừa chạy khi rà soát: **10/10 đạt**, dùng `httpx.MockTransport`. Đây không phải kiểm thử tích hợp thật giữa hai container.

Các file cần đọc khi tiếp tục bên New: `app/repositories/admin_bundle.py`, `app/repositories/reports.py`, `app/services/reports.py`, `app/routes/pages.py`, `app/routes/reports.py`, `app/routes/video.py`, `templates/components/dashboard/navigation.html`, `static/js/pages/`, `compose.yaml`.

## 6. Hợp đồng giữa hai dự án

Chi tiết tại [report-bundles.md](report-bundles.md). Endpoint đã có:

```text
GET /api/internal/v1/report-bundles/{report_id}?revision=N
Authorization: Bearer <backend-only service token>
```

- Schema `1.0`: `report`, `client`, `period`, `comparison`, `freshness`, `quality`, `navigation`, `branding`, `sections`.
- ID `rpt_...` ổn định; mỗi revision là một snapshot riêng.
- Draft không xuất hiện qua Internal API. Bỏ `revision` sẽ lấy revision đã xuất bản lớn nhất (`provisional` hoặc `final`).
- Provisional là bản đã xuất bản tạm; final phải qua kiểm tra chất lượng. Chuyển provisional sang final không được thay nội dung snapshot.
- Section keys chuẩn: `overview`, `seo`, `facebook_content`, `facebook_ads`, `tiktok`, `youtube`, `gmb`.
- **Chênh lệch cần xử lý:** validator Admin hiện chỉ cho chữ thường/số/gạch ngang nên khóa các key Facebook dạng gạch dưới trong UI; New hiện dùng slug URL `facebook-content`, `facebook-ads`, `google-maps`. Cần thống nhất key contract và ánh xạ URL ở lớp trình bày, không tự đổi contract theo slug cũ.
- Chỉ render section mà Bundle có và cho phép; đồng thời kiểm tra khi truy cập URL trực tiếp, không chỉ ẩn menu.
- KPI giao diện New đang có nhưng Dataset thật chưa cung cấp phải hiển thị thiếu dữ liệu phù hợp, không lấy số mẫu để bù. Bộ lọc kỳ chỉ được dùng dữ liệu snapshot thực sự có; không nhân số liệu mẫu theo số ngày.

## 7. Trạng thái Docker đã kiểm tra

Admin và PostgreSQL kiểm tra lại ngày 08/10/2026; Report-New giữ mốc quan sát 07/10/2026:

| Container | Địa chỉ trên máy | Quan sát |
| --- | --- | --- |
| `kdh-report-admin-admin-1` | `http://localhost:8090` | Healthy |
| `kdh-report-admin-postgres-1` | PostgreSQL `localhost:5433` | Healthy; PostgreSQL 16 |
| `kdh-report-new-app-1` | `http://localhost:8080` | Healthy ở lần rà soát 07/10; không khởi động/cập nhật New trong bước 08/10 |

Sau triển khai 08/10, truy vấn kiểm tra xác nhận migrations **1, 2, 3, 4**, **1 user, 0 datasets, 0 report bundles, 0 source snapshots**; số user/Dataset/Bundle khớp trước nâng cấp. `/health` và trang Admin trả HTTP 200. Chưa có snapshot nguồn vì chưa có lần đồng bộ thành công tạo dữ liệu thật; không bù bằng mock. Trạng thái healthy không chứng minh hai ứng dụng đã nối dữ liệu.

Compose Admin hiện dùng `postgres-data` cho PostgreSQL; giữ `admin-data` cho file ứng dụng và dữ liệu SQLite cũ phục vụ rollback. Khóa mã hóa lấy từ `ENCRYPTION_KEY` cố định. Không xóa volume, đổi khóa hoặc tự chuyển dữ liệu SQLite cũ khi chưa có kế hoạch migration.

## 8. Thứ tự tiếp tục theo các phụ thuộc

1. **Đã xong 08/10:** sửa regression Google/Data Foundation và chạy lại các kiểm thử bắt buộc.
2. **Đã xong 08/10:** triển khai và kiểm chứng migration 4/source snapshots trên Docker, giữ dữ liệu cũ.
3. **Bước tiếp theo:** nối lớp tạo Dataset từ dữ liệu sync đã lưu (`PlatformDatasetRepository`); kiểm tra kỳ, nguồn, độ mới, chất lượng và lineage. Chưa tạo lớp này trong bước source snapshots.
4. Hoàn thiện hợp đồng section và luồng review/publish/revision của Admin dựa trên snapshot.
5. Nối New qua repository + mapper + section resolver; cấu hình kết nối giữa container; kiểm tra cùng report ID/revision từ Admin đến giao diện và file xuất. Không mặc định rằng mọi biểu đồ mẫu đã có nguồn dữ liệu thật.
6. Hoàn thiện quyền người xem bên New và phần quản trị tài khoản bên Admin; sau đó mở rộng từng provider có kiểm thử. Các vấn đề quyền phải được xử lý trước khi mở truy cập báo cáo riêng tư cho bên ngoài.

Các mục 3–6 vẫn chưa hoàn tất. Đợt triển khai 08/10 chỉ hoàn thiện source snapshots và xử lý regression của Admin, kiểm thử rồi triển khai Docker Admin; không sửa code New. Sau đó chủ dự án lưu commit `8a2888b` và yêu cầu gộp về `main`, đẩy Admin lên GitHub. Không coi thao tác đồng bộ Git này là đã hoàn thành tích hợp UI của New.

## 9. Điểm bắt đầu cho lần làm tiếp

Đọc tài liệu này cùng [AGENTS.md](../AGENTS.md), [DATABASE_ARCHITECTURE.md](DATABASE_ARCHITECTURE.md) và [report-bundles.md](report-bundles.md). Kiểm tra `git status` của từng repo trước khi sửa, phân biệt code working tree với image/container đang chạy. Các quyết định đã chốt ở mục 1 không cần hỏi lại; chỉ cần làm rõ khi yêu cầu nghiệp vụ mới thay đổi phạm vi.

Các file Admin chính: `kdh/app.py` (API/auth), `kdh/google.py`, `kdh/meta.py` (provider), `kdh/jobs.py` (worker/sync), `kdh/platform_data.py` (Data Foundation), `kdh/migrations.py`, `kdh/core.py`, `kdh/postgres.py` (storage), `kdh/report_bundles.py`, `kdh/report_bundle_routes.py`, `static/app.js`, `static/views.js`, `compose.yaml`.
