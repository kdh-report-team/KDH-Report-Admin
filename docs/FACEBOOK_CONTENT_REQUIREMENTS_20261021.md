# Facebook Content: đối chiếu mock, contract và triển khai local

**Cập nhật tiếp theo:** collector Insights, kiểm thử PostgreSQL và blocker rebase
New được ghi tại [FACEBOOK_CONTENT_INSIGHTS_20261021.md](FACEBOOK_CONTENT_INSIGHTS_20261021.md).
Các mục dưới đây là baseline của lượt triển khai khung 7 mục trước collector.

Ngày: 21/10/2026. Phạm vi ban đầu là audit read-only; người dùng sau đó yêu cầu triển khai lấy các mục mock làm yêu cầu đầu ra. Thay đổi lần này chỉ ở source/test local; chưa deploy, chưa gọi Graph, chưa tạo dữ liệu nghiệp vụ trên runtime.

## 1. Kết luận audit

Mock 8082 đầy đủ vì có số liệu, tỷ lệ và nhận xét mô phỏng. Live 8080 chỉ hiển thị những dữ liệu được Admin thu thập và chốt trong Bundle. Không phát hiện New làm mất 15 bài / 80 reactions lifetime / 10 comments lifetime trong revision 1.

Ba nguyên nhân chính:

1. Adapter chỉ gọi `/{page_id}/posts`, lấy thời điểm đăng và bộ đếm lifetime; chưa lấy Page/Post Insights.
2. Snapshot cũ không lưu message, loại đính kèm hoặc permalink. `permalink_url` từng được yêu cầu nhưng bị bỏ ở bước chuẩn hóa Admin.
3. Mock dùng chủ đề, phân bố reach, ER và nhận xét mẫu riêng; các khối này không có equivalent đã được duyệt trong Bundle thật. Mapper live chủ động ẩn phần thiếu theo yêu cầu trước đó.

OAuth lưu trữ hiện `connected`; quyền đã lưu: `pages_show_list`, `pages_read_engagement`, `pages_read_user_content`, `ads_read`, `public_profile`. **Không có `read_insights`**. Đây là kiểm tra metadata lưu trữ, không xác nhận lại với Meta. Snapshot ghi Graph `v26.0`.

## 2. Bằng chứng runtime trước thay đổi

- Browser Windows Chromium, viewport 1440 × 1000, screenshot toàn trang.
- Mock: `http://127.0.0.1:8082/report/social`.
- Live: `http://127.0.0.1:8080/reports/rpt_4909119771c69125897d8bca84444abe?revision=1`.
- Live mở bằng đăng nhập Admin VIO và handoff hợp lệ; kết thúc riêng phiên test sau khi chụp.
- Client `client_meta_sandbox`, Page `2188688654687066`, kỳ 21/09–18/10/2026 UTC.
- Internal Dataset `ed761a6d1f6e554737b02dc03fc2a43f`.
- Release Dataset `e0072a5fe6155acada9d8b19fbf8c920`.
- Source snapshot `45c7036209c813bd8e943d3dce51c507`.
- Sync run `cbb42cde5643a1ede4610e51f8606157`.
- Có 1 source attestation trỏ đúng snapshot.
- Snapshot có 15 entries, 28 daily rows. Entries chỉ gồm `post_id`, `date`, `reactions_lifetime`, `comments_lifetime`, `shares_lifetime`.
- Entries, daily, identity, provenance trong Bundle khớp snapshot. Khác biệt hợp lệ: `data_origin` đổi sau xác minh và thêm cảnh báo phát hành.
- Snapshot fetched_at `2026-10-19T13:00:10.534159+00:00`.
- Tổng bài: 15, coverage 28/28 ngày. Reactions: 80 và comments: 10, coverage 15/15 bài.
- Engagement trong kỳ: null/no_data, 0/28 ngày. Shares tổng: null/partial, 7/15 bài. Những giá trị này vẫn còn trong view model; hai thẻ null bị ẩn.

Artifacts ngoài repository:

`C:/Users/Admin/AppData/Local/Temp/KDH-FB-Gap-Audit-20261021/`

