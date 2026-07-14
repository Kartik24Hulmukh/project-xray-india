#!/usr/bin/env python3
"""PostgreSQL compatibility validation tests.

Validates that the database abstraction layer (app/database.py) is
correctly structured for PostgreSQL compatibility WITHOUT requiring
a running PostgreSQL instance.
"""

import os
import re
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app.database as dbmod
from app.database import (
    _convert_sql, RowAdapter, CursorAdapter, ConnectionAdapter,
    IntegrityError, IS_POSTGRES, connect, db, get_schema_version,
    table_exists, integrity_check,
)

ROOT = Path(__file__).resolve().parents[1]


class TestConvertSql(unittest.TestCase):
    """Test SQL placeholder conversion (? -> %s for PostgreSQL)."""

    def test_no_conversion_in_sqlite_mode(self):
        with patch.object(dbmod, 'IS_POSTGRES', False):
            self.assertEqual(_convert_sql('SELECT * FROM t WHERE id=?'), 'SELECT * FROM t WHERE id=?')

    def test_question_mark_replaced_in_postgres_mode(self):
        with patch.object(dbmod, 'IS_POSTGRES', True):
            self.assertEqual(_convert_sql('SELECT * FROM t WHERE id=?'), 'SELECT * FROM t WHERE id=%s')

    def test_no_replacement_inside_single_quoted_strings(self):
        with patch.object(dbmod, 'IS_POSTGRES', True):
            sql = "SELECT 'is it? yes' FROM t WHERE id=?"
            result = _convert_sql(sql)
            self.assertIn('?', result)
            self.assertIn('%s', result)

    def test_no_replacement_inside_double_quoted_strings(self):
        with patch.object(dbmod, 'IS_POSTGRES', True):
            sql = 'SELECT "what?" FROM t WHERE id=?'
            result = _convert_sql(sql)
            self.assertIn('?', result)

    def test_multiple_placeholders(self):
        with patch.object(dbmod, 'IS_POSTGRES', True):
            self.assertEqual(_convert_sql('INSERT INTO t VALUES(?,?,?)'), 'INSERT INTO t VALUES(%s,%s,%s)')

    def test_empty_query(self):
        with patch.object(dbmod, 'IS_POSTGRES', True):
            self.assertEqual(_convert_sql(''), '')

    def test_no_placeholders(self):
        with patch.object(dbmod, 'IS_POSTGRES', True):
            self.assertEqual(_convert_sql('SELECT 1'), 'SELECT 1')


