#!/usr/bin/env python3
"""Verify the audit hash chain for SQLite or PostgreSQL.

When DATABASE_URL is set, the database path argument is ignored and the
configured PostgreSQL instance is verified. Otherwise the SQLite file path is
used via the shared database abstraction.
"""
import argparse, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.audit import verify
from app.database import IS_POSTGRES, connect


def main():
    p = argparse.ArgumentParser(description='Verify audit chain integrity')
    p.add_argument('database', nargs='?', default='', help='SQLite DB path (ignored when DATABASE_URL is set)')
    p.add_argument('--key-env', default='AUDIT_HMAC_KEY')
    a = p.parse_args()
    key = os.getenv(a.key_env, '')
    if not key:
        print(json.dumps({'status': 'error', 'error': f'{a.key_env} is required'}))
        return 1
    try:
        if IS_POSTGRES:
            c = connect()
        else:
            if not a.database:
                print(json.dumps({'status': 'error', 'error': 'database path required for SQLite mode'}))
                return 1
            c = connect(a.database)
        try:
            result = verify(c, key)
            print(json.dumps({'status': 'ok', 'backend': 'postgres' if IS_POSTGRES else 'sqlite', **result}, sort_keys=True))
            return 0
        finally:
            c.close()
    except Exception as e:
        print(json.dumps({'status': 'error', 'error': str(e)}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
