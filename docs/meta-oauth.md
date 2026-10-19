# Meta OAuth foundation

Admin supports connecting a Meta user account for KinderHealth (`client_kinderhealth`) or the isolated test client (`client_meta_sandbox`). The OAuth flow itself does not discover assets, read insights, run sync jobs, or create Datasets. Sandbox reporting uses the separate `meta_reporting` reader, routes, and worker after OAuth succeeds. Google OAuth and its existing routes are unchanged.

## Configuration

Configure these backend environment variables (see `.env.example` and `compose.yaml`):

| Variable | Purpose |
| --- | --- |
| `META_APP_ID` | Numeric Meta App ID |
| `META_APP_SECRET` | App Secret; never expose to frontend or commit |
| `META_CONFIG_ID` | Numeric Facebook Login for Business configuration ID; select a user access token |
| `META_CLIENT_ID` | Defaults to `client_kinderhealth`; use `client_meta_sandbox` for isolated Page Content testing |
| `META_GRAPH_VERSION` | Explicit Graph API version; defaults to `v26.0` |
| `META_REDIRECT_URI` | Exact registered URI, ending in `/api/meta/callback` |

Enable Facebook Login for Business for the Meta app, create a configuration for a **user access token**, and register the exact callback URI. The callback must share the `APP_URL` origin; HTTPS is required except for loopback development. Use `COOKIE_SECURE=1` with production HTTPS. Access in Meta development mode depends on the app's configured roles/test users and permission access. System-user tokens are not supported by this user-token flow.

For the intended local configuration, use `APP_URL=http://localhost:8090` and `META_REDIRECT_URI=http://localhost:8090/api/meta/callback`, then open `http://localhost:8090` in the browser. Do not switch between `localhost` and `127.0.0.1` during login: they have different session cookies. If the Meta URI is omitted/empty, it derives from `APP_URL`; explicit values are preserved and checked. `.env.example` uses matching localhost origins for both providers. Existing deployments keep their own registered Google URI; runtime Google OAuth is unchanged.

The authorization URL passes `config_id`, `response_type=code` and `override_default_response_type=true`; it does not also pass a conflicting `scope` parameter. Required permissions depend on the configured client:

- `client_kinderhealth` keeps the existing `REQUIRED_PERMISSIONS`: `pages_show_list`, `pages_read_engagement`, and `ads_read`.
- `client_meta_sandbox` requires only `pages_show_list` and `pages_read_engagement` for Page Content. An additional `ads_read` grant is optional.

Both callback validation and local connection status enforce this client-specific requirement. App ID, Config ID, token type/identity, expiry, Admin session, and OAuth state validation remain unchanged. Grant validation does not enumerate assets or call Insights.

Without `ads_read`, sandbox asset discovery still calls `me/accounts`, skips `me/adaccounts`, and returns `facebook_ads: []`. Facebook Ads sync requests fail with HTTP 403 / `meta_ads_permission` before queueing; the reader also rechecks permission before Ads Insights so an already queued job cannot bypass the guard. The existing Page-token and post-reading flow is unchanged. Page Content still reports lifetime post counters, not invented daily engagement or unavailable Insights. A successful mocked test does not confirm access to the real VIO Agency Page; that requires a live OAuth trial.

Restart the backend, sign in as an Admin, and choose **Kết nối Meta** on the Meta card under **Kết nối nền tảng** (or in its Facebook detail page). Approve the login and return to the same Admin browser session. A successful connection shows the confirmed account, timestamps, expiry, and granted scopes, with **Đã xác thực Meta. Chưa chọn tài sản dữ liệu.** It does not indicate that report data is available. To change accounts, disconnect the existing account before reconnecting.

## Admin API

All four routes require an active Admin session. POST/DELETE also require existing `X-KDH-Request`, CSRF, and Origin protections.

| Route | Behavior |
| --- | --- |
| `GET /api/meta` | Local, read-only status; never calls Meta or returns credentials |
| `POST /api/meta/connect` | Returns `{url}` for the authorization-code flow |
| `GET /api/meta/callback` | Consumes state, exchanges/validates the code, saves encrypted credentials, redirects to `/#connections/facebook?oauth=success\|denied\|failed` |
| `DELETE /api/meta` | Attempts provider revocation, clears local credentials and pending authorizations, returns `message` and `revoked_at_provider` |

