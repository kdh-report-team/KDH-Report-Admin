# Phase 5 — Meta Sandbox Recovery & Deployment Preparation

Ngày kiểm tra: 18/10/2026. Đây là kế hoạch chờ duyệt, **chưa triển khai**.
Không khởi động/recreate bốn container gốc, không ghi DB gốc, không gọi provider.
Evidence: `docs/phase5-20261018/`. Không chứa secret, token, cookie hay DSN.

## 1. Kết quả và giới hạn

| Kiểm tra thực hiện | Kết quả |
|---|---|
| Docker context/daemon | `desktop-linux`, Engine 29.7.2 |
| Cold backup PostgreSQL/appdata, nguồn mount read-only | PASS |
| Hai lần đọc độc lập mỗi volume có cùng SHA-256 | PASS |
| Backup mã hóa, khóa được Windows DPAPI bảo vệ, ACL riêng | PASS |
| Restore vào hai volume mới; bytes/uid/gid/mode từng file | PASS |
| PostgreSQL 16.15 chạy trên bản sao, network none, không host port | PASS |
| SQL read-only, migration 1–8, Page/client, dữ liệu kỳ chính | PASS |
| Hash 12 bảng giữ nguyên sau restart bản sao | PASS |
| Giải mã secret record với ENCRYPTION_KEY hiện hữu, chỉ trong bộ nhớ | PASS |
| Kiểm tra hiệu lực token bằng Meta API | NOT TESTED, không được phép |
| Build manifest 61 file khớp Phase 4 | PASS |
| Build image mới / smoke image mới | NOT EXECUTED |
| Khôi phục sandbox 8191 / login / CSRF qua HTTP | NOT EXECUTED |
| Live Content/Ads sync, independent verification, release, New E2E | NOT EXECUTED |

117 PostgreSQL và 84 UI tests là kết quả Phase 4 được giữ nguyên, không tính lại
thành các test mới của Phase 5. Lượt này chỉ thêm tài liệu/script chuẩn bị và chạy
kiểm tra backup/restore; không sửa backend/frontend/tests sản phẩm.

## 2. Identity và chẩn đoán runtime

Run: `20261016-132836-5c512a53`.

| Container gốc | Container ID |
|---|---|
| `kdh-meta-2b-pg-20261016-132836-5c512a53` | `41c3cebbed98beab58091b359ba12e4b54f7eb90a41fbe4b9cb5a86539cb87d1` |
| `kdh-meta-2b-admin-20261016-132836-5c512a53` | `3b3cb91e860b57cf7b8ac414078728b085d4cbf620014a1a186a0145dc66f371` |
| `kdh-meta-2b-relay-20261016-132836-5c512a53` | `10a498a7245ef7b9e8dc2a67b389160d7feeec2fe6939ae5d1d06cf5cac3028f` |
| `kdh-meta-3-egress-20261016-132836-5c512a53` | `c264a6c245cfd98fedd717e0f2e60743058e8d26e7a2577702622e23c993b0e6` |

Cả bốn: Exited 255, OOMKilled=false, RestartCount=0, restart policy `no`.
Admin FinishedAt `2026-10-18T11:48:29.790084871Z`; ba container còn lại cùng
giây, lệch khoảng 5 ms. Không có State.Error. Timestamp này có thể là thời điểm
daemon ghi nhận/reconcile container, không chứng minh thời điểm sự cố bên trong.

Log Docker Desktop thu thập ban đầu có tín hiệu start/WSL/boot lúc 11:48:12–13Z.
Log container còn giữ có các lần ready trước đó, không thấy shutdown/OOM/port
error ở thời điểm 11:48 trong phần log kiểm tra. Docker events truy vấn không
còn event phù hợp. File host log tiếp tục xoay vòng trong lúc kiểm tra; lần tìm
phrase chi tiết sau không thu được thêm bằng chứng (`desktop-startup-signals.json`).

**Giải thích phù hợp với bằng chứng:** Docker Desktop/WSL restart và việc daemon
khôi phục trạng thái đã dừng. **Chưa xác định được nguyên nhân shutdown ban đầu**,
không kết luận OOM hoặc lỗi port làm cả bốn container thoát. Port trùng là một
blocker độc lập khi start lại.

