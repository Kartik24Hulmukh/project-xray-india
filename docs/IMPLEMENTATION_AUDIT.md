# Implementation audit — 14 July 2026

## Verified implementation

The supplied archive checksum matched `41dea6876f599190fc4568c473ea12a470c74cba31b269a6f66d5dc842710ba6`. The original slice started and passed two tests, but it exposed research/candidate data publicly, allowed one admin token to create a directly published claim, had no independent-review records, no correction workflow, no tested restore path, and no schema migration.

The hardened v0.2 reference now has:

- public/private API separation; research projects and candidate claims are hidden;
- source records with canonical URL, retrieval time, passage/page anchor and SHA-256;
- claims that always begin as candidates;
- distinct admin and reviewer credentials;
- two different reviewer approvals before claim publication;
- correction history that invalidates prior approvals and requires two fresh approvals;
- documents recorded in an explicit quarantine/pending-scan state with size/type/hash checks;
- append-only, hash-chained audit events plus an offline chain verifier;
- request IDs, structured logs, body limits, write-rate limits and hardened headers;
- restart persistence, SQLite online backup, clean restore and integrity validation;
- safe v1→v2 migration with a pre-migration backup and safety demotion of legacy claims;
- an automated create→review→publish→report/RTI→restart→backup→restore smoke path;
- strict CSP-compatible public UI behavior and public-source provenance display;
- CI execution of unit, security baseline and full smoke checks.

## Reproducible checks

```bash
make check
make smoke
python3 scripts/verify_audit.py data/project_xray.db
python3 scripts/recovery.py backup data/project_xray.db backups/project_xray.db
python3 scripts/recovery.py restore backups/project_xray.db /tmp/clean/project_xray.db
```

## Honest release status

**Code status: public-beta reference, not v1 production.** Code-level vertical-slice and recovery gates are green. The following operator/environment gates cannot be completed inside a source archive and remain release blockers:

1. Managed non-SQLite production database, encrypted object storage and real malware scanner.
2. OIDC/MFA and deployment-specific least-privilege roles; bundled tokens are not a substitute.
3. Actual domain, HTTPS/WAF, secret manager, monitoring destination and tested human alert.
4. Named product/evidence/security/incident owners, privacy contact and on-call rotation.
5. Two real launch dossiers, each independently reviewed by two humans and relevant domain counsel/adviser.
6. Published privacy/retention/correction/takedown policies approved for the operating entity.
7. Target-environment load/capacity test, encrypted backup retention, measured RPO/RTO and rollback drill.
8. Real authorized connector execution; no connector claim is made by this release.
9. Dashboard visual/accessibility QA was intentionally deferred at the operator's request.

The application must not be marketed as production-ready until evidence for every item above is recorded in `ops/production-readiness.yaml` and the readiness checker is green.
