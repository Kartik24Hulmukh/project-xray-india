import time
import unittest

from app.gateway import (
    assertion_signature,
    mint_gateway_assertion,
    resolve_role_binding,
    stable_principal,
    strip_client_auth_headers,
)
from app.security import clear_replay_cache, verify_gateway_assertion


ISSUER = 'https://cognito-idp.ap-south-1.amazonaws.com/synthetic-pool'
AUDIENCE = 'project-xray-app'
KEY_ID = 'gateway-2026-07'
SECRET = 'gateway-secret-123456789012345678901234'


class TestGatewayContract(unittest.TestCase):
    def setUp(self):
        clear_replay_cache()

    def headers(self, **overrides):
        headers = mint_gateway_assertion(
            issuer=ISSUER,
            subject='synthetic-reviewer-a',
            role='reviewer',
            secret=SECRET,
            key_id=KEY_ID,
            audience=AUDIENCE,
            issued_at=int(time.time()),
            nonce='synthetic-nonce-00000001',
        )
        headers.update(overrides)
        return headers

    def verify(self, headers, **kwargs):
        return verify_gateway_assertion(
            headers,
            {KEY_ID: SECRET},
            AUDIENCE,
            {ISSUER},
            **kwargs,
        )

    def test_strips_all_client_assertion_headers_case_insensitively(self):
        stripped = strip_client_auth_headers(
            {'X-Auth-Role': 'admin', 'x-auth-signature': 'forged', 'Accept': 'application/json'}
        )
        self.assertEqual(stripped, {'Accept': 'application/json'})

    def test_principal_binds_issuer_and_subject(self):
        first = stable_principal(ISSUER, 'subject-1')
        self.assertEqual(first, stable_principal(ISSUER, 'subject-1'))
        self.assertNotEqual(first, stable_principal(ISSUER + '-other', 'subject-1'))

    def test_role_binding_is_server_controlled_and_exact(self):
        principal = stable_principal(ISSUER, 'subject-1')
        self.assertEqual(resolve_role_binding({principal: 'reviewer'}, ISSUER, 'subject-1'), 'reviewer')
        with self.assertRaises(PermissionError):
            resolve_role_binding({principal: 'admin,reviewer'}, ISSUER, 'subject-1')
        with self.assertRaises(PermissionError):
            resolve_role_binding({}, ISSUER, 'subject-1')

    def test_valid_assertion_returns_stable_principal(self):
        result = self.verify(self.headers())
        self.assertEqual(result, ('reviewer', stable_principal(ISSUER, 'synthetic-reviewer-a')))

    def test_replay_is_rejected(self):
        headers = self.headers()
        self.assertIsNotNone(self.verify(headers))
        self.assertIsNone(self.verify(headers))

    def test_unique_nonce_produces_unique_signature(self):
        one = self.headers()
        two = mint_gateway_assertion(
            issuer=ISSUER,
            subject='synthetic-reviewer-a',
            role='reviewer',
            secret=SECRET,
            key_id=KEY_ID,
            audience=AUDIENCE,
            issued_at=int(time.time()),
            nonce='synthetic-nonce-00000002',
        )
        self.assertNotEqual(one['X-Auth-Signature'], two['X-Auth-Signature'])

    def test_tampering_and_policy_mismatch_fail(self):
        for name, value in (
            ('X-Auth-Role', 'admin'),
            ('X-Auth-Audience', 'other-app'),
            ('X-Auth-Issuer', ISSUER + '/other'),
            ('X-Auth-Principal', 'oidc:' + '0' * 64),
            ('X-Auth-MFA', 'false'),
            ('X-Auth-Key-Id', 'unknown'),
        ):
            clear_replay_cache()
            self.assertIsNone(self.verify(self.headers(**{name: value})), name)

    def test_future_expired_and_excessive_lifetime_fail(self):
        current = int(time.time())
        future = mint_gateway_assertion(
            issuer=ISSUER, subject='s', role='reviewer', secret=SECRET,
            key_id=KEY_ID, audience=AUDIENCE, issued_at=current + 60,
            nonce='synthetic-nonce-00000003',
        )
        self.assertIsNone(self.verify(future, now_epoch=current))

        expired = mint_gateway_assertion(
            issuer=ISSUER, subject='s', role='reviewer', secret=SECRET,
            key_id=KEY_ID, audience=AUDIENCE, issued_at=current - 31,
            nonce='synthetic-nonce-00000004',
        )
        self.assertIsNone(self.verify(expired, now_epoch=current))

        headers = self.headers()
        headers['X-Auth-Expires-At'] = str(int(headers['X-Auth-Issued-At']) + 31)
        self.assertIsNone(self.verify(headers))


if __name__ == '__main__':
    unittest.main()
