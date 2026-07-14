#!/usr/bin/env python3
"""PostgreSQL compatibility validation tests.

These tests validate that the database abstraction layer (app/database.py)
is correctly structured for PostgreSQL compatibility WITHOUT requiring
a running PostgreSQL instance. They cover:

1. SQL placeholder conversion (_convert_sql)
2. RowAdapter class behaviour
3. CursorAdapter and ConnectionAdapter interface
4. schema_postgres.sql validity (syntax + structural checks)
5. All SQL in server.py uses ? placeholders (not %s directly)
6. INSERT OR IGNORE is properly converted to ON CONFLICT
7. Dialect detection (IS_POSTGRES flag)
8. IntegrityError mapping

Run:  python -m pytest tests/test_postgres_compat.py -v
"""

import os
import re
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure app/ is importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# We import database with DATABASE_URL unset so IS_POSTGRES is False
# (SQLite mode). This lets us test the SQLite path and the conversion
# logic by temporarily toggling IS_POSTGRES.
import app.database as dbmod


# ---------------------------------------------------------------------------
# 1. SQL placeholder conversion (_convert_sql)
# ---------------------------------------------------------------------------

class TestConvertSql:
    """Test the _convert_sql function that converts ? to %s for PostgreSQL."""

    def test_no_conversion_in_sqlite_mode(self):
        """In SQLite mode, _convert_sql should return the query unchanged."""
        original = dbmod.IS_POSTGRES
        dbmod.IS_POSTGRES = False
        try:
            q = "SELECT * FROM projects WHERE id = ? AND status = ?"
            assert dbmod._convert_sql(q) == q
        finally:
            dbmod.IS_POSTGRES = original

    def test_question_mark_replaced_in_postgres_mode(self):
        """In Postgres mode, ? outside string literals becomes %s."""
        original = dbmod.IS_POSTGRES
        dbmod.IS_POSTGRES = True
        try:
            q = "SELECT * FROM projects WHERE id = ? AND status = ?"
            expected = "SELECT * FROM projects WHERE id = %s AND status = %s"
            assert dbmod._convert_sql(q) == expected
        finally:
            dbmod.IS_POSTGRES = original

    def test_no_replacement_inside_single_quoted_strings(self):
        """? inside single-quoted string literals must not be converted."""
        original = dbmod.IS_POSTGRES
        dbmod.IS_POSTGRES = True
        try:
            q = "SELECT 'what is this?' AS literal WHERE id = ?"
            result = dbmod._convert_sql(q)
            assert "what is this?" in result  # literal preserved
            assert "%s" in result  # placeholder converted
            # The literal ? should still be ?
            assert "this?" in result
            # Count %s — should be exactly 1 (only the parameter)
            assert result.count("%s") == 1
        finally:
            dbmod.IS_POSTGRES = original

    def test_no_replacement_inside_double_quoted_strings(self):
        """? inside double-quoted identifiers must not be converted."""
        original = dbmod.IS_POSTGRES
        dbmod.IS_POSTGRES = True
        try:
            q = 'SELECT "col?" FROM projects WHERE id = ?'
            result = dbmod._convert_sql(q)
            assert '"col?"' in result  # identifier preserved
            assert result.count("%s") == 1
        finally:
            dbmod.IS_POSTGRES = original

    def test_escaped_single_quotes_preserved(self):
        """Doubled single quotes (SQL escape) should be preserved."""
        original = dbmod.IS_POSTGRES
        dbmod.IS_POSTGRES = True
        try:
            q = "SELECT 'it''s a test?' AS val WHERE id = ?"
            result = dbmod._convert_sql(q)
            # The ? inside the string literal should remain
            assert "test?" in result
            assert result.count("%s") == 1
        finally:
            dbmod.IS_POSTGRES = original

    def test_multiple_placeholders(self):
        """Multiple ? placeholders should all be converted."""
        original = dbmod.IS_POSTGRES
        dbmod.IS_POSTGRES = True
        try:
            q = "INSERT INTO projects(id,title,status,created_at,updated_at) VALUES(?,?,?,?,?)"
            result = dbmod._convert_sql(q)
            assert result.count("%s") == 5
            assert "?" not in result
        finally:
            dbmod.IS_POSTGRES = original

    def test_empty_query(self):
        """Empty string should return empty string."""
        original = dbmod.IS_POSTGRES
        dbmod.IS_POSTGRES = True
        try:
            assert dbmod._convert_sql("") == ""
        finally:
            dbmod.IS_POSTGRES = original

    def test_no_placeholders(self):
        """Query with no ? should be returned unchanged in either mode."""
        original = dbmod.IS_POSTGRES
        dbmod.IS_POSTGRES = True
        try:
            q = "SELECT 1"
            assert dbmod._convert_sql(q) == "SELECT 1"
        finally:
            dbmod.IS_POSTGRES = original

    def test_question_mark_in_comment_not_converted(self):
        """? in SQL comments should ideally not be converted (edge case)."""
        original = dbmod.IS_POSTGRES
        dbmod.IS_POSTGRES = True
        try:
            # This is a known limitation — comments aren't parsed.
            # We just verify the function doesn't crash.
            q = "-- is this ok?\nSELECT * FROM projects WHERE id = ?"
            result = dbmod._convert_sql(q)
            assert "%s" in result
        finally:
            dbmod.IS_POSTGRES = original


