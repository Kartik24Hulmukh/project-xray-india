# OpenTofu bootstrap — ap-south-1 staging (skeleton, review before apply)

This skeleton exists because PR #13's title claims AWS IaC but the reviewed
snapshot contains none. It encodes the co-founder verdict's Lane B requirements.
It is a starting point, not a reviewed plan. Nothing here is "done" until a
real `tofu plan` against the target account has been human-reviewed.

## Order of operations (matches verdict Lane B)
1. **Account security first (manual, console):** root MFA, IAM Identity Center
   admin, billing alerts/budget, CloudTrail on, region ap-south-1.
2. **Bootstrap (manual or one-off script):**
   - S3 state bucket: versioning + SSE-KMS + Block Public Access + restricted policy.
   - OpenTofu ≥1.10 supports S3-native state locking (`use_lockfile = true`) — no DynamoDB table needed.
   - KMS key for state + custody buckets.
   - GitHub OIDC provider `token.actions.githubusercontent.com`.
   - Plan-only role trust: `repo:<owner>/tracepaper:pull_request`.
   - Deploy role trust: `repo:<owner>/tracepaper:environment:staging`.
3. Set repo variable `AWS_BOOTSTRAPPED=true` only after step 2 exists.
4. CI behavior: `tofu fmt -check`, `tofu init -backend=false`, `tofu validate`
   always run offline; speculative plan **skips (not fails)** when
   `AWS_BOOTSTRAPPED != true`.

## Non-negotiable security posture encoded in variables.tf
- RDS PostgreSQL 16: private subnets only, encrypted, TLS enforced,
  deletion protection, automated backups.
- 4 private S3 custody buckets (intake-quarantine, private-evidence,
  restricted-dossier, publication-staging): versioning, SSE-KMS,
  Block Public Access, TLS-only bucket policy, task-role-only access.
- Only the ALB accepts public ingress; gateway and app have separate
  security groups and task roles.
- ECS: task-definition health checks (Dockerfile HEALTHCHECK is ignored by
  ECS) + deployment circuit breaker with rollback enabled.
- No wildcard IAM. No long-lived AWS keys in GitHub — OIDC only.

## Review checklist for the first real plan (from verdict)
unexpected destroys · wildcard IAM · public RDS/S3 · direct app exposure ·
missing encryption · missing deletion protection · secrets in plan output ·
mutable image tags · AZ/subnet layout · unnecessary cost.
