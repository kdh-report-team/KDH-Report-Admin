# Hai Admin, New dùng chung — 21/10/2026

## Địa chỉ và sử dụng

| Dịch vụ | Cổng | Container hiện dùng |
|---|---|---|
| Admin chính | http://localhost:8090 | kdh-report-admin-admin-1 |
| Admin VIO | http://localhost:8191 | kdh-meta-2b-relay-20261016-132836-5c512a53 (cổng ingress) |
| New chung | 8080 | kdh-report-new-app-1 |

Nhấn cổng 8090 hoặc 8191 trong Docker để vào đúng Admin. Mở Duyệt & phát hành,
chọn Bundle/revision rồi mở báo cáo. Admin chính dùng localhost:8080; VIO dùng
127.0.0.1:8080. Cả hai được phục vụ bởi cùng một container/image New.
Không tự sửa host trong URL báo cáo vì host xác định môi trường backend.

Các dịch vụ active có restart unless-stopped. Nếu đã Stop nhiều dịch vụ,
chạy Start-KDH.cmd ở thư mục Admin: kiểm tra identity rồi start theo thứ tự,
không build/recreate. Không nhấn Run tất cả container archive/test: các bản
rollback có thể còn nhãn Compose cũ. Chưa tái tạo database/relay chỉ để gom
toàn bộ chúng vào một nhóm Docker Desktop. Cổng 8193 cũ không còn phục vụ.
MockDb 8082 là bản thiết kế riêng, không thuộc luồng báo cáo thật; giữ nguyên.

## Triển khai

- Primary Admin: kdh-admin:shared-20261021-dac5a0b9468d.
- VIO Admin: giữ image origin-fix-20261021-4c8b2e4b3c8a; đổi New URL sang 8080.
- New: kdh-new:shared-20261021-4b0bc56adfe3.
- Thêm primary relay riêng chỉ chuyển đến Admin 172.26.0.3:8090.
- New chỉ nối mạng host hạn chế và hai mạng relay private; không mạng PostgreSQL.
- Không sửa OAuth, sync, Dataset, approval, Bundle, grant hoặc schema.
- Dữ liệu primary và VIO vẫn riêng; không tự chuyển primary sang KinderHealth.
- PostgreSQL/appdata được backup mã hóa ngoài Git; checksum/giải mã và pg_restore
  --list PASS. Không restore đè dữ liệu. Backup này chưa được xác nhận off-host.

## Code và cấu hình

Admin: app.py có canonical loopback redirect đã test; compose.yaml cập nhật image
và IP Admin cố định cho relay. Thêm ops/shared_viewer.py, ops/check_shared_viewer.py,
Start-KDH.cmd và tài liệu. Các thay đổi local trước đó được giữ nguyên.

New: app/config.py, app/viewer_environment.py, app/routes/viewer.py,
app/routes/handoff.py, ops/shared_viewer_entrypoint.py, tests/test_shared_viewer.py,
Dockerfile, compose.shared.yaml và compose.yaml. Không đổi mapper/KPI/dashboard.
Default compose New include cấu hình shared; fresh compose up đòi hai service
credentials private. Không in/commit credential; để start existing dùng launcher.

## Kiểm thử

- New full suite: 290 PASS, không skip; có 5 cảnh báo deprecation.
- Admin image offline/SQLite: 64 PASS, không skip.
- UI 100 PASS từ đợt origin-fix ngay trước đó, không đổi JS/UI trong đợt shared.
- JS syntax, git diff --check và Compose config validation: PASS.
- Image smoke cô lập, không DB/provider: PASS.
- Docker IP link 8090/8191 → canonical localhost login: browser PASS.
- VIO login/handoff/report revision 1 trên New 8080: browser PASS, chạy lại sau restart.
- KPI 15 posts, 80 reactions lifetime, 10 comments lifetime; engagements null/no_data;
  shares null/partial, coverage 7/15; UTC: PASS.
- Sai môi trường, report không grant, revision khác: DENIED.
- State/session/backend isolation trong regression tests: PASS.
- New → hai relay → hai Admin health: 200.
- New → hai PostgreSQL, direct Admin, Meta gateway, Internet: ENETUNREACH.
- Application stop/start: PASS; không restart database.
- Hash bảng nghiệp vụ hai DB không đổi; session/audit login/logout được loại riêng.
- Primary authenticated report E2E: NOT RUN, chưa có Bundle/grant primary phù hợp.
- Full Docker Desktop/Engine reboot: NOT RUN; đã test application restart.

Evidence: browser.json, docker-links.json, network-tests.json, deployment.json,
restart-test.json, build.json, admin-tests.log và report-after-docker-login.png.

## Rollback

ops/shared_viewer.py rollback khôi phục ba app container trước shared và New VIO
8193. Không restore database. Các container before-shared-20261021 giữ stopped,
restart=no. Không thực hiện rollback khi hệ thống đang hoạt động tốt.

Không commit/push/đổi HEAD; thay đổi chưa commit vẫn được giữ.
