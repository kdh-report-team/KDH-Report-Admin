# Phase 4 — PostgreSQL acceptance and sandbox deployment readiness

Ngày kiểm tra: 2026-10-18. Phạm vi: Admin, PostgreSQL disposable và fixtures.
Không gọi Meta/Google; không sửa New, source backend/UI, database sandbox hoặc
production; không build/restart/recreate sandbox. Không coi fixture là bằng chứng
độc lập do Meta cấp hoặc là nghiệm thu dữ liệu VIO thật.

## Baseline và bằng chứng

Branch `feat/seo-composite-release`, HEAD
`664efbc561b401d901947437c63df87348d81437`.
Đã ghi status và SHA-256 của toàn bộ tracked/untracked không bị Git ignore trước
khi chỉnh test. Các thay đổi Meta/SEO có trước được giữ nguyên.

Evidence directory của lượt này:
`C:\Users\Admin\AppData\Local\Temp\phase4-20261018-185359-65a42db7`.
Chứa baseline, skip inventory, sanitized Docker metadata, so sánh source image,
kiểm tra config bằng boolean, build manifest và kết quả từng test.
Không chứa Docker Env dump, mật khẩu, DSN, token hoặc cookie phiên.

## PostgreSQL tests

Runner: `tests/run_postgres_acceptance.py`. Runner tự tạo container mới, không nhận
DSN từ người gọi, chỉ chấp nhận Docker context `desktop-linux`, dùng image
PostgreSQL 16 hiện có, random credential trong bộ nhớ, publish cổng ngẫu nhiên trên
`127.0.0.1`, tmpfs riêng, không mount volume hoặc mạng của sandbox/production.
Chỉ nối default bridge cho container test; không tạo/sửa Docker network.
Python HTTP/socket bị chặn; mọi kết nối psycopg phải khớp chính xác host, port,
database, user và credential của container do runner vừa tạo. `.env` bị bỏ qua.
Các test dùng schema UUID riêng; cuối lượt xóa đúng container sau kiểm tra ID/name/
label. Không ghi credential ra file hoặc command arguments.

```powershell
.\.venv\Scripts\python.exe -B tests/run_postgres_acceptance.py --evidence-dir <thu-muc-moi>
```

Phân loại 104 trường hợp SKIP trước đây:

| Nhóm PostgreSQL | Số test |
|---|---:|
| Google persisted success (mock provider) | 4 |
| Marketing publication | 6 |
| Marketing verification | 13 |
| Meta OAuth (mock provider) | 20 |
| Meta transaction diagnostics | 10 |
| Platform data | 6 |
| Core PostgreSQL, concurrency/persistence | 6 |
| Report Bundles | 20 |
| Viewer ACL | 7 |
| Viewer handoff | 12 |
| **Tổng cũ** | **104** |
| Meta Content + Ads Bundle tests bổ sung | **13** |

Tất cả nhóm cũ yêu cầu `TEST_DATABASE_URL`; diagnostics thêm
`TEST_META_POSTGRES=1`. Provider đã có mock/fixture. Không có SKIP do thiếu quyền
live, Ad Account hoặc thư viện optional khác trong 104 trường hợp này.

13 test bổ sung tái sử dụng nguyên các assertion Bundle Meta từ SQLite trên
PostgreSQL: client/asset, sealed source receipt/snapshot, daily persistence,
Content và Ads Dataset/review/candidate/approval/release, null/lifetime/currency,
empty/partial periods, stale evidence và Viewer revision. Chỉ sửa fixture để
nhận database URL thuộc schema test và khóa mã hóa test; mặc định vẫn SQLite.

Kết quả PostgreSQL: **117 PASS / 0 FAIL / 0 ERROR / 0 SKIP**.
Toàn bộ **104 test cũ từng SKIP nay PASS**; 13 test Bundle Meta bổ sung cũng PASS.
Không có lỗi backend cần sửa và không có test bị giảm assertion để đạt PASS.

Database disposable:

* Container: `kdh-phase4-pg-20261018-185645-dcfa94f5`.
* ID: `c1f0cb391d03ec68b7439712f312cbb2262c5d2e184837c7f26eba7682d6c79d`.
* PostgreSQL `16.15 (Debian 16.15-1.pgdg13+2)`.
* Database `phase4_acceptance`, user `phase4_fixture`, host `127.0.0.1:54250`.
* Tmpfs riêng; container đã được remove sau khi kiểm tra ID/name/label. Không
  xóa volume, network hay container hiện hành nào.

Migrations thực thi trên DB disposable: 1 `reporting_platform_foundation`,
2 `report_bundle_snapshots`, 3 `meta_oauth_states`, 4 `source_snapshots`,
5 `marketing_dataset_reviews`, 6 `marketing_verified_releases`,
7 `report_viewer_grants`, 8 `viewer_handoff`, cùng legacy base schema của Store.
Cold-start/concurrent migration và transaction rollback được kiểm trong suite.

Bằng chứng bền vững trong repository:
[từng test và migration](phase4-20261018/postgres-results.json),
[phân loại SKIP](phase4-20261018/skip-inventory.json),
[manifest](phase4-20261018/build-manifest.json),
[runtime read-only](phase4-20261018/sandbox-readiness.json),
[Git integrity](phase4-20261018/git-integrity.json).

Content và Ads Bundle fixture trên PostgreSQL: PASS qua Flask test client và
pipeline Admin thực tế, provider được mock. Đã kiểm schema `1.0`, snapshot
`meta-reporting-v1`, đúng client/Page/account, period/lifetime và null semantics,
spend decimal/currency/attribution, release bất biến, guard bằng chứng sai/cũ,
Viewer grant/revision và từ chối mutation. Đây không phải HTTP runtime 8191 hoặc
New E2E. Hai file fixture Bundle có trước vẫn giữ nguyên hash.

## Sandbox hiện tại: chưa đủ điều kiện triển khai

Run sandbox: `20261016-132836-5c512a53`.

| Container (tiền tố + run trên) | Trạng thái đã quan sát |
|---|---|
| `kdh-meta-2b-pg-` | Exited 255; OOMKilled=false |
| `kdh-meta-3-egress-` | Exited 255; OOMKilled=false |
| `kdh-meta-2b-admin-` | Exited 255; OOMKilled=false |
| `kdh-meta-2b-relay-` | Exited 255; OOMKilled=false |

Bốn container kết thúc gần cùng thời điểm `2026-10-18T11:48:29Z`.
Điều này phù hợp với sự kiện Docker/host bị dừng, nhưng không đủ chứng minh nguyên
nhân. Không có cờ OOM trên bốn container hiện hành. Không khởi động container
`before-phase3`/`before-e2` hoặc bất kỳ PostgreSQL cũ nào.

`127.0.0.1:8191` không nhận TCP; không có HTTP 200 để nghiệm thu.
**Admin và relay đều có HostConfig.PortBindings `127.0.0.1:8191 -> 8090`.** Đây là
xung đột cấu hình tiềm tàng và trái với mục tiêu ingress chỉ qua relay. Khi cả hai
đang dừng chưa quan sát được tranh chấp bind thực tế. Không tự sửa; cần duyệt
phương án loại bỏ publish port trực tiếp của Admin khi thay Admin container.

Volume `kdh-meta-2b-pgdata-20261016-132836-5c512a53` và
`kdh-meta-2b-appdata-20261016-132836-5c512a53` còn metadata/mount đúng tên.
Đây **không** phải xác nhận checksum/khả năng restore hoặc tính toàn vẹn dữ liệu.
Không mount volume sang helper và không truy vấn DB đang dừng.
Số bài VIO, số snapshot, trạng thái token và schema_migrations đang áp dụng trong
DB hiện tại chưa thể kiểm tra lại; số liệu Phase 3 chỉ là bằng chứng lịch sử.