- `mock-1440.png`, `real-1440.png`: ảnh runtime trước chỉnh sửa.
- `mock-text.txt`, `real-text.txt`, `mock-payload.json`, `real-payload.json`.
- `permissions.json`, `snapshot-evidence.json`, `browser.json`.
- `implementation-baseline.json`: HEAD, Git status và SHA256 source trước sửa.
- `admin-fixture-*.png`, `new-fixture-*.png`: QA source mới bằng fixture cô lập, KHÔNG phải báo cáo khách hàng.

## 3. Inventory mock và công thức

Code mock: New `app/integrations/mock/facebook_content.py`, template `templates/pages/facebook_content/`.

| Thành phần | Mock mặc định tháng 09/2026 | Live revision 1 |
| --- | --- | --- |
| Tổng quan | 48 bài; reach 318.4K; engagement 34.190; ER 10,74%; follower mới 850; link clicks 4.120 | 15 bài; 80 reactions lifetime; 10 comments lifetime |
| So sánh | Bài +4; reach +15,2%; engagement +9,1%; ER -5,3%; follower +18,6% | Không có kỳ so sánh |
| Định dạng | Reels, video dài, carousel, ảnh/album; số bài, tỷ trọng, reach TB và ER | Chưa có metadata định dạng |
| Chủ đề | Nhi khoa, dinh dưỡng, tiêm chủng, review; số bài, reach, ER, diễn giải | Chưa có taxonomy/nhãn |
| Bài đăng | 5 bài mẫu, 9 cột: tiêu đề, ngày, định dạng, reach, engagement, ER, comments, shares, clicks | 15 bài, cột ID/ngày/lifetime; link từ Page/Post ID |
| Tương tác | Reactions 22.450; comments 4.820; shares 2.800; clicks 4.120; tỷ trọng | Không có cơ cấu tương tác theo kỳ |
| Tin nhắn | Tỷ lệ phản hồi 98,5% | Không có nguồn |
| Organic/Paid | 212.500 / 105.900; 66,7% / 33,3%; tỷ lệ 2,0x | Không có metric phù hợp |
| Nhận định | 2 điểm nổi bật, 1 cảnh báo, 3 hành động; Reels +42%, gợi ý tăng 20% nội dung | Không có claim/nội dung biên tập đã duyệt |
| Bộ lọc | 7/30 ngày, 3/6 tháng, chọn ngày, so sánh; search tiêu đề/chủ đề; format/topic | Kỳ cố định theo revision; tìm/sắp xếp bảng |
| Điều khiển bảng | Tất cả/reach/engagement/shares/clicks; 2/5 dòng; modal chi tiết; xuất | Search, sort, 10/25/tất cả; chi tiết dữ liệu; CSV |
| Biểu đồ | Thanh định dạng, cơ cấu tương tác, organic/paid | Số bài theo ngày UTC |

Mock scale tổng quan theo số ngày/30, chia phân bố theo trọng số fixture. ER = engagements/reach ×100, CTR = link clicks/reach ×100. Bộ 5 bài chi tiết và tổng quan là fixture độc lập, không đối soát tổng. Paid reach được tạo từ tổng trừ organic; không được mang công thức này sang live vì unique audience có thể giao nhau. Nhận xét +42%, +20%, tỷ lệ phản hồi 98,5% là nội dung mẫu, không phải kết luận tính từ VIO.

## 4. Ma trận gap trước triển khai

Ký hiệu quyền: **P** = quyền Page đang lưu; **I** = cần `read_insights` cùng `pages_read_engagement` và Page task phù hợp. Tên file viết gọn: **AR** `kdh/meta_reporting.py`; **AC** `kdh/meta_contract.py`; **CR** `kdh/facebook_content_report.py`; **MM** `kdh/meta_marketing.py`; **NM** New `app/mappers/{bundle,dashboard,facebook_content}.py`; **NT** New `templates/pages/facebook_content/`.

