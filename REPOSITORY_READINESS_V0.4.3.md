# Repository readiness — v0.4.3 controlled-beta release candidate

## Repository-complete evidence

- 163+ local unit/integration tests before target-receipt additions.
- Executable trusted ALB/Cognito gateway and synthetic ES256 adversarial tests.
- Fail-closed capability switches and all 64 switch combinations.
- ECS task-role/default-chain S3 verification with exact version/hash/length binding.
- Separate gateway and app services, IAM roles, security groups and Cloud Map boundary.
- RDS-managed secret injection, PostgreSQL TLS mode construction and Multi-AZ production configuration.
- Four private versioned KMS custody buckets, Object Lock for evidence/dossier, WAF, Cognito TOTP, alarms and budget.
- Plan-only OIDC workflow; no cloud mutation path in pull requests.
- Manual protected deployment requires exact reviewed SHA, required successful checks and exact ECR digest; verifies running digests and rolls both services back on failure.
- Eight-category same-SHA/same-digest AWS receipt validator.

## Hard blockers outside this sandbox

- OpenTofu provider initialization and validation could not run locally because OpenTofu and network access are unavailable; CI must run `fmt`, `init -backend=false`, `validate` and speculative plan.
- No authorized AWS account apply was performed.
- Cognito TOTP, ALB signer, ECS task roles, S3/KMS versions, RDS restore, network denial, WAF, alerts, load and rollback need target receipts.
- Scanner remains a controlled operator/scanner-role attestation boundary; unrestricted public upload and autonomous malware scanning are not approved for launch.
- External legal, privacy and security review remain required for real-case publication.
- Impact and traction require repeated independent use and are not claimed by repository tests.

**Label:** repository-verified controlled-beta release candidate. **Not production-certified.**
