# VioAgencyAnalytics — Rebrand File Map & Audit

Ngày 23/10/2026. Chỉ hai Git root trong workspace `D:/VioAgencyAnalytics`. Đây là audit source và thay đổi local; không nghiệm thu runtime. VIO Agency phát triển, sở hữu và vận hành VioAgencyAnalytics.

## Bổ sung sau rebrand — rà soát customer-first, chỉ sửa tài liệu

**Phạm vi lượt mới:** đối chiếu code working tree và cập nhật đúng năm Markdown bên dưới. Các mục 1–6 phía sau là audit/baseline/kết quả kiểm thử của **lượt rebrand trước**, không phải những thay đổi hay test vừa thực hiện trong lượt customer-first. Không ghi đè lịch sử hoặc coi các số PASS cũ là nghiệm thu SaaS.

### Baseline của lượt customer-first

| Repository | Branch | Modified | Deleted có trước | Untracked có trước (`-uall`) | Staged |
|---|---|---:|---:|---:|---:|
| VioAgencyAnalytics-Admin | main | 26 | 7 | 284 | 0 |
| VioAgencyAnalytics-Web | main | 38 | 0 | 5 | 0 |

Cả năm tài liệu cần cập nhật đã tồn tại dưới dạng untracked trước lượt này. Không tạo lại, xóa hoặc stage chúng. Ghi baseline status và SHA-256 trong bộ nhớ phiên cho 170 file Admin, 174 file Web thuộc tập source/tài liệu an toàn; không ghi artifact baseline mới. Không đọc `.env`, secret/token/credential, `instance/`, backup/dump hoặc nội dung evidence nhạy cảm. Hash chỉ chứng minh bảo toàn trong tập đã đọc, không tuyên bố kiểm chứng byte của toàn bộ working tree.

### Sai khác đã xác nhận từ source

- Web `app/routes/viewer.py:admin_selection` chuyển login/chọn report về Admin; production chủ yếu là Published Bundle, chưa có customer onboarding/live read API tổng quát.
- Admin `kdh/app.py` yêu cầu role `admin` ở Google/Meta Connect và callback; `meta_reporting_routes.py` yêu cầu `admin` cho discovery/chọn asset/sync. Chọn asset và enqueue sync hiện là hai bước riêng.
- `Meta.__init__` gắn client cấu hình primary/sandbox, secret theo client; `_prepare` của worker kiểm tra actor `admin`. Đây chưa phải Organization/Connection context tổng quát.
- Collector, worker, Data Foundation, KPI reader, Dataset/quality, release approval, immutable Bundle/revision và Viewer grant đã có để kế thừa. Không cần xây lại toàn bộ.
- Product/Architecture/UX sau rebrand đã nói self-service nhưng sơ đồ chính còn thiên về backend → publication → Viewer, roadmap chưa chốt Facebook Content làm MVP đầu tiên. Đã bổ sung luồng customer → Web → OAuth backend → asset → auto-sync → Live Dashboard, tách khỏi Published Report.

### File map riêng cho lượt customer-first

| Repository | File được chỉnh | Điều chỉnh |
|---|---|---|
| Admin | [VIOAGENCYANALYTICS_PRODUCT_VISION.md](VIOAGENCYANALYTICS_PRODUCT_VISION.md) | Web là điểm bắt đầu; customer journey đầy đủ, VIO vận hành platform, MVP Facebook Content trước |
| Admin | [VIOAGENCYANALYTICS_ARCHITECTURE.md](VIOAGENCYANALYTICS_ARCHITECTURE.md) | Current/Target có bằng chứng code; Mermaid customer/backend/worker; ownership, permissions, token lifecycle, automated ingestion, live/report access và kế thừa services |
| Admin | [SAAS_MIGRATION_ROADMAP.md](SAAS_MIGRATION_ROADMAP.md) | Thứ tự 1–7, MVP Sign-in → Workspace → Page → Sync → Dashboard thật; gates, reconciliation, rủi ro và điều kiện chấp thuận |
| Admin | [REBRAND_FILE_MAP.md](REBRAND_FILE_MAP.md) | Thêm audit lượt tài liệu riêng, giữ nguyên file map/baseline/test rebrand lịch sử |
| Web | [CUSTOMER_WORKSPACE_UX.md](../../VioAgencyAnalytics-Web/docs/CUSTOMER_WORKSPACE_UX.md) | UX bắt đầu từ Web; consent/callback/asset/auto-sync, live không chờ duyệt, customer sharing và trạng thái lỗi |

Không sửa application code, API/routes, migration, OAuth thật, PostgreSQL, Docker/network/volume, package/repository name, tests hoặc files ngoài năm tài liệu. Không commit/push/merge/reset/stash/clean/switch branch. `AGENTS.md` và `SYSTEM_CONTEXT.md` chỉ được đọc; mô tả luồng Provider → Dataset → Bundle → Web ở đó là đường kế thừa hiện tại, không thay thế Target State trong Architecture.

**Điểm chốt thiết kế:** VIO Super Admin quản trị hệ thống, provider apps, tenants, monitoring, templates, security/audit/support và subscription tương lai; không kết nối asset hay tạo report thay khách, không mặc định đọc dữ liệu tenant. Admin Backend tự xử lý request từ Web. Giữ quality và immutable revisions; live dashboard không phụ thuộc manual publication. Dữ liệu/token/thông tin sandbox không được coi là production.

**Điều kiện tiếp tục:** người dùng thống nhất và chấp thuận kiến trúc trước triển khai SaaS; quyết định RBAC/Brand mapping, legacy ownership, identity/session, provider permissions, token/support/retention và sync/KPI acceptance theo Roadmap. Lượt này không chạy provider, Docker, database hoặc nghiệm thu runtime.

### Kiểm tra riêng cho lượt customer-first

| Kiểm tra | Kết quả và giới hạn |
|---|---|
| Phạm vi thay đổi | Chỉ 4 Markdown Admin + 1 Markdown Web thay đổi hash; không thêm/xóa file trong tập baseline |
| Bảo toàn local | 166 file Admin + 173 file Web ngoài danh sách sửa khớp SHA-256; status `--porcelain=v1 -uall` của hai repo khớp baseline, bao gồm modified/deleted/untracked và staging. Secrets/ignored/evidence ngoài tập an toàn không được đọc hoặc hash |
| Markdown | Cả năm file đọc UTF-8 đúng, không ký tự thay thế, không trailing whitespace; các liên kết Markdown local tồn tại, code fences cân bằng |
| Mermaid | 6 khối gồm flowchart, sequence và ER; kiểm tra cấu trúc/hướng luồng trong source. Chưa render bằng Mermaid engine; không cài dependency mới |
| `git diff --check` | PASS cả hai repository; Admin có cảnh báo LF/CRLF ở file có thay đổi trước task. Vì năm tài liệu đang untracked, kiểm tra whitespace trực tiếp trên cả năm file bổ sung cho Git |
| Tests ứng dụng / runtime | NOT RUN: chỉ sửa tài liệu; không chạy app, provider, PostgreSQL, Docker hoặc browser E2E. Các số PASS ở mục 5 bên dưới thuộc lượt rebrand trước |

## 1. Baseline trước khi sửa

| Repository local | Branch | HEAD | Modified | Deleted có trước | Untracked có trước | Staged |
|---|---|---|---:|---:|---:|---:|
| `D:/VioAgencyAnalytics/VioAgencyAnalytics-Admin` | main | `6b52ee2f3ef29ebb5820e95e88ba318a7599667d` | 17 | 7 | 280 | 0 |
| `D:/VioAgencyAnalytics/VioAgencyAnalytics-Web` | main | `1e3df3c7f4a93576ad2599ceee99c1958e7cc636` | 17 | 0 | 3 | 0 |

Cả hai working tree không sạch từ đầu. Bảy file Admin bị xóa ở root và các bản cùng tên untracked trong `docs/` là trạng thái có trước, không phải thao tác rename/delete của rebrand. Không stage/commit/push/pull/merge/reset/stash/clean/switch hoặc tạo/sửa worktree.

Remote local vẫn là `https://github.com/kdh-report-team/KDH-Report-Admin.git` và `https://github.com/kdh-report-team/KDH-Report-New.git`. Theo chỉ dẫn người dùng, repository GitHub đã mang tên VioAgencyAnalytics; task này không kiểm tra GitHub/network và không đổi remote/organization/repository name.

Đã đọc `VioAgencyAnalytics-Admin/AGENTS.md`. Web không có AGENTS.md trong Git root đã kiểm tra. Các thư mục sibling `KDH-Report-New-VIO`, `docker-cleanup-20261020` không thuộc phạm vi; không đọc/sửa nội dung.

### Worktree đăng ký (chỉ đọc metadata)

**VioAgencyAnalytics-Admin**

