# Facebook Content Insights — local implementation, 21/10/2026

> Cập nhật 22/10: Admin và New đã triển khai sau khi người dùng xác nhận New hết
> rebase. CODE READY / DEPLOYED; PERMISSION NOT READY; LIVE INSIGHTS NOT RUN.
> Browser VIO revision 1 PASS. Xem [bàn giao hiện hành](tonight-delivery-20261021/README.md).
> Phần trạng thái và baseline bên dưới ghi lại lượt trước, không phải runtime mới nhất.

## Trạng thái nghiệm thu

- **CODE READY (Admin, fixture/integration):** collector tùy chọn, lưu snapshot/receipt, projection, preview và guard đã kiểm thử. Không có migration.
- **New integration BLOCKED:** checkout New đang được phiên khác rebase. Người dùng xác nhận giữ nguyên New; không tiếp tục sửa hoặc triển khai New trong lượt này.
- **DEPLOYED: NO.** Gate kiểm thử toàn bộ New chưa đạt. Không cập nhật image/runtime nào.
- **PERMISSION READY: NO.** Đọc `/api/meta` bằng phiên Admin hợp lệ ngày 21/10 xác nhận connected nhưng thiếu `read_insights`.
- **LIVE VERIFIED: NOT RUN.** Không gọi Graph, không chạy diagnostic/sync thật, không tạo Dataset/Bundle hoặc thực hiện review/publication.

Không coi các test fixture là bằng chứng Page VIO thực sự trả Insights. Report
`rpt_4909119771c69125897d8bca84444abe`, revision 1 không được sửa.

## Baseline và sự kiện đồng thời

Admin `main`, HEAD `6b52ee2f3ef29ebb5820e95e88ba318a7599667d`; giữ working tree cũ.
New lúc bắt đầu là `main` HEAD `837f655`, đang chứa các thay đổi local của các lượt trước.
Trong khi test, New chuyển sang interactive rebase lên `56a51a0`, pick commit
`1e3df3c` (`update UX/UI FB-organic`). Có conflict trong mapper, cấu hình, handoff,
template và tests. Pytest toàn bộ New dừng với 19 lỗi collection do marker conflict.
Người dùng xác nhận một phiên khác đang xử lý và yêu cầu giữ nguyên New.

Không chạy commit/push/merge/rebase/reset/stash/clean hoặc đổi branch trong lượt này.
Kiểm tra cuối (`integrity-final.json`): hash các bảng nghiệp vụ VIO không đổi,
HEAD Admin không đổi, ID/image của cả 10 container được theo dõi không đổi.
File local ngoài phạm vi được giữ nguyên.
Các file New đã thử chỉnh trước khi phát hiện rebase phải được đối chiếu lại sau
khi phiên kia hoàn tất; không khẳng định chúng còn đầy đủ trong working tree cuối.
Hai file kiểm thử mới được tạo trước đó: `tests/test_content_insights_contract.py`
và `tests/fixtures/facebook_content_insights_v1.json` (fixture tổng hợp, không phải VIO).

Runtime đã inspect:

| URL | Container | Image ID lúc preflight | Trạng thái |
| --- | --- | --- | --- |
| VIO Admin 8191 | `kdh-meta-2b-admin-20261016-132836-5c512a53` qua relay 8191 | `045e724c36a5` | Healthy, JOB_MODE=request, không publish port Admin |
| New thật 8080 | `kdh-report-new-app-1` | `fb1089d786b5` | Healthy, Viewer chung hai Admin |
| Mock 8082 | `KDH-Report-New-MockDb` | `87844f282565` | Healthy, giữ nguyên |
| Admin chính 8090 | `kdh-report-admin-admin-1` | `f3db6a2ecaa1` | Đang dừng sau Docker restart; không khởi động/sửa trong lượt này |

New 8080 vẫn có các mạng Viewer riêng, không nối PostgreSQL. VIO giữ volume
`kdh-meta-2b-pgdata-20261016-132836-5c512a53` và appdata cùng sandbox.
Không dùng thông tin cổng 8193 cũ. Không đọc `.env` hoặc token ra báo cáo.
Do chưa đủ deployment gates, chưa tạo backup/deploy mới; lần triển khai sau phải
inspect lại identity/network, xác minh backup/restore và chuẩn bị rollback mới.

## Danh mục Meta đã đối chiếu

Tài liệu đọc trực tiếp từ Meta ngày **21/10/2026**, reference hiển thị **v26.0**:

- [Page Insights reference](https://developers.facebook.com/docs/graph-api/reference/page/insights/?locale=en_US)
- [Get Page Insights](https://developers.facebook.com/documentation/pages-api/platforminsights/page)
- [Deprecated metrics](https://developers.facebook.com/documentation/pages-api/platforminsights/page/deprecated-metrics)
- [Facebook Login for Business](https://developers.facebook.com/docs/facebook-login/facebook-login-for-business/)

Reference ghi cần Page token, `read_insights`, `pages_read_engagement`, Page task
`ANALYZE`. Giới hạn tài liệu: Page tối thiểu 100 likes, phần lớn metric cập nhật
mỗi 24 giờ, lịch sử tối đa hai năm, truy vấn tối đa 90 ngày; interactions trên
Reels bị loại khỏi phạm vi. Đây là điều kiện tài liệu, chưa xác minh live với VIO.

Guide vẫn dùng ví dụ `page_impressions_unique` dù danh mục deprecated đã loại
metric đó. Guide ghi mốc 15/06/2026, trang deprecated ghi 15/06/2025: mâu thuẫn
ngày được giữ nguyên trong audit. Collector không dùng các metric cũ này.

| Nhu cầu / metric | Endpoint, period | Phạm vi / đơn vị | Tổng hợp Admin | Hỗ trợ hiện tại |
| --- | --- | --- | --- | --- |
| Lượt xem `page_media_view` | `/{page}/insights?metric=page_media_view&period=day` | Toàn Page, count; gồm nhiều loại nội dung, có thể gồm ads | Chỉ cộng khi đủ đúng các interval ngày UTC; nếu lệch giữ raw/series, tổng null | Collector có; không đổi thành reach |
| Người xem duy nhất `page_total_media_view_unique` | Page insights, day | Unique viewers theo ngày | Không cộng ngày thành unique toàn kỳ | Collector có; series riêng |
| `page_post_engagements` | Page insights, day | Tương tác toàn Page, không phải cohort bài đăng trong kỳ | Chỉ tổng hợp interval khớp; không thay `engagements` UTC/cohort cũ | Collector có; giới hạn Reels theo tài liệu |
| `page_follows` | Page insights, day | Stock số followers tại từng mốc | Không sum, không lấy delta thành follower mới | Collector có; series riêng |
| `post_media_view` | `/{page_post_id}/insights`, lifetime | Lượt xem tích lũy từng bài | Giữ giá trị từng bài tại fetch; không gán vào kỳ phát sinh | Collector có |
| `post_total_media_view_unique` | Post insights, lifetime | Người xem duy nhất từng bài | Không cộng qua bài thành unique Page | Collector có |
| Followers mới | Reference có `page_daily_follows` / unique nhưng mô tả ghi `Not defined` | Chưa đủ định nghĩa nghiệp vụ | Null, không suy từ follower stock | Chưa đưa vào collector |
| Reach / organic-paid reach | Các metric impressions/reach cũ bị deprecated; thay thế mới là views/viewers | Không mặc định tương đương reach cũ | Không total−paid, không cộng unique | Chưa có equivalent được nghiệm thu |
| Views theo ads/followers | Reference liệt kê breakdown `is_from_ads`, `is_from_followers` | Views, không phải unique reach | Chưa xác nhận shape/breakdown coverage bằng live | Chưa gọi breakdown trong đợt này |
| Link clicks / CTR | Chưa xác nhận metric link-specific hiện hành và mẫu số cùng phạm vi | Content, không dùng Ads thay thế | Null | Chưa hỗ trợ |
| ER | Cần tử/mẫu cùng định nghĩa, cohort và kỳ | Ratio | Không chia lifetime/unique sai kỳ | Chưa hỗ trợ |
| Phản hồi tin nhắn | Ngoài Content contract hiện tại | Cần nguồn/định nghĩa riêng | Null | Chưa hỗ trợ |

Collector gọi **mỗi metric riêng**, không gom một metric bị từ chối thành lỗi cả Page.
Các metric đều yêu cầu quyền/task nêu trên. Lịch sử lifetime là số tích lũy đọc tại
fetch, không phải số lifetime có thể tái dựng tại cuối một kỳ cũ.

Ranh giới thời gian: guide cho ví dụ daily `end_time` 07:00/08:00 GMT. Không tự
coi đó là ngày UTC hoặc timezone của client. Lưu nguyên offset/end_time; chỉ
tính tổng UTC khi tập mốc kết thúc khớp chính xác từng ngày của kỳ. Nếu chưa
chứng minh được timezone nguồn thì `period_boundary_mismatch`, tổng giữ null.

## Những phần đã triển khai

- `kdh/meta_content_insights.py`: catalog allowlist v26, permission/task/version gates;
  chuẩn hóa metric/object/period/value/end_time, lỗi và projection có coverage.
- `kdh/meta_reporting.py`: tích hợp collector sau đọc bài; budget mặc định 200 request
  dùng chung, tính cả retry và pagination. Đọc tối đa 30 bài Insights, vượt mức có
  post coverage và trạng thái partial. Page/Post data cơ bản vẫn lưu khi Insights
  thiếu quyền hoặc một metric lỗi. Không gọi khi mở preview/history/render.
- `content_insights_diagnostic`: service đọc riêng, không tạo job, tối đa 20 request
  gồm Page lookup/retry/pagination; kỳ 1–3 ngày đã kết thúc, tối đa 3 ID cùng Page.
  Đây là service nội bộ, không mở endpoint provider công khai mới.
- Pagination dùng cursor có kiểm tra, không dereference `paging.next` chứa token;
  với Insights, next/previous chỉ sang cửa sổ thời gian khác không được tự truy cập.
- Retry chỉ lỗi tạm thời có cấu trúc. Permission/token/100/invalid-response không retry.
  Code 100 được ghi `invalid_metric_or_parameter`, không khẳng định deprecated khi
  chưa phân biệt được invalid query và unsupported metric.
- Empty là `empty_unconfirmed`: không suy 0 hoặc khẳng định Page không có dữ liệu.
  Null và 0 thật, partial, permission, token, budget, paging lỗi được phân biệt.
- Chỉ lưu các field allowlist. Không lưu token, provider error text, paging URL,
  payload OAuth hoặc app secret vào snapshot/report.
- Snapshot/receipt hiện có bao phủ cả `insights`; không cần bảng/migration mới.
- `facebook_content_report.py` đóng projection/biểu đồ/post lifetime mới vào
  `content_report.insights` và các rows của 7 mục hiện có. Không sửa Dataset cũ.
- `meta_marketing.py` giữ source-check/hash/review/approval cũ; thêm guard
  `insights_permission_unconfirmed` nếu snapshot có số đo nhưng grant hiện không
  còn read_insights hoặc thiếu bằng chứng ANALYZE.
- `meta.py`, `static/views.js`: trạng thái quyền đã lưu và nút cấp lại quyền qua
  OAuth hiện có. Không ép read_insights thành quyền bắt buộc cho Content cơ bản,
  không tự đổi Business Login config hoặc gửi scope giả bên cạnh config_id.
- `static/facebook-content-report.js`: preview số đo/period/end_time, tổng và lý do
  chưa đủ điều kiện; HTML escape mọi nhãn/nội dung.

Giữ nguyên 7 mục: tổng quan, định dạng, chủ đề, bài đăng, tương tác, organic/paid,
nhận định. Định dạng chỉ từ metadata; chủ đề và nhận xét vẫn do agency nhập, đóng
băng vào Dataset, chỉ approved khi đi qua release hợp lệ. Không tự sinh nhận xét
hiệu quả từ dữ liệu thiếu. Reactions/comments/shares cũ vẫn lifetime.

## Kiểm thử và bằng chứng

Artifacts ngoài Git: `C:/Users/Admin/AppData/Local/Temp/KDH-FB-Insights-20261021/`.

- Admin full offline: **553 run = 412 PASS / 141 SKIP / 0 FAIL/ERROR**.
  `offline-result.json`, `admin-python.log`.
- Chạy lại toàn bộ 141 SKIP bằng PostgreSQL 16 disposable: **141 PASS / 0 SKIP**,
  container tmpfs đã xóa sau kiểm tra identity. `postgres/results.json`.
- Test mới bổ sung sau discovery đầu: **5 PostgreSQL PASS / 0 SKIP**;
  `postgres-insights/results.json`. Gồm sync→receipt→Dataset→review→Bundle,
  permission bị gỡ chặn source-check và OAuth cấp thêm quyền.
- Nhóm focused cuối: **50 PASS / 0 SKIP** (collector + Content + workflow/OAuth).
- Admin UI: **102 PASS / 0 SKIP**; `admin-ui-final.log`, `ui-result.json`.
  Lượt npm đầu bị ngắt không có summary, không tính PASS; lượt sau chạy đủ.
- JS syntax: 7 file PASS. Admin `git diff --check`: PASS.
- Browser Admin fixture: **5 viewport PASS**, 1440/1024/768/390/360, không overflow,
  không lỗi JavaScript, preview không tạo Dataset và không gọi provider.
  `browser-fixture.json`, `admin-insights-fixture-{width}.png`.
- New: targeted trước rebase **22 PASS / 1 FAIL** (binding KPI chưa đi qua
  `content_shell`); đã bắt đầu sửa nhưng không được tính PASS lại. Full suite sau
  đó **19 collection ERROR** do conflict rebase. **New final tests và New browser
  QA: BLOCKED/NOT RUN**, không dùng kết quả 305 PASS của lượt trước cho code này.

Phân loại 141 test trước đây SKIP:

| Nhóm PostgreSQL | Số test đã PASS |
| --- | ---: |
| Bundle | 21 |
| Facebook Bundle | 28 |
| Google platform | 4 |
| Handoff | 12 |
| Meta diagnostics | 10 |
| Meta OAuth | 20 |
| Platform data | 6 |
| Publication | 6 |
| Storage/PostgreSQL | 6 |
| Verification | 13 |
| Viewer ACL | 7 |
| VIO handoff | 8 |

Các PostgreSQL test ghi vào schema riêng của container mới. Test transport chặn
provider/network; không có test nào dùng PostgreSQL nghiệp vụ VIO làm fixture.

## Bàn giao New sau khi rebase xong

Đối chiếu lại `app/mappers/facebook_content.py`, `app/mappers/dashboard.py` và tests
mới; không lấy nguyên bản GitHub cũ ghi đè local. Cần:

1. Validate `content_report.insights` khớp raw `source.insights`, Page, period,
   quyền/task, raw measurements; bảo toàn snapshot status và lifetime.
2. Copy chart arrays/tổng KPI do Admin tính, không tính lại trong New.
3. Thêm KPI Page chính xác vào `content_shell` (không chỉ `overview_kpis`);
   dùng nhãn toàn Page, không đổi views thành reach.
4. Thêm cột post views/unique viewers lifetime từ projection Admin; ẩn cột thiếu.
5. Giữ main section timezone UTC; chart Insights dùng mốc end_time nguồn riêng.
6. Chạy toàn bộ New suite, fixture responsive và real revision 1 qua handoff.
   Không chỉnh Bundle đang phát hành để làm giao diện có thêm dữ liệu.

## Việc cần làm tiếp

1. Phiên khác hoàn tất rebase New; xác minh lại source và chạy gates của New.
2. Sau gates PASS: backup/restore và rollback mới, build source local; chỉ deploy
   đúng VIO Admin và New thử nghiệm đã inspect. Không sửa primary8090 hoặc mock8082.
3. Trong Meta App Dashboard, quản trị ứng dụng kiểm tra config Facebook Login for
   Business đang dùng có quyền read_insights được phép yêu cầu. Không đổi App Secret.
   Người dùng mở Admin → Kết nối nền tảng → Facebook → Cấp lại quyền qua Meta,
   đăng nhập và chấp thuận. Không dùng nút Ngắt kết nối, không gửi token vào chat.
4. Kiểm tra lại scopes lưu trữ, Page task, đúng client/Page. Reconnect làm grant
   lineage thay đổi: provenance cũ không tự nâng trạng thái hoặc tái dùng để duyệt
   dữ liệu mới. Revision 1 đã phát hành vẫn giữ nguyên payload/seal/grant.
5. Khi runtime và permission đạt: diagnostic dự kiến **17–18/10/2026**, tối đa
   3 bài đã xác minh thuộc VIO, hard cap 20 requests. Xác nhận ranh giới ngày Meta
   thực tế; chưa có kết quả live để kết luận reach/engagement/followers.
6. **Một kỳ sync đầy đủ đề xuất có điều kiện**, chỉ xin duyệt sau diagnostic:
   **21/09–18/10/2026 UTC** cho đúng Page VIO. Với 15 bài như snapshot cũ,
   dự kiến 36 requests nếu không pagination/retry (Page lookup + posts + 4 Page
   metrics + 2 × 15 Post metrics). Hard cap **200**, tối đa 30 post Insights;
   phải báo partial nếu vượt cap. Tạo snapshot/Dataset mới rồi human review mới;
   không tự sync hoặc sửa revision 1.