| Mock field | Meta API support | Current permission | Admin collected | Snapshot stored | New mapped | Missing reason / loại | File to change | Priority |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Posts published | Page posts + creation time | P có | Có | Có | Đúng 15 | Đã có | Giữ AR/AC/NM | P0 bảo toàn |
| Daily posts | Đếm bài đúng ngày UTC | P có | Có | 28 ngày | Có | Đã có | Giữ AR/AC | P0 |
| Reactions/comments | Post summary lifetime | P có | Có | Có | Đúng 80/10 | Lifetime không phải kỳ | Giữ AC/NM | P0 |
| Shares | Optional post count | P có | Có một phần | 7/15 bài | null/partial đúng | B: thiếu count ở 8 bài, không suy 0 | AR/AC/CR | P0 |
| Reach | Unique media viewers mới; cần đối chiếu reach cũ và kỳ | I thiếu | Không | Không | Không có để map | B+C: tên/semantics v26 và quyền | AR/AC/CR/NM | P1 |
| Engagement trong kỳ | Page Insights có metric engagement; scope Page khác cohort bài trong kỳ | I thiếu | Không | null | no_data đúng | B+C+D: cần phạm vi và period được duyệt | AR/AC/CR | P1 |
| ER | Tỷ lệ do Admin tính từ đầu vào cùng scope | I thiếu đầu vào | Không | Không | Không | D: không chia lifetime cho reach khác kỳ | AC/CR | P1 |
| Followers mới | Page follows/follow/unfollow metrics, không đồng nhất likes | I thiếu | Không | Không | Không | B+C | AR/AC/CR/NM | P1 |
| Link clicks | Phải xác minh metric và loại click được hỗ trợ trên v26 | I thiếu | Không | Không | Không | C; không lấy Ads clicks | AR/AC/CR | P1 |
| CTR mock | Công thức clicks/reach, không phải CTR Ads mặc định | Thiếu đầu vào | Không | Không | Không | D: phải chốt mẫu số/nhãn | AC/CR | P1 |
| Post title | `message` excerpt hoặc metadata có thật; nhiều bài không có title | P có | Chưa gọi | Không | Không | B: chưa thu thập, không tự đặt tiêu đề như thật | AR/CR/NM | P0 |
| Post URL | `permalink_url` | P có | Có yêu cầu, bị bỏ | Không | Link dựng từ ID | B: mất tại normalizer Admin | AR/CR/NM | P0 |
| Post format | Attachment type; không đủ để suy Reels/video dài/carousel nghiệp vụ | P có | Chưa gọi | Không | Không | B+D: phân loại thận trọng | AR/CR/NM/NT | P0/P1 |
| Format reach/ER | Cần post Insights đủ coverage; không cộng unique thành Page reach | I thiếu | Không | Không | Không | C+D | AR/AC/CR/NT | P1 |
| Topic | Không có taxonomy agency tương đương | Không giải quyết bằng OAuth | Không | Không | Không | D: người phụ trách phân loại | CR/MM/NM/NT | P1 |
| Topic reach/ER | Từ post metrics đã xác minh + taxonomy | I thiếu | Không | Không | Không | C+D | AC/CR | P1 |
| Engagement breakdown | Cần metric thành phần cùng scope/kỳ | I thiếu | Chỉ lifetime | Không có breakdown kỳ | Không | B+C+D | AR/AC/CR/NT | P1 |
| Organic/Paid reach | Metrics reach cũ bị loại; view breakdown không tương đương unique reach | I thiếu | Không | Không | Không | C/E: không có equivalent đã nghiệm thu | AR/AC/CR | P1 |
| Message response 98,5% | Ngoài Content contract; cần nguồn/định nghĩa riêng | Chưa xác nhận | Không | Không | Không | C/E, không tái dùng hằng số mẫu | CR | P2 |
| Nhận định/hành động | Nội dung biên tập hoặc rules có bằng chứng | Không cần Graph để biên tập | Chưa có trong Meta preview | Không | Không có claim để hiện | D: cần lưu và human review | CR/MM/NT | P1 |
| Previous/deltas | Hai snapshot cùng định nghĩa và coverage | Contract Meta đang single-period | Không | Không | Không | D: chưa hỗ trợ comparison | MM/AC/CR | P1 |
| Filter format/topic | Lọc bảng trên metadata đã chốt | P/taxonomy | Thiếu metadata | Không | Chỉ search bảng | B+D, không đổi KPI toàn kỳ khi lọc bảng | CR/NM/NT | P2 |

Không có trường numeric nào trong revision 1 được chứng minh thuộc loại A (đã lưu nhưng map sai). Tuy nhiên New trước thay đổi có whitelist bảng 5 cột và nhánh live chưa có binding chuyên biệt cho taxonomy/nhận xét; mở rộng collector riêng lẻ sẽ không tự làm giao diện đầy đủ.

