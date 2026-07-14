# Deployment Runbook — Project X-Ray India

This runbook covers staging and production deployment, health checks,
rollback, database migration (SQLite → PostgreSQL), and backup/restore.

## Prerequisites

- Docker Engine 24+ and Docker Compose v2+
- Access to the GitHub Container Registry (GHCR) image
- `.env.production` file with all variables (see `.env.production.example`)
- S3-compatible bucket created and credentials configured
- OIDC/MFA gateway deployed and reachable from the app network
- Monitoring webhook endpoint configured

---

## 1. Pre-Deployment Checklist

Run through every item before any deployment:

- [ ] **CI green** — `ci` workflow passed on the target commit
- [ ] **Tests pass** — `python3 -m unittest discover -s tests` exits 0
- [ ] **Smoke E2E passes** — `python3 scripts/smoke_e2e.py` exits 0
- [ ] **Release check passes** — `python3 scripts/check_release.py` exits 0
- [ ] **`.env.production` validated** — all `[SECRET]` fields are 32+ random chars, no placeholder values
- [ ] `APP_ENV=production` set
- [ ] `PUBLIC_BASE_URL` is HTTPS and matches the public domain
- [ ] `OBJECT_STORAGE_MODE=managed` and S3 credentials verified
- [ ] `OIDC_PROXY_SECRET` matches the gateway's signing key
- [ ] `MONITORING_WEBHOOK_URL` and `MONITORING_WEBHOOK_SECRET` configured
- [ ] PostgreSQL instance reachable and `POSTGRES_PASSWORD` set
- [ ] Database schema applied (see Section 6)
- [ ] Disk space adequate for PostgreSQL data volume and upload volume
- [ ] Backup of current production database taken (see Section 7)

---

## 2. Staging Deployment Procedure

Staging should mirror production configuration with staging-specific values.

### 2.1 Deploy

```bash
# Pull latest image
docker compose -f docker-compose.prod.yml --env-file .env.staging pull

# Start services
docker compose -f docker-compose.prod.yml --env-file .env.staging up -d

# Wait for health checks to pass
docker compose -f docker-compose.prod.yml --env-file .env.staging ps
```

### 2.2 Verify

```bash
# Health endpoint
curl -sf https://staging.xray-india.example.org/health | jq .

# Readiness endpoint
curl -sf https://staging.xray-india.example.org/ready | jq .

# Run smoke E2E against staging
PUBLIC_BASE_URL=https://staging.xray-india.example.org python3 scripts/smoke_e2e.py

# Verify audit chain
python3 scripts/verify_audit.py <staging_db_path_or_dsn>
```

### 2.3 Automated via GitHub Actions

Pushing to `main` triggers the `deploy` workflow which:
1. Builds and pushes the Docker image to GHCR (tagged with commit SHA)
2. Deploys to the `staging` environment
3. Runs health check (30 retries, 5s interval)
4. Runs smoke E2E against staging
5. On failure, triggers rollback

---

## 3. Production Deployment Procedure

Production deployment requires manual approval via GitHub Actions
environment protection rules.

### 3.1 Deploy

```bash
# Pull the specific image version (by SHA tag)
IMAGE_TAG=<commit-sha-short>
docker compose -f docker-compose.prod.yml --env-file .env.production pull

# Start or update services
docker compose -f docker-compose.prod.yml --env-file .env.production up -d

# Verify containers are running and healthy
docker compose -f docker-compose.prod.yml --env-file .env.production ps
```

### 3.2 Post-Deploy Verification

```bash
# Health check
curl -sf https://xray-india.example.org/health | jq .

# Readiness check
curl -sf https://xray-india.example.org/ready | jq .

# Audit chain integrity
python3 scripts/verify_audit.py <production_db_dsn>

# Monitoring webhook test
# The app should send a deployment event to MONITORING_WEBHOOK_URL.
# Verify receipt at the monitoring endpoint.
```

### 3.3 Automated via GitHub Actions

After staging passes, the `deploy` workflow's `deploy-production` job:
1. Requires manual approval (environment protection)
2. Deploys the same image to production
3. Runs health check (30 retries, 5s interval)
4. Verifies audit chain integrity
5. On failure, triggers rollback and exits with error

---

## 4. Health Check Verification

The application exposes two endpoints:

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `GET /health` | Liveness — process is up | `200` with `{"status":"ok"}` |
| `GET /ready` | Readiness — can serve requests | `200` with `{"status":"ok"}` |

### Manual health check

