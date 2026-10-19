# TikTok Ads integration scaffold

## Current Admin contract

TikTok Ads is represented as the planned source `tiktok_ads`, provider `tiktok`,
asset type `tiktok_ad_account`, report type/section key `tiktok`, and metric
catalog group `tiktok_ads`. The platform registry marks it `planned`; the Admin
UI presents a disabled setup path. No TikTok OAuth, account discovery, sync
worker, source receipt, verification adapter, or live Dataset/Report Bundle
generation is currently implemented. A registry entry or metric catalog entry
does not mean the source is connected or available.

## Requirements before implementation can claim live support

1. Add a backend-only TikTok Business authentication adapter using documented
   permissions selected for the approved read use case. Keep credentials out of
   browser responses and logs.
2. Add an explicit, user-initiated advertiser-account discovery and selection
   flow. Persist the selected account with the configured `client_id`, provider,
   asset type, external account ID, account currency, and account timezone.
   Never infer ownership from an account name or silently select an account.
3. Add a read-only sync worker using bounded date windows, pagination, and the
   provider's rate-limit rules. Persist actual sync provenance and a
   source-specific receipt; do not reuse the Meta receipt contract without an
   explicit compatibility definition.
4. Define metric semantics from actual provider responses before exposing a
   KPI: currency and decimal precision for spend; provider date grain and
   timezone; click/impression denominators for derived rates; reach/frequency
   non-additivity; and action/attribution metadata for conversion results.
   Missing or unsupported fields remain unavailable/null and are not converted
   to zero.
5. Add source verification that checks client and advertiser identity, granted
   account scope, sync/job lineage, receipt/snapshot integrity, freshness,
   period coverage, timezone, and missing-metric semantics. Keep Dataset,
   review, approval, and Publication Guard requirements intact.
6. Add offline provider fixtures and tests for permission failure, account
   ownership, pagination, empty responses, partial fields, duplicate records,
   date boundaries, currency, attribution, verification failure, and bundle
   serialization. Live acceptance requires a separately authorized advertiser
   account and a short completed reporting window.
7. Confirm the published Bundle contract with KDH-Report-New before claiming
   downstream display support. No New-side contract or end-to-end behavior is
   asserted by this scaffold.

Until these requirements are implemented and accepted, keep Connect, discovery,
sync, Dataset, and publication actions unavailable for TikTok Ads. Do not create
sample advertiser identities, sync runs, metrics, receipts, or bundles.