Status fields: `configured`, `connected`, `has_connection`, `status`, `client_id`, `account_id`, `account_name`, `connected_at`, `expires_at`, `data_access_expires_at`, and `scopes`. Status is `disconnected`, `connected`, `expired`, `reconnect_required`, or `error`. Changing App ID/Config ID or lacking a required permission marks an existing connection for reauthorization. Expiry reflects stored Meta metadata. Status does **not** detect remote revocation; reconnect to validate a fresh grant. No automatic refresh or deauthorization webhook is implemented.

## Storage and security

Migration **3** appends `meta_oauth_states`; migrations 1–2 are unchanged. States are hashed, session/configuration-bound (including Config ID), expire after ten minutes, and can be claimed once (including denied callbacks). A new connect replaces pending attempts for this client. Disconnect cancels in-flight callbacks; expired/revoked Admin sessions cannot save credentials.

The legacy `oauth_states` table is Google-specific: it has no provider namespace, and Google deletes states by session. A separate Meta state table prevents one provider's connect from cancelling the other's state without changing the working Google flow. Both use the existing Store/transaction infrastructure.

Meta tokens and identity metadata use the existing Fernet cipher and `secrets` table under `meta:client_kinderhealth` or `meta:client_meta_sandbox`, scoped to the configured client. SQLite uses the existing `instance/encryption.key`; PostgreSQL requires the deployment's stable `ENCRYPTION_KEY`. Back up the key with the encrypted database. `connections` stores client/provider identity and a secret reference, never a token. Credential and connection updates are atomic. Provider errors are sanitized; audit events contain no codes or tokens.

Disconnect serializes with connect/callback through the existing database write transaction while attempting bounded provider revocation (3-second connect, 5-second read timeout). A failed revocation still clears the local connection and produces an explicit warning; the user can remove the app's permissions in Facebook. A crashed/uncompleted disconnect can be retried. Avoid enabling HTTP debug logging or recording callback query strings in proxy access logs.

## Provider calls and validation

The backend OAuth flow calls these endpoints:

- `/{version}/oauth/access_token`: code exchange, then long-lived user-token exchange.
- `/{version}/debug_token`: validate app, user, token type, scopes and expiry.
- `GET /{version}/me?fields=id,name`: confirm account identity using bearer authorization and `appsecret_proof`.
- `DELETE /{version}/me/permissions`: attempt revocation with bearer authorization and `appsecret_proof`.

Token exchange and inspection use Graph's POST transport with `method=GET` in the form body. This retains the read operation while keeping codes, App Secret, and token inputs out of request URLs. Bearer tokens remain in backend Authorization headers. Tests inspect prepared HTTP URLs and fail if credentials appear there; there is no fallback to credentials in query strings.

No asset, Page, ad-account, insights, Google, TikTok, or YouTube API is called by this flow. Report Builder and Preview continue to use immutable Dataset snapshots only.

Protocol references: Meta's [OAuth client implementation](https://github.com/facebookarchive/php-graph-sdk/blob/5.x/src/Facebook/Authentication/OAuth2Client.php), [POST method-override implementation](https://github.com/facebookarchive/facebook-php-sdk/blob/master/src/base_facebook.php), [User permissions implementation](https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/adobjects/user.py), and [Graph version configuration](https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/apiconfig.py). The developer documentation site returned HTTP 429 during implementation; the method-override reference is Meta's archived SDK, so confirm this transport and app-specific setup in a live authorization trial before deployment.

Run `python -m unittest discover -s tests -p "test_meta*.py" -v` and `npm.cmd test`. Provider calls are mocked; PostgreSQL cases require a disposable `TEST_DATABASE_URL`. Live authorization/revocation needs configured Meta credentials and is not covered by the mocked tests.

## Sync diagnostics

Meta sync uses the dedicated `kdh.meta_sync` logger at INFO level, writing JSON to stderr so both the background worker and request-mode worker are visible in Docker without enabling HTTP debug logging:

```sh
docker compose logs admin --since=30m --tail=200 --timestamps
```