```text
worktree D:/VioAgencyAnalytics/VioAgencyAnalytics-Admin
HEAD 6b52ee2f3ef29ebb5820e95e88ba318a7599667d
branch refs/heads/main

worktree C:/Users/Admin/orca/workspaces/.orca-preparing/19412-62c9eacf-69ac-4111-b7ef-f62e20b7af3d
HEAD 6b52ee2f3ef29ebb5820e95e88ba318a7599667d
detached
locked orca-create-preparation:v1:19412:19412-62c9eacf-69ac-4111-b7ef-f62e20b7af3d:machine=win32-machine-guid:23f4a070-aab9-4845-8864-a8a1ba07dd32
```

**VioAgencyAnalytics-Web**

```text
worktree D:/VioAgencyAnalytics/VioAgencyAnalytics-Web
HEAD 1e3df3c7f4a93576ad2599ceee99c1958e7cc636
branch refs/heads/main

worktree C:/Users/Admin/orca/workspaces/KDH-Report-New/codex-review-new
HEAD e5c23af79a458978682e0c3e3d307307ef125e76
branch refs/heads/bac2908/codex-review-new

worktree D:/KDH-Report-All/KDH-Report-New-VIO-Phase9
HEAD 56a51a015b465323d862394dcbeb8b4e250f2845
branch refs/heads/feat/vio-handoff-phase9
prunable gitdir file points to non-existent location
```

Worktree detached/locked của Orca và worktree review ngoài workspace không được mở hay sửa. Entry `D:/KDH-Report-All/KDH-Report-New-VIO-Phase9` được Git đánh dấu prunable vì gitdir không còn tại vị trí đăng ký; không prune/repair. Metadata này không chứng minh thư mục sandbox hoặc dữ liệu cần xóa.

### Phương pháp đếm và vùng loại trừ

Trước khi sửa, quét text an toàn trong file tracked và untracked của hai root (source, templates, JS/CSS, Markdown, tests/fixtures, manifest/config mẫu), ghi SHA-256 cho 219 file Admin và 195 file Web. Có **170 file Admin / 65 file Web** chứa ít nhất một chuỗi KDH hoặc KinderHealth không phân biệt hoa thường. Đây là số file có tên cũ gồm cả identifier, fixture và lịch sử, **không phải số file cần đổi thương hiệu**. Logo raster Web còn chữ KDH được kiểm tra hình ảnh riêng, không nằm trong số text này.

Không đọc nội dung `.env` thật, `instance/`, encryption keys, credential/token, backup/dump, ignored dependencies/cache hoặc evidence JSON cấu hình nhạy cảm. Các file có tên liên quan secret/token/credential/config-before/startup-manifest và JSON/YAML evidence dưới docs được loại khỏi content scan. Chỉ ghi nhận tên của những file đó qua Git metadata; không suy ra chúng không chứa thông tin quan trọng. Vì vậy số đếm không phải thống kê byte toàn bộ máy/ignored artifacts.

Baseline đầy đủ modified/deleted/untracked và ignored nằm ở phụ lục. Những file không chỉnh trong tập SHA-256 sẽ được đối chiếu lại khi bàn giao. File dirty được sửa chỉ ở phần branding/docs riêng; không coi toàn bộ git diff từ HEAD là thay đổi của task này.

## 2. Phát hiện và phân loại

| Nhóm | Phát hiện | Xử lý / kiểm thử |
|---|---|---|
| Branding/UI text | Title/login/sidebar/footer, tên ứng dụng FastAPI, thông báo kết nối, logo Web chứa KDH | MODIFY theo từng chuỗi; dùng biểu tượng chart có sẵn của Admin, giữ logo cũ; UI/route/render, syntax, CSS build. |
| Tài liệu hiện hành | README Admin nói Meta chỉ OAuth; README Web mô tả service app/network cũ; AGENTS single-client không phản ánh sandbox | Sửa README/AGENTS, thêm mốc mới SYSTEM_CONTEXT và chú thích DATABASE_ARCHITECTURE; giữ lịch sử bên dưới. |
| Tài liệu lịch sử | KDH_*.md, Phase 9, audit UX và bằng chứng 21–22/10 có mốc runtime khác nhau | KEEP, không sửa số liệu/kết quả/đường dẫn bằng chứng. |
| Tên package/module | Python `kdh/`, `run.py`, package import; npm packages private phục vụ tests/styles | Giữ Python; đổi metadata npm đồng bộ lock, kiểm tra dependencies không đổi. |
| API/database contract | `X-KDH-Request`, `X-KDH-Viewer-Session`, health service IDs, cookie/realm, report keys, client IDs, export filenames/CSV headers | KEEP hoặc DEFER đổi tên, không đổi auth/CSRF, payload hay consumer contract. |
| Docker/Compose/network | Admin project kdh-report-admin; Web include shared, relays/IP, external networks, image pinning | DEFER migration đồng bộ; không chạy Docker hoặc compose config có thể resolve secrets. |
| Runtime configuration | Callback Google/Meta, public/internal URL, cookie namespace, mount /legacy và .work/layout-preview | Giữ nguyên giá trị/cấu hình thực; chỉ đổi APP_NAME mẫu Web và comment mẫu Admin. |
| Data migration | Chưa có SaaS Organization/membership schema tổng quát; existing client scopes không phải tenant production | Chỉ thiết kế migration trong Architecture/Roadmap; không chạy app production/migrations hoặc SQL. |
| Test/fixture | Fixtures KinderHealth/VIO, header/cookie assertion, định dạng export cũ | KEEP. Không assertion thương hiệu cũ nào buộc đổi; tests chạy offline với DB tạm/MockTransport. |
| File chưa rõ nguồn gốc | Admin `t`; ignored `kdh/meta.py.bak`; nhiều untracked/evidence | KEEP. Không đọc backup hoặc xóa; chưa đủ bằng chứng xác nhận không dùng. |

### Phụ thuộc triển khai phải xử lý riêng

- Admin `compose.yaml`: project `kdh-report-admin`, services `admin/postgres`, DB `kdh_report`, user `kdh`, volumes `admin-data/postgres-data`, static Admin IP, `LEGACY_REPORT_DIR` và `KDH_DEMO_PACK_DIR` mounts. Default network `kdh-report-admin_default` vẫn là tên kỹ thuật.
- Web `compose.yaml` include `compose.shared.yaml`: service `new`, container `kdh-report-new-app-1`, image pin `kdh-new:insights-chart-20261022-fed378fa5436`; relay endpoints/IP và host-only origins primary/VIO. Networks `kdh-vio-host-phase9-20261019`, `kdh-shared-viewer-primary-20261021`, `kdh-vio-handoff-phase9-recovery-20261019`. Chúng không phải tenant IDs.
- `compose.mock.yaml` là mock riêng; `compose.preview.yaml` và `compose.design-preview.yaml` **không tồn tại trong Web root này**. Không thêm hoặc liệt kê chúng như file đã sửa.
- Google `/api/google/callback`, Meta `/api/meta/callback`, Viewer handoff/state/PKCE/origin và internal service+viewer session giữ nguyên. Migration hostname cần redirect allowlist/provider registration và test đồng bộ riêng.
- Đường dẫn legacy `D:/KDH-Report/KDH-Report`, các đường dẫn `D:/KDH-Report-All/...` trong script/evidence, sibling `KDH-Report-New` trong `ops/unify_primary.py` không được tự sửa. Một số script không còn phù hợp vị trí checkout hiện tại; không chạy lại để thử branding.
- Web `.env.example` có biến provider dành cho script chẩn đoán cũ: chỉ thêm chú thích, không yêu cầu customer điền secrets và không đưa chúng vào Web runtime. Tách tooling/config cần task riêng.

### Bằng chứng chức năng

Đối chiếu source cho thấy Google SEO/Meta adapters, sync, stored Dataset, review/approval/publication và Viewer renderer đã hiện diện. Phase 9 chứng minh VIO Facebook Content provisional trong sandbox ở ngày nghiệm thu. Ghi nhận 22/10 mô tả Insights và shared Viewer; không phải kiểm tra runtime mới. TikTok là planned; YouTube/Google Ads/Instagram/CRM không được xác nhận tích hợp production chỉ từ catalog/mock/script. Xem ma trận source và giới hạn trong [Architecture](VIOAGENCYANALYTICS_ARCHITECTURE.md).

## 3. File Change Map — thay đổi của task này

Đường dẫn tương đối với Git root ở cột Repository. Mọi hàng MODIFY/ADD dưới đây là file thực tồn tại sau thay đổi. Không rename, không delete, không DELETE CANDIDATE đủ bằng chứng. RENAME = 0; DELETE CANDIDATE = 0; DELETE = 0. Các rename có nguy cơ đều DEFER ở phần 4.