Image PostgreSQL: `sha256:ca0bd484cb98bf4b24eb1010e73fb3fcbd6714d240fbc1a10eea5b7dbecb641d`.
Image Admin/relay/gateway hiện hữu:
`sha256:d4e4e09a6a43af0c01e98d135bb1ff8ac65bd2c0bbb27cd5bc778c28e658b0b9`.

## 3. Ingress và isolation chính xác

HostConfig.PortBindings của **cả Admin và relay** hiện là:
`8090/tcp -> HostIp 127.0.0.1, HostPort 8191`.
Đây là binding khai báo trên container dừng, không phải bằng chứng cả hai đang
listen thành công. Không được start nguyên cấu hình cả hai.

Thiết kế được chuẩn bị:

```text
127.0.0.1:8191
  -> kdh-meta-2b-relay-20261016-132836-5c512a53:8090
  -> 192.168.0.3:8090 (Admin; KHÔNG publish host port)
```

Chỉ cần thay container **Admin** vì Docker không sửa được published binding của
container hiện hữu. Giữ relay, gateway, PostgreSQL, volume và network hiện tại.
Admin listen 0.0.0.0:8090 bên trong container là cần thiết cho relay; không có
host binding 0.0.0.0. `admin-desired-config.json` là cấu hình đã lọc để review.

| Network | Internal | IP/attachment cần giữ |
|---|---|---|
| `kdh-meta-2b-net-20261016-132836-5c512a53` | true | PG kỳ vọng .2; Admin pin 192.168.0.3; gateway pin 192.168.0.10; relay tham gia |
| `kdh-meta-2b-ingress-20261016-132836-5c512a53` | false | Chỉ relay trong nhóm này; listen 192.168.16.2 |
| `kdh-meta-3-outbound-20261016-132836-5c512a53` | false | Chỉ gateway trong nhóm này |

PG hiện cấp IP động; **sau start phải đúng 192.168.0.2, nếu khác thì STOP**.
Không tự sửa gateway/relay hay đổi subnet/IP để né gate. Admin phải đúng .3;
gateway .10; relay giữ .16.2. Source hash của bảy file gateway/relay không đổi.

Gateway chỉ nhận client Admin .3, CONNECT graph.facebook.com:443, kiểm SNI tương
ứng và kết nối Graph IP pin `57.144.14.141`. Relay bỏ default route, pin upstream
.3; gateway bỏ default route tổng quát và giới hạn tuyến đi. Không cần mở domain
mới cho Ads theo adapter hiện tại. Pin IP còn dùng được hay không chưa thử live.
Giữ Gate C, cap/security options và isolation hiện hữu; không mở Internet rộng.

Admin giữ `JOB_MODE=request`, DNS 127.0.0.1, HTTP(S) proxy .10:3128, NO_PROXY
hiện tại, read-only rootfs, drop ALL caps, no-new-privileges, memory 512 MiB,
CPU 1, tmpfs /tmp 64 MiB; appdata RW theo cấu hình cũ. Không chạy background worker.

Giữ APP_URL `http://localhost:8191`, callback `/api/meta/callback`, cookie namespace
`kdh_meta_acceptance_session`, COOKIE_SECURE=0 cho localhost HTTP, App ID
1831786608275511, Config ID 1683586973182335. Tất cả env được giữ nguyên trong bộ nhớ,
không chép secret vào artifact. Config private và env container hiện khớp nhau.

## 4. Bảo toàn dữ liệu và backup

Volume gốc được đối chiếu container identity, mount và run ID:

* `kdh-meta-2b-pgdata-20261016-132836-5c512a53` → `/var/lib/postgresql/data`.
* `kdh-meta-2b-appdata-20261016-132836-5c512a53` → `/app/instance`.

Bind mount bảo mật được giữ:
`D:\KDH-Meta-Phase2B\20261016-132836-5c512a53\relay` và
`D:\KDH-Meta-Phase2B\20261016-132836-5c512a53\phase3\gateway` (RO).

