# Multi-platform Admin — sandbox deployment

Status: **PASS**. URL: http://localhost:8191/#overview

## Deployment identity

- Branch: `feat/seo-composite-release`.
- HEAD: `664efbc561b401d901947437c63df87348d81437`.
- Sandbox run: `20261016-132836-5c512a53`.
- Client: `client_meta_sandbox`.
- Image: `kdh-admin-meta:multiplatform-20261019-36536d720762-r3`.
- Image ID: `sha256:926d563949e1ecfa70aca33e0aff42f1e73f9f184178a27a099107833ea8c626`.
- Admin container ID: `3081d4b8d34970759f82d341697d3f0decd2f74ae714bdde476cead499f28ca8`.
- Rollback container, stopped: `kdh-meta-2b-admin-20261016-132836-5c512a53-before-multiplatform-20261019`.

Only the Admin application container was replaced. PostgreSQL, gateway and relay identities, startup timestamps, mounts and runtime configurations stayed unchanged. Admin retains internal IP `192.168.0.3`; only the relay binds host `127.0.0.1:8191`. Environment values, encryption configuration and appdata mount were preserved.

## Validation

- Fresh encrypted database/appdata/config backup: PASS. Restore tested on isolated, network-none PostgreSQL with tmpfs storage; 29 business-table hashes matched. No off-host backup was established.
- Immutable image build: PASS. Source hashes matched the frozen manifest. No application source was changed during deployment.
- Disposable smoke: PASS for imports, HTTP health, login/session/CSRF, platform status, unified sync history, client scope, Marketing workflow, routes and migrations 1–8.
- Deployed HTTP health: 200. Login/session/CSRF: PASS.
- Served static assets match the build hashes. Platform status, sync-history scope and Marketing scope: PASS.
- Business-table counts/hashes unchanged across startup and authenticated checks. Existing datasets, reviews, snapshots, metrics and history preserved.
- No new migration, provider request, sync, Dataset, review, approval or publication was requested. Authentication checks create normal temporary session/audit activity; these are excluded from business-data hashes.
- Git branch and HEAD unchanged; source files match the pre-deployment manifest. Existing modified/untracked work retained. `git diff --check`: PASS (existing line-ending warnings only).

## Build diagnostics

The first build failed because BuildKit interpreted an image ID in `FROM` as a remote repository. The second build used the verified local base tag, but smoke found an inherited `kdh/meta.py.bak`. Revision 3 removes that backup file inside the image before copying the unchanged source allowlist. Smoke then passed. Neither failed attempt replaced the serving application.

The initial manifest's `dockerfile_sha256` records the first attempted Dockerfile, not the final build recipe. The final build uses the verified local tag for the same base image ID, `USER root`, `RUN rm -f /app/kdh/meta.py.bak`, `USER kdh`, then the source COPY instructions. The effective R3 context checksum is recorded in `multiplatform-build-result-r3.json`; source file hashes and aggregate identity are unchanged. Earlier failed-build evidence is retained.

## User-facing boundaries

- Open http://localhost:8191/#overview and use Ctrl+F5 to reload assets.
- Meta was already disconnected before this deployment. This deployment does not reconnect it or grant provider access; historical records remain intact.
- TikTok Ads is a disconnected scaffold, not a live integration.
- No KDH-Report-New change or Admin-to-New E2E acceptance is claimed.

## Evidence

- `ui-deployment-20261019/multiplatform-preflight.json`
- `ui-deployment-20261019/multiplatform-backup-evidence.json`
- `ui-deployment-20261019/multiplatform-manifest-r3.json`
- `ui-deployment-20261019/multiplatform-build-result-r3.json`
- `ui-deployment-20261019/multiplatform-smoke.json`
- `ui-deployment-20261019/multiplatform-deployment-result.json`

The previous Admin container is retained for application-only rollback. Do not restore over the original PostgreSQL volume or run the old container with a conflicting endpoint. No rollback was needed.
