"""Docker browser links normalize to APP_URL without relaxing request guards."""
import tempfile
import unittest

from kdh.app import create_app


class LoopbackEntryTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.app = create_app({
            'DATA_DIR': folder.name, 'DATABASE_URL': '', 'ENCRYPTION_KEY': '',
            'TESTING': True, 'JOB_MODE': 'request', 'APP_URL': 'http://localhost:8191',
            'INITIAL_ADMIN_EMAIL': '', 'INITIAL_ADMIN_PASSWORD': '',
            'GOOGLE_CLIENT_ID': '', 'GOOGLE_CLIENT_SECRET': '', 'META_CLIENT_ID': 'client_meta_sandbox',
        })
        self.client = self.app.test_client()

    def test_docker_entry_uses_configured_origin(self):
        for method in ('GET', 'HEAD'):
            for path in ('/', '/marketing?report_id=rpt_example&revision=1'):
                with self.subTest(method=method, path=path):
                    r = self.client.open(path, method=method, base_url='http://127.0.0.1:8191')
                    self.assertEqual(r.status_code, 303)
                    self.assertEqual(r.location, 'http://localhost:8191' + path)

    def test_canonical_entry_and_internal_health_do_not_redirect(self):
        self.assertEqual(self.client.get('/', base_url='http://localhost:8191').status_code, 200)
        r = self.client.get('/health', base_url='http://127.0.0.1:8090')
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('Location', r.headers)

    def test_api_origin_guard_remains_strict(self):
        r = self.client.post('/api/auth/login', base_url='http://127.0.0.1:8191', json={},
                             headers={'X-KDH-Request': '1', 'Origin': 'http://127.0.0.1:8191'})
        self.assertEqual(r.status_code, 403)
        self.assertNotIn('Location', r.headers)
        self.assertIn('Nguồn gửi', r.json['error'])
        self.assertEqual(self.client.post('/api/auth/login', json={}).status_code, 403)

    def test_different_port_and_forwarded_headers_do_not_select_origin(self):
        r = self.client.get('/', base_url='http://127.0.0.1:8090',
                            headers={'X-Forwarded-Host': 'localhost:8191'})
        self.assertEqual(r.status_code, 200)
        r = self.client.get('/?next=https://evil.example', base_url='http://127.0.0.1:8191')
        self.assertEqual(r.location, 'http://localhost:8191/?next=https://evil.example')
        r = self.client.get('/', base_url='http://evil.example:8191')
        self.assertNotIn('Location', r.headers)

    def test_public_origin_configuration_is_not_rewritten(self):
        self.app.config['APP_URL'] = 'https://admin.example.test'
        r = self.client.get('/', base_url='http://127.0.0.1:8191')
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('Location', r.headers)


if __name__ == '__main__':
    unittest.main()
