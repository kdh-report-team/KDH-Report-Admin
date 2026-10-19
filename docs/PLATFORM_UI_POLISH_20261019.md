# Platform visual refinement — 19/10/2026

Deployed to http://localhost:8191/#overview. Status: **PASS**.

## Changes

- Local provider logos for Google, Analytics, Search Console, Sheets, Facebook, Meta, TikTok and YouTube. Provenance and licensing: [PLATFORM_BRAND_ASSETS.md](PLATFORM_BRAND_ASSETS.md).
- Consistent logo tiles across Overview, Connections, Assets, sync history and source previews.
- More balanced platform cards, clear status placement, two-column connection cards and responsive single-column layout.
- Permission details available through an accessible disclosure; unverified/empty/failed states remain visible. Reduced repetitive explanatory text without changing guards or KPI semantics.
- Missing asset identifiers no longer render the literal `undefined`.

Application files changed: `static/ui.js`, `static/views.js`, `static/admin-refinement.css`, eight new SVGs in `static/brands/`. Tests changed: `tests/ui.test.js`, `tests/admin_refinement.browser.cjs`. Existing XSS tests now validate the local logo allowlist while continuing to reject injected images and event attributes.

## Validation

- `npm.cmd test`: 100 PASS, 0 FAIL, 0 SKIP.
- `.venv/Scripts/python.exe -B tests/run_offline.py`: 499 total; 380 PASS, 119 SKIP, 0 FAIL. PostgreSQL tests skipped in this offline run; no runtime DB used by tests.
- JS syntax checks and `git diff --check`: PASS (existing Git line-ending warnings only).
- Browser fixture QA: 75 screen/viewport checks PASS at 1440, 1024, 768, 390 and 360 pixels; no overflow, missing brand images, live API calls or mutations. Screenshots: `test-results/platform-brand-polish/browser-approved/`. These are offline fixtures, not evidence of live provider access.

## Deployment

- Image: `kdh-admin-meta:brand-polish-20261019-5a9912259a3a`.
- Image ID: `sha256:61fc38a6e3d5e64271db0d88ed994b7d355f659d0a3dbbe2dee68632d9baa030`.
- Admin container: `41a7100e18cbde6d0aa1d58c281a0ad96086b3023b67f73c3a53ee38328cd104`.
- Fresh encrypted backup, checksum validation and isolated PostgreSQL restore: PASS. Backup is local; no off-host copy established.
- Isolated image smoke and runtime health/login/CSRF/client scope: PASS.
- Served static asset hashes match the manifest, including all logos.
- All 29 business-table hashes/counts unchanged. Normal authentication session/audit activity excluded from this comparison.
- PostgreSQL, gateway and relay unchanged. Only relay publishes `127.0.0.1:8191`; Admin remains internal at `192.168.0.3`.
- Rollback container retained, stopped: `kdh-meta-2b-admin-20261016-132836-5c512a53-before-brand-polish-20261019`.
- No provider calls, sync, migration, review, publication or OAuth changes. No New/production changes.
- Branch/HEAD and all unrelated local changes preserved. Backend file hashes unchanged from turn baseline.

Evidence: `docs/ui-deployment-20261019/brand-polish-{preflight,backup,manifest,build,smoke,deployment}.json`. Deployment wrapper reuses the verified sandbox-only procedure.
