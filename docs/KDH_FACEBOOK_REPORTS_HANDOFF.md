# Facebook Content + Facebook Ads — Admin → New handoff

## Scope and acceptance boundary

Admin implementation, offline fixtures and two separate Report Bundles. No live
Meta/Google request, sandbox database mutation, Docker deployment or New edit was
performed in this implementation run. Admin fixture acceptance is **not** New E2E
acceptance. The current VIO historical snapshots remain unverified; no receipt is
backfilled from the earlier diagnostic audit.

Existing identifiers are preserved:

| Source | Report type | Bundle section | Asset type |
|---|---|---|---|
| `facebook_content` | `facebook-content` | `facebook_content` | `facebook_page` |
| `facebook_ads` | `facebook-ads` | `facebook_ads` | `facebook_ad_account` |

The implementation uses the existing Marketing Dataset, review, candidate,
approval, release snapshot, report revision and Viewer ACL services. There is no
parallel publication endpoint. Meta v1 accepts one explicit client, one asset and
one exact period (1–90 completed days). Comparisons are explicitly refused with
`meta_comparison_unsupported`; there is no implicit previous-period fetch.

## Actual API endpoints

Admin APIs require an active Admin application session. Mutations also require
the existing `X-KDH-Request: 1` and `X-CSRF-Token` protections. Provider credentials
are never accepted as report inputs and never forwarded to New.

| Method/path | Purpose / inputs |
|---|---|
| `GET /api/meta/reporting/assets?source=facebook_content` | Existing Content discovery; sandbox automatic navigation remains Content-only |
| `GET /api/meta/reporting/assets?source=facebook_ads&external_id=act_123` | Explicit lookup of exactly one authorized Ad Account; does not enumerate other accounts |
| `POST /api/meta/reporting/assets` | Existing selection: `source`, `external_id`, `enabled`; Ads selection rechecks that exact account |
| `POST /api/meta/reporting/sync` | Existing queue contract: `asset_id`, `start`, `end`; **not invoked live in this run** |
| `GET /api/meta/reporting/kpis/{asset_id}?start=...&end=...` | Existing period KPIs plus additive `snapshot_metrics` for new-contract snapshots |
| `GET /api/meta/reporting/preview?asset_id=...&start=...&end=...` | Existing sandbox preview; persisted snapshots only |
| `POST /api/marketing/datasets` | For Meta require explicit `client_id`, `source`, `asset_id`, `start`, `end`; no fallback to KinderHealth |
| `GET /api/marketing/datasets/{id}/review` | Snapshot assessment and current review |
| `POST /api/marketing/datasets/{id}/review` | `decision`, `note`, `expected_sha256`; internal review does not verify source |
| `POST /api/marketing/datasets/{id}/release-candidates` | `expected_sha256`, `expected_review_id` |
| `GET /api/marketing/release-candidates/{id}/source-check` | Server-side snapshot/receipt/grant/lineage verification; never calls Meta |
| `POST /api/marketing/release-candidates/{id}/approval` | Existing decision/note and expected Candidate, Dataset and review hashes/IDs |
| `POST /api/marketing/release-candidates/{id}/release-snapshots` | `expected_approval_id`, `expected_candidate_sha256`; creates a new immutable release Dataset |
| `POST /api/report-bundles` | Explicit client, name, dates, default section and release Dataset ID |
| `POST /api/report-bundles/{report_id}/revisions` | New revision, preserving captured historical data |
| `POST /api/report-bundles/{report_id}/revisions/{revision}/publish` | Existing explicit `status: provisional|final` gate; no automatic publication |
| `POST /api/report-bundles/{report_id}/access` | Existing Admin grant: user, minimum/maximum revision, active flag |

Read contracts:

* `GET /api/report-bundles/{report_id}?revision=N`: Admin session.
* `GET /api/internal/v1/report-bundles/{report_id}?revision=N`: backend service
  Bearer authentication, published revisions only. This is a trusted internal
  service endpoint, **not** a Viewer authorization check.
* `GET /api/internal/v1/viewer/report-bundles/{report_id}?revision=N`: backend
  service Bearer plus `X-KDH-Viewer-Session`; validates Viewer session, active
  account, client/report grant and revision range. New must use the authorized
  Viewer path for customer requests. Never expose service credentials to JS.

The existing Admin → New handoff/session mechanism is retained. A valid service
credential alone must not substitute for the customer's Viewer ACL.

## Bundle schema and two sanitized examples

Outer `schema_version` remains **`1.0`**. Source payload adds
`contract_version: meta-reporting-v1`. The examples below were generated through
the real Admin routes with mocked provider transport and disposable SQLite:

* [Facebook Content fixture Bundle](fixtures/facebook_content.bundle.json)
* [Facebook Ads fixture Bundle](fixtures/facebook_ads.bundle.json)

They contain synthetic test assets and arbitrary test report/review identifiers,
not VIO business evidence. The release seal is replaced by
`SANITIZED_FIXTURE_SEAL_NOT_VALID_FOR_PUBLICATION`; these files must never be
imported as valid release approval evidence. No provider or session credentials
are present.

Important paths in **both** contracts:

| Field path | Meaning / New binding |
|---|---|
| `report.id`, `report.revision`, `report.status` | Pin the authorized report/revision; do not silently choose another revision |
| `client.id` | Must match authorized client; never default to KinderHealth |
| `period.start`, `period.end`, `comparison` | Reporting dates; Meta v1 comparison is null |
| `navigation.sections`, `default_section` | Render only sections actually included |
| `sections[S].report_type` | `facebook-content` or `facebook-ads` |
| `sections[S].data.sources[S]` | Normalized, frozen source payload |
| `...identity.external_id`, `...identity.asset_type` | Exact Page or Ad Account identity |
| `...asset_id`, `...snapshot_id`, `...snapshot_sha256`, `...sync_run_id` | Source identity and evidence references |
| `...fetched_at`, `...timezone` | Actual fetch time and source reporting timezone |
| `...kpis[]` | Source-specific KPI contract below; use status/coverage, never truthiness for zero |
| `...daily`, `...entries` | Frozen daily rows and posts/campaigns; do not sum all entity levels together |
| `...provenance` | Graph version, provider and sanitized grant/asset observation metadata |
| `sections[S].data.evidence[]`, `.release` | Exact approved evidence, reviewer, hashes, approval and release version |

Every KPI exposes `key`, `metric_id`, `label`, `unit`, `currency`, `value`,
`status`, `coverage {available, expected, unit}`, `observed_sum`, `aggregation`,
`grain`, `fetched_at`, `attribution`, `provider`, `verified`, `publishable`.
Money KPI `spend.value` is an exact decimal **string**. Other implemented values
are numeric or null. Do not parse decimal money into binary floats for totals.
For Meta date boundaries use the source payload's `timezone`, not the client's
display timezone; for example, a Vietnam client can have a UTC Content period.

## Facebook Content contract

| KPI key | Unit / grain | Rule |
|---|---|---|
| `posts_published` | count / day | Count unique Page post IDs whose creation instant is in the UTC period |
| `engagements` | count / day | Null/no_data; no genuine daily interaction source implemented |
| `reactions_lifetime` | count / snapshot | Sum across distinct posts at this fetch, only complete when all posts supply the field |
| `comments_lifetime` | count / snapshot | Same rule, independent of reactions/shares availability |
| `shares_lifetime` | count / snapshot | Missing shares stay missing; no zero imputation |

UTC interval is `[start 00:00Z, day-after-end 00:00Z)`. Daily post rows include
genuine zero-publication days. Daily-record coverage does not mean posts were
published every day. Counters are lifetime **as of fetched_at**, for posts created
in the selected period; they are not interactions occurring during that period.
An authenticated, completely paginated empty Page response can verify a zero post
count. The release records `ingestion_status=no_data` and `status=ready` for that
completed observation; lifetime and period interaction KPIs stay null/unverified.

When some posts omit a counter, `value=null`, `status=partial`, and `observed_sum`
is only the sum on observed posts. Render it, if desired, as “sum on X/Y posts
with data”, never as the complete KPI. Missing optional values are not marked
verified/publishable even inside a valid release. `engagements` always remains
separate. Snapshot IDs must not be pooled to sum lifetime counters repeatedly.

## Facebook Ads contract

Account reads and Insights requests target the exact `act_...` identity.
Currency and account timezone come from that account; `report_timezone` equals
`account_timezone`. Daily API dates remain account-local dates, not UTC dates
relabelled after retrieval. The account-local reporting day must have ended.

| KPI key | Unit | Aggregation / availability |
|---|---|---|
| `spend` | currency | Exact Decimal sum, serialized decimal string; null unless full daily coverage and every spend exists |
| `impressions`, `clicks` | count | Sum same-account daily values; clicks means all clicks |
| `link_clicks` | count | Sum `inline_link_clicks` if present every day; no fallback to all clicks |
| `ctr` | ratio | Total clicks / total impressions; fraction, not percent (0.1 → 10% in UI) |
| `cpc` | currency | Total exact spend / total clicks |
| `cpm` | currency | 1000 × total exact spend / total impressions |
| `reach`, `frequency` | count / number | Period values null; daily reach may be stored but never summed into unique period reach |
| `leads`, `results` | count | Exact `actions[action_type=lead].value`; not a fallback union of lead aliases or campaign objectives |
| `cost_per_result` | currency | Total spend / exact lead count |
| `purchases`, `roas` | count / number | Explicitly unavailable; purchase/value attribution contract not implemented |