Every event contains `source`, `client_id`, `stage`, `status`, `database`, and the generated `job_id` when available. After the sync record is created, subsequent events also contain `sync_run_id`. Failures add `exception_type`, a fixed internal `error_code`, and the innermost application `file`/`line` when available. `MetaRequestError` retains only validated scalar metadata: `http_status`, `graph_error_code`, `graph_error_subcode`, and boolean `is_transient`. Missing or invalid values are omitted, never coerced from strings or objects. PostgreSQL errors include a five-character `sqlstate` when available, including constraints wrapped by the Store bridge. Exception messages, formatted tracebacks, locals, SQL, request URLs/headers, credentials, OAuth codes, cookies, and provider response bodies are never logged.

The operation `stage` and request `failure_layer` have different meanings. For example, `stage=page_token, failure_layer=graph_api` means Graph rejected the Page-token lookup; `stage=fetch_posts, failure_layer=transport` means the posts request could not complete. `response_decode` means a successful HTTP response was not usable JSON/object data. These fields do not imply that permission or provider data has been independently verified. OAuth validation here is the sync worker's local grant check, not a new OAuth callback logging system.

| Stage | Operation |
| --- | --- |
| `job_validation`, `sync_start` | Validate the job, Admin and asset permissions, then start the sync record |
| `oauth_validation` | Check the stored OAuth connection before starting a sync; failure has a job ID but no sync ID |
| `page_token` | Resolve the selected Page and obtain its Page token through the existing flow |
| `fetch_posts` | Read and paginate the Page posts |
| `normalize_content` | Normalize publication counts and lifetime post counters |
| `snapshot_validation` | Reject unsafe snapshot fields and verify JSON serialization before database writes |
| `database_write` | Execute metrics and snapshot writes inside the transaction |
| `sync_finalize` | Update sync/job status and watermarks, then commit the transaction |
| `sync_complete` | Emitted only after the successful transaction commit |
| `failure_status_write`, `job_status_write` | Persist safe failure status; failures here are logged separately without hiding the original error |

`database_write` success means its SQL statements executed; only `sync_complete` confirms the overall transaction committed. A later finalization/commit failure rolls back those writes.

Sync history distinguishes `meta_api_error`, `meta_permission_error`, `meta_page_permission`, `meta_ads_permission`, `meta_reconnect_required`, `meta_data_error`, `meta_snapshot_invalid`, `meta_database_error`, `meta_validation_error`, and `meta_sync_internal_error`. Graph code 190 is categorized as reconnect-required; Graph codes 10/200 or HTTP 401/403 as permission failures. Unknown codes remain API errors with their numeric metadata preserved. JSON is inspected only to extract the allowlisted fields; messages, arbitrary error data and trace IDs are discarded. An error object on HTTP 200 is also rejected. Local Page/Ads permission failures retain their specific codes. Public job/sync errors use fixed safe messages and do not expose diagnostic metadata. Historical failed rows retain their original codes; a later approved sync is needed to obtain new diagnostics. Existing request retries and reporting semantics are unchanged.

Mock tests exercise OAuth validation, Page-token failures, HTTP/Graph errors, transport/decode failures, malformed post data, snapshot rejection, database writes, finalization/commit rollback, secondary failure-status writes, the job boundary, and stderr output. They check correlation and leakage through logs, jobs, sync records and events, and preserve an earlier successful snapshot/metrics/watermark after a failed resync. SQLite tests that inject PostgreSQL exception types are simulations, not PostgreSQL integration results.

### Safe Phase 0 verification