Không tìm được backup cũ đã có bằng chứng restore trong hồ sơ Phase 2B/3/4 được
kiểm tra; không dùng metadata volume làm bằng chứng đã backup. Đã tạo backup mới:

`C:\Users\Admin\AppData\Local\KDH-Meta-Backups\kdh-phase5-20261018-59770a49`

Thư mục ACL riêng CurrentUser + SYSTEM, không kế thừa. Archives PostgreSQL/appdata
và admin.config đều Fernet encrypted; `backup-key.dpapi` được Windows DPAPI
CurrentUser bảo vệ. Không có bản plaintext archive/config trên host. Backup này
cần cùng Windows user/profile/máy để mở khóa; chưa có bản DR độc lập/off-host.

| Archive | Dung lượng trước mã hóa | Entries | SHA-256 nội dung archive |
|---|---:|---:|---|
| PostgreSQL | 52,203,520 bytes | 1,456 | `bb46a6d37bdaf32985f3c331ae2b6c2aa20bea19c7c7fcfadd5e43e3fc26c68c` |
| Appdata | 10,240 bytes | 2 | `b59960cace514cd265eb47c6f016b407694de1e91fe03388023ac87da763aefe` |

Mỗi nguồn được đọc hai lần từ helper `network=none`, rootfs RO, volume RO,
volume-nocopy, log-driver none. Hash hai lần giống nhau. Kiểm tra từ chối symlink
hoặc special files để không bỏ sót tablespace ngoài volume. PostgreSQL có
PG_VERSION=16, pg_control và WAL trong archive. Binary archive không qua log Docker.

Restore riêng:

* Container `kdh-phase5-20261018-59770a49-pg-restore`.
* Volume `kdh-phase5-20261018-59770a49-postgres-restore`.
* Volume `kdh-phase5-20261018-59770a49-appdata-restore`.

Restore bytes, uid/gid/mode của mọi entry khớp archive **trước khi start bản sao**.
Chỉ xóa stale postmaster.pid trên bản sao. PostgreSQL 16.15 chạy với network none,
không host port, Unix socket /tmp và default_transaction_read_only=on. Không gọi
Store/create_app, không migration/bootstrap. Appdata được kiểm file, chưa boot app.

Clone đã dừng sạch Exited(0). Các helper đều Exited(0); giữ lại để review, không
xóa/prune. Cluster data_checksums=off: kiểm tra restore/hash/SQL không thay thế
kiểm định vật lý mọi page hoặc backup off-host.

## 5. Dữ liệu thực đọc từ bản sao

DB: `meta_acceptance_20261016_132836`. Migration thực tế: 1–8; source migration
hiện tại cùng hash với image cũ. **Không có migration mới cần áp dụng**.

* Client `client_meta_sandbox`; một Meta connection trạng thái lưu `connected`.
* Asset `cff1f3d5e6f433e021850fbde5b1d3f3`, facebook_page VIO Agency,
  Page ID `2188688654687066`, enabled=1. Không có Ad Account asset.
* Kỳ 2026-09-19 → 2026-10-16: 14 provider post IDs khác nhau, 28 Page/day records.
* Toàn DB có 34 posts + 57 Page/day rows = 91 daily_metrics. Phần còn lại thuộc
  kỳ lịch sử riêng 2025-07-19 → 2025-08-16, không trộn vào 14 posts của kỳ chính.
* Ba jobs và ba sync_runs: 2 succeeded, 1 failed lịch sử; không queued/running.
* Hai source_snapshots, JSON đọc được, IDs/hashes lưu trong evidence.
* Trùng daily metric keys: 0. Post lifetime fields tách khỏi Page daily fields.
* datasets/reports/source_attestations/approvals/release_snapshots: đều 0.
* Secret record còn đầy đủ, giải mã được bằng khóa cũ. Stored grant có
  pages_show_list, pages_read_engagement, pages_read_user_content, ads_read,
  public_profile. Đây là grant **đã lưu**, không phải xác minh live còn hiệu lực.

