# Phase 9 — VIO Facebook Content Admin → New

Ngày hoàn tất: 19/10/2026  
Kết quả: **PHASE 9 COMPLETE — VIO FACEBOOK CONTENT OPENED IN NEW**

## Kết quả hiện tại

Đã hoàn tất luồng thật từ phiên Admin sandbox qua relay riêng tới New sandbox. New đọc đúng Report Bundle đã phát hành của VIO và hiển thị dashboard tại:

`http://127.0.0.1:8193/reports/rpt_4909119771c69125897d8bca84444abe?revision=1`

Report `rpt_4909119771c69125897d8bca84444abe`, revision 1, client `client_meta_sandbox`, trạng thái `provisional`, kỳ 2026-09-21–2026-10-18 UTC. Dashboard gắn nhãn **Tạm thời**; đây không phải báo cáo final/chính thức.

## Git và phạm vi

- Admin: `feat/seo-composite-release`, HEAD `1878a41e1fa291da8a2cd970cf80f7a99fa02959`.
- New VIO worktree: `D:\KDH-Report-All\KDH-Report-New-VIO-Phase9`, branch `feat/vio-handoff-phase9`, HEAD `56a51a015b465323d862394dcbeb8b4e250f2845`.
- New checkout gốc và New container tại 8080 không bị sửa; container ID/image vẫn giữ nguyên.
- Không commit/push/merge/reset/stash/clean/switch branch. File untracked `t` được giữ nguyên; checksum khớp baseline.
- `git diff --check` PASS trên hai worktree. Có cảnh báo Git về chuẩn hóa CRLF ở vài file Admin đã sửa từ trước; không có lỗi whitespace.

Thay đổi source Phase 9 có từ bước triển khai ban đầu:

- Admin: `kdh/core.py`, `kdh/viewer_handoff.py`, `kdh/marketing_console.py`, `kdh/report_bundle_routes.py`, `static/marketing.js`, `tests/test_vio_handoff.py`.
- New worktree: handoff/viewer routes, bundle repositories/mappers/schemas, Facebook Content templates và tests trong `app/`, `templates/`, `tests/`, cùng `ops/vio_sandbox_entrypoint.py`.
- Trong lượt tiếp tục này, chỉ tăng assertion trong `docs/phase9-20261019/browser_e2e.py` để xác nhận coverage và nhãn provisional, và thêm `verify_final.py` làm kiểm tra cuối read-only. Không sửa thêm application source.

## Mạng và sandbox

Nguyên nhân ban đầu là network ingress Meta giữ `enable_icc=false`, còn listener relay gốc chỉ nghe trên ingress. New không thể truy cập listener đó qua network cô lập. Không bật ICC và không nới gateway policy.

Đường đi hiện tại là:

`Browser (127.0.0.1:8193) → New → relay riêng (network nội bộ) → Admin:8090`

- Admin image: `kdh-admin-meta:phase9-4ed4f1cab6e9`, image ID `sha256:058291bbe5a905e6467b4907ab77bf18bc0e702280f08722ce2908b9e81ca970`; chỉ nghe cổng nội bộ 8090, không publish host port.
- New image: `kdh-vio-new:phase9-af197ceb7cae`, image ID `sha256:4fc62476f20335567fc4c88aaf33f317fc4f52a1870a7eff24bfe8d4cb5cb931`; chỉ bind `127.0.0.1:8193`.
- Relay gốc vẫn là thành phần duy nhất bind `127.0.0.1:8191`; Admin và PostgreSQL không publish cổng host.
- Relay sidecar `kdh-vio-relay-phase9-20261019` chỉ nghe tại IP riêng trên mạng handoff, không có host port. Nó chuyển tiếp tới đúng Admin upstream cố định; không nhận đích tùy chọn. Route mặc định bị gỡ, IPv6/forwarding tắt, quyền Linux bị hạ và chỉ cho phép IPv4 TCP.
- Ingress ICC=false; handoff network là Internal=true; host network của New có ICC=false và masquerade=false. PostgreSQL vẫn riêng trên network Admin; New không tham gia network PostgreSQL.
- HTTP kiểm tra: New → relay 200; relay → Admin health 200. New truy cập trực tiếp Admin/PostgreSQL/Meta gateway/Internet đều bị chặn. Relay truy cập PostgreSQL/Meta gateway/Internet đều bị chặn. Không có route forwarding.
- Health hiện tại: Admin 8191 = 200; New VIO 8193 = 200; New cũ 8080 = 200.
- PostgreSQL sandbox gốc, Meta gateway, OAuth, snapshot, Dataset, approval, Bundle và Viewer grant không bị thay đổi. Schema vẫn migrations 1–8. 29 bảng nghiệp vụ khớp baseline; không có provider call hoặc sync.
- Admin container cũ được giữ lại để rollback ứng dụng; không rollback vì deployment và E2E đều PASS.

