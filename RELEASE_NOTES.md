# Release notes

## v0.3.0 — transactional production hardening

- Serialized review/correction/publication transitions with claim-version binding and concurrency tests.
- Credential expiry, revocation and atomic rotation; production bearer tokens disabled.
- Fresh MFA-marked, HMAC-authenticated OIDC gateway assertions.
- Production idempotency-key requirement and replay/conflict handling.
- Externally keyed per-event audit checkpoints and fork/tamper detection.
- Quarantine blocks publication until a separate scanner role records a clean result.
- Atomic v2→v3 migration plus authenticated pre-migration backups.
- Authenticated backup manifests, audit-aware clean restore and signed RPO/RTO evidence.
- Signed S3-compatible object verification and authenticated monitoring webhooks.
- 23 automated tests plus restart/restore smoke verification.


## v0.2.0 — hardened public beta (14 July 2026)

### Added
- Provenance-first sources, documents, reviews and revision history.
- Two-person independent approval gate and fresh review after corrections.
- Public/private data separation and candidate-claim suppression.
- Hash-chained immutable audit trail with offline verifier.
- Request IDs, structured logs, rate/body limits and strict security headers.
- Online SQLite backup, clean restore verification and restart/restore E2E smoke test.
- Safety-preserving legacy migration with automatic pre-v2 backup.
- Reproducible source release, CycloneDX SBOM, checksums and build provenance.

### Security behavior
- Claims cannot be created directly as reviewed or published.
- Admin credentials cannot act as reviewer credentials.
- Public endpoints expose only published projects and public claim states.
- Uploaded-document metadata begins in quarantine/pending-scan state; no malware-scan claim is fabricated.

### Honest limitations
This is a public-beta reference, not a v1 production certification. Managed database/object storage, OIDC/MFA, HTTPS/WAF, monitoring/on-call, legal/privacy approval, real two-person launch-case review and target-environment recovery/load evidence must be supplied by the operator. See `docs/IMPLEMENTATION_AUDIT.md`.