Admin/DB chỉ gắn network `kdh-meta-2b-net-20261016-132836-5c512a53`,
`Internal=true`, subnet `192.168.0.0/20`. DB không publish port. Admin có IPAM
pin `192.168.0.3`; PostgreSQL chưa có IPAM pin và địa chỉ live đang trống.
Gateway pin `.10`, nối thêm outbound network; relay nối ingress network và
internal network, upstream cố định `192.168.0.3:8090`, cấu hình DB `.2`.
IP và các rule hiệu lực phải được kiểm lại sau khi khôi phục được phê duyệt.

Gateway code chỉ nhận `CONNECT graph.facebook.com:443`, kiểm SNI và nguồn Admin,
chuyển tiếp tới Graph IP pin `57.144.14.141:443`. Relay giới hạn route tới Admin;
gateway/relay bỏ default route, drop privileges, dùng seccomp. Chỉ xác minh code/
config trên đĩa: chưa kiểm tra lại allow/deny hiệu lực khi container dừng.
Ads Insights dùng cùng `graph.facebook.com`; không có nhu cầu mở thêm domain từ
source đã kiểm tra. IP pin hiện hành chưa được kiểm tra tính khả dụng; không đổi
IP/routing/allowlist hoặc cấp unrestricted Internet trong phiên này.

Config sandbox đọc an toàn trong bộ nhớ:

* `JOB_MODE=request`, `META_CLIENT_ID=client_meta_sandbox`.
* App ID `1831786608275511`; Config ID `1683586973182335`.
* APP_URL `http://localhost:8191`; callback `/api/meta/callback`.
* Cookie namespace `kdh_meta_acceptance_session`, `COOKIE_SECURE=0` cho localhost.
* App Secret, ENCRYPTION_KEY và DATABASE_URL: PRESENT, khớp file `admin.config`
  với container hiện có. Không khẳng định secret/token còn hợp lệ tại Meta.
* DB target đúng host sandbox và database `meta_acceptance_20261016_132836`.
* HTTP/HTTPS proxy tới `192.168.0.10:3128`; không có proxy userinfo.

## Source/image và migration

Image Admin hiện tại:
`sha256:d4e4e09a6a43af0c01e98d135bb1ff8ac65bd2c0bbb27cd5bc778c28e658b0b9`.
PostgreSQL 16 image:
`sha256:ca0bd484cb98bf4b24eb1010e73fb3fcbd6714d240fbc1a10eea5b7dbecb641d`.

Đọc file từ container đã dừng bằng Docker archive, không chạy app:
`meta_contract.py` và `meta_marketing.py` chưa có trong image cũ; adapter và UI
khác local. `kdh/migrations.py` và `kdh/app.py` khớp byte với local.
Không có migration mới trong thay đổi Facebook hiện tại. Tuy nhiên trạng thái
schema_migrations thực tế của DB vẫn phải đọc trước triển khai.

`build-manifest.json` ghi 61 file được dùng cho build: Dockerfile, .dockerignore,
requirements.lock, run.py và kdh/templates/static. Aggregate SHA-256:
`1db981c78d84f9b0c7582948d734c62cf0b6064da893f0c7dfedba7ebb0baae5`.
Manifest gồm working tree thực tế, kể cả module untracked cần thiết, không chỉ
HEAD. Chưa build image. Dockerfile dùng `python:3.12-slim` và requirements.lock;
khi được duyệt phải ghi digest base đã resolve, image ID kết quả, dependency
versions và kiểm hash file trong image theo manifest. Giữ image cũ để rollback.

## Quy trình triển khai đề xuất — CHƯA THỰC HIỆN

1. **Gate phê duyệt riêng:** thống nhất xử lý binding trùng 8191; duyệt khôi phục
   container hiện hành và thay đúng Admin sandbox. Không dùng compose up.
2. Trước mọi thao tác runtime, xác minh lại container/volume/network IDs theo
   evidence và baseline mới. Không chạm Admin 8090, sandbox 8190, PostgreSQL chính,
   New hoặc các container `before-*`.
3. Khi được phép khôi phục, khởi động tuần tự PG → gateway → Admin → relay, sau
   khi đã giải quyết rõ owner cổng 8191. Dừng nếu PG không ở `.2`, Admin không ở
   `.3`, gateway không ở `.10` hoặc security gate khác baseline. Không tự sửa IP.
