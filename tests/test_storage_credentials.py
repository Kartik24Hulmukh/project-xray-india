import os
import unittest
from unittest.mock import patch

from app.storage import (
    StorageConfigurationError,
    managed_uri_components,
    settings_from_env,
    verify_managed_object,
)


class FakeS3Client:
    def __init__(self, response=None):
        self.response = response or {
            'ContentLength': 128,
            'Metadata': {'sha256': 'a' * 64},
            'VersionId': 'version-1',
        }
        self.calls = []

    def head_object(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class TestStorageCredentials(unittest.TestCase):
    def setUp(self):
        self.old = dict(os.environ)
        for name in (
            'STORAGE_BUCKET',
            'STORAGE_ENDPOINT',
            'STORAGE_REGION',
            'STORAGE_ACCESS_KEY',
            'STORAGE_SECRET_KEY',
            'STORAGE_SESSION_TOKEN',
        ):
            os.environ.pop(name, None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old)

    def test_partial_static_credentials_fail_before_network(self):
        with self.assertRaises(StorageConfigurationError):
            settings_from_env(bucket='evidence', access_key='only-key', secret_key='')
        with self.assertRaises(StorageConfigurationError):
            settings_from_env(bucket='evidence', access_key='', secret_key='only-secret')

    def test_no_static_credentials_uses_default_chain_client(self):
        client = FakeS3Client()
        result = verify_managed_object(
            's3://evidence/case/a.pdf?versionId=version-1',
            'a' * 64,
            128,
            bucket='evidence',
            access_key='',
            secret_key='',
            client=client,
            require_version=True,
        )
        self.assertEqual(result['credential_mode'], 'default_chain')
        self.assertEqual(
            client.calls,
            [{'Bucket': 'evidence', 'Key': 'case/a.pdf', 'VersionId': 'version-1'}],
        )

    def test_version_is_required_and_bound(self):
        client = FakeS3Client()
        with self.assertRaises(StorageConfigurationError):
            verify_managed_object(
                's3://evidence/case/a.pdf',
                'a' * 64,
                128,
                bucket='evidence',
                access_key='',
                secret_key='',
                client=client,
                require_version=True,
            )
        client.response['VersionId'] = 'different-version'
        with self.assertRaises(RuntimeError):
            verify_managed_object(
                's3://evidence/case/a.pdf?versionId=version-1',
                'a' * 64,
                128,
                bucket='evidence',
                access_key='',
                secret_key='',
                client=client,
                require_version=True,
            )

    def test_uri_rejects_unknown_or_duplicate_query(self):
        with self.assertRaises(ValueError):
            managed_uri_components('s3://evidence/a?acl=public-read', 'evidence')
        with self.assertRaises(ValueError):
            managed_uri_components(
                's3://evidence/a?versionId=one&versionId=two', 'evidence'
            )

    def test_static_session_token_is_signed(self):
        class Response:
            status = 200
            headers = {
                'Content-Length': '128',
                'x-amz-meta-sha256': 'a' * 64,
                'x-amz-version-id': 'version-1',
            }

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        captured = {}

        def fake_urlopen(request, timeout):
            captured.update(dict(request.headers))
            return Response()

        with patch('app.storage.urllib.request.urlopen', fake_urlopen):
            result = verify_managed_object(
                's3://evidence/case/a.pdf?versionId=version-1',
                'a' * 64,
                128,
                endpoint='https://minio.example.invalid',
                bucket='evidence',
                access_key='key',
                secret_key='secret',
                session_token='temporary-session-token',
                require_version=True,
            )
        normalized = {key.lower(): value for key, value in captured.items()}
        self.assertEqual(normalized['x-amz-security-token'], 'temporary-session-token')
        self.assertEqual(result['credential_mode'], 'static')


if __name__ == '__main__':
    unittest.main()
