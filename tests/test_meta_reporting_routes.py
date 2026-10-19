"""HTTP integration tests for Meta Reporting; no actual Meta or production DB.

Run:
    python -m unittest discover -s tests -p test_meta_reporting_routes.py -v

Creates a temporary SQLite DB and replaces Meta with a deterministic fake
when Flask is constructed. No external requests or production database writes.
"""

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from kdh.core import digest, now, pack, uid
from kdh.platform_data import PlatformData


class FakeMeta:
    """Return deterministic provider responses; never contact Meta's servers."""

    client_id = "client_meta_sandbox"

    def __init__(self, store, config, cipher):
        self.store = store
        self.config = config
        self.cipher = cipher
        self.empty_ads = False
        self.calls = []
        self.scopes = ['pages_show_list', 'pages_read_engagement', 'ads_read']

    def info(self):
        return {"connected": True, "configured": True, "has_connection": True,
                "client_id": self.client_id, "scopes": list(self.scopes)}

    def read(self):
        return {"account_id": "999123", "access_token": "FAKE_USER_TOKEN", "scopes": self.scopes}

    def call(self, method, path, *, token=None, params=None):
        if method != "GET":
            raise AssertionError("Only read requests are allowed in this fake")
        if "access_token" in (params or {}):
            raise AssertionError("Token must not be included in URL params")
        self.calls.append((path, (params or {}).get("level")))
        if path == 'act_123':
            return {'id': 'act_123', 'name': 'Sandbox Ads', 'currency': 'VND', 'timezone_name': 'Asia/Ho_Chi_Minh'}
        if path.startswith('act_') and '/' not in path:
            from kdh.core import Problem
            raise Problem('Fixture account outside authorization.', 403, 'meta_asset_not_permitted')

        if path == "me/adaccounts":
            return {"data": [{
                "id": "act_123", "name": "Sandbox Ads", "currency": "VND",
                "account_status": 1, "timezone_name": "Asia/Ho_Chi_Minh"
            }]}
        if path == "me/accounts":
            return {"data": [{
                "id": "1234", "name": "Sandbox Page", "tasks": ["ANALYZE"],
                "access_token": "FAKE_PAGE_TOKEN"
            }]}
        if path == "act_123/insights":
            if self.empty_ads:
                return {"data": []}
            if (params or {}).get("level") == "account":
                return {"data": [
                    {
                        "date_start": "2026-09-01", "spend": "100.75",
                        "impressions": "120", "clicks": "10", "reach": "90",
                        "actions": [{"action_type": "lead", "value": "2"}],
                    },
                    {
                        "date_start": "2026-09-02", "spend": "20.25",
                        "impressions": "50", "clicks": "4", "reach": "30",
                        "actions": [{"action_type": "lead", "value": "1"}],
                    },
                ]}
            if (params or {}).get("level") == "campaign":
                return {"data": [{
                    "date_start": "2026-09-01",
                    "campaign_id": "campaign_1", "campaign_name": "Sandbox Campaign",
                    "spend": "100.75", "impressions": "120", "clicks": "10",
                }]}
        if path == "1234/posts":
            return {"data": [{
                "id": "1234_1", "created_time": "2026-09-01T03:00:00+0000",
                "reactions": {"summary": {"total_count": 4}},
                "comments": {"summary": {"total_count": 2}},
                "shares": {"count": 3},
            }]}
        raise AssertionError("Unexpected provider endpoint: " + path)


