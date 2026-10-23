# Hợp nhất cải tiến vào Admin chính — 20/10/2026

## Kết quả

- Admin chính: **http://localhost:8090**.
- New chính: **http://localhost:8080**. Trang gốc chuyển về Admin `/viewer/reports`.
- Giữ `META_CLIENT_ID=client_meta_sandbox` theo xác nhận của người dùng.
- VIO sandbox và database riêng được giữ nguyên. Không chuyển Bundle, Dataset, tài khoản hoặc grant giữa hai môi trường.
- Không sync, gọi provider, reconnect, review, approve, publish hay thay đổi schema.
- Chưa nghiệm thu E2E đăng nhập và xem báo cáo thật trên cặp chính: chưa có thông tin đăng nhập để tự động kiểm tra; truy vấn chỉ đọc xác nhận **database chính chưa có Bundle của `client_meta_sandbox`**.

## Source và Git

Admin đã ở `main`, HEAD `6b52ee2f3ef29ebb5820e95e88ba318a7599667d` khi bắt đầu; source cải tiến đã nằm trong main, runtime cũ chưa nạp. Không đổi branch hoặc merge thêm.

New chính vẫn ở `main`, HEAD `837f655525d4ee061c1e1365d1e47b57bba175f4`. Đưa 133 file runtime/test/config từ working tree VIO đã nghiệm thu vào working tree chính: 79 file có sẵn, 54 file mới. Gồm handoff, Viewer repository, Bundle mapper, null/partial/lifetime semantics, giao diện Facebook Content, căn cột số và liên kết bài đăng. Không chuyển `.env`, token, dữ liệu hoặc cấu hình sandbox.

Giữ các sửa đổi có sẵn của New tại README, Compose và script preview; bổ sung tối thiểu README/Compose để phản ánh source/image mới. New VIO không chỉnh sửa.

File vận hành bổ sung/cập nhật trong Admin:

- `compose.yaml`: pin image đã kiểm thử; capability VIO mặc định tắt.
- `compose.primary-viewer.yaml`: override local rõ ràng để bật published VIO handoff; không đổi client.
- `ops/unify_primary.py`: build, backup mã hóa, restore test, smoke, triển khai có rollback và kiểm tra hash.
- `ops/verify_primary_browser.py`: QA anonymous, chỉ GET/HEAD, chặn yêu cầu ngoài allowlist.
- `docs/unified-admin-20261020/`: baseline, manifest, test logs, ảnh và kết quả triển khai.

Danh sách chi tiết các file New đã tích hợp: `docs/unified-admin-20261020/new-source-integration.json`.
HEAD hai repository giữ nguyên; không commit/push/reset/stash/checkout.

## Runtime

| Thành phần | Container | Image |
|---|---|---|
| Admin | `kdh-report-admin-admin-1` | `kdh-admin:unified-20261020-ffeef2ce9a18` |
| New | `kdh-report-new-app-1` | `kdh-new:unified-20261020-0d8c6b94bb93` |
| PostgreSQL chính | `kdh-report-admin-postgres-1` | Giữ nguyên container/image/volume |

Admin image ID: `sha256:e1c8ce68bcbd5c66464a0298ce86be09c5d15e7ed838295fa27322fbd1b63adf`.

New image ID: `sha256:87844f282565682fefffb3f1436a48b70099129a96704abb743b134df16256f9`.

Manifest: 68 file Admin, 162 file New. Dependencies khớp image nền, migration source khớp trước triển khai; database đã có migrations 1–8. Build không tải dependency, không chứa `.env`, `instance` hoặc credential.

Chỉ thay hai app container. Giữ mount, network, loopback ports, OAuth encryption key, service token của cặp chính và `JOB_MODE=worker`. Không có job queued/running hoặc lịch enabled trước triển khai. Không chuyển hệ chính sang chế độ request của sandbox.

Capability `REPORT_VIO_HANDOFF_ENABLED=1` chỉ mở luồng published đã có: vẫn bắt buộc client VIO được cấu hình, APP_URL loopback, Bundle hợp lệ, session hợp lệ và Viewer grant đúng user/report/revision. Không mở internal preview VIO hoặc cấp grant mới.

New → Admin `/health`: 200. Service token hợp lệ nhưng không có Viewer session → Bundle API trả 401. New production chặn các route demo (404).

## Kiểm thử