Ratios are recalculated from period denominators, never summed or averaged from
daily ratios. Zero denominator gives null. Missing lead/action rows give null,
not zero; explicit provider zero remains zero. Results is deliberately labelled
`action_type=lead`; no generic goal-dependent result claim is made.

Conversion query metadata is fixed and persisted in v1:

```json
{
  "action_report_time": "impression",
  "action_attribution_windows": ["7d_click", "1d_view"],
  "use_account_attribution_setting": false,
  "use_unified_attribution_setting": false,
  "result_action_type": "lead"
}
```

Changing this policy requires a new reviewed contract, not mixing existing
snapshots. Account/currency mismatches, contradictory duplicates, malformed
numbers and dates outside the period are rejected. Identical duplicate rows are
deduplicated. Missing days are partial and block core-metric release; they are
not invented as zero-spend days. Campaign rows are detail, never additional
account totals. Unsupported catalog metrics are not fabricated.
Day metrics with some available days expose `status=partial` and their actual
coverage, while their complete-period `value` stays null.
An extraction can finish successfully while its source payload remains partial.
Incomplete Ads dates or missing core metrics do not advance the complete-period
watermark and cannot pass source verification. Job success is not release approval.

## Empty Ads data and operational states

The read contract keeps these states separate:

* A completed Graph request with HTTP 2xx, an object body, a complete pagination
  chain, and `data: []` is a successful empty observation. The reader normalizes
  it to `status=no_data`; period KPI values stay `null` and metric availability
  stays `no_data`. This says only that this exact account query and date range
  returned no rows.
* A missing/non-list `data` field or malformed paging is `meta_bad_response`.
  A denied scope is `meta_ads_permission`; Graph permission/token errors and
  transport failures remain errors and cannot be normalized to `no_data`.
  Implementation caveat: `_page_rows` currently retries any `SourceError` up to
  three attempts, including non-transient Meta permission/token failures. The
  error stays an error, but retry classification should be narrowed before the
  next live Ads operation.
* Before an asset is selected, the Admin returns no selected asset (or rejects a
  KPI request for an unselected asset). After selection but before a sync, sync
  history is empty, KPI freshness has no `latest_sync_status`, and
  `snapshot_metrics` is `null`. That is not evidence that an Insights request
  returned an empty list.
* While the KPI request is pending, no result contract exists yet. The current
  UI disables the clicked button but does not show a dedicated loading message.
  The modal also omits `latest_sync_status`, so use **Lịch sử Sync** to tell an
  unrun asset from a completed empty observation. This is a UI feedback gap; it
  does not change stored metrics or source verification.

For a genuinely completed empty Ads sync, the normal worker may persist a
`no_data` snapshot and an adapter receipt bound to that actual fetched payload,
with a successful run/job and zero normalized rows. The receipt proves only the
server-side adapter path for that request; it does not prove performance data
or publication eligibility. The core Ads metrics (`spend`, `impressions`, and
`clicks`) remain unavailable, so source verification must report
`required_metric_missing` and block approval/release. The generic Bundle 1.0
envelope preserves the finalized Dataset JSON, but the existing guard must not
produce a publishable Ads Bundle from this empty source.

A diagnostic report or screenshot is not a sync input. No public receipt or
attestation creation endpoint exists; never derive daily metrics, snapshots,
receipts, or attestations from diagnostic text. Historical Content snapshots
that lack `meta-reporting-v1` lineage cannot be retro-sealed from an audit. A
new, authorized Content sync must create fresh worker provenance before the
existing source-check, current Dataset review, separate release approval, and
publication gates can be evaluated.

Field/parameter names were checked against Meta's official SDK definitions:
[AdsInsights](https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/adobjects/adsinsights.py)
and [AdAccount Insights](https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/adobjects/adaccount.py).
This documentation check is not a live Marketing API acceptance test.

## Verification and publication policy

New reader results carry a server-only adapter receipt bound to the sanitized
payload hash. The worker writes normalized rows, snapshot, terminal run/job state
and source attestation in the same transaction. No public receipt-creation API
exists. Receipts attest the authenticated application adapter path; they are not
signatures issued by Meta or an independent external audit.