From the Admin repository, with no real provider requests:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p 'test_meta*.py' -v
npm.cmd test
```

Meta worker/diagnostics fixtures use temporary SQLite and mocked providers; HTTP diagnostics tests block unmocked requests. Never set `TEST_DATABASE_URL` to the runtime database. The optional `PostgresMetaDiagnosticsTests` additionally requires `TEST_META_POSTGRES=1` and a separately provisioned disposable PostgreSQL test database. It creates a unique schema per test and drops only that schema. It tests successful Content persistence, a real uniqueness failure during writing, and a deferred foreign-key failure at commit. Neither test database provisioning nor Docker startup is automatic.

With an explicitly disposable `TEST_DATABASE_URL` already supplied to the test process (not the project's `.env`):

```powershell
$env:TEST_META_POSTGRES = '1'
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p 'test_meta_diagnostics.py' -v
```

Without these prerequisites, PostgreSQL cases SKIP. A SQLite PASS, simulated PostgreSQL exception, or skipped test is not PostgreSQL validation.

For a later, separately approved live Content trial:

1. Use an isolated Admin process/container and database, distinct data directory/ports and test-only credentials; never reuse runtime volumes. Keep `client_meta_sandbox`, and do not enable the primary-client override.
2. Confirm the running files include `meta_diagnostics.py` and match the reviewed code. Do not launch the normal Admin application merely to inspect a production database: startup and workers may write.
3. Select one authorized Page and a short completed date range. Starting sync writes to the chosen test database even though provider requests are read-only.
4. Record the returned `job_id`; correlate `meta_sync` events with `sync_run_id` and the sync-history endpoint. Use only allowlisted JSON diagnostic events when sharing logs. Do not enable HTTP debug/access logging that captures OAuth query strings.
5. Require `sync_complete` plus matching successful job/sync/snapshot records. On failure, inspect the first failed stage and any later `failure_status_write`/`job_status_write` errors. Missing completion or a stuck `running` row is not success.
6. Keep results `meta_api_unverified` and publication blocked. Phase 0 does not fix Content metric semantics, add Ads, create receipts, or change Publishing Guard. The historical `meta_read_or_persistence_error` cannot identify yesterday's root cause without runtime evidence.

## Phase 1 — PostgreSQL and Facebook Content (15/10/2026)

Content retains the existing UTC reporting window. Offset-aware `created_time` values are now converted to UTC before assigning publication dates; this is not a switch to Vietnam business-day reporting. Missing/invalid post identity or timestamps, malformed counters, conflicting duplicate posts and malformed pagination fail closed with safe data diagnostics. Missing optional counters remain `null`; valid zero counters remain zero. Identical posts repeated across pages count once. Reactions/comments/shares remain lifetime observations and never become daily engagement, reach, views or follower KPIs.

A fully paginated `data: []` is a successful empty observation: snapshot/job step `no_data`, no post entries and `posts_published=0` on each requested UTC day. Those zero publication counts describe only the accessible Page posts returned for that period; they do not attest complete Page visibility or source verification. A missing `data` field, malformed response or API failure is a failed sync, not an empty observation. To retain the existing metric-reader contract, `latest_available_date` and the successful watermark describe the completed daily observation window, including zero-post days. The separate snapshot field `latest_post_date` is the latest returned post's UTC day, or `null` for an empty result. Neither field proves full Page visibility or source verification.

After all pages have been fetched and the snapshot validated, Content persistence replaces only that client's selected Page/post metric rows within the requested dates, in the same transaction as snapshot insertion and finalization. Thus posts absent from a successful resync no longer remain in current metrics. Other assets/dates and earlier source snapshots are preserved. Any write or commit failure rolls back this replacement. A new successful sync intentionally has a new source snapshot; idempotency means stable current metric identities/counts, not deleting sync history.

Page asset selection now discovers only Pages. For an isolated Content discovery request, use the existing endpoint with `GET /api/meta/reporting/assets?source=facebook_content`; it never requests Ad Accounts even when the grant also contains `ads_read`. Page-only grants continue to support Content sync without `ads_read`. The unfiltered discovery endpoint/UI still requests both available source types and can fail if Ads discovery fails; use the Content filter for the controlled trial. No Ads reporting feature or Publishing Guard was changed in this phase.

### Test environment and acceptance

The Phase 1 PostgreSQL environment is an independently named `postgres:16` container with a dedicated network, a random localhost-only port and tmpfs data storage, with no runtime mounts. Tests receive `TEST_DATABASE_URL` and `TEST_META_POSTGRES=1` only in their process. Database identity/version and Docker mounts/network must be checked before enabling these flags. Providers are mocked and unmocked HTTP is blocked; no live Meta conclusion follows from these tests.

Run the Meta suite with those process-only variables pointing to the verified disposable database:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p 'test_meta*.py' -v
```