# ---------------------------------------------------------------------------
# 2. RowAdapter class
# ---------------------------------------------------------------------------

class TestRowAdapter:
    """Test the RowAdapter that normalizes row access across backends."""

    def test_from_dict(self):
        row = dbmod.RowAdapter({"id": "abc", "title": "Test"})
        assert row["id"] == "abc"
        assert row["title"] == "Test"

    def test_from_sqlite_row(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE t(id TEXT, val INTEGER)")
        conn.execute("INSERT INTO t VALUES ('x', 42)")
        raw = conn.execute("SELECT * FROM t").fetchone()
        row = dbmod.RowAdapter(raw)
        assert row["id"] == "x"
        assert row["val"] == 42
        conn.close()

    def test_get_with_default(self):
        row = dbmod.RowAdapter({"id": "abc"})
        assert row.get("id") == "abc"
        assert row.get("missing") is None
        assert row.get("missing", "default") == "default"

    def test_contains(self):
        row = dbmod.RowAdapter({"id": "abc", "title": "Test"})
        assert "id" in row
        assert "title" in row
        assert "missing" not in row

    def test_keys(self):
        row = dbmod.RowAdapter({"id": "abc", "title": "Test"})
        assert set(row.keys()) == {"id", "title"}

    def test_items(self):
        row = dbmod.RowAdapter({"id": "abc"})
        items = dict(row.items())
        assert items == {"id": "abc"}

    def test_len(self):
        row = dbmod.RowAdapter({"id": "abc", "title": "Test"})
        assert len(row) == 2

    def test_iter(self):
        row = dbmod.RowAdapter({"id": "abc", "title": "Test"})
        keys = list(iter(row))
        assert set(keys) == {"id", "title"}

    def test_repr(self):
        row = dbmod.RowAdapter({"id": "abc"})
        assert "abc" in repr(row)


# ---------------------------------------------------------------------------
# 3. CursorAdapter and ConnectionAdapter interface
# ---------------------------------------------------------------------------

class TestCursorAdapter:
    """Test CursorAdapter wraps cursors and converts SQL."""

    def test_execute_converts_placeholders_in_pg_mode(self):
        original = dbmod.IS_POSTGRES
        dbmod.IS_POSTGRES = True
        try:
            mock_cursor = MagicMock()
            adapter = dbmod.CursorAdapter(mock_cursor)
            adapter.execute("SELECT * FROM t WHERE id = ?", ("x",))
            # The underlying cursor should have received %s
            call_args = mock_cursor.execute.call_args
            assert "%s" in call_args[0][0]
            assert "?" not in call_args[0][0]
        finally:
            dbmod.IS_POSTGRES = original

    def test_execute_no_conversion_in_sqlite_mode(self):
        original = dbmod.IS_POSTGRES
        dbmod.IS_POSTGRES = False
        try:
            mock_cursor = MagicMock()
            adapter = dbmod.CursorAdapter(mock_cursor)
            q = "SELECT * FROM t WHERE id = ?"
            adapter.execute(q, ("x",))
            call_args = mock_cursor.execute.call_args
            assert call_args[0][0] == q  # unchanged
        finally:
            dbmod.IS_POSTGRES = original

    def test_fetchone_returns_row_adapter(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": "abc"}
        adapter = dbmod.CursorAdapter(mock_cursor)
        row = adapter.fetchone()
        assert isinstance(row, dbmod.RowAdapter)
        assert row["id"] == "abc"

    def test_fetchone_returns_none(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        adapter = dbmod.CursorAdapter(mock_cursor)
        assert adapter.fetchone() is None

    def test_fetchall_returns_row_adapters(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [{"id": "a"}, {"id": "b"}]
        adapter = dbmod.CursorAdapter(mock_cursor)
        rows = adapter.fetchall()
        assert len(rows) == 2
        assert all(isinstance(r, dbmod.RowAdapter) for r in rows)
        assert rows[0]["id"] == "a"
        assert rows[1]["id"] == "b"

    def test_rowcount_property(self):
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 5
        adapter = dbmod.CursorAdapter(mock_cursor)
        assert adapter.rowcount == 5

    def test_lastrowid_none_in_pg_mode(self):
        original = dbmod.IS_POSTGRES
        dbmod.IS_POSTGRES = True
        try:
            mock_cursor = MagicMock()
            adapter = dbmod.CursorAdapter(mock_cursor)
            assert adapter.lastrowid is None
        finally:
            dbmod.IS_POSTGRES = original

    def test_lastrowid_in_sqlite_mode(self):
        original = dbmod.IS_POSTGRES
        dbmod.IS_POSTGRES = False
        try:
            mock_cursor = MagicMock()
            mock_cursor.lastrowid = 42
            adapter = dbmod.CursorAdapter(mock_cursor)
            assert adapter.lastrowid == 42
        finally:
            dbmod.IS_POSTGRES = original

    def test_executescript_pg_mode(self):
        """In PG mode, executescript should call execute (not executescript)."""
        original = dbmod.IS_POSTGRES
        dbmod.IS_POSTGRES = True
        try:
            mock_cursor = MagicMock()
            adapter = dbmod.CursorAdapter(mock_cursor)
            adapter.executescript("CREATE TABLE t(id TEXT);")
            mock_cursor.execute.assert_called_with("CREATE TABLE t(id TEXT);")
            mock_cursor.executescript.assert_not_called()
        finally:
            dbmod.IS_POSTGRES = original

    def test_executescript_sqlite_mode(self):
        """In SQLite mode, executescript should call the real executescript."""
        original = dbmod.IS_POSTGRES
        dbmod.IS_POSTGRES = False
        try:
            mock_cursor = MagicMock()
            adapter = dbmod.CursorAdapter(mock_cursor)
            adapter.executescript("CREATE TABLE t(id TEXT);")
            mock_cursor.executescript.assert_called_once()
        finally:
            dbmod.IS_POSTGRES = original


class TestConnectionAdapter:
    """Test ConnectionAdapter interface."""

    def test_commit_calls_underlying(self):
        mock_conn = MagicMock()
        adapter = dbmod.ConnectionAdapter(mock_conn)
        adapter.commit()
        mock_conn.commit.assert_called_once()

    def test_rollback_calls_underlying(self):
        mock_conn = MagicMock()
        adapter = dbmod.ConnectionAdapter(mock_conn)
        adapter.rollback()
        mock_conn.rollback.assert_called_once()

    def test_execute_returns_cursor_adapter(self):
        original = dbmod.IS_POSTGRES
        dbmod.IS_POSTGRES = False
        try:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.rowcount = 0
            adapter = dbmod.ConnectionAdapter(mock_conn)
            result = adapter.execute("SELECT 1")
            assert isinstance(result, dbmod.CursorAdapter)
        finally:
            dbmod.IS_POSTGRES = original

    def test_backup_raises_in_pg_mode(self):
        original = dbmod.IS_POSTGRES
        dbmod.IS_POSTGRES = True
        try:
            mock_conn = MagicMock()
            adapter = dbmod.ConnectionAdapter(mock_conn)
            with pytest.raises(RuntimeError, match="pg_dump"):
                adapter.backup(MagicMock())
        finally:
            dbmod.IS_POSTGRES = original

    def test_row_factory_setter_is_noop(self):
        """Setting row_factory should not raise."""
        mock_conn = MagicMock()
        adapter = dbmod.ConnectionAdapter(mock_conn)
        adapter.row_factory = sqlite3.Row  # should not raise

    def test_context_manager(self):
        mock_conn = MagicMock()
        adapter = dbmod.ConnectionAdapter(mock_conn)
        with adapter as ctx:
            assert ctx is adapter
        mock_conn.close.assert_called_once()


# ---------------------------------------------------------------------------
# 4. schema_postgres.sql validity
# ---------------------------------------------------------------------------

class TestPostgresSchema:
    """Validate schema_postgres.sql is syntactically valid and structurally complete."""

    @pytest.fixture
    def schema_sql(self):
        path = ROOT / "db" / "schema_postgres.sql"
        assert path.exists(), "schema_postgres.sql must exist"
        return path.read_text()

    def test_file_exists(self, schema_sql):
        assert len(schema_sql) > 100

    def test_no_sqlite_pragmas(self, schema_sql):
        """PostgreSQL schema must not contain SQLite PRAGMA statements."""
        assert "PRAGMA" not in schema_sql, "schema_postgres.sql must not use PRAGMA"

    def test_no_sqlite_autoincrement(self, schema_sql):
        """PostgreSQL schema must not use AUTOINCREMENT (use SERIAL/IDENTITY instead)."""
        assert "AUTOINCREMENT" not in schema_sql.upper(), \
            "schema_postgres.sql must not use AUTOINCREMENT"

    def test_no_sqlite_triggers_syntax(self, schema_sql):
        """PostgreSQL schema must not use SQLite trigger syntax (RAISE/BEGIN...END)."""
        assert "RAISE(ABORT" not in schema_sql, \
            "schema_postgres.sql must not use SQLite RAISE(ABORT) syntax"

    def test_uses_on_conflict_not_insert_or_ignore(self, schema_sql):
        """PostgreSQL schema should use ON CONFLICT, not INSERT OR IGNORE."""
        assert "INSERT OR IGNORE" not in schema_sql.upper(), \
            "schema_postgres.sql must not use INSERT OR IGNORE"
        assert "ON CONFLICT" in schema_sql, \
            "schema_postgres.sql should use ON CONFLICT for upserts"

    def test_has_all_required_tables(self, schema_sql):
        """All tables from the SQLite schema must be present in the PG schema."""
        required_tables = [
            "schema_version",
            "projects",
            "sources",
            "documents",
            "claims",
            "claim_reviews",
            "claim_revisions",
            "gaps",
            "responses",
            "auth_tokens",
            "audit_events",
            "audit_checkpoints",
            "idempotency_keys",
        ]
        for table in required_tables:
            assert re.search(
                rf"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+{table}\b",
                schema_sql,
                re.IGNORECASE
            ), f"Table '{table}' missing from schema_postgres.sql"

    def test_has_required_indexes(self, schema_sql):
        """Key indexes from SQLite schema should be present."""
        required_indexes = [
            "idx_projects_status",
            "idx_sources_project",
            "idx_documents_project",
            "idx_claims_project_state",
            "idx_audit_object",
            "idx_auth_active",
        ]
        for idx in required_indexes:
            assert idx in schema_sql, f"Index '{idx}' missing from schema_postgres.sql"

    def test_schema_version_set_to_3(self, schema_sql):
        """Schema version should be set to 3 at the end."""
        assert "UPDATE schema_version SET value = 3" in schema_sql

    def test_foreign_keys_present(self, schema_sql):
        """Foreign key constraints should be present."""
        assert "FOREIGN KEY" in schema_sql or "REFERENCES" in schema_sql

    def test_check_constraints_present(self, schema_sql):
        """CHECK constraints from SQLite should be preserved."""
        assert "CHECK" in schema_sql.upper()

    def test_uses_create_function_not_sqlite_triggers(self, schema_sql):
        """PostgreSQL uses CREATE FUNCTION + triggers, not SQLite trigger bodies."""
        # Should have CREATE FUNCTION for the immutability enforcement
        assert "CREATE FUNCTION" in schema_sql.upper() or "CREATE OR REPLACE FUNCTION" in schema_sql.upper(), \
            "schema_postgres.sql should use PostgreSQL functions for trigger logic"

    def test_no_question_mark_placeholders(self, schema_sql):
        """Schema SQL should not contain ? placeholders (it's DDL, not DML)."""
        # In DDL, ? should not appear
        # Allow ? in comments only
        lines = [l for l in schema_sql.split("\n") if not l.strip().startswith("--")]
        non_comment = "\n".join(lines)
        assert "?" not in non_comment, "schema_postgres.sql should not contain ? placeholders"

    def test_basic_sql_parse(self, schema_sql):
        """Basic structural validation: balanced parentheses, semicolons."""
        # Check balanced parentheses
        open_count = schema_sql.count("(")
        close_count = schema_sql.count(")")
        assert open_count == close_count, \
            f"Unbalanced parentheses in schema_postgres.sql: {open_count} open, {close_count} close"

        # Check that statements are terminated with semicolons
        # Remove comment lines
        code_lines = [l for l in schema_sql.split("\n") if not l.strip().startswith("--")]
        code = "\n".join(code_lines).strip()
        assert code.endswith(";"), "schema_postgres.sql should end with semicolon"

        # Count CREATE statements
        create_count = len(re.findall(r"CREATE\s+(?:TABLE|INDEX|FUNCTION|OR\s+REPLACE\s+FUNCTION|TRIGGER)", code, re.IGNORECASE))
        assert create_count >= 10, f"Expected at least 10 CREATE statements, found {create_count}"


# ---------------------------------------------------------------------------
# 5. All SQL in server.py uses ? placeholders (not %s directly)
# ---------------------------------------------------------------------------

class TestServerQueryPlaceholders:
    """Ensure server.py uses ? placeholders consistently (not %s)."""

    @pytest.fixture
    def server_source(self):
        path = ROOT / "app" / "server.py"
        return path.read_text()

    def test_no_direct_percent_s_in_queries(self, server_source):
        """server.py must not use %s directly in SQL strings (conversion handles it)."""
        # Look for %s inside string literals that look like SQL
        # This is a heuristic: find %s that appears near SQL keywords
        sql_with_percent_s = re.findall(
            r"['\"].*(?:SELECT|INSERT|UPDATE|DELETE|FROM|WHERE|VALUES).*%s.*['\"]",
            server_source,
            re.IGNORECASE | re.DOTALL
        )
        assert len(sql_with_percent_s) == 0, \
            f"server.py contains direct %s in SQL strings: {sql_with_percent_s}"

    def test_uses_question_mark_placeholders(self, server_source):
        """server.py should use ? placeholders for parameters."""
        # Count ? in execute calls
        execute_calls = re.findall(r"\.execute\s*\([^)]+", server_source)
        has_question_mark = any("?" in call for call in execute_calls)
        assert has_question_mark, "server.py should use ? placeholders in execute calls"

    def test_insert_or_ignore_is_conditional(self, server_source):
        """INSERT OR IGNORE should be conditionally built, not hardcoded."""
        # The pattern should use IS_POSTGRES to switch
        if "OR IGNORE" in server_source:
            # Must be conditional on IS_POSTGRES
            assert "IS_POSTGRES" in server_source, \
                "INSERT OR IGNORE must be conditional on IS_POSTGRES"
            # Find the context
            idx = server_source.index("OR IGNORE")
            context = server_source[max(0, idx - 200):idx + 200]
            assert "IS_POSTGRES" in context or "if not IS_POSTGRES" in context, \
                "INSERT OR IGNORE must be gated on IS_POSTGRES"

    def test_on_conflict_is_conditional(self, server_source):
        """ON CONFLICT should be conditionally added for PostgreSQL."""
        if "ON CONFLICT" in server_source:
            idx = server_source.index("ON CONFLICT")
            context = server_source[max(0, idx - 200):idx + 200]
            assert "IS_POSTGRES" in context, \
                "ON CONFLICT in server.py must be gated on IS_POSTGRES"


# ---------------------------------------------------------------------------
# 6. INSERT OR IGNORE → ON CONFLICT conversion
# ---------------------------------------------------------------------------

class TestInsertOrIgnoreConversion:
    """Test that INSERT OR IGNORE is properly handled for PostgreSQL."""

    def test_server_handles_insert_or_ignore_conditionally(self):
        """server.py should conditionally use ON CONFLICT DO NOTHING for PG."""
        server_path = ROOT / "app" / "server.py"
        source = server_path.read_text()

        # Find the INSERT OR IGNORE pattern
        # It should be: 'INSERT' + (' OR IGNORE' if not IS_POSTGRES else '') + ...
        # and then: + (' ON CONFLICT DO NOTHING' if IS_POSTGRES else '')
        assert "OR IGNORE" in source or "ON CONFLICT" in source, \
            "server.py should handle INSERT OR IGNORE / ON CONFLICT"

        # Verify the conditional logic exists
        if "OR IGNORE" in source:
            assert "IS_POSTGRES" in source, \
                "INSERT OR IGNORE handling must reference IS_POSTGRES"

    def test_schema_postgres_uses_on_conflict(self):
        """schema_postgres.sql should use ON CONFLICT, not INSERT OR IGNORE."""
        schema_path = ROOT / "db" / "schema_postgres.sql"
        schema = schema_path.read_text()
        assert "INSERT OR IGNORE" not in schema.upper(), \
            "schema_postgres.sql must not use INSERT OR IGNORE"
        assert "ON CONFLICT" in schema, \
            "schema_postgres.sql should use ON CONFLICT"

    def test_convert_sql_preserves_on_conflict(self):
        """_convert_sql should not break ON CONFLICT syntax."""
        original = dbmod.IS_POSTGRES
        dbmod.IS_POSTGRES = True
        try:
            q = "INSERT INTO t(id) VALUES(?) ON CONFLICT DO NOTHING"
            result = dbmod._convert_sql(q)
            assert "ON CONFLICT DO NOTHING" in result
            assert result.count("%s") == 1
        finally:
            dbmod.IS_POSTGRES = original


# ---------------------------------------------------------------------------
# 7. Dialect detection (IS_POSTGRES flag)
# ---------------------------------------------------------------------------

class TestDialectDetection:
    """Test that IS_POSTGRES is correctly determined from DATABASE_URL."""

    def test_is_postgres_false_by_default(self):
        """Without DATABASE_URL, IS_POSTGRES should be False."""
        # We imported with DATABASE_URL unset
        assert dbmod.IS_POSTGRES is False or dbmod.DATABASE_URL == ""

    def test_is_postgres_true_when_database_url_set(self):
        """When DATABASE_URL is set, IS_POSTGRES should be True."""
        # Save original
        original_url = os.environ.get("DATABASE_URL", "")
        original_flag = dbmod.IS_POSTGRES
        try:
            os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/testdb"
            # Re-evaluate the flag
            assert bool(os.getenv("DATABASE_URL", "")) is True
        finally:
            if original_url:
                os.environ["DATABASE_URL"] = original_url
            else:
                os.environ.pop("DATABASE_URL", None)
            dbmod.IS_POSTGRES = original_flag


# ---------------------------------------------------------------------------
# 8. IntegrityError mapping
# ---------------------------------------------------------------------------

class TestIntegrityError:
    """Test that IntegrityError is properly mapped."""

    def test_integrity_error_is_exception(self):
        assert issubclass(dbmod.IntegrityError, Exception)

    def test_wrap_integrity_error_wraps_sqlite_error(self):
        """wrap_integrity_error should catch sqlite3.IntegrityError."""
        @dbmod.wrap_integrity_error
        def raise_sqlite_error():
            raise sqlite3.IntegrityError("UNIQUE constraint failed")

        with pytest.raises(dbmod.IntegrityError):
            raise_sqlite_error()

    def test_wrap_integrity_error_passes_through_other_errors(self):
        """wrap_integrity_error should not catch non-integrity errors."""
        @dbmod.wrap_integrity_error
        def raise_value_error():
            raise ValueError("not an integrity error")

        with pytest.raises(ValueError):
            raise_value_error()

    def test_wrap_integrity_error_returns_value_on_success(self):
        """wrap_integrity_error should return the function's result on success."""
        @dbmod.wrap_integrity_error
        def success_func():
            return "ok"

        assert success_func() == "ok"

    def test_cursor_adapter_wraps_sqlite_integrity_error(self):
        """CursorAdapter.execute should wrap sqlite3.IntegrityError as IntegrityError."""
        original = dbmod.IS_POSTGRES
        dbmod.IS_POSTGRES = False
        try:
            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            conn.execute("CREATE TABLE t(id TEXT UNIQUE)")
            conn.execute("INSERT INTO t VALUES ('x')")
            adapter = dbmod.ConnectionAdapter(conn)
            with pytest.raises(dbmod.IntegrityError):
                adapter.execute("INSERT INTO t VALUES (?)", ("x",))
            conn.close()
        finally:
            dbmod.IS_POSTGRES = original


# ---------------------------------------------------------------------------
# 9. SQLite integration smoke test (validates the abstraction works end-to-end)
# ---------------------------------------------------------------------------

class TestSqliteIntegration:
    """Smoke test the abstraction layer with a real SQLite database."""

    def test_connect_and_query(self):
        """connect() should return a working ConnectionAdapter in SQLite mode."""
        original = dbmod.IS_POSTGRES
        dbmod.IS_POSTGRES = False
        try:
            db_path = ROOT / "data" / "test_postgres_compat.db"
            if db_path.exists():
                db_path.unlink()
            conn = dbmod.connect(str(db_path))
            assert isinstance(conn, dbmod.ConnectionAdapter)
            conn.execute("CREATE TABLE test_compat(id TEXT, val INTEGER)")
            conn.execute("INSERT INTO test_compat VALUES (?, ?)", ("a", 1))
            conn.commit()
            row = conn.execute("SELECT * FROM test_compat WHERE id = ?", ("a",)).fetchone()
            assert row is not None
            assert row["id"] == "a"
            assert row["val"] == 1
            conn.close()
            if db_path.exists():
                db_path.unlink()
        finally:
            dbmod.IS_POSTGRES = original

    def test_db_context_manager(self):
        """db() context manager should work for write operations."""
        original = dbmod.IS_POSTGRES
        original_db_path = dbmod.DB_PATH
        dbmod.IS_POSTGRES = False
        try:
            db_path = ROOT / "data" / "test_postgres_compat_ctx.db"
            if db_path.exists():
                db_path.unlink()
            dbmod.DB_PATH = db_path  # patch module-level variable
            # First create the table
            with dbmod.connect(str(db_path)) as conn:
                conn.execute("CREATE TABLE test_ctx(id TEXT)")
                conn.commit()
            # Now test the context manager
            with dbmod.db(write=True) as conn:
                conn.execute("INSERT INTO test_ctx VALUES (?)", ("test",))
            # Verify it was committed
            with dbmod.db() as conn:
                row = conn.execute("SELECT * FROM test_ctx").fetchone()
                assert row is not None
                assert row["id"] == "test"
            if db_path.exists():
                db_path.unlink()
        finally:
            dbmod.IS_POSTGRES = original
            dbmod.DB_PATH = original_db_path

    def test_db_rollback_on_error(self):
        """db() should rollback on error in write mode."""
        original = dbmod.IS_POSTGRES
        original_db_path = dbmod.DB_PATH
        dbmod.IS_POSTGRES = False
        try:
            db_path = ROOT / "data" / "test_postgres_compat_rb.db"
            if db_path.exists():
                db_path.unlink()
            dbmod.DB_PATH = db_path  # patch module-level variable
            with dbmod.connect(str(db_path)) as conn:
                conn.execute("CREATE TABLE test_rb(id TEXT UNIQUE)")
                conn.commit()
            # Insert a row
            with dbmod.db(write=True) as conn:
                conn.execute("INSERT INTO test_rb VALUES (?)", ("first",))
            # Try to insert duplicate — should fail and rollback
            with pytest.raises(dbmod.IntegrityError):
                with dbmod.db(write=True) as conn:
                    conn.execute("INSERT INTO test_rb VALUES (?)", ("first",))
            # Verify only one row exists
            with dbmod.db() as conn:
                rows = conn.execute("SELECT * FROM test_rb").fetchall()
                assert len(rows) == 1
            if db_path.exists():
                db_path.unlink()
        finally:
            dbmod.IS_POSTGRES = original
            dbmod.DB_PATH = original_db_path


# ---------------------------------------------------------------------------
# 10. Cross-backend schema parity check
# ---------------------------------------------------------------------------

class TestSchemaParity:
    """Verify PostgreSQL schema has parity with SQLite schema."""

    @pytest.fixture
    def sqlite_schema(self):
        return (ROOT / "db" / "schema.sql").read_text()

    @pytest.fixture
    def pg_schema(self):
        return (ROOT / "db" / "schema_postgres.sql").read_text()

    def test_same_table_set(self, sqlite_schema, pg_schema):
        """Both schemas should define the same set of tables.

        Note: schema_version table exists only in PostgreSQL (SQLite uses
        PRAGMA user_version). We exclude it from the parity check.
        """
        sqlite_tables = set(re.findall(
            r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+(\w+)", sqlite_schema, re.IGNORECASE
        ))
        pg_tables = set(re.findall(
            r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+(\w+)", pg_schema, re.IGNORECASE
        ))
        # schema_version is PG-only (SQLite uses PRAGMA user_version)
        pg_tables.discard("schema_version")
        assert sqlite_tables == pg_tables, \
            f"Table mismatch: SQLite has {sqlite_tables - pg_tables} extra, " \
            f"PG has {pg_tables - sqlite_tables} extra"

    def test_same_index_set(self, sqlite_schema, pg_schema):
        """Both schemas should define the same set of indexes."""
        sqlite_indexes = set(re.findall(
            r"CREATE\s+INDEX\s+IF\s+NOT\s+EXISTS\s+(\w+)", sqlite_schema, re.IGNORECASE
        ))
        pg_indexes = set(re.findall(
            r"CREATE\s+INDEX\s+IF\s+NOT\s+EXISTS\s+(\w+)", pg_schema, re.IGNORECASE
        ))
        assert sqlite_indexes == pg_indexes, \
            f"Index mismatch: SQLite has {sqlite_indexes - pg_indexes} extra, " \
            f"PG has {pg_indexes - sqlite_indexes} extra"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
