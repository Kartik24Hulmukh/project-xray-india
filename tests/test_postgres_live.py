#!/usr/bin/env python3
"""Live PostgreSQL checks. Skipped unless DATABASE_URL is set."""
import os
import unittest

from app.database import (
    IS_POSTGRES,
    connect,
    table_exists,
    get_schema_version,
    integrity_check,
    db,
)


@unittest.skipUnless(bool(os.getenv('DATABASE_URL')), 'DATABASE_URL not set')
class TestPostgresLive(unittest.TestCase):
    def test_backend_is_postgres(self):
        self.assertTrue(IS_POSTGRES)

    def test_core_tables_exist(self):
        c = connect()
        try:
            for name in (
                'projects', 'sources', 'documents', 'claims',
                'claim_reviews', 'audit_events', 'audit_checkpoints',
                'idempotency_keys',
            ):
                self.assertTrue(table_exists(c, name), name)
        finally:
            c.close()

    def test_integrity_ok(self):
        c = connect()
        try:
            self.assertEqual(integrity_check(c), 'ok')
        finally:
            c.close()

    def test_schema_version_readable(self):
        c = connect()
        try:
            version = get_schema_version(c)
            self.assertIsInstance(version, int)
            self.assertGreaterEqual(version, 0)
        finally:
            c.close()

    def test_write_rollback_roundtrip(self):
        try:
            with db(True) as c:
                c.execute(
                    "INSERT INTO projects(id,title,authority,location,summary,status,synthetic,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        'prj_live_test_aaaaaaaa', 'Live PG', 'Authority', '', '',
                        'research', 0, 't', 't',
                    ),
                )
                raise RuntimeError('force rollback')
        except RuntimeError:
            pass
        c = connect()
        try:
            row = c.execute(
                "SELECT id FROM projects WHERE id=?",
                ('prj_live_test_aaaaaaaa',),
            ).fetchone()
            self.assertIsNone(row)
        finally:
            c.close()

    def test_write_commit_roundtrip(self):
        with db(True) as c:
            c.execute(
                "INSERT INTO projects(id,title,authority,location,summary,status,synthetic,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    'prj_live_test_bbbbbbbb', 'Live PG Commit', 'Authority', '', '',
                    'research', 0, 't', 't',
                ),
            )
        c = connect()
        try:
            row = c.execute(
                "SELECT title FROM projects WHERE id=?",
                ('prj_live_test_bbbbbbbb',),
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row['title'], 'Live PG Commit')
            with db(True) as w:
                w.execute("DELETE FROM projects WHERE id=?", ('prj_live_test_bbbbbbbb',))
        finally:
            c.close()


if __name__ == '__main__':
    unittest.main()
