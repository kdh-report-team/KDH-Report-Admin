# Phase 5B — Meta Sandbox Deployment Result

Ngày thực thi: 18/10/2026. Run `20261016-132836-5c512a53`.
Phạm vi: deployment Admin sandbox đã được người dùng duyệt, không provider API,
sync, OAuth, source attestation, approval, publication hoặc KDH-Report-New.

## Kết quả các gate

| Gate | Kết quả | Bằng chứng |
|---|---|---|
| Backup safety | PASS | Checksum encrypted/plaintext archives khớp, DPAPI giải mã được; restore Phase 5 độc lập PASS |
| Image build/smoke | PASS | Image mới, 59 file ứng dụng trong image khớp context 61 file; 2 file còn lại là Dockerfile/.dockerignore |
| PostgreSQL gốc | PASS | Healthy, đúng image/volume/database, IP 192.168.0.2, migrations 1–8 |
| Admin mới | PASS | Healthy, IP 192.168.0.3, JOB_MODE=request, không host binding |
| Gateway/relay | PASS | Running, kiểm chức năng/policy PASS; hai container không khai báo Docker HEALTHCHECK |
| localhost:8191 | PASS | GET /health=200, root=200, authenticated login/session/logout PASS |
| CSRF/Origin/cookie | PASS | Thiếu CSRF hoặc sai Origin bị 403; cookie namespace/HttpOnly/SameSite=Lax giữ nguyên |
| Content persistence | PASS | 14 posts/28 Page dates kỳ chính, 2 snapshots, 3 sync_runs, 0 duplicate keys, hash 12 bảng khớp |
| OAuth encryption | PASS | Env/key không đổi, secret giải mã được; không kiểm token với Meta |
| Source/publication guards | PASS | VIO vẫn persisted_unverified; historical preview bị 409 meta_contract_missing; không có attestation/release mới |
| Network isolation | PASS | Chỉ relay bind loopback 8191; PG/Admin private; allow TLS Meta và các deny probes PASS |
| Git integrity | PASS | Không đổi branch/HEAD/source đã checkpoint; chỉ thêm deployment artifacts |

## Backup và giới hạn

Backup nằm ngoài volume gốc tại:
`C:\Users\Admin\AppData\Local\KDH-Meta-Backups\kdh-phase5-20261018-59770a49`.
PostgreSQL/appdata/config được mã hóa; key DPAPI CurrentUser, ACL riêng.
Đã kiểm lại hash archive trước khi start PostgreSQL gốc. Khóa OAuth hiện tại
khớp config backup và container cũ. Không restore đè DB gốc.

**Chưa có backup off-host.** DPAPI phụ thuộc Windows user/profile/máy hiện hữu.
PG data_checksums=off như trước; không thay cấu hình checksum. Backup là điểm
trước recovery/deployment, không phải cold copy sau khi PG đang chạy.

## Image và container

Tag: `kdh-admin-meta:phase5-20261018-1db981c78d84`.

Image ID mới:
`sha256:de56eef854fe84f7e8d8a630c2de62ae65399b0c1204fe24e7f29c997adbbfb5`.

Source manifest SHA-256:
`1db981c78d84f9b0c7582948d734c62cf0b6064da893f0c7dfedba7ebb0baae5`.

Build dùng đúng context allowlist Phase 5, không workspace đầy đủ; không .env,
instance, secret/config/backup hoặc test fixture trong image. Không sửa source
để build hoặc smoke PASS. Không ghi đè tag có trước.

Admin mới:
`kdh-meta-2b-admin-20261016-132836-5c512a53`, ID
`51843a6c05fadeffc22955e8edbddd5a08246dc7ae9ba6c86380c173f59d6990`.

Admin cũ được giữ stopped, cùng ID cũ, đổi tên thành:
`kdh-meta-2b-admin-20261016-132836-5c512a53-before-phase5`.
Đã detach riêng endpoint của Admin cũ để chuyển IP .3 cho Admin mới. Không đổi
subnet/gateway/allowlist hoặc membership của PostgreSQL, relay và gateway.

Các tài nguyên được khôi phục, giữ nguyên ID/image/volume:

* `kdh-meta-2b-pg-20261016-132836-5c512a53`.
* `kdh-meta-3-egress-20261016-132836-5c512a53`.
* `kdh-meta-2b-relay-20261016-132836-5c512a53`.

Chỉ relay đang hoạt động có `127.0.0.1:8191 -> 8090/tcp`. Container Admin cũ đã
dừng vẫn giữ khai báo binding cũ, nên tuyệt đối không start nguyên container đó.
Admin mới chỉ có internal 8090; PostgreSQL không host port.

## Điều chỉnh helper thực thi

Lần precheck đầu của bước thay Admin dừng trước khi khởi động gateway hoặc đổi
Admin: helper chuẩn bị coi mọi IPAM requested address là IP đang được cấp.
Container lịch sử `...-before-e2-20261017-091341` cũng lưu requested IP .3, nhưng
không Running, không IPAddress, không EndpointID và không nằm trong active
network endpoints. Network lúc đó chỉ có PG .2.

