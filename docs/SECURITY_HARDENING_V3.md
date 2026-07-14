# Backend hardening evidence — v0.3

## Implemented invariants

- All writes use SQLite `BEGIN IMMEDIATE`; review, correction and publication decisions are serialized.
- Reviews bind to an immutable claim version. Corrections increment the version and require two fresh, distinct approvals.
- Publication is idempotent and records one publication audit event under concurrent requests.
- Production writes require an idempotency key; conflicting replay payloads return `409`.
- Tokens are stored as peppered HMAC digests with expiry, revocation and atomic rotation.
- Production authentication accepts only fresh, MFA-marked, HMAC-authenticated gateway assertions.
- Every audit event has an HMAC checkpoint keyed outside the database. Rehashed forks without the external key fail verification.
- Source documents fail closed while quarantined or rejected. Only a scanner role can transition quarantine.
- v1 and v2 migrations use temporary databases, preserve signed pre-migration backups and demote legacy publications for fresh review.
- Backups and restores require authenticated manifests, database integrity, audit-chain verification and atomic replacement.
- Managed object metadata is verified through signed S3-compatible HEAD requests.
- Monitoring webhooks and recovery evidence are HMAC-authenticated.

## Automated evidence

`python3 scripts/check_release.py` executes 23 tests, including concurrent publication/correction, stale review rejection, idempotent replay, credential rotation/expiry, audit tampering, quarantine enforcement, signed managed-storage requests, monitoring delivery, atomic migration, tampered-manifest rejection and measured recovery.
