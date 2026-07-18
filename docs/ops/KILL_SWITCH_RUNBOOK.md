# Kill-switch runbook

## Goal

Contain a serious incident in under five minutes without editing the database by hand.

## Triggers

Fire the kill switch if any of the following occur:

1. Real-person/project data appears in preview.
2. Forbidden field or PII canary appears in anonymous output.
3. Unreviewed publication succeeds.
4. Auth bypass or forged identity is accepted.
5. Quarantined object becomes public.
6. Credible legal/privacy complaint arrives.
7. Data integrity is uncertain.
8. Maintainer cannot monitor the system.

## Levels

### L1 — Soft containment

- Disable anonymous non-essential routes or show maintenance banner.
- Disable publication and uploads via configuration flags if available:
  - `DISABLE_PUBLICATION=true`
  - `DISABLE_UPLOADS=true`
  - `DISABLE_WRITES=true`
  - `READ_ONLY_MODE=true`
  - `MAINTENANCE_MODE=true`

### L2 — Hard containment

- Set ECS desired count to 0 **or** attach ALB/WAF deny rule for public traffic.
- Keep health endpoint internal if needed for diagnosis.
- Preserve logs and audit evidence.

### L3 — Identity containment

- Revoke Cognito sessions / rotate gateway secret after containment.
- Disable operator access except incident roles.

### L4 — Narrative

Publish a short status note:

> We identified a safety, privacy, or integrity issue during the technical preview and paused the hosted surface while we correct it. The repository remains available for review. This preview used synthetic data only unless otherwise stated in an incident update.

## Recovery

1. Identify root cause and freeze SHA.
2. Add regression test.
3. Redeploy only after two-person review of the fix.
4. Re-run public allowlist, auth matrix, and synthetic smoke.
5. Record receipts under `artifacts/preview/`.

## Drill requirement

At least one L1/L2 drill must be recorded before hosted preview opens.