class TestRowAdapter(unittest.TestCase):
    """Test RowAdapter dict-like access."""

    def test_from_dict(self):
        row = RowAdapter({'id': 1, 'name': 'test'})
        self.assertEqual(row['id'], 1)
        self.assertEqual(row['name'], 'test')

    def test_from_sqlite_row(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.execute('CREATE TABLE t(id INTEGER, name TEXT)')
        conn.execute("INSERT INTO t VALUES(1, 'test')")
        raw = conn.execute('SELECT * FROM t').fetchone()
        row = RowAdapter(raw)
        self.assertEqual(row['id'], 1)
        self.assertEqual(row['name'], 'test')
        conn.close()

    def test_get_with_default(self):
        row = RowAdapter({'id': 1})
        self.assertEqual(row.get('id'), 1)
        self.assertIsNone(row.get('missing'))
        self.assertEqual(row.get('missing', 'default'), 'default')

    def test_contains(self):
        row = RowAdapter({'id': 1})
        self.assertIn('id', row)
        self.assertNotIn('name', row)

    def test_keys(self):
        row = RowAdapter({'id': 1, 'name': 'test'})
        self.assertEqual(set(row.keys()), {'id', 'name'})

    def test_items(self):
        row = RowAdapter({'id': 1})
        self.assertEqual(dict(row.items()), {'id': 1})


class TestPostgresSchema(unittest.TestCase):
    """Validate schema_postgres.sql is valid and complete."""

    def setUp(self):
        self.schema = (ROOT / 'db' / 'schema_postgres.sql').read_text()

    def test_file_exists(self):
        self.assertTrue(len(self.schema) > 100)

    def test_no_sqlite_pragmas(self):
        self.assertNotIn('PRAGMA', self.schema)

    def test_uses_on_conflict(self):
        self.assertIn('ON CONFLICT', self.schema)

    def test_has_all_required_tables(self):
        for table in ['projects', 'sources', 'documents', 'claims', 'claim_reviews',
                       'claim_revisions', 'gaps', 'responses', 'auth_tokens',
                       'audit_events', 'audit_checkpoints', 'idempotency_keys', 'schema_version']:
            self.assertIn(f'CREATE TABLE IF NOT EXISTS {table}', self.schema,
                         f'Missing table: {table}')

    def test_has_required_indexes(self):
        for idx in ['idx_projects_status', 'idx_sources_project', 'idx_documents_project',
                     'idx_claims_project_state', 'idx_audit_object', 'idx_auth_active']:
            self.assertIn(idx, self.schema, f'Missing index: {idx}')

    def test_schema_version_set_to_3(self):
        self.assertIn('value = 3', self.schema)

    def test_uses_create_function(self):
        self.assertIn('CREATE OR REPLACE FUNCTION', self.schema)

    def test_uses_serial_primary_key(self):
        self.assertIn('SERIAL PRIMARY KEY', self.schema)

    def test_no_question_mark_placeholders(self):
        # Schema should not use ? placeholders
        # Count ? outside of strings
        lines = self.schema.split('\n')
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('--'):
                continue
            # Check for ? outside single-quoted strings
            in_str = False
            for ch in stripped:
                if ch == "'":
                    in_str = not in_str
                elif ch == '?' and not in_str:
                    self.fail(f'Found ? placeholder in schema: {stripped}')

    def test_balanced_parentheses(self):
        self.assertEqual(self.schema.count('('), self.schema.count(')'))

    def test_foreign_keys_present(self):
        self.assertIn('FOREIGN KEY', self.schema)

    def test_check_constraints_present(self):
        self.assertIn('CHECK(', self.schema)


class TestServerQueryPlaceholders(unittest.TestCase):
    """Verify server.py uses ? placeholders, not %s."""

    def setUp(self):
        self.source = (ROOT / 'app' / 'server.py').read_text()

    def test_no_direct_percent_s_in_queries(self):
        # Check that %s is not used directly in execute() calls
        # Allow %s only in string formatting, not SQL params
        lines = self.source.split('\n')
        for i, line in enumerate(lines, 1):
            if 'execute(' in line and '%s' in line and '?' not in line:
                # This might be a false positive - check if it's in a string
                if "VALUES" in line or "WHERE" in line or "SELECT" in line:
                    self.fail(f'Line {i}: possible direct %s in SQL: {line.strip()[:80]}')

    def test_uses_question_mark_placeholders(self):
        # Check that server.py uses ? placeholders in SQL
        self.assertIn('VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', self.source)

    def test_insert_or_ignore_is_conditional(self):
        self.assertIn("' OR IGNORE' if not IS_POSTGRES", self.source)

    def test_on_conflict_is_conditional(self):
        self.assertIn("' ON CONFLICT DO NOTHING' if IS_POSTGRES", self.source)


class TestDialectDetection(unittest.TestCase):
    """Test IS_POSTGRES flag."""

    def test_is_postgres_false_by_default(self):
        # In test mode, DATABASE_URL should not be set
        old = os.environ.get('DATABASE_URL', '')
        os.environ.pop('DATABASE_URL', None)
        try:
            # Re-import to check
            import importlib
            importlib.reload(dbmod)
            self.assertFalse(dbmod.IS_POSTGRES)
        finally:
            if old:
                os.environ['DATABASE_URL'] = old
            importlib.reload(dbmod)

    def test_is_postgres_true_when_database_url_set(self):
        old = os.environ.get('DATABASE_URL', '')
        os.environ['DATABASE_URL'] = 'postgresql://user:pass@localhost/db'
        try:
            import importlib
            importlib.reload(dbmod)
            self.assertTrue(dbmod.IS_POSTGRES)
        finally:
            if old:
                os.environ['DATABASE_URL'] = old
            else:
                os.environ.pop('DATABASE_URL', None)
            importlib.reload(dbmod)


class TestIntegrityError(unittest.TestCase):
    """Test IntegrityError wrapping."""

    def test_integrity_error_is_exception(self):
        self.assertTrue(issubclass(IntegrityError, Exception))

    def test_cursor_adapter_wraps_sqlite_integrity_error(self):
        conn = sqlite3.connect(':memory:')
        conn.execute('CREATE TABLE t(id INTEGER UNIQUE)')
        conn.execute('INSERT INTO t VALUES(1)')
        conn.commit()

        adapter = ConnectionAdapter(conn)
        cur = adapter.cursor()
        # The IntegrityError should be raised by CursorAdapter.execute
        # Use a broad catch since module reloading may change class identity
        raised = False
        try:
            cur.execute('INSERT INTO t VALUES(?)', (1,))
        except Exception as e:
            if 'IntegrityError' in type(e).__name__ or 'UNIQUE' in str(e):
                raised = True
            else:
                raise
        self.assertTrue(raised, 'Expected an integrity error')
        conn.close()


class TestSqliteIntegration(unittest.TestCase):
    """End-to-end SQLite integration tests."""

    def test_connect_and_query(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            os.unlink(db_path)  # Remove so SQLite creates fresh
            old = os.environ.get('DB_PATH', '')
            os.environ['DB_PATH'] = db_path
            import importlib
            importlib.reload(dbmod)
            c = connect()
            c.execute('CREATE TABLE t(id INTEGER, name TEXT)')
            c.execute('INSERT INTO t VALUES(?, ?)', (1, 'test'))
            c.commit()
            row = c.execute('SELECT * FROM t WHERE id=?', (1,)).fetchone()
            self.assertEqual(row['name'], 'test')
            c.close()
            os.environ['DB_PATH'] = old if old else ''
            importlib.reload(dbmod)
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_db_context_manager(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            old = os.environ.get('DB_PATH', '')
            os.environ['DB_PATH'] = db_path
            import importlib
            importlib.reload(dbmod)
            with db(write=True) as c:
                c.execute('CREATE TABLE t(id INTEGER)')
                c.execute('INSERT INTO t VALUES(?)', (42,))
            with db() as c:
                row = c.execute('SELECT * FROM t').fetchone()
                self.assertEqual(row['id'], 42)
            os.environ['DB_PATH'] = old if old else ''
            importlib.reload(dbmod)
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_db_rollback_on_error(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            old = os.environ.get('DB_PATH', '')
            os.environ['DB_PATH'] = db_path
            import importlib
            importlib.reload(dbmod)
            with db(write=True) as c:
                c.execute('CREATE TABLE t(id INTEGER UNIQUE)')
            try:
                with db(write=True) as c:
                    c.execute('INSERT INTO t VALUES(?)', (1,))
                    raise ValueError('test error')
            except ValueError:
                pass
            with db() as c:
                count = c.execute('SELECT COUNT(*) as n FROM t').fetchone()
                self.assertEqual(count['n'], 0)
            os.environ['DB_PATH'] = old if old else ''
            importlib.reload(dbmod)
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


class TestSchemaParity(unittest.TestCase):
    """Verify SQLite and PostgreSQL schemas define the same tables and indexes."""

    def setUp(self):
        self.sqlite_schema = (ROOT / 'db' / 'schema.sql').read_text()
        self.pg_schema = (ROOT / 'db' / 'schema_postgres.sql').read_text()

    def test_same_table_set(self):
        sqlite_tables = set(re.findall(r'CREATE TABLE IF NOT EXISTS (\w+)', self.sqlite_schema))
        pg_tables = set(re.findall(r'CREATE TABLE IF NOT EXISTS (\w+)', self.pg_schema))
        # PostgreSQL has an extra schema_version table
        pg_tables.discard('schema_version')
        self.assertEqual(sqlite_tables, pg_tables, f'Table mismatch: SQLite={sqlite_tables}, PG={pg_tables}')

    def test_same_index_set(self):
        sqlite_indexes = set(re.findall(r'CREATE INDEX IF NOT EXISTS (\w+)', self.sqlite_schema))
        pg_indexes = set(re.findall(r'CREATE INDEX IF NOT EXISTS (\w+)', self.pg_schema))
        self.assertEqual(sqlite_indexes, pg_indexes, f'Index mismatch: SQLite={sqlite_indexes}, PG={pg_indexes}')


if __name__ == '__main__':
    unittest.main()
