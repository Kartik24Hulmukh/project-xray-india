# Staging Readiness Package — Project X-Ray India v0.4.1

**Do not put secrets in this file or in git.** Enter secrets only in a secret manager or GitHub Environment secrets UI.

## Required environment variable names

| Name | Where | Purpose |
|------|-------|---------|
| `APP_ENV` | runtime | Must be `production` for production-mode auth |
| `PORT` | runtime | HTTP listen port |
| `PUBLIC_BASE_URL` | runtime | Canonical public HTTPS URL |
| `DATABASE_URL` | secret | PostgreSQL DSN (preferred production backend) |
| `DB_PATH` | runtime | SQLite path (dev/rehearsal only) |
| `DB_POOL_MAX` | runtime | PG pool max connections (default 10) |
| `TOKEN_PEPPER` | secret | ≥32 chars |
| `AUDIT_HMAC_KEY` | secret | ≥32 chars |
| `BACKUP_HMAC_KEY` | secret | ≥32 chars |
| `OIDC_PROXY_SECRET` | secret | ≥32 chars; matches gateway HMAC key |
| `OIDC_MAX_AGE_SECONDS` | runtime | Assertion max age (default 90) |
| `MONITORING_WEBHOOK_URL` | secret/config | Human alert delivery endpoint |
| `MONITORING_WEBHOOK_SECRET` | secret | ≥32 chars |
| `OBJECT_STORAGE_MODE` | runtime | `managed` for production evidence |
| `STORAGE_ENDPOINT` | config | Object storage API endpoint |
| `STORAGE_BUCKET` | config | Evidence bucket |
| `STORAGE_REGION` | config | Region |
| `STORAGE_ACCESS_KEY` | secret | IAM access key |
| `STORAGE_SECRET_KEY` | secret | IAM secret |
| `TRUST_PROXY_HEADERS` | runtime | `1` only behind trusted proxy |
| `WRITE_RATE_LIMIT` / `PUBLIC_READ_RATE_LIMIT` / `AUTH_READ_RATE_LIMIT` / `EXPENSIVE_WRITE_RATE_LIMIT` | runtime | Rate limits |

### GitHub Actions / Environments

| Name | Type | Environment |
|------|------|-------------|
| `STAGING_URL` | variable | staging |
| `STAGING_DEPLOY_CMD` | variable | staging |
| `STAGING_ROLLBACK_CMD` | variable | staging |
| `PRODUCTION_URL` | variable | production |
| `PRODUCTION_DEPLOY_CMD` | variable | production |
| `PRODUCTION_ROLLBACK_CMD` | variable | production |
| `PROD_DB_PATH` | secret | production (optional file path for audit verify) |

## Provider-neutral deployment

1. Build image: `docker build -t project-xray-india:0.4.1 .`
2. Or use GHCR image from deploy workflow build job.
3. Provide env file from secret store (never commit).
4. Start: `docker compose -f docker-compose.prod.yml --env-file .env.production up -d`
5. Or: `python3 app/server.py` behind TLS-terminating reverse proxy.

## PostgreSQL migration command

Schema is applied by application `init()` against `DATABASE_URL`.

```bash
export DATABASE_URL='postgresql://USER:***@HOST:5432/xray'
python3 -c "from app.server import init; init(); print('schema ready')"
```

Legacy SQLite migrators refuse `DATABASE_URL` by design.

## OIDC claim contract

Gateway must strip client `X-Auth-*` and send:

- `X-Auth-Subject` — stable subject (format-validated)
- `X-Auth-Roles` — **exactly one** of `admin` | `reviewer` | `scanner`
- `X-Auth-MFA: true`
- `X-Auth-Timestamp` — Unix seconds
- `X-Auth-Nonce` — unique per request (recommended)
- `X-Auth-Signature` — HMAC-SHA256 of `subject|roles|mfa|timestamp` or `subject|roles|mfa|timestamp|nonce`

Ambiguous multi-role assertions are denied. Replayed signatures are denied.

## Object storage IAM requirements

- PutObject / GetObject / HeadObject on evidence prefix only
- No public ACL
- Separate scanner path for quarantine objects if used
- Credentials only via env/secret manager

## Monitoring webhook requirements

- HTTPS endpoint that accepts signed POST from `send_alert`
- Human-visible channel (PagerDuty/Slack/email bridge)
- Secret shared via `MONITORING_WEBHOOK_SECRET`

## Backup / restore

```bash
# PostgreSQL
python3 scripts/recovery.py backup --destination /backups/xray.dump
python3 scripts/recovery.py restore --source /backups/xray.dump --force

# Evidence collection
python3 scripts/recovery_evidence.py
```

## Rollback

```bash
# compose
docker compose -f docker-compose.prod.yml up -d --no-deps --force-recreate web
# or set PRODUCTION_ROLLBACK_CMD / STAGING_ROLLBACK_CMD in GitHub env
```

## Smoke

```bash
export PUBLIC_BASE_URL=https://staging.example
python3 scripts/smoke_e2e.py
curl -sf "$PUBLIC_BASE_URL/health"
curl -sf "$PUBLIC_BASE_URL/ready"
```

## Evidence receipt template

```json
{
  "receipt_type": "staging_deploy",
  "git_sha": "",
  "staging_url": "",
  "deployment_status": "deployment_skipped|deployment_attempted|deployment_succeeded|rollback_executed",
  "health_http_status": null,
  "smoke_e2e": null,
  "oidc_mfa_real": false,
  "managed_storage_real": false,
  "human_alert_received": false,
  "restore_drill": {"performed": false, "rpo_seconds": null, "rto_seconds": null},
  "operator": "",
  "timestamp": ""
}
```

## What is not configured in this agent environment

| Need | Permission | Where to enter |
|------|------------|----------------|
| Cloud account / VM / k8s | deploy rights | provider console |
| `STAGING_URL` | GitHub env var write | repo Settings → Environments → staging |
| `DATABASE_URL` | secret write | secret manager / GH secret |
| OIDC tenant | IdP admin | Keycloak/Auth0/etc. |
| Storage IAM | cloud IAM admin | cloud console |
| Monitoring webhook | channel admin | monitoring vendor |
| Org OAuth app approval for Gumloop GitHub | org owner | https://docs.github.com/articles/restricting-access-to-your-organization-s-data/ |

After secrets exist, re-run workflow `deploy` (workflow_dispatch, staging) and fill the receipt.
