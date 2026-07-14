# Security Findings Resolution — PR #10 (v0.4.1 medium findings)

Baseline: `1caf22dd08963c9261cce2bd94fce57f70929be4`  
Branch: `security/v0-4-1-medium-findings`

| ID | Severity | Finding | Disposition | Commit | Regression test | Residual risk |
|----|----------|---------|-------------|--------|-----------------|---------------|
| SEC-1 | HIGH | `pg_dump`/`pg_restore` pass DATABASE_URL as CLI arg | **fixed** (prior PR #7 + verified) — components via host/port/user/db + `PGPASSWORD` env only | e3e6efa (redaction harden) | recovery paths in `scripts/recovery.py` | Operator must not wrap tools with shell that re-injects URL into argv |
| SEC-2 | HIGH | stderr may expose credentials | **fixed** — `_redact_pg_text` strips URL/password from tool output | e3e6efa | recovery redaction helper | Tool may log other secrets if misconfigured by operator |
| SEC-3 | MEDIUM | `_convert_sql` dollar quotes | **fixed** | 60cc533 | `tests/test_convert_sql_hardened.py` | Nested exotic dollar tags not used by app SQL |
| SEC-4 | MEDIUM | `_convert_sql` SQL comments | **fixed** | 60cc533 | same | — |
| SEC-5 | MEDIUM | No global exception handler | **fixed** — `do_GET`/`do_POST` fail-safe | 20c3073 | `tests/test_runtime_safety.py` | Partial writes after headers still best-effort |
| SEC-6 | MEDIUM | OIDC first-role wins | **fixed** — single-role fail-closed | 5e57615 | `tests/test_security_roles.py` | Gateway must map IdP groups correctly |
| SEC-7 | MEDIUM | No OIDC replay protection | **fixed** — signature replay cache + optional nonce | 5e57615 | same | In-process cache only; multi-instance needs shared store |
| SEC-8 | MEDIUM | RATE/METRICS races | **fixed** — dedicated locks | 20c3073 | `tests/test_runtime_safety.py` | — |
| SEC-9 | MEDIUM | `_get_pool` init race | **fixed** — double-checked lock | 60cc533 | pool init code path | — |
| SEC-10 | MEDIUM | Broad gitleaks allowlists | **fixed** — narrow anchored paths/regexes | e3e6efa | `TestGitleaksPolicy` | Placeholder tokens in tests remain allowlisted by exact regex |
| SEC-11 | MEDIUM | No CORS / OPTIONS | **fixed** — OPTIONS returns 405, no ACAO | 20c3073 | server OPTIONS handler | Same-origin only by design |
| SEC-12 | MEDIUM | psycopg2 undeclared | **resolved-prior** | 549d26b | requirements.txt | — |
| SEC-13 | MEDIUM | Migration SQLite-only guard | **resolved-prior** | 549d26b | version consistency tests | — |
| SEC-14 | LOW | `str(exc)` client leak | **fixed** for unexpected + conflict paths; validation still returns safe messages | 20c3073 | fail-safe tests | Validation messages may include field names |
| SEC-15 | LOW | f-string SQL schema version | **accepted risk** — integer-only version write | — | schema helpers | Owner: security lead |
| SEC-17 | LOW | X-Auth-Subject format | **fixed** | 5e57615 | role tests | — |
| SEC-18 | LOW | No dockerignore | **resolved-prior** | 79e5016 | — | — |
| SEC-19 | LOW | Unpinned Docker base | **accepted risk** — tracked for v0.5 | — | — | Owner: release |
| SEC-20 | LOW | No request timeout | **disproven** — `settimeout(15)` present | — | server setup | — |
| SEC-22 | LOW | gitleaksignore unused | **accepted risk** — CI uses `.gitleaks.toml` only | e3e6efa | security workflow | — |
| SEC-23 | LOW | max_age hardcoded | **fixed** — `OIDC_MAX_AGE_SECONDS` | 5e57615 | — | — |
| DEP-health | MEDIUM | continue-on-error staging health | **fixed** — skip vs mandatory health | e3e6efa | `TestGitleaksPolicy` deploy asserts | Real staging still needs `STAGING_URL` |
| PG-BUG1 | MEDIUM | Path(None) PG restore | **disproven** — PG integrity uses `connect()`, SQLite requires path | — | recovery.py | — |
| PG-% | LOW | literal `%` in SQL | **fixed** — escaped to `%%` | 60cc533 | convert tests | — |

## External blockers (not fixable in-repo)

1. Persistent staging/production runtime and `STAGING_URL` / `PRODUCTION_URL`
2. Real OIDC/MFA IdP tenant + gateway signing with `OIDC_PROXY_SECRET`
3. Managed object storage credentials and IAM
4. Monitoring webhook that delivers to a human on-call
5. Fresh-target PostgreSQL restore drill with measured RPO/RTO
6. Named governance owners and privacy/legal/editorial approvals
7. Design-partner pilot with measured traction metrics