| Lượt | Kết quả |
|---|---|
| `npm.cmd test` — Admin | 100 PASS, 0 FAIL, 0 SKIP |
| New `.venv\Scripts\python.exe -B -m pytest -q` | 279 PASS, 0 FAIL, 0 SKIP; 5 deprecation warnings |
| Admin unittest trực tiếp trên máy, có `.env` VIO | FAILED: 107 failure assertions, 22 errors, 141 SKIP / 529 test; scope VIO làm sai giả định default-client của fixtures |
| Admin unittest trong image, `--network none`, không `.env` | 388 PASS, 0 FAIL, 141 SKIP / 529 |
| Admin full suite trên PostgreSQL disposable | 483 PASS, 0 FAIL, 46 SKIP / 529 |
| `test_facebook_bundles_postgres` với guarded flags | 14 PASS, 0 FAIL, 0 SKIP |
| `test_meta_diagnostics.PostgresMetaDiagnosticsTests` + `test_vio_handoff.PostgresVioHandoffTests` | 18 PASS, 0 FAIL, 0 SKIP |
| JS `node --check` và hai repo `git diff --check` | PASS |
| Restore backup + app startup trên bản sao isolated | PASS, hash mọi table không đổi |
| New image offline smoke | PASS |
| Browser anonymous 1440/1024/768/390/360 | PASS: form login, không tràn ngang, không page error |
| Browser New → Admin entry | PASS |
| Browser authenticated handoff / báo cáo thật trên cặp chính | NOT RUN |

46 SKIP trong full PostgreSQL suite không được tính là PASS: các nhóm tương ứng đã chạy riêng với cờ an toàn. Tổng 32 case riêng được thực thi bổ sung; 14 lượt skip còn lại là cùng class Facebook được unittest discover lần nữa qua import trong module VIO. Không cộng duplicate thành kiểm thử độc lập.

Test DB chỉ ở container `kdh-unified-20261020-postgres`, network `kdh-unified-20261020-test` internal, không host port, lưu PostgreSQL bằng tmpfs. Database `restored` dùng kiểm tra backup; `regression` dùng fixtures/test schemas. Không chạy test ghi trên DB chính/sandbox.

Các lệnh vận hành đã chạy từ Admin bằng `.venv\Scripts\python.exe -B ops/unify_primary.py <stage>`:
`preflight`, `build`, `isolated`, `isolated_validate`, `new_smoke`, `collect_postgres`, `facebook_postgres`, `extra_postgres`, `deploy`, `final_verify`.

Smoke harness ban đầu kiểm tra sai `/login` thay vì `/` của Admin nên dừng trước deployment; đã sửa harness đúng route thực tế, không sửa backend để ép PASS.

## Bảo toàn và rollback

- Backup PostgreSQL `pg_dump -Fc` và appdata được mã hóa Fernet; key bảo vệ bằng Windows DPAPI, lưu ngoài repo/volume gốc tại `%LOCALAPPDATA%\KDH-Primary-Deployment\unified-20261020`.
- Đối chiếu checksum và restore trên bản sao độc lập PASS. **Chưa có backup off-host.**
- Giữ nguyên khóa mã hóa OAuth, service token và các biến môi trường hiện hữu; không in secret vào log/báo cáo.
- Hash/count toàn bộ table database chính so với baseline không đổi sau deployment.
- Container/image/mount/network và trạng thái chạy của các tài nguyên VIO bảo vệ giữ nguyên.
- Container ứng dụng cũ giữ ở trạng thái stopped:
  - `kdh-report-admin-admin-1-rollback-unified-20261020`
  - `kdh-report-new-app-1-rollback-unified-20261020`
- Rollback ứng dụng: dừng hai app mới, đổi tên chúng để giữ chẩn đoán; đổi tên hai container rollback về tên gốc và start. Giữ nguyên PostgreSQL. Không restore đè DB, không chạy migration/data repair.
- Không start container rollback cùng lúc với app mới: chúng dùng cùng port/mount.

Nếu sau này cần recreate bằng Compose, dùng đúng cấu hình đã nghiệm thu; không chạy toàn stack hoặc `down`:

```powershell
# Admin: giữ .env hiện hữu; kiểm tra client và backup trước khi thực hiện.
docker compose -f compose.yaml -f compose.primary-viewer.yaml up -d --no-deps --no-build --pull never admin

# New: chạy từ repository New, giữ .env và service token hiện hữu.
docker compose up -d --no-deps --no-build --pull never app
```

Các lệnh trên là hướng dẫn bảo trì, không cần chạy lại để xem bản hiện tại.

## Người dùng làm tiếp

1. Mở **http://localhost:8090**, tải lại trang và đăng nhập bằng tài khoản Admin chính hiện có.
2. Kiểm tra badge client `client_meta_sandbox`; dùng Tổng quan / Đồng bộ dữ liệu / Dataset / Duyệt & phát hành trong cùng Admin.
3. Với báo cáo được phát hành tại database chính và có grant, chọn đúng report/revision rồi mở New. New dùng cổng 8080.
4. Báo cáo VIO từng nghiệm thu trên 8193 vẫn thuộc sandbox riêng. Chưa sao chép nó sang hệ chính; không dùng trạng thái hoặc grant của sandbox để nhận quyền tại hệ chính.

Việc đưa báo cáo/dữ liệu sandbox sang chính, nếu mong muốn ở giai đoạn sau, cần kế hoạch migration/ownership/grants riêng. Đợt này chỉ thống nhất source và giao diện, giữ phạm vi khách hàng và dữ liệu.
