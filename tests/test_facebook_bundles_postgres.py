"""Run the existing dual-bundle acceptance cases on disposable PostgreSQL.

Only run through run_postgres_acceptance.py, which creates and pins the test DB.
No provider transports or runtime sandbox databases are used.
"""
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from cryptography.fernet import Fernet

import test_facebook_bundles as bundles
import test_meta_reporting_routes as fixtures


@unittest.skipUnless(os.getenv('KDH_PHASE4_ISOLATED') == '1' and os.getenv('TEST_DATABASE_URL'),
                     'Requires the guarded disposable PostgreSQL acceptance runner')
class PostgresFacebookBundleTests(bundles.FacebookBundleTests):
    def setUp(self):
        url = os.environ['TEST_DATABASE_URL']
        schema = 'kdh_phase4_meta_' + uuid4().hex
        with psycopg.connect(url, autocommit=True) as db:
            db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))

        def cleanup():
            with psycopg.connect(url, autocommit=True) as db:
                db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
        self.addCleanup(cleanup)
        isolated = make_conninfo(url, options='-csearch_path=' + schema)

        class PostgresFixture(fixtures.MetaReportingHttpTests):
            database_url = isolated
            test_encryption_key = Fernet.generate_key().decode()

        with patch.object(bundles.fixtures, 'MetaReportingHttpTests', PostgresFixture):
            super().setUp()
        self.assertTrue(self.store.postgres)