Đã tạo helper mới trong `docs/phase5b-20261018/`, chỉ ngoại lệ đúng ID lịch sử
`af2d1346b5bfc2b544b0ccf844469d2dfbf98715aa289ade3e54ab778d76b86f` khi tất cả điều
kiện inactive trên cùng đúng. Các kiểm tra endpoint/IP đang hoạt động vẫn giữ.
Không sửa helper Phase 5 đã checkpoint, không sửa source image, không chạm
container before-e2/before-phase3. Không đổi thiết kế hoặc phạm vi triển khai.

Docker xác nhận Admin mới được cấp **192.168.0.3** sau start; chỉ sau checkpoint
này mới khởi động relay. Không suy ra IP từ cấu hình khai báo.

## Smoke và nghiệm thu ứng dụng

Smoke dùng hai container mới có prefix `kdh-meta-phase5b-smoke-e665a0e5`:
PostgreSQL trên tmpfs mới, network none; Admin chia sẻ namespace cô lập đó,
không host port và không mount dữ liệu/config gốc. Dùng credential/khóa fixture
ngẫu nhiên trong bộ nhớ. Các container smoke đã dừng; không xóa/prune.

Image thực chạy `run.py`, HTTP health, PostgreSQL migrations 1–8, login, session,
CSRF, logout, Meta module imports và route registration PASS; không tạo job nền.
16 tests Bundle/Publication Guard chạy trong image qua fixture runner chặn network,
dùng SQLite disposable. Không gọi chúng là 16 tests PostgreSQL.

Trên sandbox thật đã kiểm một login bằng credential sandbox hiện hữu, xác minh
hash trước khi gửi để tránh thử mật khẩu sai. Session/cookie/CSRF chỉ giữ trong
bộ nhớ; logout session kiểm thử sau khi xong. Login tạo session/event theo cơ chế
ứng dụng; không sửa user/password/OAuth. Appdata server.lock và WAL thay đổi bình
thường do startup đã được duyệt; không khẳng định toàn volume giữ nguyên byte.

KPI GET dùng DB đã lưu:
`/api/meta/reporting/kpis/cff1f3d5e6f433e021850fbde5b1d3f3?start=2026-09-19&end=2026-10-16`.

Kết quả 14 posts, 28/28 ngày, period engagements null/no_data, 0/28 ngày tương tác.
`verified=false`, `publishable=false`, `data_origin=persisted_unverified`.
Snapshot cũ chưa có contract mới nên `snapshot_metrics=null`; không đưa các
lifetime counters cũ vào UI qua dữ liệu thiếu metadata hoặc tự tạo receipt.

Renderer KPI thực tế, có hash khớp file được serve trên 8191, đã render payload
runtime bằng JSDOM: hiển thị 14, 28/28, dấu —/no_data, giải thích tương tác theo kỳ
và banner chưa xác minh. Không chạy browser navigation gây auto-discovery.
Đây là kiểm HTTP + DOM với payload thật, **không phải New E2E/full-browser E2E**.

GET preview lịch sử trả 409 `meta_contract_missing`: guard đúng vì snapshot cũ
thiếu contract/receipt mới, không phải lý do để tự sync/verify lại. Viewer Bundle
API từ chối 401 khi không có backend authorization, kể cả đang có Admin cookie.

## Dữ liệu và bảo mật

Client `client_meta_sandbox`, Page VIO Agency `2188688654687066` không đổi.
12 bảng được hash trước Admin, sau startup, sau HTTP và cuối lượt:
connections, source_assets, jobs, sync_runs, source_snapshots, daily_metrics,
secrets, datasets, reports, source_attestations, marketing_release_approvals,
marketing_release_snapshots. Kết quả khớp baseline backup.

Toàn DB 91 daily_metrics gồm 34 post rows và 57 Page rows của hai kỳ riêng.
Kỳ 2026-09-19–2026-10-16 vẫn 14 posts/28 Page rows; kỳ lịch sử 2025 riêng biệt.
2 snapshots, 3 historical jobs/sync_runs (2 succeeded, 1 failed), 0 queued/running,
0 duplicate metric keys. Không thêm Dataset/approval/attestation/release/report.

Migrations vẫn 1–8, không migration mới hoặc data repair. ENCRYPTION_KEY và toàn
bộ env mới bằng env container cũ. Stored grant vẫn có pages_read_user_content và
ads_read; chưa kiểm revoke/expiry/account access bằng provider.

Network tests thực chạy:

* Admin có duy nhất network internal; PG private IP .2, Admin .3.
* Relay/gateway PID1 uid10001, CapEff/CapBnd=0, NoNewPrivs=1, ip_forward=0,
  IPv6 disabled, không default route.
* CONNECT graph.facebook.com:443 + TLS certificate/SNI hợp lệ: PASS.
  **Không gửi HTTP/application bytes sau handshake; 0 Graph/Marketing API calls.**
* Domain ngoài allowlist, port 80, IP literal thay hostname: 403.
* Sai TLS SNI: bị đóng. Direct Internet và bypass proxy: bị chặn.
* Relay/gateway truy cập PG hoặc Internet ngoài tuyến cho phép: bị chặn.

