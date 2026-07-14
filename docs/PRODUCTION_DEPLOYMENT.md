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
python3 scripts/rehearse_production.py
AUDIT_HMAC_KEY=... python3 scripts/verify_audit.py /var/lib/project-xray/project_xray.db
BACKUP_HMAC_KEY=... AUDIT_HMAC_KEY=... \
  python3 scripts/recovery_evidence.py /var/lib/project-xray/project_xray.db \
  /var/lib/project-xray/evidence/recovery-drill.json
```

The local production rehearsal emits:
- `artifacts/prod-rehearsal/preflight.json`
- `artifacts/prod-rehearsal/capsule.json`
- `artifacts/prod-rehearsal/recovery-evidence.json`
- `artifacts/prod-rehearsal/receipt.json`

These prove that production-mode configuration, signed OIDC assertions, managed-storage verification, signed alert delivery, public dossier publication, capsule export, and recovery evidence can all execute end-to-end in a local provider-neutral rehearsal. The same rehearsal now runs from `scripts/check_release.py` and is bundled into release artifacts for operator review.

The monitoring delivery path is `POST /api/operations/test-alert` as an authenticated admin with an `Idempotency-Key`. A successful response proves that the configured receiver accepted the signed event; the operator must separately record who received it.

## Remaining operator evidence

Source code cannot prove a real IdP tenant enforces MFA, an object bucket is encrypted, an alert reached an on-call human, or a target-environment RPO/RTO drill passed. Record those receipts in `ops/production-readiness.yaml`; do not label the deployment production before they exist.

## Database backend notes (v0.4.1)

- **SQLite** remains the default local/dev path (`DB_PATH`).
- **PostgreSQL** is selected when `DATABASE_URL` is set. Apply `db/schema_postgres.sql` with operator-managed migration tooling before first boot.
- `scripts/migrate_legacy.py` and `scripts/migrate_v2_to_v3.py` are **SQLite file rewriters only**. They exit with an error if `DATABASE_URL` is set.
- Runtime recovery for both backends is via `scripts/recovery.py` (requires `pg_dump`/`pg_restore` for PostgreSQL).
- CI runs a PostgreSQL service-container job for abstraction/schema smoke; a target-environment restore drill is still an operator gate.

