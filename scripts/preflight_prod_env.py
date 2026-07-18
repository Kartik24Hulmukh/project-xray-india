#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = [
    'app/server.py',
    'scripts/smoke_e2e.py',
    'scripts/verify_capsule.py',
    'scripts/recovery_evidence.py',
    'schemas/evidence-envelope.schema.json',
]
REQUIRED_ENV = {
    'PUBLIC_BASE_URL': lambda v: isinstance(v, str) and v.startswith('https://'),
    'TOKEN_PEPPER': lambda v: isinstance(v, str) and len(v) >= 32,
    'AUDIT_HMAC_KEY': lambda v: isinstance(v, str) and len(v) >= 32,
    'BACKUP_HMAC_KEY': lambda v: isinstance(v, str) and len(v) >= 32,
    'OIDC_PROXY_SECRET': lambda v: isinstance(v, str) and len(v) >= 32,
    'GATEWAY_ASSERTION_VERSION': lambda v: v == '1',
    'GATEWAY_ASSERTION_AUDIENCE': lambda v: isinstance(v, str) and bool(v),
    'GATEWAY_ASSERTION_ISSUERS': lambda v: isinstance(v, str) and v.startswith('https://'),
    'GATEWAY_ASSERTION_KEY_ID': lambda v: isinstance(v, str) and bool(v),
    'OBJECT_STORAGE_MODE': lambda v: v == 'managed',
    'STORAGE_ENDPOINT': lambda v: isinstance(v, str) and (not v or v.startswith(('http://', 'https://'))),
    'STORAGE_BUCKET': lambda v: isinstance(v, str) and bool(v),
    'MONITORING_WEBHOOK_URL': lambda v: isinstance(v, str) and v.startswith(('http://', 'https://')),
    'MONITORING_WEBHOOK_SECRET': lambda v: isinstance(v, str) and len(v) >= 32,
}


def command_check(name):
    return {'name': f'command:{name}', 'ok': shutil.which(name) is not None}


def file_check(path):
    return {'name': f'file:{path}', 'ok': (ROOT / path).exists()}


def env_check(name, env):
    value = env.get(name, '')
    return {'name': f'env:{name}', 'ok': REQUIRED_ENV[name](value), 'value_present': bool(value)}


def collect(env=None):
    env = dict(env or os.environ)
    checks = []
    for name in ('python3', 'node', 'curl', 'chromium'):
        checks.append(command_check(name))
    for path in REQUIRED_FILES:
        checks.append(file_check(path))
    for name in REQUIRED_ENV:
        checks.append(env_check(name, env))
    access_key = env.get('STORAGE_ACCESS_KEY', '')
    secret_key = env.get('STORAGE_SECRET_KEY', '')
    checks.append({
        'name': 'env:STORAGE_STATIC_CREDENTIAL_PAIR',
        'ok': bool(access_key) == bool(secret_key),
        'value_present': bool(access_key or secret_key),
    })
    warnings = []
    if shutil.which('docker') is None:
        warnings.append('docker not installed; local rehearsal runs without container orchestration')
    report = {
        'status': 'ok' if all(item['ok'] for item in checks) else 'error',
        'checks': checks,
        'warnings': warnings,
    }
    return report


def rehearsal_env_template():
    return {
        'PUBLIC_BASE_URL': 'https://project-xray.local',
        'TOKEN_PEPPER': 'rehearsal-token-pepper-12345678901234567890',
        'AUDIT_HMAC_KEY': 'rehearsal-audit-key-1234567890123456789012',
        'BACKUP_HMAC_KEY': 'rehearsal-backup-key-123456789012345678901',
        'OIDC_PROXY_SECRET': 'rehearsal-oidc-secret-1234567890123456789',
        'GATEWAY_ASSERTION_VERSION': '1',
        'GATEWAY_ASSERTION_AUDIENCE': 'project-xray-app',
        'GATEWAY_ASSERTION_ISSUERS': 'https://cognito-idp.ap-south-1.amazonaws.com/synthetic-rehearsal-pool',
        'GATEWAY_ASSERTION_KEY_ID': 'rehearsal-key-2026-07',
        'OBJECT_STORAGE_MODE': 'managed',
        'STORAGE_ENDPOINT': 'http://127.0.0.1:9000',
        'STORAGE_BUCKET': 'evidence',
        'STORAGE_ACCESS_KEY': 'rehearsal-access',
        'STORAGE_SECRET_KEY': 'rehearsal-secret',
        'MONITORING_WEBHOOK_URL': 'http://127.0.0.1:9001/alerts',
        'MONITORING_WEBHOOK_SECRET': 'rehearsal-monitoring-secret-1234567890123',
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output')
    parser.add_argument('--rehearsal-template', action='store_true')
    args = parser.parse_args()
    report = collect(rehearsal_env_template() if args.rehearsal_template else None)
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(report, sort_keys=True))
    return 0 if report['status'] == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
