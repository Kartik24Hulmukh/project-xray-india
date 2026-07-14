# Implementation audit — v0.3

## Verified backend implementation

The original archive checksum matched the supplied SHA-256. The v0.3 hardening loops now enforce:

- serialized `BEGIN IMMEDIATE` review, correction and publication transitions;
- claim-version-bound reviews and two fresh approvals after every correction;
- one publication transition/audit event under concurrent requests;
- expiring, revocable and atomically rotatable credentials stored as peppered HMAC digests;
- production authentication through fresh MFA-marked, HMAC-authenticated OIDC gateway assertions;
- production idempotency keys and conflicting-replay rejection;
- externally keyed per-event audit checkpoints that detect a consistently rehashed database fork;
- fail-closed quarantine and an independent scanner role;
- atomic v1/v2 migrations with authenticated pre-migration backups and conservative re-review;
- authenticated backup manifests, audit-aware restore verification and atomic replacement;
- signed S3-compatible managed-object verification binding SHA-256 and byte length;
- authenticated monitoring delivery and signed RPO/RTO recovery evidence.

## Reproducible verification

- `python3 scripts/check_release.py`: **23 tests passed**.
- Five additional complete-suite stress loops: **115/115 tests passed**.
- `python3 scripts/smoke_e2e.py`: create→review→publish→export→restart→backup→restore passed.
- Dashboard visual QA was not performed in this checkpoint, per operator instruction.

## Production label

The code now contains production control paths and fails startup when required production configuration is absent. A real deployment is not certified merely by source tests. The operator must still supply receipts proving the configured IdP enforces MFA, the managed bucket is encrypted and retained correctly, a signed alert reached a named on-call human, target-environment recovery met RPO/RTO, and real dossiers passed independent editorial/legal review. Until those receipts are recorded in `ops/production-readiness.yaml`, the honest release label remains **production-capable public beta**, not certified v1 production.