Hash 12 bảng nghiệp vụ/bảo mật không đổi sau restart clone. Hai snapshot cũ chưa
có metadata/receipt mới của triển khai Phase 4. Không tạo attestation hồi tố,
không chuyển persisted_unverified thành verified, không duyệt/publish tự động.

## 6. Image readiness

`deployment-manifest.json`: đủ 61 file Dockerfile/.dockerignore/requirements.lock/
run.py/kdh/templates/static, khớp byte-for-byte manifest Phase 4. Bao gồm Meta
Content/Ads adapter, meta_contract, meta_marketing, verifier, Dataset/review/
approval/publication, Bundle, UI, template và migrations. Không sửa SEO Composite.

Source aggregate SHA-256:
`1db981c78d84f9b0c7582948d734c62cf0b6064da893f0c7dfedba7ebb0baae5`.

Tag đề xuất, không được ghi đè khi đã build:
`kdh-admin-meta:phase5-20261018-1db981c78d84`.

Context đóng băng chỉ gồm allowlist 61 file:
`C:\Users\Admin\AppData\Local\KDH-Meta-Backups\kdh-phase5-20261018-59770a49\source-context.tar`.
Không dùng cả workspace làm context: không .env, instance, token/config, backup,
test fixture hoặc file ngoài allowlist. SHA-256 context nằm trong manifest.

**Chưa build** nên chưa có image ID mới và chưa smoke image. Dockerfile dùng
python:3.12-slim; tag nguồn không đảm bảo build bit-for-bit giữa các thời điểm.
Sau build phải ghi image ID và dùng ID đó khi create; kiểm source hashes trong
image và dependencies trước khi start app. Không thay Dockerfile trong Phase 5.

## 7. Quy trình thực thi sau khi được duyệt

Các lệnh dưới đây là **review artifact, chưa chạy**. Thực hiện từng checkpoint,
dừng ngay khi một gate FAIL; không chạy toàn bộ như script không giám sát.

### 7.1 Preflight và build riêng

1. Xác nhận HEAD/branch và hash 61 file/context/backup chưa đổi. Kiểm lại bốn ID,
   state, mounts, network IDs, Internal=true, source gateway/relay hashes và env
   equality theo evidence. Không đọc .env production. Không có container nào
   khác đang mount RW hai volume gốc. Nếu dữ liệu gốc đã chạy lại, backup hiện tại
   không còn là điểm rollback mới nhất: lập cold backup mới trước khi tiếp tục.
2. Kiểm backup decrypt/checksum và restore evidence PASS. Không lặp lại scripts
   cold_backup/restore_copy vô điều kiện: chúng cố ý chặn ghi đè kết quả cũ.
3. Duyệt build trước; build script không khởi động sandbox:

```powershell
.\.venv\Scripts\python.exe -B docs/phase5-20261018/build_after_approval.py --approved-build
if ($LASTEXITCODE -ne 0) { throw 'STOP: image build' }
$image = (Get-Content docs/phase5-20261018/approved-image-result.json -Raw | ConvertFrom-Json).image_id
```

4. Kiểm image ID/source files bằng helper không mạng, không volume gốc. Chạy
   smoke image với DB clone riêng nếu cần; không dùng test fixture để ghi DB gốc.
   Nếu image khác contract hoặc startup có side effect mới chưa duyệt, STOP.

### 7.2 PG và gateway

```powershell
$run = '20261016-132836-5c512a53'
$pg = "kdh-meta-2b-pg-$run"
$admin = "kdh-meta-2b-admin-$run"
$relay = "kdh-meta-2b-relay-$run"
$gateway = "kdh-meta-3-egress-$run"
$net = "kdh-meta-2b-net-$run"
docker start $pg
if ($LASTEXITCODE -ne 0) { throw 'STOP: PostgreSQL start' }
```

Đây là **lần ghi volume gốc đầu tiên cần phê duyệt**: PostgreSQL recovery/WAL
có thể ghi dù chưa có app. Kiểm healthy, image đúng, PG IP=.2, không published
ports, network internal duy nhất. Dùng psql với role từ inspect chỉ trong bộ nhớ,
SQL BEGIN READ ONLY để đối chiếu DB identity, schema 1–8, 12 table hashes trong
restore-result.json và kỳ 14/28. Không tạo Store hoặc gọi app để kiểm tra trước gate.