4. Quiesce thao tác người dùng; không gọi sync, OAuth hay routes tạo job. Dùng
   driver DB trực tiếp với transaction READ ONLY để lấy schema_migrations,
   client/Page/Ad Account selection, counts và hashes jobs/runs/snapshots/metrics,
   pending schedules/jobs, approvals/releases. **Không gọi Store/create_app**
   trong bước đọc vì chúng chạy schema/migration/bootstrap.
5. Backup logical `pg_dump` riêng database sandbox, backup globals cần thiết và
   appdata; giữ bản cấu hình sandbox/khóa mã hóa trong kho bảo mật với ACL hạn chế.
   Không đưa backup hoặc secret vào Git/log. Kiểm checksum file backup và thử
   restore trong PostgreSQL disposable khác, xác minh counts/hashes và khả năng
   giải mã chỉ bằng boolean. Không thử restore lên volume hiện hành.
6. Tạo build context sạch chỉ từ danh sách manifest và build image Admin tag mới;
   không bake config/secret vào image hoặc gửi thư mục secret vào build context.
   Giữ migrations.py đúng hash đã kiểm tra. Nếu DB thiếu migration ngoài dự kiến,
   DỪNG để duyệt thay đổi schema và thử trên bản clone trước; không tự migrate.
7. Tạo bản ghi rollback/review manifest không chứa Env values. Dừng/giữ Admin cũ
   để rollback; thay **chỉ Admin của run này**, giữ PostgreSQL/gateway/relay, volume
   appdata, encryption key, cookie namespace và toàn bộ OAuth/source snapshots.
   Chỉ gắn internal network, IP `.3`; đề xuất **không publish port trực tiếp**.
   Giữ read-only rootfs, user kdh, cap-drop ALL, no-new-privileges, limits hiện
   hành và JOB_MODE=request. Không mở Internet trực tiếp. Port change cần duyệt
   rõ vì khác cấu hình quan sát hiện tại.
8. Giữ relay là owner duy nhất `127.0.0.1:8191`, upstream `.3:8090`; xác minh
   gateway/DB isolation và TLS allow/deny bằng probe không gọi API lấy dữ liệu.
   Không rebuild gateway/relay hoặc đổi network/egress tự động.
9. Kiểm health HTTP 200, cookie/CSRF, grant đọc tại server, source hash/image ID,
   không có worker nền (`Worker.start()` trả ngay khi JOB_MODE=request), không job
   phát sinh ngoài dự kiến; đối chiếu dữ liệu với baseline, lịch sử vẫn unverified.
   Startup có chạy DDL idempotent/bootstrap nên chỉ diễn ra sau backup/approval.
10. Nếu FAIL, dừng Admin mới, phục hồi Admin/image/config đã giữ và endpoint `.3`
    theo manifest rollback đã duyệt; không reset/recreate DB hoặc xóa volume.
    Không khởi động nguyên container rollback có bind 8191 trùng relay: manifest
    rollback cũng phải giữ relay là ingress duy nhất, dùng image cũ cùng config
    bảo mật đã duyệt. Cần chốt phương án này trước khi triển khai.
    Nếu có dữ liệu thay đổi ngoài dự kiến: giữ bằng chứng và dừng, không tự ghi
    đè DB bằng backup. Restore dữ liệu là phê duyệt riêng.

Phạm vi ảnh hưởng dự kiến: Admin sandbox và cấu hình publish port của nó; các
dịch vụ phụ trợ chỉ khôi phục/kiểm tra khi được duyệt. Không thay volume hay
schema mới. Chưa đủ bằng chứng để bật deployment ngay ở trạng thái hiện tại.

## Ads live readiness

OAuth dùng Facebook Login for Business Config ID, không tự thêm permission qua
URL. Production required_permissions có `ads_read`; sandbox OAuth chỉ bắt buộc
Page scopes để giữ Content-only. Ads reader, enqueue và worker kiểm `ads_read`
riêng; Source Verification cũng kiểm quyền/grant đã lưu. `ads_read` trong lịch
sử không thay thế kiểm tra grant hiện tại hoặc quyền trên Ad Account.

