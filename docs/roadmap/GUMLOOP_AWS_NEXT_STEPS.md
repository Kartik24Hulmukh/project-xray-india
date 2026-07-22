# Gumloop and AWS next steps

## Order of operations

1. Secure AWS account (root MFA, non-root admin, budgets, region `ap-south-1`).
2. Run Gumloop **plan-only** infrastructure PR.
3. Land code PRs: task-role storage, Cognito gateway adapter, kill switches, blocking CI.
4. Bootstrap OpenTofu state + GitHub OIDC.
5. Apply **staging only**.
6. Run full staging acceptance, restore, rollback, load, ZAP/Prowler.
7. Sunday go/no-go.
8. Apply production only if all P0 receipts exist.

## Deadline architecture

- Public ALB
- Fargate tasks in public subnets with public IP
- Task SG inbound only from ALB
- Private Single-AZ RDS
- No NAT initially
- Four S3 custody buckets: quarantine, originals, public-redacted, manifests
- Cognito MFA, no self-signup
- WAF + CloudWatch + SNS human alert path

## Gumloop must not

- apply production automatically
- request or print secrets
- create static AWS keys
- publish real dossiers
- mark readiness gates passed without receipts

## Hosted Monday fallback

If AWS target gates fail, still ship repository + local synthetic preview + evaluator kit. Do not force a weak cloud deploy to protect the date.
