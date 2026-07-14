# Release notes

## v0.4.0 — public projection and abuse-control hardening

- Added an explicit allowlisted public dossier projection so anonymous reads cannot leak reviewer-only or quarantine/internal fields.
- Added regression tests that prove public bundles exclude raw source/document tables and internal claim metadata.
- Replaced the single in-memory write limiter with route-aware public/auth/write/expensive-write quotas.
- Added optional proxy-aware client identification via `TRUST_PROXY_HEADERS=1` for trusted reverse-proxy deployments.
- Expanded Prometheus metrics for rate-limit, idempotency replay/conflict, and quarantine-block visibility.
- Updated the security workflow to use the MIT-licensed gitleaks CLI directly instead of the licensed GitHub action.
- Automated verification now covers 26 tests, browser acceptance, smoke path, release checks, and repeat loop runs.
- Added downloadable evidence capsules plus `scripts/verify_capsule.py` for offline public-verification flows.

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
