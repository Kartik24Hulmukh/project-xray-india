# AWS controlled-beta OpenTofu stack

This directory is **plan-only until an authorized operator reviews and applies it**. It contains no secret values and accepts only an immutable ECR `sha256` image digest.

## Architecture

- `ap-south-1`, VPC `10.20.0.0/16`
- two public Fargate/ALB subnets and two private DB subnets
- no NAT; Fargate receives public egress IPs but accepts inbound only from the ALB security group
- ALB `authenticate-cognito` with TOTP-required Cognito
- gateway container on `8080`; application on task-local `8081` with no VPC ingress
- encrypted RDS PostgreSQL; production plans enable Multi-AZ
- four private, versioned, KMS-encrypted custody buckets; evidence/dossier Object Lock is enabled by default
- WAF, CloudWatch, SNS and budget alerts
- GitHub OIDC role constrained to pull-request planning and read-only discovery

## Plan-only validation

```bash
cp terraform.tfvars.example terraform.tfvars
# Replace placeholders with non-secret resource identifiers only.
tofu fmt -check -recursive
tofu init -backend=false
tofu validate
tflint --recursive
checkov -d .
tofu plan -refresh=false -lock=false -out=/tmp/xray.plan
```

Never commit `terraform.tfvars`, a binary plan, state, credentials, secret values, or custody data. A saved plan can contain sensitive values.

## Hard boundary

Repository validation does not prove AWS readiness. An authorized staging apply must retain receipts for the exact Git SHA and image digest, effective task-role permissions, Cognito TOTP, ALB signer checks, S3/KMS version access, RDS TLS/restore, WAF, alert delivery, running ECS digest, rollback and load tests. Production remains blocked until those receipts pass.
