# API contract — v0.3

All write requests use `Content-Type: application/json`. Development/test deployments may use expiring bearer credentials. Production accepts only fresh, MFA-marked, HMAC-authenticated identity-gateway assertions and requires `Idempotency-Key` on writes. Admin, reviewer and scanner roles are separate.

## Public reads
- `GET /health`, `GET /ready`
- `GET /api/projects` — published projects only
- `GET /api/projects/{project_id}` — public fields and public claim states only
- `GET /api/projects/{project_id}/report`
- `GET /api/projects/{project_id}/rti`

## Admin writes
1. `POST /api/projects`
2. `POST /api/projects/{id}/sources` with publisher, canonical HTTP(S) URL, retrieval time, SHA-256 and passage/page anchor.
3. `POST /api/projects/{id}/documents` records metadata in quarantine; it does not claim malware scanning completed.
4. `POST /api/projects/{id}/claims` always creates a candidate tied to a source.
5. `POST /api/projects/{id}/claims/{claim_id}/publish` succeeds only after two distinct reviewer approvals.
6. `POST /api/projects/{id}/gaps`
7. `POST /api/projects/{id}/responses`
8. `POST /api/projects/{id}/publish` requires at least one public claim and no pending claims.
9. `POST /api/projects/{id}/claims/{claim_id}/correct` stores the previous text and returns the claim to candidate; two fresh approvals are required.

## Credential and operational endpoints
- `GET/POST /api/auth/tokens` — list metadata or issue/rotate an expiring credential; plaintext is returned once.
- `POST /api/auth/tokens/{id}/revoke` — revoke an active credential.
- `POST /api/projects/{id}/documents/{document_id}/scan` — scanner-only quarantine decision.
- `GET /metrics` — admin-only Prometheus text metrics.
- `POST /api/operations/test-alert` — authenticated monitoring delivery test.

## Reviewer writes
- `POST /api/projects/{id}/claims/{claim_id}/reviews` with `{"decision":"approve|reject","note":"..."}`.
- A reviewer can submit only one decision per claim review cycle.

## Private reads
Append `?include_private=1` and authenticate as admin/reviewer. `GET /api/projects/{id}/audit` returns append-only, hash-chained audit events.

## Error behavior
JSON errors use 400 validation, 401 unauthenticated, 403 wrong role, 404 hidden/not found, 409 workflow conflict, 413 oversized body and 429 write-rate limit.
