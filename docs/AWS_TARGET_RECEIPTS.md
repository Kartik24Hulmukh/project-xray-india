# AWS target receipt gate

Repository checks prove code behavior only. A release is not production-ready until **all eight target receipts** pass for one AWS account, `ap-south-1`, environment, Git SHA and immutable image digest.

Required files:

1. `identity.json` — Cognito TOTP enrollment/challenge, rejected wrong issuer/client/signature, disabled-user rejection, stable role mapping.
2. `deployment.json` — ECR digest, both ECS task-definition ARNs, running app/gateway digests, protected-environment approval.
3. `storage.json` — task-role caller identity, exact S3 version/hash/length, KMS encryption and negative cross-role/cross-bucket tests.
4. `database_restore.json` — private RDS, enforced TLS, migration version, destructive restore drill and measured RPO/RTO.
5. `rollback.json` — independent app and gateway rollback to compatible digests, database migration rollback decision and service recovery.
6. `alert.json` — alarm injection, SNS subscription confirmation and human acknowledgement timestamp.
7. `network.json` — external ALB path succeeds; direct app, gateway ENI and RDS paths fail; security-group and flow-log evidence.
8. `load.json` — bounded controlled-beta load test, p95 latency/error rate, rate-limit behavior and no publication invariant failures.

Validate with:

```bash
python3 scripts/validate_aws_receipts.py artifacts/aws/staging --environment staging
python3 scripts/validate_aws_receipts.py artifacts/aws/production --environment production
```

The validator fails if a receipt is missing, failed, malformed, from a different account/region/environment, or references a different Git SHA or image digest. Receipt content must not include tokens, passwords, private evidence, cookies or identity JWTs.

Impact and traction remain separate: target receipts do not prove adoption, and adoption never waives a failed security gate.