class MetaReportingHttpTests(unittest.TestCase):
    # PostgreSQL subclasses supply only a disposable, schema-scoped test URL.
    database_url = ''
    START = "2026-09-01"
    END = "2026-09-02"

    def setUp(self):
        network = patch('requests.sessions.Session.request', side_effect=AssertionError('External HTTP disabled in tests'))
        network.start()
        self.addCleanup(network.stop)
        self.temp = tempfile.TemporaryDirectory(prefix="kdh_meta_http_")
        self.addCleanup(self.temp.cleanup)

        # Default remains SQLite regardless of workstation DATABASE_URL.
        from kdh.app import create_app

        with patch.dict(os.environ, {"META_REPORTING_ALLOW_PRIMARY_CLIENT": "0"}):
            with patch("kdh.app.Meta", FakeMeta):
                self.app = create_app({
                    "TESTING": True,
                    "DATA_DIR": self.temp.name,
                    "DATABASE_URL": self.database_url,
                    "DATABASE_BACKEND": "postgres" if self.database_url else "sqlite",
                    "ENCRYPTION_KEY": self.test_encryption_key if self.database_url else "",
                    "JOB_MODE": "request",
                    "COOKIE_SECURE": False,
                    "APP_URL": "http://localhost",
                    "INITIAL_ADMIN_EMAIL": "",
                    "INITIAL_ADMIN_PASSWORD": "",
                    "META_CLIENT_ID": "client_meta_sandbox",
                })

        self.assertEqual(self.app.extensions["store"].postgres, bool(self.database_url))
        self.store = self.app.extensions["store"]
        self.meta = self.app.extensions["meta"]
        self.platform = PlatformData(self.store)
        self.client = self.app.test_client()

        stamp = now()
        self.store.execute(
            """INSERT INTO clients
               (id,name,slug,timezone,active,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?)""",
            ("client_meta_sandbox", "Meta HTTP Tests", "meta-http-test",
             "Asia/Ho_Chi_Minh", 1, stamp, stamp),
        )
        self.admin_email = "http-test-admin@example.invalid"
        self.admin_password = "temporary-local-test-password"
        self.admin_id = uid()
        self.store.execute(
            """INSERT INTO users
               (id,email,name,password,role,allowed,active,created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (self.admin_id, self.admin_email, "HTTP Test Admin",
             generate_password_hash(self.admin_password), "admin", "[]", 1, stamp),
        )
        self.connection_id = self.platform.upsert_connection(
            client_id="client_meta_sandbox", provider="meta",
            external_account_id="999123", account_name="Sandbox Fake OAuth",
        )

        # Use the real Flask login endpoint to obtain cookie + CSRF.
        login = self.client.post(
            "/api/auth/login",
            json={"email": self.admin_email, "password": self.admin_password},
            headers={"X-KDH-Request": "1"},
        )
        self.assertEqual(login.status_code, 200, login.get_data(as_text=True))
        self.csrf = login.get_json()["csrf"]

    def post(self, route, payload, *, csrf=True):
        headers = {"X-KDH-Request": "1"}
        if csrf:
            headers["X-CSRF-Token"] = self.csrf
        return self.client.post(route, json=payload, headers=headers)

    def select_asset(self, source, external_id):
        response = self.post("/api/meta/reporting/assets", {
            "source": source, "external_id": external_id, "enabled": True,
        })
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()["asset_id"]

    def sync_asset(self, asset_id):
        response = self.post("/api/meta/reporting/sync", {
            "asset_id": asset_id, "start": self.START, "end": self.END,
        })
        self.assertEqual(response.status_code, 202, response.get_data(as_text=True))
        job_id = response.get_json()["job_id"]
        self.assertTrue(self.app.extensions["worker"].run_one(job_id))
        job = self.store.one("SELECT status,error FROM jobs WHERE id=?", (job_id,))
        self.assertEqual(job["status"], "succeeded", job)
        return job_id

    def test_01_requires_authentication_and_csrf(self):
        anonymous = self.app.test_client()
        unauthenticated = anonymous.get("/api/meta/reporting/assets")
        self.assertEqual(unauthenticated.status_code, 401)

        without_csrf = self.post("/api/meta/reporting/assets", {
            "source": "facebook_ads", "external_id": "act_123",
            "enabled": True,
        }, csrf=False)
        self.assertEqual(without_csrf.status_code, 403)

    def test_02_discover_assets_without_exposing_tokens(self):
        response = self.client.get("/api/meta/reporting/assets")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        data = response.get_json()
        self.assertEqual(data["client_id"], "client_meta_sandbox")
        self.assertEqual(data["discovered"]["facebook_ads"][0]["id"], "act_123")
        self.assertEqual(data["discovered"]["facebook_content"][0]["id"], "1234")
        body = response.get_data(as_text=True)
        self.assertNotIn("FAKE_USER_TOKEN", body)
        self.assertNotIn("FAKE_PAGE_TOKEN", body)
        self.assertEqual(data["selected"], [])

    def test_03_reject_assets_outside_meta_grant(self):
        invalid = self.post("/api/meta/reporting/assets", {
            "source": "facebook_ads", "external_id": "act_98765",
            "enabled": True,
        })
        self.assertEqual(invalid.status_code, 403, invalid.get_data(as_text=True))
        missing = self.post("/api/meta/reporting/sync", {
            "asset_id": "not-an-asset", "start": self.START, "end": self.END,
        })
        self.assertEqual(missing.status_code, 403, missing.get_data(as_text=True))

    def test_04_ads_queue_worker_history_and_kpis(self):
        asset_id = self.select_asset("facebook_ads", "act_123")
        self.sync_asset(asset_id)

        history = self.client.get("/api/meta/reporting/syncs/" + asset_id)
        self.assertEqual(history.status_code, 200, history.get_data(as_text=True))
        runs = history.get_json()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["status"], "succeeded")
        self.assertEqual(runs[0]["record_count"], 3)

        response = self.client.get(
            "/api/meta/reporting/kpis/" + asset_id
            + "?start=" + self.START + "&end=" + self.END
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        data = response.get_json()
        self.assertEqual(data["client_id"], "client_meta_sandbox")
        self.assertEqual(data["source"], "facebook_ads")
        self.assertIs(data["publishable"], False)
        spend = data["metrics"]["facebook_ads.spend"]
        self.assertEqual(spend["status"], "available", spend)
        self.assertEqual(spend["summary"]["value"], 121.0)
        self.assertEqual(spend["currency"], "VND")
        self.assertNotIn("FAKE_USER_TOKEN", response.get_data(as_text=True))

    def test_05_content_queue_worker_and_post_kpi(self):
        self.meta.scopes = ['pages_show_list', 'pages_read_engagement']
        asset_id = self.select_asset("facebook_content", "1234")
        self.sync_asset(asset_id)
        response = self.client.get(
            "/api/meta/reporting/kpis/" + asset_id
            + "?start=" + self.START + "&end=" + self.END
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        data = response.get_json()
        posts = data["metrics"]["facebook_content.posts_published"]
        self.assertEqual(posts["summary"]["value"], 1)
        engagement = data["metrics"]["facebook_content.engagements"]
        self.assertIsNone(engagement["summary"]["value"])
        self.assertNotIn("FAKE_PAGE_TOKEN", response.get_data(as_text=True))
        self.assertEqual({path for path, _ in self.meta.calls}, {'me/accounts', '1234/posts'})

    def test_06_empty_ads_does_not_invent_kpis(self):
        self.meta.empty_ads = True
        asset_id = self.select_asset("facebook_ads", "act_123")
        self.sync_asset(asset_id)
        response = self.client.get(
            "/api/meta/reporting/kpis/" + asset_id
            + "?start=" + self.START + "&end=" + self.END
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        metric = response.get_json()["metrics"]["facebook_ads.spend"]
        self.assertIsNone(metric["summary"]["value"])
        n = self.store.one("SELECT COUNT(*) AS n FROM daily_metrics WHERE asset_id=?", (asset_id,))
        self.assertEqual(n["n"], 0)

    def test_platform_status_registry_is_read_only_and_keeps_tiktok_unavailable(self):
        response = self.client.get('/api/platform-status')
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        result = response.get_json()
        self.assertEqual(result['client_context'], {
            'client_id': 'client_meta_sandbox', 'environment': 'sandbox'})
        self.assertEqual({item['id'] for item in result['platforms']}, {
            'seo_website', 'facebook_content', 'facebook_ads', 'tiktok_ads'})
        self.assertEqual(result['sources']['ga4']['state'], 'not_configured')
        self.assertEqual(result['sources']['tiktok_ads']['state'], 'unavailable')
        self.assertEqual(result['sources']['facebook_content']['state'], 'connected_no_asset')
        self.assertEqual(result['sources']['facebook_content']['permission']['missing'], ['pages_read_user_content'])
        self.assertEqual(result['sources']['facebook_ads']['permission']['missing'], [])
        self.assertEqual(self.meta.calls, [])
        body = response.get_data(as_text=True)
        self.assertNotIn('FAKE_USER_TOKEN', body)
        self.assertNotIn('FAKE_PAGE_TOKEN', body)

    def test_unified_sync_history_is_client_scoped_and_does_not_require_live_discovery(self):
        asset_id = self.select_asset('facebook_content', '1234')
        self.sync_asset(asset_id)
        calls_before_history = len(self.meta.calls)
        response = self.client.get('/api/sync-history?provider=meta&source=facebook_content')
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        result = response.get_json()
        self.assertEqual(result['client_id'], 'client_meta_sandbox')
        self.assertEqual(len(result['runs']), 1)
        self.assertEqual(result['runs'][0]['asset_external_id'], '1234')
        self.assertEqual(result['runs'][0]['job_kind'], 'meta_sync')
        self.assertEqual(len(self.meta.calls), calls_before_history)
        self.assertEqual(self.client.get('/api/sync-history?client_id=client_kinderhealth').status_code, 400)
        self.assertEqual(self.client.get('/api/sync-history?asset_id=foreign-asset').status_code, 404)

    def test_unified_sync_history_requires_admin_and_valid_filters(self):
        self.assertEqual(self.client.get('/api/sync-history?provider=unknown').status_code, 400)
        self.store.execute("UPDATE users SET role='viewer' WHERE id=?", (self.admin_id,))
        self.assertEqual(self.client.get('/api/sync-history').status_code, 403)
        self.assertEqual(self.client.get('/api/platform-status').status_code, 403)

    def test_sandbox_legacy_routes_fail_closed_without_client_lineage(self):
        stamp = now()
        asset_id = self.platform.upsert_asset(
            client_id='client_meta_sandbox', provider='meta', asset_type='facebook_page',
            external_id='1234', name='Sandbox Page', connection_id=self.connection_id,
        )
        for dataset_id, report_type, data in (
            ('primary-legacy-dataset', 'seo', {
                'id': 'primary-legacy-dataset', 'client_id': 'client_kinderhealth',
                'params': {'report_type': 'seo'}, 'sources': {},
            }),
            ('sandbox-marketing-dataset', 'facebook-content', {
                'id': 'sandbox-marketing-dataset', 'client_id': 'client_meta_sandbox',
                'dataset_kind': 'marketing_internal_preview_v1',
                'params': {'source': 'facebook_content', 'report_type': 'facebook-content',
                           'start': self.START, 'end': self.END},
                'sources': {}, 'marketing': {},
            }),
        ):
            self.store.execute(
                'INSERT INTO datasets (id,user_id,report_type,created_at,valid,data) VALUES (?,?,?,?,?,?)',
                (dataset_id, self.admin_id, report_type, stamp, 0, pack(data)),
            )
        self.store.execute(
            '''INSERT INTO reports
               (id,report_type,name,version,dataset_id,user_id,created_at,start_date,end_date,
                valid,origin,content_hash,html)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            ('primary-report', 'seo', 'Primary report', 1, 'primary-legacy-dataset',
             self.admin_id, stamp, self.START, self.END, 1, 'test', 'primary-hash', '<p>primary</p>'),
        )
        for job_id, kind, params in (
            ('primary-job', 'analysis', {'report_type': 'seo', 'start': self.START, 'end': self.END}),
            ('sandbox-meta-job', 'meta_sync', {'source': 'facebook_content', 'asset_id': asset_id,
             'report_type': 'facebook-content', 'start': self.START, 'end': self.END, 'demo': False}),
        ):
            self.store.execute(
                '''INSERT INTO jobs (id,kind,user_id,params,status,active_key,created_at,steps)
                   VALUES (?,?,?,?,?,?,?,?)''',
                (job_id, kind, self.admin_id, pack(params), 'succeeded', job_id, stamp, '[]'),
            )
        self.store.execute(
            'INSERT INTO events (id,user_id,action,at,detail) VALUES (?,?,?,?,?)',
            ('primary-event', self.admin_id, 'primary_action', stamp,
             pack({'client_id': 'client_kinderhealth'})),
        )

        self.assertEqual(self.client.get('/api/datasets/primary-legacy-dataset').status_code, 404)
        scoped = self.client.get('/api/datasets/sandbox-marketing-dataset')
        self.assertEqual(scoped.status_code, 200, scoped.get_data(as_text=True))
        self.assertEqual(scoped.get_json()['client_id'], 'client_meta_sandbox')
        self.assertEqual(self.client.get('/api/reports').get_json(), [])
        self.assertEqual(self.client.get('/api/reports/primary-report/html').status_code, 404)
        self.assertEqual(self.post('/api/reports/primary-report/publish', {}).status_code, 404)
        self.assertEqual(self.client.get('/api/jobs/primary-job').status_code, 404)
        self.assertEqual(self.client.get('/api/jobs/sandbox-meta-job').status_code, 200)
        self.assertEqual([job['id'] for job in self.client.get('/api/jobs').get_json()], ['sandbox-meta-job'])
        self.assertEqual(self.client.get('/api/events').get_json(), [])
        self.assertEqual(self.post('/api/analyses', {'report_type': 'seo'}).status_code, 403)
        self.assertEqual(self.post('/api/datasets/sandbox-marketing-dataset/save', {}).status_code, 409)

    def test_selected_ads_without_sync_is_not_an_empty_provider_observation(self):
        asset_id = self.select_asset("facebook_ads", "act_123")
        history = self.client.get('/api/meta/reporting/syncs/' + asset_id)
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.get_json(), [])

        response = self.client.get(
            '/api/meta/reporting/kpis/' + asset_id
            + '?start=' + self.START + '&end=' + self.END
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        data = response.get_json()
        self.assertEqual(data['source'], 'facebook_ads')
        self.assertFalse(data['verified'])
        self.assertFalse(data['publishable'])
        self.assertIsNone(data['snapshot_metrics'])
        for metric in data['metrics'].values():
            self.assertEqual(metric['status'], 'no_data')
            self.assertIsNone(metric['summary']['value'])
            self.assertIsNone(metric['freshness']['latest_sync_status'])

        for table in ('jobs', 'sync_runs', 'daily_metrics', 'source_snapshots', 'source_attestations'):
            self.assertEqual(self.store.one('SELECT COUNT(*) AS n FROM ' + table)['n'], 0)

    def test_07_sandbox_marketing_preview(self):
        """Preview reads stored Meta metrics but never creates a Dataset."""
        from kdh.marketing_preview import build_marketing_preview

        before = self.store.one("SELECT COUNT(*) AS n FROM datasets")["n"]
        cases = [
            ("facebook_ads", "act_123", "facebook_ads.spend", '121.00'),
            ("facebook_content", "1234", "facebook_content.posts_published", 1),
        ]

        for source, external_id, metric_id, expected in cases:
            with self.subTest(source=source):
                asset_id = self.select_asset(source, external_id)
                self.sync_asset(asset_id)

                preview = build_marketing_preview(
                    self.store,
                    client_id="client_meta_sandbox",
                    allowed_sources={source},
                    source=source,
                    asset_id=asset_id,
                    start=self.START,
                    end=self.END,
                )

                self.assertEqual(preview["client_id"], "client_meta_sandbox")
                self.assertEqual(preview["sources"], [source])
                self.assertIs(preview["publishable"], False)
                self.assertIs(preview["quality"]["independently_verified"], False)

                values = {
                    item["metric_id"]: item["value"]
                    for item in preview["widgets"]
                }
                self.assertEqual(values[metric_id], expected)
                if source == "facebook_content":
                    self.assertIsNone(values["facebook_content.engagements"])

        after = self.store.one("SELECT COUNT(*) AS n FROM datasets")["n"]
        self.assertEqual(before, after, "Preview must not create a Dataset")

    def test_08_sandbox_preview_api(self):
        """Admin Preview API returns unverified data without mutating datasets."""
        before = self.store.one("SELECT COUNT(*) AS n FROM datasets")["n"]
        cases = [
            ("facebook_ads", "act_123", "facebook_ads.spend", '121.00'),
            ("facebook_content", "1234", "facebook_content.posts_published", 1),
        ]

        for source, external_id, metric_id, expected in cases:
            with self.subTest(source=source):
                asset_id = self.select_asset(source, external_id)
                self.sync_asset(asset_id)

                response = self.client.get(
                    "/api/meta/reporting/preview",
                    query_string={
                        "asset_id": asset_id,
                        "start": self.START,
                        "end": self.END,
                    },
                )
                self.assertEqual(
                    response.status_code,
                    200,
                    response.get_data(as_text=True),
                )
                preview = response.get_json()
                self.assertEqual(preview["client_id"], "client_meta_sandbox")
                self.assertEqual(preview["sources"], [source])
                self.assertIs(preview["publishable"], False)
                self.assertIs(preview["quality"]["independently_verified"], False)

                values = {
                    item["metric_id"]: item["value"]
                    for item in preview["widgets"]
                }
                self.assertEqual(values[metric_id], expected)
                if source == "facebook_content":
                    self.assertIsNone(values["facebook_content.engagements"])

                body = response.get_data(as_text=True)
                self.assertNotIn("FAKE_USER_TOKEN", body)
                self.assertNotIn("FAKE_PAGE_TOKEN", body)

        after = self.store.one("SELECT COUNT(*) AS n FROM datasets")["n"]
        self.assertEqual(before, after, "Preview API must not create a Dataset")

    def test_page_only_assets_response_succeeds_without_ads(self):
        self.meta.scopes = ['pages_show_list', 'pages_read_engagement']
        response = self.client.get('/api/meta/reporting/assets')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['discovered']['facebook_ads'], [])
        self.assertEqual(data['discovered']['facebook_content'][0]['id'], '1234')
        self.assertEqual(self.meta.calls, [('me/accounts', None)])
        for secret in ('FAKE_USER_TOKEN', 'FAKE_PAGE_TOKEN', 'access_token'):
            self.assertNotIn(secret, response.get_data(as_text=True))

    def test_content_filtered_discovery_selection_and_sync_ignore_ads_endpoint(self):
        original = self.meta.call
        def call(method, path, **kwargs):
            if path == 'me/adaccounts':
                raise AssertionError('Page workflow must not request Ads')
            return original(method, path, **kwargs)
        with patch.object(self.meta, 'call', side_effect=call):
            response = self.client.get('/api/meta/reporting/assets?source=facebook_content')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['discovered']['facebook_content'][0]['id'], '1234')
            self.assertEqual(response.json['discovered']['facebook_ads'], [])
            asset_id = self.select_asset('facebook_content', '1234')
            self.sync_asset(asset_id)
        self.assertEqual({path for path, _ in self.meta.calls}, {'me/accounts', '1234/posts'})

    def test_invalid_discovery_filter_fails_before_provider_request(self):
        for query in ('source=unknown', 'source=', 'source=facebook_content&source=facebook_ads', 'unexpected=1'):
            with self.subTest(query=query):
                response = self.client.get('/api/meta/reporting/assets?' + query)
                self.assertEqual(response.status_code, 400)
        self.assertEqual(self.meta.calls, [])

    def test_missing_ads_permission_rejects_sync_before_queueing(self):
        asset_id = self.select_asset('facebook_ads', 'act_123')
        self.meta.scopes = ['pages_show_list', 'pages_read_engagement']
        self.meta.calls.clear()
        response = self.post('/api/meta/reporting/sync', {
            'asset_id': asset_id, 'start': self.START, 'end': self.END,
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()['code'], 'meta_ads_permission')
        self.assertIn('ads_read', response.get_json()['error'])
        self.assertEqual(self.meta.calls, [])
        for table in ('jobs', 'sync_runs', 'daily_metrics', 'source_snapshots'):
            self.assertEqual(self.store.one('SELECT COUNT(*) AS n FROM ' + table)['n'], 0)
        self.assertNotIn('FAKE_USER_TOKEN', response.get_data(as_text=True))

    def test_queued_ads_sync_rechecks_permission_before_insights(self):
        asset_id = self.select_asset('facebook_ads', 'act_123')
        response = self.post('/api/meta/reporting/sync', {
            'asset_id': asset_id, 'start': self.START, 'end': self.END,
        })
        self.assertEqual(response.status_code, 202)
        job_id = response.get_json()['job_id']
        self.meta.scopes = ['pages_show_list', 'pages_read_engagement']
        self.meta.calls.clear()
        self.assertTrue(self.app.extensions['worker'].run_one(job_id))
        job = self.store.one('SELECT status,error FROM jobs WHERE id=?', (job_id,))
        self.assertEqual(job['status'], 'failed')
        self.assertIn('ads_read', job['error'])
        self.assertEqual(self.meta.calls, [])
        for table in ('daily_metrics', 'source_snapshots'):
            self.assertEqual(self.store.one('SELECT COUNT(*) AS n FROM ' + table)['n'], 0)
        for secret in ('FAKE_USER_TOKEN', 'FAKE_PAGE_TOKEN'):
            self.assertNotIn(secret, pack(job) + pack(self.store.all('SELECT * FROM events')))


if __name__ == "__main__":
    unittest.main()