Source-check requires all of the following:

1. Exact client/source/asset/Page-or-account identity and active client/asset.
2. Matching connected OAuth account, current stored grant, required scopes,
   expiry, and the grant version observed during ingestion. Secrets are decrypted
   only in server memory; provider revocation is not probed at review time.
3. Exact successful `meta_sync` job/run and requested dates; no demo data.
4. Valid sealed attestation and snapshot hash, matching persisted Page/post or
   account/campaign rows and source hashes.
5. Latest exact-period snapshot; resync or changed normalized data invalidates
   stale review projections. Seven-day maximum evidence age before release or
   publication, with future/missing timestamps rejected.
6. Complete required metrics: Content post counts; Ads spend, impressions and
   clicks. Missing optional metrics remain explicitly unavailable/partial and
   cannot become verified claims.
7. UTC Content or account-timezone Ads semantics, with fixed Ads attribution and
   asset currency matching the source payload.
8. Active Admin reviewer, unchanged Dataset/Candidate hashes and current review,
   then separate explicit release approval. Release creation is not publication.
9. Existing release seal/registry/approval checks on publication, then report
   revision ACL on Viewer reads.

Published reads validate the captured release seal and do not reread mutable
source data. Later sync, grant changes or evidence expiry must not rewrite a
published revision. A new revision requires the relevant current gates again.
No schema migration is added; existing `source_attestations` and Marketing tables
are reused. Production/sandbox deployment is a separate approved operation.

## New implementation work and integration tests

New must bind `facebook_content` and `facebook_ads` separately to their frozen
source `kpis` contract, retaining legacy mappings for other report types. The
dashboard must show account/Page, dates, timezone, snapshot fetch time, currency,
attribution for conversions, coverage and unavailable/partial warnings. Do not
call Meta, read Admin PostgreSQL or accept provider credentials in New.

Read-only inspection of the current New tree identified these concrete follow-ups
(none were edited):

* `app/mappers/bundle.py`: it currently reads both `totals` and `kpis`; for
  `meta-reporting-v1`, prefer the qualified `kpis` entries and avoid duplicate
  metric IDs or choosing legacy float spend over canonical decimal spend.
* `app/schemas/bundle_view.py`: carry KPI availability, currency, grain, coverage,
  snapshot identity/fetch time and attribution into the presentation model.
* `app/mappers/dashboard.py`: the current Content cards still expect period
  engagements/reach/followers; introduce separate lifetime bindings. Ads cards
  currently expect `cpl`; this contract supplies `cost_per_result` for exact
  `lead`, so bind that explicitly without manufacturing unrelated result types.
* Facebook Content/Ads templates and partials: show missing/partial warnings,
  UTC/account timezone and decimal currency without changing report filters into
  live API queries. Keep the Viewer repository's authorized endpoint and pinned
  revision behavior in `app/repositories/viewer.py`.

Use the two fixture Bundles to test rendering and then run actual two-application
E2E with isolated authorized test revisions:

* Correct source/section/client; wrong-client payload rejected.
* Content zero post days, period engagements null, lifetime separated, missing
  shares partial and observed sum explicitly qualified.
* Ads decimal currency, ratio formatting, denominator zero, unavailable reach,
  conversion attribution and account timezone; no currency/attribution mixing.
* Viewer without grant, revoked session/grant, wrong client and out-of-range
  revision denied; Viewer cannot review, approve, sync or publish.
* Exact revision pinned across reload/navigation; draft hidden; published source
  remains immutable after later ingestion.
* Marketing unverified snapshots remain internal-only, and SEO/other sections
  keep existing behavior.

## Remaining live acceptance gates

* Phase 6 confirmed access to VIO Ad Account `849921003837218` for
  `client_meta_sandbox`, with a valid User grant and `ads_read`. The account
  metadata returned VND and `Asia/Ho_Chi_Minh`. This permission is separate from
  VIO Page access and does not establish business ownership beyond the operator
  authorization already supplied.
* The bounded Insights query for 2026-10-15 through 2026-10-17 returned an empty
  list. Ads performance metrics remain **NOT ACCEPTED**. Compare the same account,
  dates, timezone, account-level scope and columns manually in Ads Manager; if a
  future test period is needed, select a short completed period known to contain
  rows. Do not widen the period automatically or create an ad to get data.
* Phase 5B reports the new Admin image deployed to the isolated 8191 sandbox.
  Verify runtime against that report before future live operations; this does not
  imply live Ads metrics, review, or release acceptance.