| Repository | File | Action | Lý do | Đã xử lý? | Dependencies | Rủi ro | Bước kiểm thử |
|---|---|---|---|---|---|---|---|
| VioAgencyAnalytics-Admin | `.env.example` | MODIFY | Chỉ nhãn/comment mẫu; không sửa .env thật | Có | Tên biến và giá trị security giữ nguyên | Thấp | Diff hẹp, config tests |
| VioAgencyAnalytics-Admin | `AGENTS.md` | MODIFY | Định hướng hiện hành, ownership VIO; sửa mô tả đã lỗi thời, giữ mốc lịch sử | Có | Implementation + Product/Architecture/Roadmap | Thấp | Review đối chiếu source, liên kết local |
| VioAgencyAnalytics-Admin | `README.md` | MODIFY | Định hướng hiện hành, ownership VIO; sửa mô tả đã lỗi thời, giữ mốc lịch sử | Có | Implementation + Product/Architecture/Roadmap | Thấp | Review đối chiếu source, liên kết local |
| VioAgencyAnalytics-Admin | `docs/DATABASE_ARCHITECTURE.md` | MODIFY | Định hướng hiện hành, ownership VIO; sửa mô tả đã lỗi thời, giữ mốc lịch sử | Có | Implementation + Product/Architecture/Roadmap | Thấp | Review đối chiếu source, liên kết local |
| VioAgencyAnalytics-Admin | `docs/SYSTEM_CONTEXT.md` | MODIFY | Định hướng hiện hành, ownership VIO; sửa mô tả đã lỗi thời, giữ mốc lịch sử | Có | Implementation + Product/Architecture/Roadmap | Thấp | Review đối chiếu source, liên kết local |
| VioAgencyAnalytics-Admin | `package-lock.json` | MODIFY | Metadata npm private, không nâng dependency | Có | package.json ↔ package-lock.json | Thấp | So sánh lock trước/sau trừ hai name |
| VioAgencyAnalytics-Admin | `package.json` | MODIFY | Metadata npm private, không nâng dependency | Có | package.json ↔ package-lock.json | Thấp | So sánh lock trước/sau trừ hai name |
| VioAgencyAnalytics-Admin | `static/admin-refinement.css` | MODIFY | Cho tên sản phẩm dài xuống dòng; comment branding hoặc CSS build tương ứng | Có | Templates + CSS source; dist sinh bởi build | Thấp | CSS build, đối chiếu generated diff |
| VioAgencyAnalytics-Admin | `static/app.js` | MODIFY | Tên sản phẩm/ownership và nhãn mẫu; giữ client/data/revision | Có | Template/JS renderer; SVG chung | Thấp | Admin UI hoặc Web pytest, JS syntax, kiểm tra branding |
| VioAgencyAnalytics-Admin | `static/marketing.js` | MODIFY | Tên sản phẩm/ownership và nhãn mẫu; giữ client/data/revision | Có | Template/JS renderer; SVG chung | Thấp | Admin UI hoặc Web pytest, JS syntax, kiểm tra branding |
| VioAgencyAnalytics-Admin | `static/style.css` | MODIFY | Cho tên sản phẩm dài xuống dòng; comment branding hoặc CSS build tương ứng | Có | Templates + CSS source; dist sinh bởi build | Thấp | CSS build, đối chiếu generated diff |
| VioAgencyAnalytics-Admin | `static/views.js` | MODIFY | Tên sản phẩm/ownership và nhãn mẫu; giữ client/data/revision | Có | Template/JS renderer; SVG chung | Thấp | Admin UI hoặc Web pytest, JS syntax, kiểm tra branding |
| VioAgencyAnalytics-Admin | `templates/index.html` | MODIFY | Tên sản phẩm/ownership và nhãn mẫu; giữ client/data/revision | Có | Template/JS renderer; SVG chung | Thấp | Admin UI hoặc Web pytest, JS syntax, kiểm tra branding |
| VioAgencyAnalytics-Admin | `templates/marketing.html` | MODIFY | Tên sản phẩm/ownership và nhãn mẫu; giữ client/data/revision | Có | Template/JS renderer; SVG chung | Thấp | Admin UI hoặc Web pytest, JS syntax, kiểm tra branding |
| VioAgencyAnalytics-Admin | `docs/SAAS_MIGRATION_ROADMAP.md` | ADD | Tài liệu mới chuyên biệt cho định hướng SaaS/UX/audit; chưa có tài liệu tương đương | Có | Architecture + source audit | Thấp | Kiểm tra link/nội dung; asset path nếu SVG |
| VioAgencyAnalytics-Admin | `docs/VIOAGENCYANALYTICS_ARCHITECTURE.md` | ADD | Tài liệu mới chuyên biệt cho định hướng SaaS/UX/audit; chưa có tài liệu tương đương | Có | Architecture + source audit | Thấp | Kiểm tra link/nội dung; asset path nếu SVG |
| VioAgencyAnalytics-Admin | `docs/VIOAGENCYANALYTICS_PRODUCT_VISION.md` | ADD | Tài liệu mới chuyên biệt cho định hướng SaaS/UX/audit; chưa có tài liệu tương đương | Có | Architecture + source audit | Thấp | Kiểm tra link/nội dung; asset path nếu SVG |
| VioAgencyAnalytics-Admin | `docs/REBRAND_FILE_MAP.md` | ADD | Tài liệu mới chuyên biệt cho định hướng SaaS/UX/audit; chưa có tài liệu tương đương | Có | Architecture + source audit | Thấp | Kiểm tra link/nội dung; asset path nếu SVG |
| VioAgencyAnalytics-Web | `.env.example` | MODIFY | Chỉ nhãn/comment mẫu; không sửa .env thật | Có | Tên biến và giá trị security giữ nguyên | Thấp | Diff hẹp, config tests |
| VioAgencyAnalytics-Web | `README.md` | MODIFY | Định hướng hiện hành, ownership VIO; sửa mô tả đã lỗi thời, giữ mốc lịch sử | Có | Implementation + Product/Architecture/Roadmap | Thấp | Review đối chiếu source, liên kết local |
| VioAgencyAnalytics-Web | `app/__init__.py` | MODIFY | Tên hiển thị/metadata/comment/thông báo; không đổi route/key/guard | Có | FastAPI settings/render/repository | Thấp | AST + pytest routes/Bundle |
| VioAgencyAnalytics-Web | `app/config.py` | MODIFY | Tên hiển thị/metadata/comment/thông báo; không đổi route/key/guard | Có | FastAPI settings/render/repository | Thấp | AST + pytest routes/Bundle |
| VioAgencyAnalytics-Web | `app/design_preview.py` | MODIFY | Tên hiển thị/metadata/comment/thông báo; không đổi route/key/guard | Có | FastAPI settings/render/repository | Thấp | AST + pytest routes/Bundle |
| VioAgencyAnalytics-Web | `app/repositories/admin_bundle.py` | MODIFY | Tên hiển thị/metadata/comment/thông báo; không đổi route/key/guard | Có | FastAPI settings/render/repository | Thấp | AST + pytest routes/Bundle |
| VioAgencyAnalytics-Web | `main.py` | MODIFY | Tên hiển thị/metadata/comment/thông báo; không đổi route/key/guard | Có | FastAPI settings/render/repository | Thấp | AST + pytest routes/Bundle |
| VioAgencyAnalytics-Web | `package-lock.json` | MODIFY | Metadata npm private, không nâng dependency | Có | package.json ↔ package-lock.json | Thấp | So sánh lock trước/sau trừ hai name |
| VioAgencyAnalytics-Web | `package.json` | MODIFY | Metadata npm private, không nâng dependency | Có | package.json ↔ package-lock.json | Thấp | So sánh lock trước/sau trừ hai name |
| VioAgencyAnalytics-Web | `static/css/dist/dashboard.css` | MODIFY | Cho tên sản phẩm dài xuống dòng; comment branding hoặc CSS build tương ứng | Có | Templates + CSS source; dist sinh bởi build | Thấp | CSS build, đối chiếu generated diff |
| VioAgencyAnalytics-Web | `static/css/shared/dashboard.source.css` | MODIFY | Cho tên sản phẩm dài xuống dòng; comment branding hoặc CSS build tương ứng | Có | Templates + CSS source; dist sinh bởi build | Thấp | CSS build, đối chiếu generated diff |
| VioAgencyAnalytics-Web | `static/js/pages/seo.js` | MODIFY | Tên sản phẩm/ownership và nhãn mẫu; giữ client/data/revision | Có | Template/JS renderer; SVG chung | Thấp | Admin UI hoặc Web pytest, JS syntax, kiểm tra branding |
| VioAgencyAnalytics-Web | `templates/components/dashboard/header.html` | MODIFY | Tên sản phẩm/ownership và nhãn mẫu; giữ client/data/revision | Có | Template/JS renderer; SVG chung | Thấp | Admin UI hoặc Web pytest, JS syntax, kiểm tra branding |
| VioAgencyAnalytics-Web | `templates/components/dashboard/sidebar.html` | MODIFY | Tên sản phẩm/ownership và nhãn mẫu; giữ client/data/revision | Có | Template/JS renderer; SVG chung | Thấp | Admin UI hoặc Web pytest, JS syntax, kiểm tra branding |
| VioAgencyAnalytics-Web | `templates/layouts/basic.html` | MODIFY | Tên sản phẩm/ownership và nhãn mẫu; giữ client/data/revision | Có | Template/JS renderer; SVG chung | Thấp | Admin UI hoặc Web pytest, JS syntax, kiểm tra branding |
| VioAgencyAnalytics-Web | `templates/layouts/dashboard.html` | MODIFY | Tên sản phẩm/ownership và nhãn mẫu; giữ client/data/revision | Có | Template/JS renderer; SVG chung | Thấp | Admin UI hoặc Web pytest, JS syntax, kiểm tra branding |
| VioAgencyAnalytics-Web | `templates/pages/demo_bundle.html` | MODIFY | Tên sản phẩm/ownership và nhãn mẫu; giữ client/data/revision | Có | Template/JS renderer; SVG chung | Thấp | Admin UI hoặc Web pytest, JS syntax, kiểm tra branding |
| VioAgencyAnalytics-Web | `templates/pages/facebook_content/partials/bundle.html` | MODIFY | Tên sản phẩm/ownership và nhãn mẫu; giữ client/data/revision | Có | Template/JS renderer; SVG chung | Thấp | Admin UI hoặc Web pytest, JS syntax, kiểm tra branding |
| VioAgencyAnalytics-Web | `templates/pages/facebook_content/partials/insights.html` | MODIFY | Tên sản phẩm/ownership và nhãn mẫu; giữ client/data/revision | Có | Template/JS renderer; SVG chung | Thấp | Admin UI hoặc Web pytest, JS syntax, kiểm tra branding |
| VioAgencyAnalytics-Web | `templates/pages/overview/partials/footer.html` | MODIFY | Tên sản phẩm/ownership và nhãn mẫu; giữ client/data/revision | Có | Template/JS renderer; SVG chung | Thấp | Admin UI hoặc Web pytest, JS syntax, kiểm tra branding |
| VioAgencyAnalytics-Web | `templates/pages/published/index.html` | MODIFY | Tên sản phẩm/ownership và nhãn mẫu; giữ client/data/revision | Có | Template/JS renderer; SVG chung | Thấp | Admin UI hoặc Web pytest, JS syntax, kiểm tra branding |
| VioAgencyAnalytics-Web | `templates/pages/seo/partials/details.html` | MODIFY | Tên sản phẩm/ownership và nhãn mẫu; giữ client/data/revision | Có | Template/JS renderer; SVG chung | Thấp | Admin UI hoặc Web pytest, JS syntax, kiểm tra branding |
| VioAgencyAnalytics-Web | `docs/CUSTOMER_WORKSPACE_UX.md` | ADD | Tài liệu mới chuyên biệt cho định hướng SaaS/UX/audit; chưa có tài liệu tương đương | Có | Architecture + source audit | Thấp | Kiểm tra link/nội dung; asset path nếu SVG |
| VioAgencyAnalytics-Web | `static/img/analytics-mark.svg` | ADD | Tái sử dụng nguyên biểu tượng chart của Admin; không sửa logo lịch sử | Có | Architecture + source audit | Thấp | Kiểm tra link/nội dung; asset path nếu SVG |