Discovery tự động sandbox vẫn chỉ `source=facebook_content`. Ads có thao tác
tường minh nhập `act_<id>` và xác nhận chủ sở hữu/quyền kiểm tra, gọi
`GET /api/meta/reporting/assets?source=facebook_ads&external_id=act_<id>`;
selection POST recheck đúng account. Sync POST nhận selected asset thuộc đúng
client, connection, asset type và enabled. Không dùng quyền Page để suy ra Ads.

**Live Ads BLOCKED:** chưa có Ad Account ID/Business Owner được người dùng xác
nhận, grant hiện tại chưa đọc lại và runtime đang dừng. Trước test live cần:

* Exact account ID, Business/owner, quyền của người vận hành và phạm vi dữ liệu.
* `ads_read` thực tế, token còn hạn, quyền account; client_meta_sandbox isolation.
* Currency/account timezone, definition `lead`, fixed attribution window được
  chấp nhận; snapshot không trộn currencies/attributions.
* Sau deployment PASS, duyệt phép đọc Insights nhỏ trước; chỉ sau nghiệm thu
  read-only mới duyệt một sync Content/Ads hữu hạn riêng.
* Chọn 1–3 ngày **đã kết thúc theo timezone account**; ưu tiên ngày có hoạt động
  được chủ account xác nhận. Không lấy hôm nay hoặc 28 ngày mặc định. Kiểm dates,
  spend precision, clicks/impressions, null/partial, pagination và dedup.
* Missing days/actions/conversions giữ null/partial; không biến thành zero;
  reach/frequency period và purchase/ROAS chưa có nguồn phù hợp vẫn unavailable.

KDH-Report-New và HTTP E2E hai ứng dụng: chưa kiểm thử trong Phase 4 này.

## Tổng kết nghiệm thu Phase 4

| Kiểm tra thực chạy | PASS | FAIL/ERROR | SKIP |
|---|---:|---:|---:|
| PostgreSQL guarded runner, 117 cases | 117 | 0 | 0 |
| Python offline discovery, 473 cases | 356 | 0 | 117 |
| `npm.cmd test` | 84 | 0 | 0 |
| JS syntax và `git diff --check` | PASS | 0 | 0 |

117 SKIP của lượt offline là 104 PostgreSQL cũ + 13 Meta PostgreSQL mới;
chúng đã được chạy riêng và PASS trên PostgreSQL thật. Không còn test trong nhóm
này chưa được thực thi. Không cộng SKIP thành PASS. Hai lượt Python bao phủ 473
test IDs, trong đó 117 dùng PostgreSQL và 356 dùng offline fixtures.

Git: 164 file baseline được đối chiếu; 163 giữ nguyên hash, chỉ
`tests/test_meta_reporting_routes.py` thay đổi để hỗ trợ fixture PostgreSQL.
Thêm hai file test/runner cùng báo cáo và evidence đã lọc; không sửa backend,
frontend, migration, SEO Composite, hai Bundle fixture cũ hoặc KDH-Report-New.
Không mất file, không đổi HEAD/branch, không staging/commit/reset/stash.
Container/image/state/port bindings/network IDs của cả bốn sandbox container
không đổi sau lượt test.

**PostgreSQL integration acceptance: PASS.**
**Sandbox deployment readiness: BLOCKED.** Cần phê duyệt và thực hiện preflight
khôi phục riêng, giải quyết bind trùng 8191, kiểm tra lại DB/schema/snapshots/grant,
backup và thử restore trước khi chuyển image. Không dùng kết quả fixture để
chứng nhận dữ liệu VIO lịch sử hoặc quyền Ads thật.

**PHASE 4 POSTGRESQL ACCEPTANCE BLOCKED — sandbox 8191 đang dừng, ingress binding
chưa đạt và chưa xác minh được baseline/backup runtime để duyệt triển khai.**
