# AWS Bootstrap Runbook

## Purpose

This runbook explains how the Infrastructure plan workflow separates
**offline OpenTofu validation** from **AWS speculative planning**, and how to
enable or disable the speculative plan after AWS bootstrap.

## Why offline validation and target planning are different

| Aspect | Offline validation (`tofu-validate`) | AWS speculative plan (`speculative-plan`) |
|---|---|---|
| AWS credentials | None required | OIDC plan-only role |
| id-token: write | No | Yes (job-level only) |
| What it proves | HCL syntax, format, provider schema | Real AWS resource plan |
| When it runs | Always on IaC/infra-workflow PRs | Only when `AWS_BOOTSTRAPPED=true` |
| Binary plan | Never produced | Produced then deleted; never uploaded |
| Production evidence | No | No (plan-only, never applied) |

Offline validation confirms the OpenTofu code is well-formed and internally
consistent. It cannot prove that the AWS target account accepts the plan or
that staging inputs are correct. The speculative plan bridges that gap but
requires a real OIDC plan-role and all staging inputs.

## Default: AWS_BOOTSTRAPPED=false

The repository variable `AWS_BOOTSTRAPPED` defaults to absent or `false`.

When absent or `false`:
- `tofu-validate` and `static` jobs run on every qualifying PR.
- `speculative-plan` exits with a notice: **"AWS speculative plan not run — target not bootstrapped."**
- The workflow summary states the plan was not run.
- This is **not** production evidence.

Only the literal lowercase string `true` enables the speculative plan. Any
other value (including `True`, `TRUE`, `1`, `yes`) is treated as disabled.

## Required GitHub repository variables

When `AWS_BOOTSTRAPPED=true`, all of the following must be set and
format-validated before OIDC credentials are requested:

| Variable | Format |
|---|---|
| `AWS_PLAN_ROLE_ARN` | `arn:aws:iam::<12-digit>:role/...` |
| `OPENTOFU_IMAGE_DIGEST` | `sha256:` + 64 hex chars |
| `STAGING_DOMAIN_NAME` | valid DNS domain |
| `STAGING_CERTIFICATE_ARN` | `arn:aws:acm:<region>:<12-digit>:certificate/...` |
| `CANDIDATE_IMAGE_DIGEST` | `sha256:` + 64 hex chars |
| `NOTIFICATION_EMAIL` | valid email address |
| `GITHUB_OIDC_PROVIDER_ARN` | `arn:aws:iam::<12-digit>:oidc-provider/...` |
| `GATEWAY_ROLE_BINDINGS_SECRET_ARN` | `arn:aws:secretsmanager:<region>:<12-digit>:secret:...` |
| `APP_SECRET_ARNS_JSON` | JSON array string |
| `COGNITO_DOMAIN_PREFIX` | alphanumeric with hyphens |
| `CALLBACK_URLS_JSON` | JSON array string |
| `LOGOUT_URLS_JSON` | JSON array string |

No placeholders. Each variable must contain a real, non-placeholder value.
If any variable is missing or invalid, the speculative-plan job **fails
closed** and no OIDC token is requested.

## OIDC plan-role trust subject

The plan-only OIDC role must trust this exact subject:

```
repo:Kartik24Hulmukh/project-xray-india:pull_request
```

The role must be plan-only: it must not permit `apply`, `destroy`, or
`import`. The workflow never executes those commands.

## How to enable the real speculative plan after AWS bootstrap

1. Create the OIDC plan-only IAM role in the target AWS account with the
   trust subject above.
2. Create or obtain all required staging inputs (domain, certificate, image
   digest, secrets, Cognito prefix, callback/logout URLs, notification email).
3. Set all required GitHub repository variables listed above.
4. Set `AWS_BOOTSTRAPPED` to `true` (lowercase).
5. Open or update a PR that touches `infra/aws-controlled-beta/**` or
   `.github/workflows/infra-plan.yml`.
6. The `speculative-plan` job will validate all inputs, request OIDC
   credentials, and produce a speculative plan. The plan is deleted
   immediately; no binary plan is retained or uploaded.

## How to disable it immediately

Set `AWS_BOOTSTRAPPED` to `false` or delete the variable.

The `speculative-plan` job will exit with the notice:
**"AWS speculative plan not run — target not bootstrapped."**

No OIDC token will be requested. No AWS credentials will be used.

## Production remains blocked

A successful speculative plan is **not** production certification.
Production remains blocked until all target receipts pass:

- exact Git SHA and image digest retention
- effective task-role permissions
- Cognito TOTP enforcement
- ALB signer checks
- S3/KMS version access
- RDS TLS/restore
- WAF rules
- alert delivery
- running ECS digest
- rollback and load tests

See `docs/AWS_TARGET_RECEIPTS.md` for the full receipt checklist.

## Security invariants preserved

- `tofu-validate` uses no AWS credentials and has no `id-token` permission.
- `id-token: write` exists only on the `speculative-plan` job.
- No PR workflow executes `tofu apply`, `destroy`, or `import`.
- No binary plan artifact is uploaded.
- Missing required variables are never interpreted as a successful plan.
- A skipped plan is reported as "not run," never as "passed."
