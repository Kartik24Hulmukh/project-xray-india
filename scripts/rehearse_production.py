#!/usr/bin/env python3
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.security import proxy_signature
from scripts.preflight_prod_env import collect as collect_preflight
from scripts.recovery_evidence import collect as collect_recovery_evidence


class StorageHandler(BaseHTTPRequestHandler):
    catalog = {}
    received = []

    def log_message(self, *_args):
        pass

    def do_HEAD(self):
        StorageHandler.received.append({'path': self.path, 'authorization': self.headers.get('Authorization', '')})
        item = StorageHandler.catalog.get(self.path)
        if not item:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header('Content-Length', str(item['size_bytes']))
        self.send_header('x-amz-meta-sha256', item['sha256'])
        self.end_headers()


class MonitorHandler(BaseHTTPRequestHandler):
    events = []

    def log_message(self, *_args):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        MonitorHandler.events.append({'headers': dict(self.headers), 'body': json.loads(body)})
        self.send_response(204)
        self.end_headers()


def call(base_url, path, method='GET', body=None, headers=None):
    req = urllib.request.Request(
        base_url + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers or {},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            payload = response.read()
            parsed = json.loads(payload) if 'json' in response.headers.get('Content-Type', '') else payload.decode()
            return response.status, parsed
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        parsed = json.loads(payload) if payload else {'error': exc.reason}
        return exc.code, parsed


def auth_headers(role, subject, secret, action='request'):
    stamp = str(int(time.time()))
    nonce = f'{action}-{time.time_ns()}'
    headers = {
        'Content-Type': 'application/json',
        'X-Auth-Subject': subject,
        'X-Auth-Roles': role,
        'X-Auth-MFA': 'true',
        'X-Auth-Timestamp': stamp,
        'X-Auth-Nonce': nonce,
        'Idempotency-Key': f'{role}-{subject}-{action}-{nonce}',
    }
    headers['X-Auth-Signature'] = proxy_signature(
        headers['X-Auth-Subject'],
        headers['X-Auth-Roles'],
        headers['X-Auth-MFA'],
        stamp,
        secret,
        nonce=nonce,
    )
    return headers


def wait_ready(base_url):
    for _ in range(100):
        try:
            status, _ = call(base_url, '/ready')
            if status == 200:
                return
        except Exception:
            pass
        time.sleep(0.1)
    raise RuntimeError('production rehearsal server did not become ready')


def run():
    artifacts = ROOT / 'artifacts' / 'prod-rehearsal'
    artifacts.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp_dir:
        tmp = Path(temp_dir)
        db_path = tmp / 'rehearsal.db'
        backup_receipt = artifacts / 'recovery-evidence.json'
        capsule_path = artifacts / 'capsule.json'
        preflight_path = artifacts / 'preflight.json'
        receipt_path = artifacts / 'receipt.json'

        storage_server = ThreadingHTTPServer(('127.0.0.1', 0), StorageHandler)
        storage_thread = threading.Thread(target=storage_server.serve_forever, daemon=True)
        storage_thread.start()
        monitor_server = ThreadingHTTPServer(('127.0.0.1', 0), MonitorHandler)
        monitor_thread = threading.Thread(target=monitor_server.serve_forever, daemon=True)
        monitor_thread.start()

        storage_url = f'http://127.0.0.1:{storage_server.server_address[1]}'
        monitor_url = f'http://127.0.0.1:{monitor_server.server_address[1]}/alerts'
        StorageHandler.catalog['/evidence/case/fixture.pdf'] = {'sha256': 'a' * 64, 'size_bytes': 128}

        env = {
            **os.environ,
            'DB_PATH': str(db_path),
            'PORT': '18140',
            'APP_ENV': 'production',
            'PUBLIC_BASE_URL': 'https://project-xray.local',
            'TOKEN_PEPPER': 'rehearsal-token-pepper-12345678901234567890',
            'AUDIT_HMAC_KEY': 'rehearsal-audit-key-1234567890123456789012',
            'BACKUP_HMAC_KEY': 'rehearsal-backup-key-123456789012345678901',
            'OIDC_PROXY_SECRET': 'rehearsal-oidc-secret-1234567890123456789',
            'OBJECT_STORAGE_MODE': 'managed',
            'STORAGE_ENDPOINT': storage_url,
            'STORAGE_BUCKET': 'evidence',
            'STORAGE_REGION': 'ap-south-1',
            'STORAGE_ACCESS_KEY': 'rehearsal-access',
            'STORAGE_SECRET_KEY': 'rehearsal-secret',
            'MONITORING_WEBHOOK_URL': monitor_url,
            'MONITORING_WEBHOOK_SECRET': 'rehearsal-monitoring-secret-1234567890123',
            'WRITE_RATE_LIMIT': '1000',
            'PUBLIC_READ_RATE_LIMIT': '1000',
            'AUTH_READ_RATE_LIMIT': '1000',
            'EXPENSIVE_WRITE_RATE_LIMIT': '1000',
        }

        preflight = collect_preflight(env)
        preflight_path.write_text(json.dumps(preflight, indent=2, sort_keys=True) + '\n')
        if preflight['status'] != 'ok':
            raise RuntimeError('preflight failed')

        process = subprocess.Popen(
            [sys.executable, 'app/server.py'],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        base_url = 'http://127.0.0.1:18140'
        try:
            wait_ready(base_url)
            admin_role = ('admin', 'admin@example.org')
            reviewer_a_role = ('reviewer', 'reviewer-a@example.org')
            reviewer_b_role = ('reviewer', 'reviewer-b@example.org')
            scanner_role = ('scanner', 'scanner@example.org')

            def headers_for(role_tuple, action):
                return auth_headers(role_tuple[0], role_tuple[1], env['OIDC_PROXY_SECRET'], action)

            project = call(base_url, '/api/projects', 'POST', {'title': 'Production rehearsal fixture', 'authority': 'Synthetic Authority', 'summary': 'Prod-mode rehearsal', 'synthetic': True}, headers_for(admin_role, 'create-project'))
            pid = project[1]['id']
            source = call(base_url, f'/api/projects/{pid}/sources', 'POST', {'publisher': 'Synthetic Publisher', 'url': 'https://example.invalid/rehearsal', 'source_class': 'official', 'retrieved_at': '2026-07-14T00:00:00Z', 'sha256': 'b' * 64, 'passage': 'Synthetic production anchor'}, headers_for(admin_role, 'create-source'))
            sid = source[1]['id']
            document = call(base_url, f'/api/projects/{pid}/documents', 'POST', {'source_id': sid, 'filename': 'fixture.pdf', 'media_type': 'application/pdf', 'size_bytes': 128, 'sha256': 'a' * 64, 'storage_uri': 's3://evidence/case/fixture.pdf'}, headers_for(admin_role, 'create-document'))
            did = document[1]['id']
            scan = call(base_url, f'/api/projects/{pid}/documents/{did}/scan', 'POST', {'result': 'clean'}, headers_for(scanner_role, 'scan-document'))
            claim = call(base_url, f'/api/projects/{pid}/claims', 'POST', {'claim_type': 'official_claim', 'text': 'Production rehearsal claim', 'source_id': sid, 'passage': 'Synthetic production anchor'}, headers_for(admin_role, 'create-claim'))
            cid = claim[1]['id']
            review1 = call(base_url, f'/api/projects/{pid}/claims/{cid}/reviews', 'POST', {'decision': 'approve'}, headers_for(reviewer_a_role, 'review-a'))
            review2 = call(base_url, f'/api/projects/{pid}/claims/{cid}/reviews', 'POST', {'decision': 'approve'}, headers_for(reviewer_b_role, 'review-b'))
            publish_claim = call(base_url, f'/api/projects/{pid}/claims/{cid}/publish', 'POST', {}, headers_for(admin_role, 'publish-claim'))
            publish_project = call(base_url, f'/api/projects/{pid}/publish', 'POST', {}, headers_for(admin_role, 'publish-project'))
            capsule = call(base_url, f'/api/projects/{pid}/capsule', 'GET')
            metrics = call(base_url, '/metrics', 'GET', headers=headers_for(admin_role, 'metrics'))
            alert = call(base_url, '/api/operations/test-alert', 'POST', {}, headers_for(admin_role, 'test-alert'))

            capsule_path.write_text(json.dumps(capsule[1], indent=2, sort_keys=True) + '\n')
            verify_capsule = subprocess.run([sys.executable, 'scripts/verify_capsule.py', str(capsule_path)], cwd=ROOT, capture_output=True, text=True, check=True)
            receipt = {
                'status': 'ok',
                'project_id': pid,
                'document_scan_status': scan[1]['storage_state'],
                'claim_publication_state': publish_claim[1]['publication_state'],
                'project_status': publish_project[1]['status'],
                'capsule_verifier': json.loads(verify_capsule.stdout),
                'metrics_preview': metrics[1].splitlines()[:5],
                'storage_authorized': bool(StorageHandler.received and StorageHandler.received[-1]['authorization']),
                'monitor_event_count': len(MonitorHandler.events),
                'monitor_event_id': alert[1]['event_id'],
            }
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            storage_server.shutdown()
            monitor_server.shutdown()

        receipt['recovery'] = collect_recovery_evidence(db_path, backup_receipt, backup_key=env['BACKUP_HMAC_KEY'], audit_key=env['AUDIT_HMAC_KEY'])['payload']
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
        print(json.dumps(receipt, sort_keys=True))
        return 0


def main():
    try:
        return run()
    except Exception as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
