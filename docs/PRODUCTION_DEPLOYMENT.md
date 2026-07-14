# Production deployment contract

The v0.3 service fails startup when production controls are absent. Dashboard visual QA is outside this checkpoint.

## Identity boundary

Set `APP_ENV=production`. Bearer bootstrap tokens are ignored in production. An identity-aware gateway must perform OIDC authentication and MFA, then send:

- `X-Auth-Subject`: stable IdP subject identifier.
- `X-Auth-Roles`: one of `admin`, `reviewer`, or `scanner`.
- `X-Auth-MFA: true`.
- `X-Auth-Timestamp`: current Unix timestamp.
- `X-Auth-Signature`: HMAC-SHA256 of `subject|roles|mfa|timestamp` using `OIDC_PROXY_SECRET`.

Assertions older than 90 seconds, missing MFA, invalid signatures, or unknown roles fail closed. The gateway-to-app network must be private and must strip client-supplied `X-Auth-*` headers.

## Required production configuration

- HTTPS `PUBLIC_BASE_URL`.
- 32+ character `TOKEN_PEPPER`, `AUDIT_HMAC_KEY`, `BACKUP_HMAC_KEY`, `OIDC_PROXY_SECRET`, and `MONITORING_WEBHOOK_SECRET` from a secret manager.
- `OBJECT_STORAGE_MODE=managed`.
- S3-compatible `STORAGE_ENDPOINT`, `STORAGE_BUCKET`, `STORAGE_REGION`, `STORAGE_ACCESS_KEY`, and `STORAGE_SECRET_KEY`.
- `MONITORING_WEBHOOK_URL` to an incident/alert receiver.

Document creation performs a signed S3-compatible HEAD request and binds the recorded SHA-256 and byte length to object metadata. Every document remains quarantined until a distinct scanner identity records `clean`. Publication rejects quarantined or rejected evidence.

## Operational verification

```bash
python3 scripts/check_release.py
python3 scripts/smoke_e2e.py
AUDIT_HMAC_KEY=... python3 scripts/verify_audit.py /var/lib/project-xray/project_xray.db
BACKUP_HMAC_KEY=... AUDIT_HMAC_KEY=... \
  python3 scripts/recovery_evidence.py /var/lib/project-xray/project_xray.db \
  /var/lib/project-xray/evidence/recovery-drill.json
```

The monitoring delivery path is `POST /api/operations/test-alert` as an authenticated admin with an `Idempotency-Key`. A successful response proves that the configured receiver accepted the signed event; the operator must separately record who received it.

## Remaining operator evidence

Source code cannot prove a real IdP tenant enforces MFA, an object bucket is encrypted, an alert reached an on-call human, or a target-environment RPO/RTO drill passed. Record those receipts in `ops/production-readiness.yaml`; do not label the deployment production before they exist.