Tài liệu `KDH_ARCHITECTURE.md` (mốc 10/10), `KDH_PROVIDER_STATUS.md`, contracts và handover được giữ để không viết lại bằng chứng lịch sử. Các tài liệu mới tập trung product/target architecture/roadmap/UX; không sao chép toàn bộ API contract. README và AGENTS liên kết chúng. `docs/README.md` là file untracked có trước task nên giữ nguyên; entrypoint README tracked đã bổ sung các link cần thiết.

## 4. KEEP / DEFER — inventory text có tham chiếu và file được yêu cầu kiểm tra

Mỗi hàng dưới đây có path thực (file có trước audit). Lý do phân loại có thể áp dụng nhiều nhóm; chi tiết exception ở phần 2. KEEP không có nghĩa tính năng đã được nghiệm thu; DEFER không cấp phép đổi runtime.

| Repository | File | Action | Lý do | Dependencies | Rủi ro nếu đổi | Bước kiểm thử ở task sau |
|---|---|---|---|---|---|---|
| VioAgencyAnalytics-Admin | `Dockerfile` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `Start-KDH.cmd` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `compose.primary-viewer.yaml` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `compose.yaml` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `demo.cmd` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `docs/ADMIN_NEW_HANDOFF.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/ADMIN_UI_REFINEMENT_20261019.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/DEPLOY_DOCKER.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/FACEBOOK_CONTENT_INSIGHTS_20261021.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/FACEBOOK_CONTENT_REQUIREMENTS_20261021.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/KDH_ADMIN_UX_WORKFLOW_AUDIT_20261019.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/KDH_API_INTEGRATION.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/KDH_ARCHITECTURE.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/KDH_DEPLOYMENT_GUIDE.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/KDH_FACEBOOK_REPORTS_HANDOFF.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/KDH_HANDOVER.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/KDH_PHASE4_POSTGRES_ACCEPTANCE.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/KDH_PHASE5B_SANDBOX_DEPLOYMENT_RESULT.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/KDH_PHASE5_SANDBOX_DEPLOYMENT_PLAN.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/KDH_PHASE9_IMPLEMENTATION_RESULT.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/KDH_PRIMARY_UNIFICATION_RESULT.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/KDH_PROVIDER_STATUS.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/KDH_TEST_RESULTS.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/MULTIPLATFORM_SANDBOX_DEPLOYMENT_20261019.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/PLATFORM_UI_POLISH_20261019.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/README.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/TIKTOK_ADS_SCAFFOLD.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/content-insights-deploy-20261021/README.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/content-polish-20261021/RESULT.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/content-shell-20261021/RESULT.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/insights-chart-20261022/README.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/marketing-remaining-implementation.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/meta-oauth.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/origin-fix-20261021/RESULT.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/phase5-20261018/build_after_approval.py` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/phase5-20261018/cold_backup.py` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/phase5-20261018/create_admin_after_approval.py` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/phase5-20261018/final_integrity.py` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/phase5-20261018/prepare_evidence.py` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/phase5-20261018/restore_copy.py` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/phase5-20261018/verify_restored_period.py` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/phase5b-20261018/create_admin_after_approval.py` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/phase5b-20261018/deploy_admin.py` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/phase5b-20261018/final_checks.py` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/phase5b-20261018/preflight.py` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/phase5b-20261018/runtime_common.py` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/phase5b-20261018/smoke_image.py` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/phase5b-20261018/verify_http.py` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/phase9-20261019/browser_e2e.py` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/phase9-20261019/operations.py` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/phase9-20261019/verify_final.py` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/report-bundles.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/shared-viewer-20261021/RESULT.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/tonight-delivery-20261021/README.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/tonight-delivery-20261021/browser_fixture.py` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/tonight-delivery-20261021/run_offline.py` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/ui-deployment-20261019/brand_polish_deploy.py` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/ui-deployment-20261019/deploy_ui.py` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/ui-deployment-20261019/multiplatform_deploy.py` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/ui-deployment-20261019/smoke_ui.py` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/vio-handoff-recovery-20261022/README.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `docs/vio-insights-live-20261022/README.md` | KEEP | Contract, tài liệu có ngày/bằng chứng hoặc local untracked cần bảo toàn | Handover/history/source | Vừa | Đối chiếu mốc thời gian; không sửa evidence |
| VioAgencyAnalytics-Admin | `kdh/__init__.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `kdh/app.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `kdh/core.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `kdh/demo.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `kdh/google.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `kdh/jobs.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `kdh/manual_load_pack.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `kdh/marketing_console.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `kdh/marketing_release.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `kdh/marketing_review.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `kdh/meta.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `kdh/meta.py.bak` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `kdh/meta_diagnostics.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `kdh/meta_reporting_routes.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `kdh/metric_calculator.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `kdh/metric_catalog.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `kdh/metric_reader.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `kdh/migrations.py` | KEEP | Migration/data contract, không rewrite lịch sử | PostgreSQL/SQLite + snapshots/grants | Cao | Dry-run/restore/hash trên bản sao ở task migration |
| VioAgencyAnalytics-Admin | `kdh/platform_data.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `kdh/platform_dataset.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `kdh/platform_registry.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `kdh/report_bundles.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `kdh/reports.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `kdh/viewer_access.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `kdh/viewer_handoff.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `ops/check_content_insights_deploy.py` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `ops/check_content_polish.py` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `ops/check_content_shell.py` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `ops/check_insights_chart_20261022.py` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `ops/check_sandbox_origin.py` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `ops/check_shared_viewer.py` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `ops/check_tonight_content.py` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `ops/deploy_content_insights.py` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `ops/deploy_content_shell.py` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `ops/deploy_tonight_content.py` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `ops/fix_sandbox_origin.py` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `ops/shared_viewer.py` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `ops/unify_primary.py` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `ops/vio_content_prepare_20261022.py` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `ops/vio_content_preview_qa_20261022.py` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `ops/vio_content_retry_20261022.py` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `ops/vio_content_sync_20261022.py` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `ops/vio_content_verify_20261022.py` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `ops/vio_insights_diagnostic_20261022.py` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `run.py` | KEEP | Entrypoint được yêu cầu giữ; CLI banner KDH hoãn cùng tooling | Launcher + worker | Vừa | CLI/offline regression trước đổi riêng |
| VioAgencyAnalytics-Admin | `start.ps1` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Admin | `static/admin-shell.css` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Admin | `static/api.js` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Admin | `static/marketing.css` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Admin | `static/ui.js` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Admin | `stitch_kdh_report_admin_frontend/b_o_c_o_l_u_kdh_report_admin_1/code.html` | KEEP | Tham chiếu thiết kế có tên cũ | UI/design evidence | Thấp | Kiểm tra tham chiếu trước thay đổi riêng |
| VioAgencyAnalytics-Admin | `stitch_kdh_report_admin_frontend/b_o_c_o_l_u_kdh_report_admin_2/code.html` | KEEP | Tham chiếu thiết kế có tên cũ | UI/design evidence | Thấp | Kiểm tra tham chiếu trước thay đổi riêng |
| VioAgencyAnalytics-Admin | `stitch_kdh_report_admin_frontend/k_t_n_i_google_kdh_report_admin_1/code.html` | KEEP | Tham chiếu thiết kế có tên cũ | UI/design evidence | Thấp | Kiểm tra tham chiếu trước thay đổi riêng |
| VioAgencyAnalytics-Admin | `stitch_kdh_report_admin_frontend/k_t_n_i_google_kdh_report_admin_2/code.html` | KEEP | Tham chiếu thiết kế có tên cũ | UI/design evidence | Thấp | Kiểm tra tham chiếu trước thay đổi riêng |
| VioAgencyAnalytics-Admin | `stitch_kdh_report_admin_frontend/kinderhealth_report_admin_logo/code.html` | KEEP | Tham chiếu thiết kế có tên cũ | UI/design evidence | Thấp | Kiểm tra tham chiếu trước thay đổi riêng |
| VioAgencyAnalytics-Admin | `stitch_kdh_report_admin_frontend/ph_n_t_ch_xu_t_excel_kdh_report_admin_1/code.html` | KEEP | Tham chiếu thiết kế có tên cũ | UI/design evidence | Thấp | Kiểm tra tham chiếu trước thay đổi riêng |
| VioAgencyAnalytics-Admin | `stitch_kdh_report_admin_frontend/ph_n_t_ch_xu_t_excel_kdh_report_admin_2/code.html` | KEEP | Tham chiếu thiết kế có tên cũ | UI/design evidence | Thấp | Kiểm tra tham chiếu trước thay đổi riêng |
| VioAgencyAnalytics-Admin | `stitch_kdh_report_admin_frontend/t_ng_quan_kdh_report_admin_1/code.html` | KEEP | Tham chiếu thiết kế có tên cũ | UI/design evidence | Thấp | Kiểm tra tham chiếu trước thay đổi riêng |
| VioAgencyAnalytics-Admin | `stitch_kdh_report_admin_frontend/t_ng_quan_kdh_report_admin_2/code.html` | KEEP | Tham chiếu thiết kế có tên cũ | UI/design evidence | Thấp | Kiểm tra tham chiếu trước thay đổi riêng |
| VioAgencyAnalytics-Admin | `t` | KEEP | Nguồn gốc/chức năng chưa xác định đầy đủ; không có bằng chứng để xóa | Local user/rollback chưa xác định | Cao | Xác minh nguồn gốc trước mọi đề xuất xóa |
| VioAgencyAnalytics-Admin | `templates/report.html` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Admin | `tests/admin_refinement.browser.cjs` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/http_smoke.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/marketing.browser.cjs` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/run_http_smoke.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/run_marketing_e2e.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/run_postgres_acceptance.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/serve_ui.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_app.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_demo.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_evidence_engine.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_facebook_bundles.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_facebook_bundles_postgres.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_facebook_content_report.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_google_platform_success.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_keyword_tiers.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_loopback_entry.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_marketing_dataset.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_marketing_preview.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_marketing_publication.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_marketing_publish_guard.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_marketing_release.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_marketing_review.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_marketing_sandbox_scope.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_marketing_verification.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_meta.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_meta_content_insights.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_meta_diagnostics.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_meta_oauth_diagnostics.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_meta_reporting.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_meta_reporting_routes.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_meta_worker_integration.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_metric_calculator.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_metric_catalog.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_metric_reader.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_metric_routes.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_opportunity_engine.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_platform_data.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_platform_registry.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_postgres.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_report_bundles.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_runtime.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_seo_composite.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_seo_composite_integration.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_seo_composite_loader.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_session_cookie.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_viewer_access.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_viewer_handoff.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/test_vio_handoff.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Admin | `tests/ui.test.js` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Web | `alembic.ini` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Web | `app/integrations/mock/facebook_content.py` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Web | `app/integrations/mock/overview.py` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Web | `app/integrations/mock/video.py` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Web | `app/mappers/dashboard.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Web | `app/repositories/viewer.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Web | `app/routes/demo_bundle.py` | DEFER | Export header/filename, service identifier hoặc đường chạy legacy còn consumer | API/CSV/JS consumers + fixtures | Vừa | Consumer inventory và compatibility tests |
| VioAgencyAnalytics-Web | `app/routes/health.py` | DEFER | Export header/filename, service identifier hoặc đường chạy legacy còn consumer | API/CSV/JS consumers + fixtures | Vừa | Consumer inventory và compatibility tests |
| VioAgencyAnalytics-Web | `app/routes/published.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Web | `app/routes/reports.py` | DEFER | Export header/filename, service identifier hoặc đường chạy legacy còn consumer | API/CSV/JS consumers + fixtures | Vừa | Consumer inventory và compatibility tests |
| VioAgencyAnalytics-Web | `app/routes/video.py` | DEFER | Export header/filename, service identifier hoặc đường chạy legacy còn consumer | API/CSV/JS consumers + fixtures | Vừa | Consumer inventory và compatibility tests |
| VioAgencyAnalytics-Web | `app/routes/viewer.py` | KEEP | Package/client/DB/API/security hoặc tương thích dữ liệu | Imports + callers + grants/revision | Cao | Offline contract/authorization + tenant negative tests khi đổi |
| VioAgencyAnalytics-Web | `compose.mock.yaml` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Web | `compose.shared.yaml` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Web | `compose.yaml` | DEFER | Deployment/launcher/mount/đường dẫn và topology đang có | Cả hai repo + cấu hình riêng | Cao | Migration đồng bộ, isolation, backup/rollback |
| VioAgencyAnalytics-Web | `scripts/real_data_tests/CRM_BOOKING_CHECKLIST.md` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Web | `scripts/real_data_tests/README.md` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Web | `scripts/real_data_tests/run_all.py` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Web | `scripts/real_data_tests/test_meta_ad_accounts.py` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Web | `scripts/real_data_tests/test_meta_ads.py` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Web | `static/css/pages/facebook-content.css` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Web | `static/img/kdh-logo.png` | KEEP | Asset thương hiệu cũ giữ phục vụ lịch sử/rollback; UI dùng chart chung | HTML cũ/export/reference | Thấp | Inventory mọi consumer, chưa đủ điều kiện xóa |
| VioAgencyAnalytics-Web | `static/js/pages/facebook-ads.js` | DEFER | Export header/filename, service identifier hoặc đường chạy legacy còn consumer | API/CSV/JS consumers + fixtures | Vừa | Consumer inventory và compatibility tests |
| VioAgencyAnalytics-Web | `static/js/pages/facebook-content.js` | DEFER | Export header/filename, service identifier hoặc đường chạy legacy còn consumer | API/CSV/JS consumers + fixtures | Vừa | Consumer inventory và compatibility tests |
| VioAgencyAnalytics-Web | `static/js/pages/overview.js` | DEFER | Export header/filename, service identifier hoặc đường chạy legacy còn consumer | API/CSV/JS consumers + fixtures | Vừa | Consumer inventory và compatibility tests |
| VioAgencyAnalytics-Web | `static/js/pages/video.js` | DEFER | Export header/filename, service identifier hoặc đường chạy legacy còn consumer | API/CSV/JS consumers + fixtures | Vừa | Consumer inventory và compatibility tests |
| VioAgencyAnalytics-Web | `templates/components/dashboard/controls.html` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Web | `templates/components/dashboard/navigation.html` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Web | `templates/pages/facebook_ads/index.html` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Web | `templates/pages/facebook_content/index.html` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Web | `templates/pages/overview/partials/action_plan.html` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Web | `templates/pages/overview/partials/executive_summary.html` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Web | `templates/pages/seo/partials/funnel.html` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Web | `templates/pages/seo/partials/result.html` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Web | `templates/pages/tiktok/index.html` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Web | `templates/pages/video/partials/funnel.html` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Web | `templates/pages/youtube/index.html` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Web | `templates/pages/youtube/partials/insights.html` | KEEP | Nội dung Client/demo, comment kỹ thuật hoặc không có branding cần đổi | UI/data/reference hiện có | Thấp | Offline renderer và kiểm tra diff nếu cần đổi |
| VioAgencyAnalytics-Web | `tests/fixtures/facebook_content_insights_v1.json` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Web | `tests/fixtures/facebook_content_report_v1.json` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Web | `tests/fixtures/facebook_content_vio.json` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Web | `tests/test_admin_bundle_repository.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Web | `tests/test_content_insights_contract.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Web | `tests/test_content_report_contract.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Web | `tests/test_executive_ui.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Web | `tests/test_handoff.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Web | `tests/test_seo.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Web | `tests/test_shared_viewer.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Web | `tests/test_viewer.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |
| VioAgencyAnalytics-Web | `tests/test_vio_content.py` | KEEP | Fixture/assertion/QA dùng identifier và dữ liệu cũ | Test suite + renderer/contracts | Vừa | Chạy offline; không Replace All |

## 5. Kiểm thử và giới hạn bàn giao

Không dùng runtime production, provider thật hoặc Docker để kiểm thử branding. Các phép thử SQLite chỉ dùng thư mục tạm dưới Git root; khởi tạo schema test không phải migration database hiện hành.

| Kiểm tra | Kết quả thực tế ngày 23/10 | Phạm vi / giới hạn |
|---|---|---|
| Admin Python — `.venv/Scripts/python.exe -B tests/run_offline.py` | **PASS: 419; SKIP: 146; FAIL: 0** (565 tổng, 206.867s) | Runner có sẵn chặn đọc `.env`, socket network và psycopg; SQLite disposable. Không cấp `TEST_DATABASE_URL`, không provision PostgreSQL. |
| Admin JavaScript UI — `npm.cmd test` | **PASS: 102; FAIL: 0** | JSDOM + mocked API, không browser/runtime thật. Có cảnh báo VM Modules experimental. |
| Web pytest — suite `tests/` qua harness offline | **PASS: 317; FAIL: 0**, 5 deprecation warnings | Có tests routes, production isolation, Viewer/handoff, Bundle renderer, null/coverage và revision/grant. Không chạy script provider live. |
| Web harness lần đầu | **FAIL ở harness, đã khắc phục** | Chặn toàn bộ `socket.connect` làm Windows asyncio không tạo được socketpair tự đánh thức; lượt đó dừng, không được tính PASS. Chạy lại toàn suite với ngoại lệ chỉ cho đúng hàm `socket.socketpair` của thư viện chuẩn, vẫn chặn network ứng dụng. |
| JavaScript syntax | **PASS hai repo** | `node --check` toàn bộ static JS Admin và Web; kiểm tra lại `seo.js` sau chỉnh nhãn mẫu cuối. |
| Python syntax | **PASS** | AST parse 94 file Admin, 61 file Web; không import app production hoặc ghi bytecode. |
| Web CSS — `npm.cmd run build:css` | **PASS** | Dependencies đã có, không cài/cập nhật. Generated diff chỉ thêm `.sidebar-app-name{overflow-wrap:anywhere}`; cảnh báo caniuse-lite cũ chưa xử lý vì ngoài scope. |
| Branding/render | **PASS** | Web metadata và 6 routes demo render in-process (overview/SEO/Facebook Ads/Content/TikTok/YouTube), ownership VIO và SVG mới; service health ID giữ nguyên. Admin 5 bề mặt HTML/JS đúng tên, request header không đổi. |
| Jinja templates | **PASS hai repo** | Parse toàn bộ templates; không thay thế browser visual QA. |
| Package/lock | **PASS hai repo** | `name` root và package entry đồng bộ; so sánh lock sau khi bỏ thay đổi name khớp trước, không nâng dependencies. |
| Liên kết tài liệu hiện hành/mới | **PASS** | README, Product, Architecture, Roadmap, UX; không sửa đường dẫn lịch sử trong evidence. |
| `git diff --check` | **PASS hai repo** | Có cảnh báo LF/CRLF của Git ở một số file, không có lỗi whitespace. |
| Bảo toàn source ngoài danh sách sửa | **PASS** | SHA-256 của 205 file text Admin + 173 file text Web khớp baseline; không có file bị mất trong tập này. Secret/backup/ignored evidence không đọc nên không tuyên bố hash-verified. |
| Git state | **PASS** | Hai HEAD/branch và staging giữ nguyên; không thao tác remote/worktree. |
| PostgreSQL disposable, live provider, deployed browser E2E | **SKIP / NOT RUN** | Không tạo hạ tầng và không chạm runtime. 146 SKIP không được tính là PASS; branding source chưa được deploy. |

Web harness không sửa application: loại biến cấu hình provider/runtime khỏi process kiểm thử, đặt `APP_ENV=test`, patch `DotEnvSettingsSource._read_env_files` và `dotenv.main.DotEnv.dict` trả rỗng trước import app, chặn `socket.connect/connect_ex` và `asyncio.BaseEventLoop.create_connection` ngoài socketpair nội bộ. Pytest dùng in-process TestClient/MockTransport. Temp/cache của kiểm thử nằm trong `.pytest_cache/` ở từng Git root; bản inventory hash không chứa secret lưu ở Admin `.pytest_cache/rebrand-baseline.json` (ignored), không xóa cache có trước.

Tổng thay đổi của task: **Admin 14 MODIFY + 4 ADD; Web 22 MODIFY + 2 ADD; RENAME 0; DELETE 0**. 5 tài liệu mới và 1 SVG tái sử dụng. Không sửa tests/fixtures, package Python, `run.py`, migrations, API guards, dữ liệu, Compose, `.env` thật, remote hoặc worktree. Những file dirty được chạm là README/SYSTEM_CONTEXT, UI branding Admin và nhãn nhận định mẫu Web; các thay đổi nghiệp vụ có trước được giữ. Các bảy deleted file ở baseline vẫn là thay đổi có trước của người dùng.

Rủi ro còn lại: source local chưa commit có nhiều thay đổi nghiệp vụ nằm ngoài rebrand; container/image vẫn giữ phiên bản đang chạy. Launcher/ops và worktree cũ còn đường dẫn KDH cần migration riêng nếu sử dụng lại. Các CSV/export header, CLI banner, security identifiers và tên trong Bundle đã lưu có thể vẫn mang KDH theo contract/lịch sử. UI tên dài có CSS wrap nhưng không nghiệm thu browser deployed trong task này. Không có bằng chứng mới về provider permission, coverage live hoặc health của relay/PostgreSQL.

Roadmap tiếp theo chia thành 7 task riêng: Customer Authentication; Organization/Workspace & isolation/onboarding; Self-service Connections; Background Sync/Freshness; Smart Dashboards; Report Builder/Publication; Billing/White Label. Repository phụ trách, dependency, migration, rủi ro và acceptance của từng task ở [SAAS_MIGRATION_ROADMAP.md](SAAS_MIGRATION_ROADMAP.md).

## 6. Baseline local changes được bảo toàn

Bên dưới là metadata `git status --porcelain=v1 --untracked-files=all` trước thay đổi. Không chứa nội dung file/secret. Những file dirty có thay đổi branding cùng file được giới hạn ở patch nhỏ; phần nghiệp vụ có trước giữ nguyên. Không xóa/untrack/rename bất kỳ file local nào.

### VioAgencyAnalytics-Admin

```text
 D DEPLOY_DOCKER.md
 D KDH_ADMIN_UX_WORKFLOW_AUDIT_20261019.md
 D KDH_FACEBOOK_REPORTS_HANDOFF.md
 D KDH_PHASE4_POSTGRES_ACCEPTANCE.md
 D KDH_PHASE5B_SANDBOX_DEPLOYMENT_RESULT.md
 D KDH_PHASE5_SANDBOX_DEPLOYMENT_PLAN.md
 D KDH_PHASE9_IMPLEMENTATION_RESULT.md
 M README.md
 M compose.yaml
 M docs/SYSTEM_CONTEXT.md
 M docs/phase5-20261018/final_integrity.py
 M docs/phase5b-20261018/final_checks.py
 M kdh/app.py
 M kdh/marketing_dataset.py
 M kdh/marketing_preview.py
 M kdh/meta.py
 M kdh/meta_marketing.py
 M kdh/meta_reporting.py
 M static/marketing.js
 M static/views.js
 M templates/marketing.html
 M tests/test_facebook_bundles.py
 M tests/test_meta.py
 M tests/ui.test.js
