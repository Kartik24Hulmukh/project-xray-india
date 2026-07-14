#!/usr/bin/env python3
"""Database abstraction layer supporting SQLite and PostgreSQL.

When DATABASE_URL is set (e.g. postgresql://user:pass@host:5432/dbname),
this module uses psycopg2 with a connection pool. Otherwise it falls
back to SQLite using the DB_PATH environment variable.

The rest of the application interacts only with the context manager
and helper functions exported here; no other module imports sqlite3
or psycopg2 directly.
"""

import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

try:
    import psycopg2
    from psycopg2 import pool as pg_pool
    from psycopg2.extras import RealDictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

ROOT = Path(__file__).resolve().parents[1]
DATABASE_URL = os.getenv('DATABASE_URL', '')
DB_PATH = Path(os.getenv('DB_PATH', str(ROOT / 'data/project_xray.db')))

# Dialect flag
IS_POSTGRES = bool(DATABASE_URL)

_pool = None


def _get_pool():
    global _pool
    if _pool is None and HAS_PSYCOPG2:
        _pool = pg_pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=int(os.getenv('DB_POOL_MAX', '10')),
            dsn=DATABASE_URL,
            cursor_factory=RealDictCursor,
        )
    return _pool


def _convert_sql(query):
    """Convert SQLite-style ? placeholders to PostgreSQL %s."""
    if not IS_POSTGRES:
        return query
    # Replace ? with %s but not inside string literals
    result = []
    in_string = False
    quote_char = None
    i = 0
    while i < len(query):
        ch = query[i]
        if in_string:
            result.append(ch)
            if ch == quote_char:
                # Check for escaped quote
                if i + 1 < len(query) and query[i + 1] == quote_char:
                    result.append(query[i + 1])
                    i += 2
                    continue
                in_string = False
            i += 1
        else:
            if ch in ("'", '"'):
                in_string = True
                quote_char = ch
                result.append(ch)
                i += 1
            elif ch == '?':
                result.append('%s')
                i += 1
            else:
                result.append(ch)
                i += 1
    return ''.join(result)


class RowAdapter:
    """Wraps a psycopg2 RealDictRow or sqlite3.Row for dict-like access."""

    def __init__(self, row):
        if isinstance(row, dict):
            self._data = row
        elif isinstance(row, sqlite3.Row):
            self._data = dict(row)
        else:
            self._data = dict(row)

    def __getitem__(self, key):
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

    def get(self, key, default=None):
        return self._data.get(key, default)

    def keys(self):
        return self._data.keys()

    def items(self):
        return self._data.items()

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __repr__(self):
        return repr(self._data)


class CursorAdapter:
    """Wraps a cursor to convert ? placeholders and normalize row types."""

    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, params=()):
        try:
            self._cursor.execute(_convert_sql(query), params)
        except Exception as e:
            # Wrap sqlite3.IntegrityError and psycopg2.IntegrityError
            if isinstance(e, sqlite3.IntegrityError):
                raise IntegrityError(str(e))
            if HAS_PSYCOPG2 and isinstance(e, psycopg2.IntegrityError):
                raise IntegrityError(str(e))
            raise
        return self

    def executemany(self, query, params_seq):
        self._cursor.executemany(_convert_sql(query), params_seq)

    def executescript(self, script):
        if IS_POSTGRES:
            self._cursor.execute(script)
        else:
            self._cursor.executescript(script)

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return RowAdapter(row)

    def fetchall(self):
        return [RowAdapter(r) for r in self._cursor.fetchall()]

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        if IS_POSTGRES:
            return None
        return self._cursor.lastrowid

    def close(self):
        self._cursor.close()

    def __iter__(self):
        for row in self._cursor:
            yield RowAdapter(row)