## 5. Đối chiếu Meta chính thức

- Page Insights reference: https://developers.facebook.com/docs/graph-api/reference/page/insights/
- Page Post fields: https://developers.facebook.com/docs/graph-api/reference/page-post/
- Deprecated metrics: https://developers.facebook.com/documentation/pages-api/platforminsights/page/deprecated-metrics

Page Insights yêu cầu Page token, `read_insights`, `pages_read_engagement` và task ANALYZE. Tài liệu v26 liệt kê `page_total_media_view_unique`, `post_total_media_view_unique`, `page_media_view`, `post_media_view`, follow metrics. Không mặc định chúng tương đương reach/impressions cũ. Unique theo ngày/tuần/28 ngày không cộng thành reach tùy kỳ; views chia `is_from_ads` không phải organic/paid unique reach. Tài liệu cũng cảnh báo giới hạn Reels và lịch cập nhật Insights.

Trang deprecation và trang reference đang có mốc ngày June 15 không đồng nhất (2025/2026); không dùng mốc chưa thống nhất làm contract runtime. Cần xác minh metric/period trên đúng app v26 khi được phép live acceptance. Audit này không gọi Graph để xác nhận kết quả trả về.

## 6. Phần đã triển khai local sau yêu cầu tiếp theo

Contract mới: `facebook-content-report-v1`, đặt trong `marketing.preview.content_report` của Dataset mới và `sources.facebook_content.content_report` của release mới. Không migration, không cập nhật Dataset cũ.

- Adapter yêu cầu/lưu message, permalink an toàn, attachment type. Video không bị suy thành Reel; title là trích đoạn message, có `title_source`.
- Admin tạo đủ 7 mục: overview, formats, topics, posts, engagement, reach, insights. Mỗi mục có status/reason/rows; metric thiếu giữ null.
- Phân bố số bài, tỷ trọng định dạng/chủ đề tính tại Admin; nhóm chưa phân loại được giữ riêng, không âm thầm loại khỏi mẫu số.
- Nhập chủ đề theo đúng post_id và nhận xét theo từng mục. Không có quyền sửa KPI qua editorial payload.
- POST `/api/marketing/preview` là phép tính read-only, có Admin/CSRF/client/asset guard; không tạo Dataset hoặc gọi provider.
- Form “Xem dữ liệu đã lưu” hiển thị các mục và lý do thiếu. Tạo Dataset mới đóng băng editorial cùng nội dung để duyệt.
- Source-check tái lập projection từ nguồn đã attest + editorial trong Dataset; thay đổi nội dung làm thay hash và vô hiệu phê duyệt cũ.
- Release dùng đúng review/approval hiện hành, chuyển commentary từ pending_review sang approved trong snapshot mới đã ký.
- New xác thực version/client/period/timezone, rows, trạng thái duyệt; copy cùng contract. Không tính KPI hoặc gọi Meta.
- New mở rộng bảng title/format/topic; link bài thật an toàn; phân bố và chủ đề dùng style có sẵn; nhận xét đã duyệt gắn đúng mục. Ô thiếu không thành 0.
- Revision 1 cũ không được tự bổ sung contract. Code vẫn đọc revision cũ bằng đường cũ.

## 7. Chưa triển khai / chưa nghiệm thu

- Chưa có collector Page/Post Insights. Quyền lưu trữ chưa có read_insights. Không reconnect/cấp quyền trong lượt này.
- Chưa có reach/ER/follower/link-click/paid-organic thật, so sánh hai kỳ, phân loại Reels/long-video/livestream có bằng chứng, messenger response metric.
- Chưa có dropdown filter format/topic riêng ở live; search/sort bảng vẫn hoạt động. KPI toàn kỳ không thay khi lọc bảng.
- Chưa nghiệm thu metadata fields mới với Graph thật; chỉ test transport fixture. Đổi fields có thể yêu cầu điều chỉnh theo response/permission thực tế.
- Chưa deploy runtime, chưa tạo Dataset/Candidate/Bundle/grant, chưa tự duyệt. Vì vậy báo cáo live revision 1 hiện vẫn giữ kết quả cũ.