```powershell
docker start $gateway
if ($LASTEXITCODE -ne 0) { throw 'STOP: gateway start' }
```

Kiểm .10, inbound client .3, pin Graph IP/domain/SNI, dropped privileges, routes,
no published ports, không thay network. Nếu pin hết hiệu lực: STOP xin duyệt
riêng; không mở default route/unrestricted egress.

### 7.3 Thay riêng Admin, bỏ publish port

Chỉ sau backup/build/PG/gateway gates PASS. Giữ nguyên container Admin cũ để
rollback; không xóa nó. Việc rename/detach dưới đây là thay đổi được xin duyệt
rõ ràng, không đụng subnet, gateway hay membership của container khác.

```powershell
docker rename $admin "$admin-before-phase5"
if ($LASTEXITCODE -ne 0) { throw 'STOP: retain old Admin' }
docker network disconnect --force $net "$admin-before-phase5"
if ($LASTEXITCODE -ne 0) { throw 'STOP: release old Admin endpoint' }
.\.venv\Scripts\python.exe -B docs/phase5-20261018/create_admin_after_approval.py --approved-create --image-id $image
if ($LASTEXITCODE -ne 0) { throw 'STOP: Admin create; do not start anything else' }
```

Script chỉ create STOPPED; preserve toàn bộ env từ container ID cũ trong child
process memory, giữ appdata, pin IP .3, host PortBindings rỗng. Không env file hay
secret trên command line. Script dùng --env KEY, không --env KEY=value. Kiểm
image/config/env equality/security/port trước start. Không dùng docker compose up.

```powershell
docker start $admin
if ($LASTEXITCODE -ne 0) { throw 'STOP: Admin start' }
```

Startup app hiện gọi Store/bootstrap và kiểm migration ngay cả JOB_MODE=request;
đó là thao tác DB được duyệt trong giai đoạn deployment, không phải read-only.
Không có migration mới; nếu schema/version lệch hoặc startup muốn thay schema
ngoài 1–8, STOP. Kiểm Admin healthy, IP .3, JOB_MODE=request, không worker/job mới,
chỉ internal network, không host ports, đúng image ID. Nếu IP khác .3: STOP.

### 7.4 Relay và nghiệm thu bảo toàn

```powershell
docker start $relay
if ($LASTEXITCODE -ne 0) { throw 'STOP: relay start' }
$status = (Invoke-WebRequest -UseBasicParsing -Uri 'http://localhost:8191/health').StatusCode
if ($status -ne 200) { throw 'STOP: HTTP health' }
```

* Chỉ relay có binding 127.0.0.1:8191, không container mới expose host 0.0.0.0.
* Xác nhận relay upstream .3:8090 và listen .16.2 không đổi; Gate C isolation.
* Đăng nhập Admin bằng trình duyệt; cookie namespace/HttpOnly/SameSite/callback
  không đổi. Không xuất cookie/session/CSRF token vào evidence. Kiểm request
  thiếu CSRF bị từ chối bằng endpoint auth an toàn; không dùng sync/select/OAuth
  làm phép thử. Login có thể thêm session/attempts; không được thay nghiệp vụ.
* So sánh hash 12 bảng và snapshot payload IDs/hash trước/sau startup với baseline
  clone; đúng Page/client, 14 bài/28 ngày kỳ chính, 2 snapshots, 3 jobs/sync_runs,
  0 queued/running, không thêm Ads asset, không attestation/release mới.
* Giữ Content-only discovery tự động. Không mở trang/endpoint gây discovery khi
  chưa duyệt provider call. Đọc snapshot/preview chỉ DB khi cần kiểm UI.
* Kiểm allow/deny egress sau khi được duyệt riêng cho probe: chỉ CONNECT/TLS
  graph.facebook.com:443, **không HTTP Graph API**; deny domain ngoài allowlist,
  sai port, sai SNI, bypass proxy. Nếu Phase 5 approval chưa bao gồm network probe
  thì ghi NOT TESTED, không tự gọi provider hoặc sửa allowlist.