class ConnectionAdapter:
    """Wraps a connection to provide a uniform interface."""

    def __init__(self, conn):
        self._conn = conn
        self._is_pg = IS_POSTGRES

    def cursor(self):
        if self._is_pg:
            return CursorAdapter(self._conn.cursor(cursor_factory=RealDictCursor))
        cur = self._conn.cursor()
        cur.row_factory = sqlite3.Row
        return CursorAdapter(cur)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        if self._is_pg:
            _get_pool().putconn(self._conn)
        else:
            self._conn.close()

    def backup(self, dst_conn):
        """SQLite-only: backup to another SQLite connection."""
        if self._is_pg:
            raise RuntimeError('Use pg_dump for PostgreSQL backup')
        if hasattr(dst_conn, '_conn'):
            dst_conn._conn.backup(self._conn)
        else:
            self._conn.backup(dst_conn)

    def execute(self, query, params=()):
        cur = self.cursor()
        cur.execute(query, params)
        return cur

    def executescript(self, script):
        cur = self.cursor()
        cur.executescript(script)
        cur.close()
        return self

    @property
    def row_factory(self):
        return None

    @row_factory.setter
    def row_factory(self, value):
        # No-op for PostgreSQL; SQLite uses cursor-level setting
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def connect(path=None):
    """Return a ConnectionAdapter for the configured database."""
    if IS_POSTGRES:
        if not HAS_PSYCOPG2:
            raise RuntimeError('DATABASE_URL is set but psycopg2 is not installed')
        p = _get_pool()
        conn = p.getconn()
        adapter = ConnectionAdapter(conn)
        # Set connection-level options
        adapter.execute('SET statement_timeout = %s', (int(os.getenv('DB_STATEMENT_TIMEOUT_MS', '30000')),))
        return adapter
    else:
        p = Path(path or DB_PATH)
        p.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(p), timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA busy_timeout=5000')
        return ConnectionAdapter(conn)


@contextmanager
def db(write=False):
    """Context manager yielding a connection. Commits on write, rolls back on error."""
    c = connect()
    try:
        if write and not IS_POSTGRES:
            c.execute('BEGIN IMMEDIATE')
        elif write and IS_POSTGRES:
            # PostgreSQL auto-begins on first statement; explicit for clarity
            pass
        yield c
        if write:
            c.commit()
    except Exception:
        if write:
            c.rollback()
        raise
    finally:
        c.close()


def get_schema_version(c):
    """Return the schema version integer."""
    if IS_POSTGRES:
        row = c.execute(
            "SELECT value FROM schema_version WHERE id = 1"
        ).fetchone()
        return int(row['value']) if row else 0
    else:
        row = c.execute('PRAGMA user_version').fetchone()
        # PRAGMA returns a row with integer-indexed columns
        if isinstance(row, RowAdapter):
            # Try string key first, then integer index
            try:
                return int(row['user_version'])
            except (KeyError, TypeError):
                return int(list(row._data.values())[0])
        return int(row[0])


def set_schema_version(c, version):
    """Set the schema version."""
    if IS_POSTGRES:
        c.execute(
            "UPDATE schema_version SET value = %s WHERE id = 1",
            (version,),
        )
    else:
        c.execute(f'PRAGMA user_version = {version}')


def table_exists(c, table_name):
    """Check if a table exists."""
    if IS_POSTGRES:
        row = c.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
            (table_name,),
        ).fetchone()
        return row is not None
    else:
        row = c.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        return row is not None


def integrity_check(c):
    """Run database integrity check."""
    if IS_POSTGRES:
        # PostgreSQL doesn't have a single integrity check; verify core tables exist
        required = {'projects', 'sources', 'documents', 'claims', 'claim_reviews',
                    'audit_events', 'audit_checkpoints', 'idempotency_keys'}
        existing = set()
        for row in c.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        ).fetchall():
            existing.add(row['table_name'])
        missing = required - existing
        if missing:
            return f'missing tables: {sorted(missing)}'
        return 'ok'
    else:
        return c.execute('PRAGMA integrity_check').fetchone()[0]


class IntegrityError(Exception):
    """Raised on constraint violations. Maps sqlite3.IntegrityError and psycopg2 errors."""


def wrap_integrity_error(func):
    """Decorator to wrap database integrity errors uniformly."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except sqlite3.IntegrityError:
            raise IntegrityError('constraint violation')
        except Exception as e:
            if HAS_PSYCOPG2 and isinstance(e, psycopg2.IntegrityError):
                raise IntegrityError(str(e))
            raise
    return wrapper
