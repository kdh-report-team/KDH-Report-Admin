"""Independent Admin cookie namespaces without weakening OAuth/session checks."""
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from kdh.app import create_app
from kdh.core import digest


class SessionCookieTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.network = patch('requests.sessions.Session.request', side_effect=AssertionError('No provider HTTP'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.config = {
            'DATA_DIR': self.folder.name, 'DATABASE_URL': '', 'ENCRYPTION_KEY': '',
            'TESTING': True, 'JOB_MODE': 'request', 'APP_URL': 'http://localhost:8190',
            'COOKIE_SECURE': False, 'ADMIN_SESSION_COOKIE_NAME': 'kdh_sandbox_session',
            'INITIAL_ADMIN_EMAIL': 'sandbox@example.test', 'INITIAL_ADMIN_PASSWORD': 'Sandbox-password-123',
            'GOOGLE_CLIENT_ID': '', 'GOOGLE_CLIENT_SECRET': '',
            'META_CLIENT_ID': 'client_meta_sandbox', 'META_APP_ID': '123456',
            'META_APP_SECRET': 'fake-secret', 'META_CONFIG_ID': '654321',
            'META_GRAPH_VERSION': 'v26.0',
            'META_REDIRECT_URI': 'http://localhost:8190/api/meta/callback',
        }

    def login(self, client):
        response = client.post('/api/auth/login', json={
            'email': self.config['INITIAL_ADMIN_EMAIL'],
            'password': self.config['INITIAL_ADMIN_PASSWORD'],
        }, headers={'X-KDH-Request': '1', 'Origin': self.config['APP_URL']})
        self.assertEqual(response.status_code, 200)
        return response

    def test_foreign_cookie_cannot_replace_sandbox_session_or_break_callback(self):
        app = create_app(self.config)
        client = app.test_client()
        client.set_cookie('kdh_session', 'foreign-runtime-cookie')
        login = self.login(client)
        header = login.headers['Set-Cookie']
        self.assertIn('kdh_sandbox_session=', header)
        self.assertIn('HttpOnly', header)
        self.assertIn('SameSite=Lax', header)
        self.assertEqual(client.get_cookie('kdh_session').value, 'foreign-runtime-cookie')
        headers = {'X-KDH-Request': '1', 'X-CSRF-Token': login.json['csrf'], 'Origin': self.config['APP_URL']}
        response = client.post('/api/meta/connect', json={}, headers=headers)
        self.assertEqual(response.status_code, 200)
        state = parse_qs(urlsplit(response.json['url']).query)['state'][0]
        session_id = digest(client.get_cookie('kdh_sandbox_session').value)
        self.assertEqual(app.extensions['store'].one('SELECT session_id FROM meta_oauth_states')['session_id'], session_id)
        client.set_cookie('kdh_session', 'another-runtime-login')
        with patch.object(app.extensions['meta'], 'callback', return_value='success') as callback:
            response = client.get('/api/meta/callback', query_string={'state': state, 'code': 'fake-code'})
            self.assertEqual(response.status_code, 302)
            callback.assert_called_once_with(state, 'fake-code', session_id, '')
        self.assertEqual(client.post('/api/auth/logout', json={}, headers={'X-KDH-Request': '1'}).status_code, 403)
        response = client.post('/api/auth/logout', json={}, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(client.get_cookie('kdh_sandbox_session'))
        self.assertEqual(client.get_cookie('kdh_session').value, 'another-runtime-login')
        self.assertEqual(client.get('/api/meta/callback?code=fake').status_code, 401)

    def test_legacy_cookie_alone_cannot_authenticate_sandbox(self):
        app = create_app(self.config)
        authenticated = app.test_client()
        self.login(authenticated)
        client = app.test_client()
        client.set_cookie('kdh_session', authenticated.get_cookie('kdh_sandbox_session').value)
        with patch.object(app.extensions['meta'], 'callback') as callback:
            self.assertEqual(client.get('/api/meta/callback?code=fake').status_code, 401)
            callback.assert_not_called()

    def test_invalid_cookie_name_rejected_before_store_initialization(self):
        for value in ('', 'bad;name', 'bad name', None, 'x' * 65):
            with self.subTest(value=value), patch('kdh.app.Store') as store:
                with self.assertRaises(RuntimeError):
                    create_app({**self.config, 'ADMIN_SESSION_COOKIE_NAME': value})
                store.assert_not_called()