* Historical VIO vẫn unverified và guard publication vẫn chặn. Không resync,
  tạo Dataset/Candidate/approval, publish hoặc kiểm New E2E trong recovery.

## 8. Rollback không phá dữ liệu

Migration 1–8 giống nhau nên rollback app không yêu cầu hạ schema. Nếu start mới
gặp lỗi, dừng Admin mới; giữ PG/gateway/volume và toàn bộ evidence. **Không start
nguyên container Admin cũ**: nó vẫn có binding 8191 gây xung đột relay.

Sau khi kiểm đúng identity container mới và được duyệt rollback:

```powershell
docker stop $admin
if ($LASTEXITCODE -ne 0) { throw 'STOP: stop new Admin' }
docker network disconnect --force $net $admin
if ($LASTEXITCODE -ne 0) { throw 'STOP: release new endpoint' }
$oldImage = 'sha256:d4e4e09a6a43af0c01e98d135bb1ff8ac65bd2c0bbb27cd5bc778c28e658b0b9'
.\.venv\Scripts\python.exe -B docs/phase5-20261018/create_admin_after_approval.py --approved-create --rollback --image-id $oldImage
if ($LASTEXITCODE -ne 0) { throw 'STOP: rollback create' }
docker start "$admin-rollback-phase5"
if ($LASTEXITCODE -ne 0) { throw 'STOP: rollback start' }
```

Rollback tạo Admin từ **image cũ nhưng ingress đã sửa**, không publish host port,
giữ IP .3/env/appdata/DB hiện có. Relay upstream không đổi. Kiểm health/14/28/
snapshots/hashes như trên. Nếu deployment chưa create Admin mới, bỏ hai lệnh
stop/disconnect chỉ sau khi xác minh đúng trạng thái; không chạy mù.

Nếu DB bị thay đổi ngoài dự kiến: STOP, không ghi đè volume gốc. Restore backup
vào volume mới, kiểm lại isolated copy, xin duyệt riêng việc chuyển DB sang bản
khôi phục. Không drop database/reset migration, không xóa volume hoặc khôi phục
đè bản gốc. Backup được mã hóa và các clone hiện tại giữ nguyên.

## 9. Rủi ro và phê duyệt còn thiếu

* Nguyên nhân shutdown chưa được xác minh tuyệt đối; Docker events không giữ đủ.
* PG checksums off; backup chỉ trên host và phụ thuộc DPAPI user/profile.
* Image mới chưa build/smoke. Pin Graph IP chưa probe. PG dynamic IP phải kiểm .2.
* Stored OAuth giải mã được không chứng minh token chưa thu hồi/hết hạn trên Meta.
* VIO snapshots lịch sử thiếu receipt mới; deployment không tự xác minh lại chúng.
* Ads live BLOCKED: chưa xác nhận Ad Account ID, Business/Owner và quyền kiểm tra.
  ads_read lưu sẵn không chứng minh account access. Cần phê duyệt read-only Insights
  ngắn, currency/account timezone/attribution rồi mới cân nhắc sync riêng.

**Cần người dùng duyệt:** build/smoke image; start PG gốc (recovery ghi dữ liệu);
start gateway/relay; rename và detach endpoint Admin cũ; create/start Admin mới
không publish port; app bootstrap trên DB gốc; health/login/CSRF và egress probes
trong phạm vi đã nêu. Rollback nếu cần cũng chỉ theo kế hoạch sandbox này.
Không bao gồm live discovery/sync, OAuth lại, verification/approval/publication,
thay gateway allowlist, xóa tài nguyên, production hoặc KDH-Report-New.

Git branch/HEAD và hash file gốc được kiểm trong `git-integrity.json`; các artifact
Phase 5 là file mới. Bốn container gốc giữ nguyên identity/state/config so baseline.

**PHASE 5 SANDBOX DEPLOYMENT PLAN READY — AWAITING APPROVAL**