```bash
# Single check
curl -sf https://xray-india.example.org/health

# Polling loop (useful during rollout)
for i in $(seq 1 30); do
  STATUS=$(curl -s -o /dev/null -w '%{http_code}' https://xray-india.example.org/health)
  echo "Attempt $i: HTTP $STATUS"
  [ "$STATUS" = "200" ] && break
  sleep 5
done
```

### Docker-level health check

```bash
docker inspect --format='{{.State.Health.Status}}' xray-web-1
docker inspect --format='{{.State.Health.Status}}' xray-db-1
```

Both should report `healthy`.

---

## 5. Rollback Procedure

### 5.1 Docker Compose Rollback

```bash
# 1. Identify the previous working image tag
docker images --format '{{.Repository}}:{{.Tag}}  {{.CreatedAt}}' | grep xray

# 2. Update .env.production or override the image tag
#    Edit docker-compose.prod.yml or use:
export IMAGE_TAG=<previous-working-sha>

# 3. Force recreate the web service with the previous image
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --no-deps --force-recreate web

# 4. Verify health
curl -sf https://xray-india.example.org/health

# 5. Verify audit chain
python3 scripts/verify_audit.py <production_db_dsn>
```

### 5.2 GitHub Actions Rollback

The `deploy` workflow includes a rollback step that fires on failure:
- Staging: `if: failure()` triggers rollback notification
- Production: `if: failure()` triggers rollback and exits with error

For manual rollback via GitHub Actions:
1. Go to the Actions tab → `deploy` workflow
2. Click "Run workflow" with `environment=production`
3. Use a known-good commit SHA

### 5.3 Database Rollback

If a migration caused issues:

```bash
# 1. Stop the web service
docker compose -f docker-compose.prod.yml stop web

# 2. Restore from the pre-deployment backup (see Section 7.2)
pg_restore -d "$DATABASE_URL" -c backups/pre-deploy-$(date +%Y%m%d).dump

# 3. Restart with previous image
docker compose -f docker-compose.prod.yml --env-file .env.production up -d web

# 4. Verify
curl -sf https://xray-india.example.org/health
python3 scripts/verify_audit.py <production_db_dsn>
```

---

## 6. Database Migration Procedure (SQLite to PostgreSQL)

### 6.1 Overview

The application's `app/database.py` abstraction layer supports both SQLite
(via `DB_PATH`) and PostgreSQL (via `DATABASE_URL`). When `DATABASE_URL`
is set, the app uses psycopg2 with a connection pool. Otherwise it falls
back to SQLite.

### 6.2 Prepare PostgreSQL

```bash
# Create database and user
psql -U postgres -c "CREATE USER xray WITH PASSWORD '<strong-password>';"
psql -U postgres -c "CREATE DATABASE xray OWNER xray;"

# Apply schema
# The schema in db/schema.sql uses SQLite-specific syntax (PRAGMA, AUTOINCREMENT).
# A PostgreSQL-compatible schema migration is needed. Use the migration script:
psql -U xray -d xray -f db/schema_postgres.sql
```

> **Note:** `db/schema_postgres.sql` must be created as part of the
> PostgreSQL migration work. The `app/database.py` layer handles
> placeholder conversion (`?` → `%s`) at runtime, but DDL differences
> (PRAGMA, AUTOINCREMENT → SERIAL, TEXT → appropriate types) require
> a PostgreSQL-specific schema file.

### 6.3 Migrate Existing Data

```bash
# 1. Export from SQLite
sqlite3 data/project_xray.db ".dump" > /tmp/xray_sqlite_dump.sql

# 2. Transform SQLite DDL to PostgreSQL-compatible DDL
#    (Manual or scripted: PRAGMA removal, AUTOINCREMENT → GENERATED,
#     INTEGER PRIMARY KEY → SERIAL, etc.)
#    Alternatively, use pgloader for automated migration:
#    pgloader sqlite:///data/project_xray.db postgresql://xray:pass@db:5432/xray

# 3. Load into PostgreSQL
psql -U xray -d xray -f /tmp/xray_pg_dump.sql

# 4. Verify row counts match
sqlite3 data/project_xray.db "SELECT COUNT(*) FROM projects;" 
psql -U xray -d xray -c "SELECT COUNT(*) FROM projects;"
```

### 6.4 Switch the Application to PostgreSQL