## 8. Kế hoạch tiếp theo và gates

1. Hoàn tất local regression và UI QA; giữ cả đường Bundle cũ và mới.
2. Người phụ trách xác nhận định nghĩa: Page-wide engagement hay cohort posts; reach/viewers; ER numerator/denominator; follower gained hay net; taxonomy và phân loại media.
3. Cấp và nghiệm thu read_insights + task Page bằng luồng OAuth đúng, chỉ khi được cho phép thao tác live. Không dùng ads_read thay thế.
4. Xây collector Insights theo allowlist v26, lưu requested/returned period, coverage, null, provenance và failures từng metric. Test isolated trước live.
5. Bổ sung metric vào Publication Guard có kiểm tra quyền/period/aggregation; không bỏ điều kiện hiện đang chặn period engagement không có bằng chứng.
6. Đồng bộ được cho phép → Dataset mới → biên tập → review → source verification → approval → release/revision mới. Không sửa revision 1.
7. Deploy có kiểm tra image/config/rollback riêng; browser E2E bằng Viewer grant hiện có đúng report/revision. Không cấp grant tự động để khiến test đạt.

Files chính: Admin `kdh/facebook_content_report.py`, `kdh/meta_reporting.py`, `kdh/meta_marketing.py`, `kdh/marketing_dataset.py`, `kdh/marketing_preview.py`, `static/facebook-content-report.js`, `static/marketing.js`, `templates/marketing.html`. New `app/mappers/facebook_content.py`, `app/mappers/bundle.py`, `app/mappers/dashboard.py`, `app/schemas/bundle_view.py`, các partial formats/topics/insights, snapshot table component và Facebook CSS.

Không cần viết lại backend, thay schema/ACL, copy mock sang live, tính KPI ở New hoặc dùng Ads attribution cho Content.

## 9. Kết quả kiểm thử và integrity

- Admin Python: **400 PASS, 141 SKIP, 0 FAIL** (541 tests). PostgreSQL suites cần disposable DB nên SKIP, không tính PASS.
- Admin UI: **101 PASS, 0 FAIL/SKIP**.
- New Python: **305 PASS, 0 FAIL/SKIP**; còn 5 cảnh báo deprecation thư viện có sẵn.
- JS syntax và `git diff --check`: PASS cho thay đổi hiện tại; Git báo cảnh báo line ending Dockerfile New có sẵn, file đó không được sửa trong lượt này.
- Chromium fixture: Admin đăng nhập bằng user test; xem trước, nhập nhận xét/chủ đề; New render contract được Admin sinh. 1440/1024/768/390/360 cho mỗi ứng dụng, tổng 10 viewport PASS, không lỗi JS hoặc tràn toàn trang.
- Preview fixture: 0 provider calls thêm, 0 Dataset writes. Transport sync fixture chạy trước QA chỉ trong SQLite tạm, bị chặn toàn bộ external HTTP.
- Audit runtime ban đầu: mở report thật qua handoff hợp lệ PASS. **Code mới live E2E: NOT RUN**, do chưa deploy hoặc tạo revision mới.
- Lần chạy unittest đầu có 107 FAIL/22 ERROR do `.env` local chọn client VIO làm các fixture KinderHealth bị chặn scope. Chạy lại với môi trường test cô lập, không đọc `.env`, đã đạt kết quả 400/141 ở trên. Không sửa client guard để làm test đạt.
- Hash bảng nghiệp vụ của cả Admin chính và VIO khớp baseline cuối lượt. Auth sessions/events của lượt browser audit được loại khỏi phép so sánh nghiệp vụ.
- HEAD hai repository không đổi; local changes trước lượt được giữ. Không commit/push/merge/reset/stash; không sửa file `t`.
- New runtime vẫn image SHA256 `fb1089d786b5b3f5a9d383b77e2c13024fb32435a0eff505395a1416943228db`; không deploy Docker.

Audit: **FACEBOOK CONTENT GAP ANALYSIS READY**.

Implementation: **LOCAL CONTRACT/EDITORIAL/PREVIEW READY; INSIGHTS COLLECTION AND LIVE ACCEPTANCE BLOCKED BY PERMISSION/CONTRACT VALIDATION**.