`PostgresMetaDiagnosticsTests` covers actual uniqueness violations (`23505`), deferred foreign-key violations at commit (`23503`), preservation of previous metrics/snapshots/watermarks/connection timestamps after those failures, repeated syncs, scoped empty replacement, malformed provider data, Page-token failure and snapshot rejection. OAuth PostgreSQL cases are in `PostgresMetaTest`. A skipped case is never a pass. The local evidence logs are under ignored `test-results/phase1-*.txt`.

Final local validation on 15/10/2026: **425 Python PASS, 0 FAIL, 0 SKIP**, including **121 Meta cases** and, within those, **27 actual PostgreSQL Meta cases** (17 OAuth + 10 diagnostics/persistence). These counts overlap and must not be added together. UI: **69 PASS, 0 FAIL, 0 SKIP**; JS/Python syntax and `git diff --check` passed. Evidence: `test-results/phase1-full-python.txt`, `test-results/phase1-ui-tests.txt`. An intermediate run exposed four KPI/preview regressions when `latest_available_date` was changed to the last post date; the final implementation preserves that field's coverage contract and uses `latest_post_date` separately. No Meta API was contacted and no historical runtime root cause was confirmed.

Before a separately approved live trial, start an isolated Admin with a separate test database, data directory, encryption key and port; use `client_meta_sandbox` without the primary-client override. Authenticate through the existing Admin flow and use normal CSRF protections. Connect an authorized Page grant, discover with the Content filter, select one Page and sync a short completed UTC period. Do not copy runtime `.env`, credentials or database into that environment.

Acceptance requires matching job/sync IDs, a final `sync_complete` event, a persisted unverified snapshot and expected Page post counts checked against the accessible source. Repeat the same period and verify current metric counts do not multiply and the prior snapshot remains unchanged. For empty results, require `no_data` and unknown engagement metrics. For failures, inspect the first failed stage and confirm previous good metrics/snapshots remain intact. App-specific permissions, actual response shapes and the historical production failure remain unverified until that approved trial. A live API success still does not create a verification receipt or authorize publication.

## OAuth callback diagnostics (16/10/2026)

The `meta_oauth` event records a random attempt ID, the last callback stage and the outcome. It never logs callback code/state, tokens, App Secret, raw provider responses or exception messages. Numeric HTTP/Graph error metadata and validated SQLSTATE are allowlisted when available. State cleanup failures have a separate event with the same attempt ID and do not replace the original failure.

An `expiration_validation` failure additionally records `expiration_field` (`expires_at` or `data_access_expires_at`) and `expiration_reason` (`missing`, `invalid_type`, `out_of_range` or `past`; older diagnostics also emitted `zero`). Values outside the allowlists become `unknown`; the provider value itself is never logged. An older event without these fields cannot distinguish those causes. OAuth diagnostics do not establish the cause of a historical Content sync failure.

### Explicit zero expiry

Sandbox callbacks on 16/10/2026 reached expiry validation with `expires_at=0` after token validity, app and USER identity checks passed. The former validator rejected this sentinel. Facebook's [archived official PHP SDK metadata validator](https://github.com/facebookarchive/php-graph-sdk/blob/5.x/src/Facebook/Authentication/AccessTokenMetadata.php) also treats zero separately from a dated expiry (`castTimestampsToDateTime`, `validateExpiration`).

The callback now preserves an explicit numeric zero in the encrypted token record as **no scheduled token expiry**, not a date in 1970 or an invented future date. `/api/meta` returns `expires_at=null` with `expires_at_unbounded=true` for that case; existing dated grants retain their ISO date. Missing required expiry, booleans, strings, malformed or elapsed timestamps remain invalid. Optional data-access expiry may be absent/zero; a provided date is still enforced independently, including for zero-expiry tokens. App, token validity/type, identity, scope, session/state and CSRF checks still apply. No scheduled expiry is not a promise that access cannot be revoked; the UI continues to state that status reflects the saved grant rather than a live revocation check. No schema migration is needed.

For separate Admin instances on the same localhost, set a distinct `ADMIN_SESSION_COOKIE_NAME` in the sandbox process environment. The default remains `kdh_session`. A separate cookie namespace prevents sessions at different ports from overwriting each other while retaining session binding, HttpOnly, SameSite, authorization and CSRF checks.