* Existing VIO snapshots cannot be automatically verified retroactively. Any new
  bounded Content ingestion needed for adapter evidence requires explicit
  approval; do not repeat the old 28-day sync automatically.
* For either source, complete current source-check evidence, an authorized
  internal review, separate release approval, publication guard and report
  revision ACL. No old VIO Content snapshot was verified or released here.
* Implement/test New bindings and execute actual Admin → New Viewer E2E. Until
  then: **New integration/E2E NOT TESTED**.

## Offline validation commands

```powershell
npm.cmd test
.\.venv\Scripts\python.exe -B tests/run_offline.py test_facebook_bundles.py
.\.venv\Scripts\python.exe -B tests/run_offline.py
Get-ChildItem static/*.js | ForEach-Object { node --check $_.FullName }
git diff --check
```

The offline runner blocks socket and PostgreSQL connections, ignores local `.env`
and clears provider configuration. SQLite fixtures own temporary directories.
PostgreSQL-specific suites skip; no PostgreSQL runtime validation is claimed.

Validation results on 2026-10-17:

| Check | Result |
|---|---|
| `npm.cmd test` | 84 PASS, 0 FAIL, 0 SKIP |
| Offline Python discovery | 460 cases: 356 PASS, 0 FAIL, 104 SKIP (disposable PostgreSQL required) |
| Focused `test_facebook_bundles.py` | 16 PASS, including final release evidence metadata checks |
| JavaScript syntax checks | PASS |
| `git diff --check` | PASS |
| Two generated fixture Bundles | PASS: client/period/source identity, qualified KPIs, sanitized seals |
| Live Ads / runtime PostgreSQL / New E2E | NOT TESTED; live Ads authorization remains BLOCKED |

The regression run found a legacy Facebook Ads Dataset compatibility failure;
the new strict Meta section guard was limited to Marketing datasets, and the
legacy regression now passes. The final focused run also verifies the released
KPI evidence state is `provider_origin_confirmed`, while optional unavailable
metrics remain unverified. No skipped test is counted as a pass.

Phase 6 evidence recorded on 2026-10-18 is outside the repository at
`%LOCALAPPDATA%\KDH-Meta-Acceptance-Evidence\phase6-20261018-act849921003837218`.
The exact account permission check passed; four read-only API requests returned
HTTP 200, but the 2026-10-15–17 Insights result was empty. No selection, sync,
snapshot, receipt, or attestation was created from that diagnostic. Offline
empty-data contract checks added in this continuation:

| Check | Result |
|---|---|
| Reader/normalizer (`test_meta_reporting.py`) | 23 PASS |
| Admin routes (`test_meta_reporting_routes.py`) | 14 PASS |
| Dataset/review/publication guard (`test_facebook_bundles.py`) | 17 PASS |
| UI (`npm.cmd test`) | 86 PASS |
| Live Ads metrics / manual Ads Manager comparison | NOT ACCEPTED / PENDING |
| Admin → New E2E | NOT TESTED |

## Implementation files and Git boundary

Focused implementation files (some also contained unrelated local edits before
this work; the full `git diff` is not solely this task):

* Source semantics/provenance: `kdh/meta_contract.py`, `kdh/meta_marketing.py`,
  `kdh/meta_reporting.py`, `kdh/meta_reporting_worker.py`,
  `kdh/meta_reporting_routes.py`, `kdh/metric_catalog.py`.
* Existing lifecycle integration: `kdh/marketing_dataset.py`,
  `kdh/marketing_preview.py`, `kdh/marketing_review.py`,
  `kdh/marketing_source_check.py`, `kdh/marketing_publication.py`,
  `kdh/report_bundles.py`.
* UI: `static/app.js`, `static/meta_reporting_ui.js`, `tests/ui.test.js`.
* Python fixtures/validation: `tests/test_facebook_bundles.py`,
  `tests/run_offline.py`, `tests/test_meta_reporting.py`,
  `tests/test_meta_reporting_routes.py`, `tests/test_meta_worker_integration.py`.
* Handoff: this document and the two JSON files linked above.

Branch remains `feat/seo-composite-release`, HEAD
`664efbc561b401d901947437c63df87348d81437`. No commit, checkout, reset, stash or
source-wide formatting was performed. A durable SHA-256 baseline of 164 files was
recorded at the resume checkpoint; no baseline file was deleted, and subsequent
hash changes were limited to task files. This checkpoint comparison does not
claim a reconstructable hash comparison against the beginning of earlier turns.
Existing SEO modules and unrelated modified/untracked files remain present.
