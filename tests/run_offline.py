"""Run unittest fixtures with no provider, local .env or PostgreSQL access.

Usage: .venv/Scripts/python.exe -B tests/run_offline.py [test_pattern.py]
SQLite tests own disposable directories. PostgreSQL suites explicitly skip.
"""
import os
import pathlib
import socket
import sys
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for key in list(os.environ):
    if key.startswith(('TEST_DATABASE', 'TEST_META', 'META_', 'GOOGLE_', 'GA4_', 'GSC_', 'KEYWORD_', 'INITIAL_ADMIN_', 'ADMIN_SESSION_')) or key in {
            'DATABASE_URL', 'DATA_DIR', 'ENCRYPTION_KEY', 'JOB_MODE', 'APP_URL', 'COOKIE_SECURE', 'REPORT_SIGNING_KEY'}:
        os.environ.pop(key, None)
original_read = pathlib.Path.read_text


def offline_read(path, *args, **kwargs):
    return '' if path.resolve() == ROOT / '.env' else original_read(path, *args, **kwargs)


def deny_network(*args, **kwargs):
    raise AssertionError('Offline tests forbid network and runtime PostgreSQL access')


if __name__ == '__main__':
    with patch.object(pathlib.Path, 'read_text', offline_read), patch.object(socket.socket, 'connect', deny_network), \
            patch.object(socket.socket, 'connect_ex', deny_network), patch('psycopg.connect', deny_network):
        suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern=sys.argv[1] if len(sys.argv) > 1 else 'test_*.py')
        result = unittest.TextTestRunner(verbosity=1).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