```bash
# 1. Set DATABASE_URL in .env.production
echo 'DATABASE_URL=postgresql://xray:pass@db:5432/xray' >> .env.production

# 2. Restart the application
docker compose -f docker-compose.prod.yml --env-file .env.production up -d

# 3. Verify the app is using PostgreSQL
#    Check logs for psycopg2 connection, not sqlite3
docker compose -f docker-compose.prod.yml logs web | grep -i "database\|postgres"

# 4. Run smoke E2E
PUBLIC_BASE_URL=https://xray-india.example.org python3 scripts/smoke_e2e.py

# 5. Verify audit chain
python3 scripts/verify_audit.py "$DATABASE_URL"
```

### 6.5 Rollback to SQLite (Emergency)

```bash
# 1. Unset DATABASE_URL (or set DB_PATH)
# 2. Restart the app
docker compose -f docker-compose.prod.yml --env-file .env.production up -d web
# 3. The app will fall back to SQLite at DB_PATH
```

---

## 7. Backup and Restore Procedure (PostgreSQL)

### 7.1 Backup

#### Manual backup

```bash
# Full custom-format backup (compressible, parallelizable restore)
pg_dump -U xray -d xray -Fc -f backups/xray-$(date +%Y%m%d-%H%M%S).dump

# Verify backup integrity
pg_restore --list backups/xray-$(date +%Y%m%d-%H%M%S).dump | head -20
```

#### Automated backup (cron)

```bash
# Add to crontab on the database host:
0 2 * * * pg_dump -U xray -d xray -Fc -f /backups/xray-$(date +\%Y\%m\%d).dump && \
          find /backups -name "xray-*.dump" -mtime +30 -delete
```

#### Pre-deployment backup (always run before migrations)

```bash
pg_dump -U xray -d xray -Fc -f backups/pre-deploy-$(date +%Y%m%d-%H%M%S).dump
```

### 7.2 Restore

```bash
# 1. Stop the web service to prevent writes during restore
docker compose -f docker-compose.prod.yml stop web

# 2. Restore from backup
pg_restore -d "$DATABASE_URL" -c backups/xray-YYYYMMDD-HHMMSS.dump

# 3. Verify row counts
psql -U xray -d xray -c "SELECT COUNT(*) FROM projects;"
psql -U xray -d xray -c "SELECT COUNT(*) FROM audit_events;"

# 4. Verify audit chain integrity
python3 scripts/verify_audit.py "$DATABASE_URL"

# 5. Restart web service
docker compose -f docker-compose.prod.yml --env-file .env.production up -d web

# 6. Health check
curl -sf https://xray-india.example.org/health
```

### 7.3 Point-in-Time Recovery (PITR)

If PostgreSQL WAL archiving is enabled:

```bash
# 1. Identify target recovery time
TARGET_TIME="2026-07-14 03:00:00 IST"

# 2. Stop PostgreSQL
docker compose -f docker-compose.prod.yml stop db

# 3. Restore base backup to data volume
rm -rf /var/lib/docker/volumes/xray-pgdata/_data/*
tar xzf /backups/base/xray-base.tar.gz -C /var/lib/docker/volumes/xray-pgdata/_data/

# 4. Create recovery signal
echo "recovery_target_time = '$TARGET_TIME'" >> /var/lib/docker/volumes/xray-pgdata/_data/postgresql.auto.conf
touch /var/lib/docker/volumes/xray-pgdata/_data/recovery.signal

# 5. Start PostgreSQL (it will replay WAL and pause at target time)
docker compose -f docker-compose.prod.yml --env-file .env.production up -d db

# 6. Verify and promote
psql -U xray -d xray -c "SELECT pg_wal_replay_resume();"
```

---

## 8. Post-Deployment Monitoring

After a successful deployment:

1. **Watch logs for 15 minutes**:
   ```bash
   docker compose -f docker-compose.prod.yml logs -f --since 5m web
   ```

2. **Check metrics endpoint** (if available):
   ```bash
   curl -sf https://xray-india.example.org/metrics | jq .
   ```

3. **Verify monitoring webhook received deployment event**

4. **Confirm no spike in error rate or auth failures**

5. **Document the deployment**:
   - Commit SHA deployed
   - Image tag deployed
   - Timestamp
   - Any issues encountered and resolution

---

## 9. Emergency Contacts

| Role | Responsibility | Contact |
|------|---------------|---------|
| On-call SRE | First responder for incidents | _set in monitoring system_ |
| DBA | Database issues, migrations | _set in team directory_ |
| Security Lead | Auth/OIDC/security incidents | _set in team directory_ |
| Release Manager | Rollback decisions | _set in team directory_ |
