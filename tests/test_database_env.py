import unittest

from app.database import database_url_from_env


class TestDatabaseEnvironment(unittest.TestCase):
    def test_explicit_database_url_wins(self):
        self.assertEqual(
            database_url_from_env({'DATABASE_URL': 'postgresql://explicit/db'}),
            'postgresql://explicit/db',
        )

    def test_ecs_secret_fields_are_encoded(self):
        url = database_url_from_env({
            'DB_HOST': 'db.internal',
            'DB_PORT': '5432',
            'DB_NAME': 'xray',
            'DB_USERNAME': 'app user',
            'DB_PASSWORD': 'p@ss:/?#',
            'DB_SSLMODE': 'verify-full',
        })
        self.assertEqual(
            url,
            'postgresql://app%20user:p%40ss%3A%2F%3F%23@db.internal:5432/xray?sslmode=verify-full',
        )

    def test_partial_or_unsafe_configuration_fails_closed(self):
        self.assertEqual(database_url_from_env({'DB_HOST': 'db.internal'}), '')
        base = {
            'DB_HOST': 'db.internal', 'DB_NAME': 'xray',
            'DB_USERNAME': 'user', 'DB_PASSWORD': 'password',
        }
        for update in (
            {'DB_HOST': 'db.internal/path'},
            {'DB_PORT': 'not-a-port'},
            {'DB_NAME': 'bad/name'},
            {'DB_SSLMODE': 'disable'},
        ):
            with self.assertRaises(RuntimeError):
                database_url_from_env({**base, **update})


if __name__ == '__main__':
    unittest.main()