## Browser E2E

Playwright chạy bằng Python môi trường `.venv`; trình duyệt Chromium dùng headless. Kết quả trong `docs/phase9-20261019/browser-e2e.json` và kiểm tra runtime cuối trong `final-verification.json`.

- Đăng nhập Admin sandbox, chọn đúng report/revision và hoàn tất handoff PKCE/state/callback tới New.
- New tạo Viewer session riêng; cookie namespace VIO tách với session New 8080. Service/provider credential không xuất hiện trong HTML.
- Dashboard xác nhận report ID/revision, client, Page `2188688654687066`, kỳ và timezone UTC.
- KPI thật từ Bundle: 15 bài (28/28 ngày), 80 reactions lifetime (15/15 bài), 10 comments lifetime (15/15 bài), engagements `null/no_data` (0/28 ngày), shares `null/partial` (7/15 bài).
- Không biến null thành 0; không cộng lifetime counters thành period engagement; trạng thái `provisional` hiển thị là “Tạm thời”. Demo routes bị từ chối.
- Negative checks: report không có grant 404; revision sai 404; report sai 404; phiên không hợp lệ/hết hạn 401; yêu cầu sai client 400; logout thu hồi Viewer session và bundle API trả 401.
- Responsive: 1440, 1024, 768, 390, 360 px đều không tràn ngang. Browser errors = 0; request ngoài allowlist = 0.
- Chỉ bảng handoff/session được phép thay đổi trong E2E; dữ liệu nghiệp vụ và Bundle không đổi.

Ảnh: `docs/phase9-20261019/screenshots/vio-content-1440.png`, `vio-content-1024.png`, `vio-content-768.png`, `vio-content-390.png`, `vio-content-360.png`.

## Kiểm thử

| Nhóm | Kết quả |
| --- | --- |
| Admin offline Python | 507 chạy, 388 PASS, 119 SKIP, 0 FAIL |
| Admin UI (`npm.cmd test`) | 100 PASS, 0 FAIL |
| Admin PostgreSQL/security isolated | 82 PASS, 0 SKIP, 0 FAIL |
| New worktree pytest | 267 PASS, 0 FAIL (5 deprecation warnings) |
| Image build và isolated smoke | PASS |
| Docker network isolation + HTTP relay smoke | PASS |
| Browser handoff, KPI, ACL, logout, responsive | PASS |
| Final live health/data/Git safety checks | PASS |
| Provider calls / sync / report mutation | 0 / 0 / 0 |

119 lượt SKIP trong toàn bộ offline suite không được tính PASS; các kiểm thử PostgreSQL/security liên quan đã chạy riêng trong DB cô lập.

## Backup và giới hạn còn lại

Backup sandbox có checksum/decryption PASS, và lần restore trên bản sao cô lập trước đó PASS. Bản backup Phase 9 nằm trên host nhưng **chưa có bản off-host**. PostgreSQL volume gốc không bị restore đè hay xóa. Nên sao lưu off-host trước các thao tác triển khai/migration tương lai.

Một container `kdh-report-new-design-preview-preview-1` ngoài phạm vi Phase 9 xuất hiện trạng thái Restarting trong lần Docker inventory cuối; không bị tác động. New 8080 vẫn healthy và nguyên cấu hình.

## Bằng chứng

- `docs/phase9-20261019/browser-e2e.json`
- `docs/phase9-20261019/final-verification.json`
- `docs/phase9-20261019/network-tests.json`
- `docs/phase9-20261019/deployment.json`
- `docs/phase9-20261019/build.json`, `smoke.json`
- `docs/phase9-20261019/preflight.json`, `runtime-recovery.json`
- `docs/phase9-20261019/screenshots/`

**PHASE 9 COMPLETE — VIO FACEBOOK CONTENT OPENED IN NEW**