## Kiểm thử đã chạy

| Lệnh/kiểm thử | PASS | FAIL | SKIP |
|---|---:|---:|---:|
| `python -B docs/phase5b-20261018/preflight.py` | Gate PASS | 0 | 0 |
| `python -B docs/phase5-20261018/build_after_approval.py --approved-build` | Build PASS | 0 | 0 |
| `python -B docs/phase5b-20261018/smoke_image.py` | Runtime smoke PASS + 16 fixture cases | 0 | 0 |
| `npm.cmd test` | 84 | 0 | 0 |
| `node --experimental-vm-modules docs/phase5b-20261018/verify_kpi_dom.mjs` | 1 integration probe | 0 | 0 |
| `verify_http.py`, `verify_network.py`, data checksum gates | PASS | 0 | 0 |
| Python artifact parse, JS syntax, `git diff --check` | PASS | 0 | 0 |

Precheck helper false-positive đã được ghi riêng ở trên; không che giấu thành
một lần deployment liên tục không có stop. Không có product test fail hay sửa
source để vượt gate. 117 PostgreSQL cases Phase 4 không chạy lại trong lượt này;
không cộng kết quả cũ thành test mới. Ads live/New E2E: NOT TESTED.

## Rollback readiness

Không cần rollback trong lượt này. Image cũ còn nguyên:
`sha256:d4e4e09a6a43af0c01e98d135bb1ff8ac65bd2c0bbb27cd5bc778c28e658b0b9`.
Admin cũ giữ stopped để đọc nguyên env/config; encrypted backup còn dùng được.

Nếu phải rollback, kiểm đúng Admin mới ID trước thao tác, rồi dùng helper Phase
5B đã sửa điều kiện inactive endpoint. Không chạy các lệnh này trong lượt PASS:

```powershell
$admin = 'kdh-meta-2b-admin-20261016-132836-5c512a53'
$net = 'kdh-meta-2b-net-20261016-132836-5c512a53'
$current = (docker inspect $admin | ConvertFrom-Json)[0]
if ($current.Id -ne '51843a6c05fadeffc22955e8edbddd5a08246dc7ae9ba6c86380c173f59d6990') { throw 'STOP: identity changed' }
docker stop $admin
if ($LASTEXITCODE -ne 0) { throw 'STOP: Admin stop' }
docker network disconnect --force $net $admin
if ($LASTEXITCODE -ne 0) { throw 'STOP: endpoint release' }
$oldImage = 'sha256:d4e4e09a6a43af0c01e98d135bb1ff8ac65bd2c0bbb27cd5bc778c28e658b0b9'
.\.venv\Scripts\python.exe -B docs/phase5b-20261018/create_admin_after_approval.py --approved-create --rollback --image-id $oldImage
if ($LASTEXITCODE -ne 0) { throw 'STOP: rollback create' }
docker start "$admin-rollback-phase5"
if ($LASTEXITCODE -ne 0) { throw 'STOP: rollback start' }
```

Phải kiểm IP .3, no host binding, health và data hashes trước nghiệm thu rollback.
Không start nguyên container before-phase5; không restore/drop/reset DB. Nếu dữ
liệu lệch, stop và xin quyết định riêng, không data repair tự động. Application
rollback chưa thực chạy vì deployment đạt; không tuyên bố rollback drill PASS.

## Git và evidence

Branch `feat/seo-composite-release`, HEAD `664efbc561b401d901947437c63df87348d81437`.
Không thay file source/fixture đã checkpoint, không commit/push/reset/stash/merge.
Chỉ thêm báo cáo này, `docs/phase5b-20261018/` và image result mới ở thư mục Phase 5.
Source manifest 61 file và toàn bộ baseline files được kiểm bằng SHA-256.

Evidence chính: preflight.json, smoke.json, postgres-start.json, deployment.json,
data-before-admin.json, data-after-admin.json, data-after-http.json,
data-final.json, http-verification.json, network-verification.json, kpi-dom.json,
final-integrity.json. Không có token, secret, cookie hay DSN trong evidence.

## Facebook Ads live acceptance còn thiếu

1. Người dùng xác nhận exact Ad Account ID (`act_...`), Business/Owner và quyền
   kiểm tra tài khoản đó. Không suy ra từ Page VIO.
2. Duyệt phép đọc live nhỏ riêng; kiểm token thực tế, ads_read và asset/account
   authorization. Grant đã lưu không đủ chứng minh quyền hiện tại.
3. Xác nhận currency, account timezone, attribution windows và định nghĩa
   results=action_type lead theo contract. Chọn 1–3 ngày đã kết thúc theo timezone
   account, dữ liệu được owner xác nhận; chưa tự chạy Insights hoặc sync.
4. Chỉ sau read-only acceptance đạt mới xin duyệt bounded sync riêng, rồi review/
   source verification/approval theo kiến trúc hiện hữu. VIO cũ vẫn unverified.
5. New integration và E2E giữa hai ứng dụng vẫn cần triển khai/kiểm thử riêng.

**PHASE 5 SANDBOX DEPLOYMENT PASS — READY FOR FACEBOOK ADS ACCEPTANCE**
