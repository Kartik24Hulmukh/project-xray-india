#!/usr/bin/env python3
"""OIDC proxy role semantics and replay protection tests."""

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.security import (
    clear_replay_cache,
    proxy_signature,
    resolve_single_role,
    verify_proxy,
)


SECRET = 'proxy-secret-1234567890123456789012'


def signed(subject, roles, mfa='true', stamp=None, secret=SECRET, nonce=None):
    stamp = stamp or str(int(time.time()))
    headers = {
        'X-Auth-Subject': subject,
        'X-Auth-Roles': roles,
        'X-Auth-MFA': mfa,
        'X-Auth-Timestamp': stamp,
    }
    if nonce is not None:
        headers['X-Auth-Nonce'] = nonce
    headers['X-Auth-Signature'] = proxy_signature(
        subject, roles, mfa, stamp, secret, nonce=nonce or ''
    )
    return headers


class TestRoleResolution(unittest.TestCase):
    def test_admin_only(self):
        self.assertEqual(resolve_single_role('admin'), 'admin')

    def test_reviewer_only(self):
        self.assertEqual(resolve_single_role('reviewer'), 'reviewer')

    def test_scanner_only(self):
        self.assertEqual(resolve_single_role('scanner'), 'scanner')

    def test_unknown_only_denied(self):
        self.assertIsNone(resolve_single_role('superuser'))

    def test_admin_reviewer_ambiguous(self):
        self.assertIsNone(resolve_single_role('admin,reviewer'))

    def test_reviewer_scanner_ambiguous(self):
        self.assertIsNone(resolve_single_role('reviewer,scanner'))

    def test_unknown_with_admin_denied(self):
        self.assertIsNone(resolve_single_role('unknown,admin'))

    def test_whitespace_case_normalization(self):
        self.assertEqual(resolve_single_role('  Reviewer  '), 'reviewer')
        self.assertEqual(resolve_single_role('ADMIN'), 'admin')

    def test_duplicate_role_collapsed(self):
        self.assertEqual(resolve_single_role('reviewer,reviewer'), 'reviewer')
        self.assertEqual(resolve_single_role('Admin, admin'), 'admin')


class TestVerifyProxy(unittest.TestCase):
    def setUp(self):
        clear_replay_cache()

    def test_admin_accepted(self):
        h = signed('admin@example.org', 'admin')
        self.assertEqual(verify_proxy(h, SECRET), ('admin', 'admin@example.org'))

    def test_reviewer_accepted(self):
        h = signed('r@example.org', 'reviewer')
        self.assertEqual(verify_proxy(h, SECRET), ('reviewer', 'r@example.org'))

    def test_scanner_accepted(self):
        h = signed('s@example.org', 'scanner')
        self.assertEqual(verify_proxy(h, SECRET), ('scanner', 's@example.org'))

    def test_unknown_denied(self):
        h = signed('u@example.org', 'root')
        self.assertIsNone(verify_proxy(h, SECRET))

    def test_ambiguous_denied(self):
        h = signed('u@example.org', 'admin,reviewer')
        self.assertIsNone(verify_proxy(h, SECRET))

    def test_invalid_signature_denied(self):
        h = signed('u@example.org', 'admin')
        h['X-Auth-Signature'] = 'ab' * 32
        self.assertIsNone(verify_proxy(h, SECRET))

    def test_missing_mfa_denied(self):
        h = signed('u@example.org', 'admin', mfa='false')
        # resign with false mfa so signature matches content
        h['X-Auth-Signature'] = proxy_signature(
            h['X-Auth-Subject'], h['X-Auth-Roles'], 'false', h['X-Auth-Timestamp'], SECRET, nonce=h.get('X-Auth-Nonce','')
        )
        self.assertIsNone(verify_proxy(h, SECRET))

    def test_stale_assertion_denied(self):
        h = signed('u@example.org', 'admin', stamp=str(int(time.time()) - 1000))
        self.assertIsNone(verify_proxy(h, SECRET, max_age=90))

    def test_replay_denied(self):
        h = signed('u@example.org', 'admin')
        self.assertIsNotNone(verify_proxy(h, SECRET))
        self.assertIsNone(verify_proxy(h, SECRET))

    def test_replay_allowed_when_opted_in(self):
        h = signed('u@example.org', 'admin')
        self.assertIsNotNone(verify_proxy(h, SECRET, allow_replay=True))
        self.assertIsNotNone(verify_proxy(h, SECRET, allow_replay=True))

    def test_subject_format_rejected(self):
        h = signed('bad subject\nwith\nnewlines', 'admin')
        self.assertIsNone(verify_proxy(h, SECRET))

    def test_distinct_nonce_allows_multiple_requests(self):
        h1 = signed('u@example.org', 'admin', nonce='n1')
        h2 = signed('u@example.org', 'admin', nonce='n2')
        self.assertIsNotNone(verify_proxy(h1, SECRET))
        self.assertIsNotNone(verify_proxy(h2, SECRET))


if __name__ == '__main__':
    unittest.main()