?? Start-KDH.cmd
?? compose.primary-viewer.yaml
?? docs/DEPLOY_DOCKER.md
?? docs/FACEBOOK_CONTENT_INSIGHTS_20261021.md
?? docs/FACEBOOK_CONTENT_REQUIREMENTS_20261021.md
?? docs/KDH_ADMIN_UX_WORKFLOW_AUDIT_20261019.md
?? docs/KDH_FACEBOOK_REPORTS_HANDOFF.md
?? docs/KDH_PHASE4_POSTGRES_ACCEPTANCE.md
?? docs/KDH_PHASE5B_SANDBOX_DEPLOYMENT_RESULT.md
?? docs/KDH_PHASE5_SANDBOX_DEPLOYMENT_PLAN.md
?? docs/KDH_PHASE9_IMPLEMENTATION_RESULT.md
?? docs/KDH_PRIMARY_UNIFICATION_RESULT.md
?? docs/README.md
?? docs/content-insights-deploy-20261021/README.md
?? docs/content-insights-deploy-20261021/admin-tonight-full-final.log
?? docs/content-insights-deploy-20261021/admin-tonight-full.log
?? docs/content-insights-deploy-20261021/admin-tonight-tests.log
?? docs/content-insights-deploy-20261021/browser-before-bootstrap-wait.json
?? docs/content-insights-deploy-20261021/browser-observations.json
?? docs/content-insights-deploy-20261021/browser.json
?? docs/content-insights-deploy-20261021/build.json
?? docs/content-insights-deploy-20261021/deployment.json
?? docs/content-insights-deploy-20261021/existing-report-1440.png
?? docs/content-insights-deploy-20261021/facebook-tonight.log
?? docs/content-insights-deploy-20261021/first-attempt-rollback.json
?? docs/content-insights-deploy-20261021/image-tests.log
?? docs/content-insights-deploy-20261021/insights-permission-1440.png
?? docs/content-insights-deploy-20261021/kdh-admin-meta-build.log
?? docs/content-insights-deploy-20261021/new-tonight-tests.log
?? docs/content-insights-deploy-20261021/postgres-tonight-final.log
?? docs/content-insights-deploy-20261021/postgres-tonight.log
?? docs/content-insights-deploy-20261021/prepared.json
?? docs/content-insights-deploy-20261021/previous-startup-manifest.json
?? docs/content-insights-deploy-20261021/second-attempt-rollback.json
?? docs/content-insights-deploy-20261021/source-verification.json
?? docs/content-insights-deploy-20261021/tests.json
?? docs/content-insights-deploy-20261021/ui-tests.log
?? docs/content-insights-deploy-20261021/ui-tonight-tests.log
?? docs/content-polish-20261021/RESULT.md
?? docs/content-polish-20261021/baseline.json
?? docs/content-polish-20261021/browser.json
?? docs/content-polish-20261021/build.json
?? docs/content-polish-20261021/deployment.json
?? docs/content-polish-20261021/final/baseline.json
?? docs/content-polish-20261021/final/build.json
?? docs/content-polish-20261021/final/deployment.json
?? docs/content-polish-20261021/final/kdh-new-build.log
?? docs/content-polish-20261021/final/previous-startup-manifest.json
?? docs/content-polish-20261021/final/protected-after.json
?? docs/content-polish-20261021/final/protected-before.json
?? docs/content-polish-20261021/final/smoke.json
?? docs/content-polish-20261021/kdh-new-build.log
?? docs/content-polish-20261021/previous-startup-manifest.json
?? docs/content-polish-20261021/protected-after.json
?? docs/content-polish-20261021/protected-before.json
?? docs/content-polish-20261021/report-1024.png
?? docs/content-polish-20261021/report-1440.png
?? docs/content-polish-20261021/report-1536.png
?? docs/content-polish-20261021/report-1920.png
?? docs/content-polish-20261021/report-360.png
?? docs/content-polish-20261021/report-390.png
?? docs/content-polish-20261021/report-768.png
?? docs/content-polish-20261021/smoke.json
?? docs/content-shell-20261021/RESULT.md
?? docs/content-shell-20261021/baseline.json
?? docs/content-shell-20261021/browser.json
?? docs/content-shell-20261021/build.json
?? docs/content-shell-20261021/deployment.json
?? docs/content-shell-20261021/final-health.json
?? docs/content-shell-20261021/kdh-new-build.log
?? docs/content-shell-20261021/network-recovery.json
?? docs/content-shell-20261021/previous-startup-manifest.json
?? docs/content-shell-20261021/report-1024.png
?? docs/content-shell-20261021/report-1440.png
?? docs/content-shell-20261021/report-360.png
?? docs/content-shell-20261021/report-390.png
?? docs/content-shell-20261021/report-768.png
?? docs/content-shell-20261021/responsive-final/baseline.json
?? docs/content-shell-20261021/responsive-final/build.json
?? docs/content-shell-20261021/responsive-final/deployment.json
?? docs/content-shell-20261021/responsive-final/kdh-new-build.log
?? docs/content-shell-20261021/responsive-final/previous-startup-manifest.json
?? docs/content-shell-20261021/responsive-final/smoke.json
?? docs/content-shell-20261021/responsive-release/baseline.json
?? docs/content-shell-20261021/responsive-release/build.json
?? docs/content-shell-20261021/responsive-release/deployment.json
?? docs/content-shell-20261021/responsive-release/previous-startup-manifest.json
?? docs/content-shell-20261021/responsive-release/protected-after.json
?? docs/content-shell-20261021/responsive-release/protected-before.json
?? docs/content-shell-20261021/responsive-release/smoke.json
?? docs/content-shell-20261021/responsive-verified/baseline.json
?? docs/content-shell-20261021/responsive-verified/build.json
?? docs/content-shell-20261021/responsive-verified/deployment.json
?? docs/content-shell-20261021/responsive-verified/previous-startup-manifest.json
?? docs/content-shell-20261021/responsive-verified/protected-after.json
?? docs/content-shell-20261021/responsive-verified/protected-before.json
?? docs/content-shell-20261021/responsive-verified/smoke.json
?? docs/content-shell-20261021/responsive/baseline.json
?? docs/content-shell-20261021/responsive/build.json
?? docs/content-shell-20261021/responsive/deployment.json
?? docs/content-shell-20261021/responsive/kdh-new-build.log
?? docs/content-shell-20261021/responsive/previous-startup-manifest.json
?? docs/content-shell-20261021/responsive/smoke.json
?? docs/content-shell-20261021/smoke.json
?? docs/insights-chart-20261022/README.md
?? docs/insights-chart-20261022/baseline.json
?? docs/insights-chart-20261022/before-startup-manifest.json
?? docs/insights-chart-20261022/build.json
?? docs/insights-chart-20261022/deployed-1440.png
?? docs/insights-chart-20261022/deployed-390.png
?? docs/insights-chart-20261022/deployed.json
?? docs/insights-chart-20261022/deployment.json
?? docs/insights-chart-20261022/image-tests-final.log
?? docs/insights-chart-20261022/image-tests.log
?? docs/insights-chart-20261022/kdh-new-build.log
?? docs/insights-chart-20261022/local-assets-1440.png
?? docs/insights-chart-20261022/local-assets-390.png
?? docs/insights-chart-20261022/local-assets.json
?? docs/insights-chart-20261022/previous-compose.yaml
?? docs/insights-chart-20261022/tests.json
?? docs/origin-fix-20261021/RESULT.md
?? docs/origin-fix-20261021/baseline.json
?? docs/origin-fix-20261021/browser.json
?? docs/origin-fix-20261021/build.log
?? docs/origin-fix-20261021/deployment.json
?? docs/origin-fix-20261021/prepared.json
?? docs/origin-fix-20261021/python-tests.log
?? docs/origin-fix-20261021/report-after-docker-login.png
?? docs/origin-fix-20261021/tests.json
?? docs/origin-fix-20261021/ui-tests.log
?? docs/shared-viewer-20261021/RESULT.md
?? docs/shared-viewer-20261021/admin-tests.log
?? docs/shared-viewer-20261021/baseline.json
?? docs/shared-viewer-20261021/browser.json
?? docs/shared-viewer-20261021/build.json
?? docs/shared-viewer-20261021/deployment.json
?? docs/shared-viewer-20261021/docker-links.json
?? docs/shared-viewer-20261021/final.json
?? docs/shared-viewer-20261021/kdh-admin-build.log
?? docs/shared-viewer-20261021/kdh-new-build.log
?? docs/shared-viewer-20261021/network-tests.json
?? docs/shared-viewer-20261021/relay.json
?? docs/shared-viewer-20261021/report-after-docker-login.png
?? docs/shared-viewer-20261021/restart-test.json
?? docs/shared-viewer-20261021/retired.json
?? docs/shared-viewer-20261021/smoke.json
?? docs/shared-viewer-20261021/startup.json
?? docs/tonight-delivery-20261021/README.md
?? docs/tonight-delivery-20261021/acceptance-gates.json
?? docs/tonight-delivery-20261021/admin-fixture-1024.png
?? docs/tonight-delivery-20261021/admin-fixture-1440.png
?? docs/tonight-delivery-20261021/admin-fixture-360.png
?? docs/tonight-delivery-20261021/admin-fixture-390.png
?? docs/tonight-delivery-20261021/admin-fixture-768.png
?? docs/tonight-delivery-20261021/admin-isolated-tests.log
?? docs/tonight-delivery-20261021/admin/admin-preview-real-1440.png
?? docs/tonight-delivery-20261021/admin/admin-preview-real-390.png
?? docs/tonight-delivery-20261021/admin/browser-observations.json
?? docs/tonight-delivery-20261021/admin/browser.json
?? docs/tonight-delivery-20261021/admin/build.json
?? docs/tonight-delivery-20261021/admin/deployment.json
?? docs/tonight-delivery-20261021/admin/image-tests.log
?? docs/tonight-delivery-20261021/admin/insights-permission-1440.png
?? docs/tonight-delivery-20261021/admin/kdh-admin-meta-build.log
?? docs/tonight-delivery-20261021/admin/new-report-real-1440.png
?? docs/tonight-delivery-20261021/admin/new-report-real-390.png
?? docs/tonight-delivery-20261021/admin/prepared.json
?? docs/tonight-delivery-20261021/admin/previous-startup-manifest.json
?? docs/tonight-delivery-20261021/admin/tests.json
?? docs/tonight-delivery-20261021/before-new-startup-manifest.json
?? docs/tonight-delivery-20261021/browser-fixture.log
?? docs/tonight-delivery-20261021/browser_fixture.py
?? docs/tonight-delivery-20261021/deployment.json
?? docs/tonight-delivery-20261021/disposable-test-cleanup.json
?? docs/tonight-delivery-20261021/fixture-browser.json
?? docs/tonight-delivery-20261021/kdh-new-build.log
?? docs/tonight-delivery-20261021/new-baseline.json
?? docs/tonight-delivery-20261021/new-build.json
?? docs/tonight-delivery-20261021/new-fixture-1024.png
?? docs/tonight-delivery-20261021/new-fixture-1440.png
?? docs/tonight-delivery-20261021/new-fixture-360.png
?? docs/tonight-delivery-20261021/new-fixture-390.png
?? docs/tonight-delivery-20261021/new-fixture-768.png
?? docs/tonight-delivery-20261021/new-image-tests.json
?? docs/tonight-delivery-20261021/new-image-tests.log
?? docs/tonight-delivery-20261021/previous-new-compose.yaml
?? docs/tonight-delivery-20261021/restart-20261022.json
?? docs/tonight-delivery-20261021/run_offline.py
?? docs/tonight-delivery-20261021/source-verification.json
?? docs/unified-admin-20261020/admin-build.log
?? docs/unified-admin-20261020/admin-isolated-tests.log
?? docs/unified-admin-20261020/admin-postgres-tests.log
?? docs/unified-admin-20261020/admin-python.log
?? docs/unified-admin-20261020/admin-ui.log
?? docs/unified-admin-20261020/browser-qa.json
?? docs/unified-admin-20261020/build.json
?? docs/unified-admin-20261020/deployment.json
?? docs/unified-admin-20261020/extra-postgres-exit.json
?? docs/unified-admin-20261020/extra-postgres-tests.log
?? docs/unified-admin-20261020/facebook-postgres-exit.json
?? docs/unified-admin-20261020/facebook-postgres-tests.log
?? docs/unified-admin-20261020/final-verification.json
?? docs/unified-admin-20261020/git-baseline.json
?? docs/unified-admin-20261020/git-final.json
?? docs/unified-admin-20261020/new-build.log
?? docs/unified-admin-20261020/new-smoke.json
?? docs/unified-admin-20261020/new-source-before.zip
?? docs/unified-admin-20261020/new-source-integration.json
?? docs/unified-admin-20261020/new-tests.log
?? docs/unified-admin-20261020/postgres-tests-exit.json
?? docs/unified-admin-20261020/preflight.json
?? docs/unified-admin-20261020/restore-smoke.json
?? docs/unified-admin-20261020/screenshots/primary-admin-login-1024.png
?? docs/unified-admin-20261020/screenshots/primary-admin-login-1440.png
?? docs/unified-admin-20261020/screenshots/primary-admin-login-360.png
?? docs/unified-admin-20261020/screenshots/primary-admin-login-390.png
?? docs/unified-admin-20261020/screenshots/primary-admin-login-768.png
?? docs/vio-handoff-recovery-20261022/README.md
?? docs/vio-handoff-recovery-20261022/browser.json
?? docs/vio-handoff-recovery-20261022/private-relay-config-before.json
?? docs/vio-handoff-recovery-20261022/recovery.json
?? docs/vio-handoff-recovery-20261022/report-1440.png
?? docs/vio-handoff-recovery-20261022/report-390.png
?? docs/vio-insights-live-20261022/README.md
?? docs/vio-insights-live-20261022/dataset-content-check.json
?? docs/vio-insights-live-20261022/dataset-create-started.json
?? docs/vio-insights-live-20261022/diagnostic-started.json
?? docs/vio-insights-live-20261022/diagnostic.json
?? docs/vio-insights-live-20261022/final-integrity.json
?? docs/vio-insights-live-20261022/kdh-meta-2b-relay-20261016-132836-5c512a53-config-before-restart.json
?? docs/vio-insights-live-20261022/kdh-vio-relay-phase9-20261019-config-before-restart.json
?? docs/vio-insights-live-20261022/new-admin-preview-1440.png
?? docs/vio-insights-live-20261022/new-admin-preview-390.png
?? docs/vio-insights-live-20261022/new-dataset.json
?? docs/vio-insights-live-20261022/new-preview-browser.json
?? docs/vio-insights-live-20261022/new-preview.json
?? docs/vio-insights-live-20261022/oauth-check.json
?? docs/vio-insights-live-20261022/pending-review-check.json
?? docs/vio-insights-live-20261022/persistence-check.json
?? docs/vio-insights-live-20261022/preflight.json
?? docs/vio-insights-live-20261022/preview-summary.json
?? docs/vio-insights-live-20261022/relay-recovery.json
?? docs/vio-insights-live-20261022/retry-http.json
?? docs/vio-insights-live-20261022/retry-job.json
?? docs/vio-insights-live-20261022/retry-persistence.json
?? docs/vio-insights-live-20261022/retry-postflight.json
?? docs/vio-insights-live-20261022/retry-preflight.json
?? docs/vio-insights-live-20261022/retry-result.json
?? docs/vio-insights-live-20261022/retry-started.json
?? docs/vio-insights-live-20261022/sync-job.json
?? docs/vio-insights-live-20261022/sync-postflight.json
?? docs/vio-insights-live-20261022/sync-preflight.json
?? docs/vio-insights-live-20261022/sync-result.json
?? docs/vio-insights-live-20261022/sync-started.json
?? kdh/facebook_content_report.py
?? kdh/meta_content_insights.py
?? ops/check_content_insights_deploy.py
?? ops/check_content_polish.py
?? ops/check_content_shell.py
?? ops/check_insights_chart_20261022.py
?? ops/check_sandbox_origin.py
?? ops/check_shared_viewer.py
?? ops/check_tonight_content.py
?? ops/deploy_content_insights.py
?? ops/deploy_content_shell.py
?? ops/deploy_tonight_content.py
?? ops/fix_sandbox_origin.py
?? ops/shared_viewer.py
?? ops/unify_primary.py
?? ops/verify_primary_browser.py
?? ops/vio_content_prepare_20261022.py
?? ops/vio_content_preview_qa_20261022.py
?? ops/vio_content_retry_20261022.py
?? ops/vio_content_sync_20261022.py
?? ops/vio_content_verify_20261022.py
?? ops/vio_insights_diagnostic_20261022.py
?? static/facebook-content-report.js
?? tests/test_facebook_content_report.py
?? tests/test_loopback_entry.py
?? tests/test_meta_content_insights.py
```

Ignored paths (chỉ metadata, không đọc secrets/backup):

```text
.env
.npm-cache/
.pytest_cache/
.venv/
__pycache__/
docs/phase5-20261018/__pycache__/
docs/phase5b-20261018/__pycache__/
docs/phase9-20261019/__pycache__/
docs/ui-deployment-20261019/__pycache__/
instance/
kdh/__pycache__/
kdh/meta.py.bak
node_modules/
ops/__pycache__/
public/
scripts/__pycache__/
test-results/
tests/__pycache__/
```

### VioAgencyAnalytics-Web

```text
 M app/mappers/dashboard.py
 M app/mappers/facebook_content.py
 M compose.shared.yaml
 M static/css/pages/facebook-content.css
 M static/js/pages/snapshot.js
 M static/js/shared/charts.js
 M templates/pages/facebook_content/index.html
 M templates/pages/facebook_content/partials/engagement.html
 M templates/pages/facebook_content/partials/formats.html
 M templates/pages/facebook_content/partials/insights.html
 M templates/pages/facebook_content/partials/kpis.html
 M templates/pages/facebook_content/partials/posts.html
 M templates/pages/facebook_content/partials/reach_mix.html
 M templates/pages/facebook_content/partials/topics.html
 M templates/pages/snapshot/components.html
 M tests/test_content_report_contract.py
 M tests/test_vio_content.py
?? templates/pages/facebook_content/partials/section_status.html
?? tests/fixtures/facebook_content_insights_v1.json
?? tests/test_content_insights_contract.py
```

Ignored paths (chỉ metadata, không đọc secrets/backup):

```text
.env
.pytest_cache/
.venv/
.work/
__pycache__/
app/__pycache__/
app/db/__pycache__/
app/integrations/mock/__pycache__/
app/mappers/__pycache__/
app/models/__pycache__/
app/repositories/__pycache__/
app/routes/__pycache__/
app/schemas/__pycache__/
app/services/__pycache__/
node_modules/
scripts/__pycache__/
scripts/real_data_tests/__pycache__/
tests/__pycache__/
```
