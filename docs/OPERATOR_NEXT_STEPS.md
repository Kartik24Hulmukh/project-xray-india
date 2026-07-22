# Operator Next Steps

Repository implementation is substantially complete for a controlled-beta release
candidate. Human review, AWS target validation, operational receipts and
legal/editorial gates remain.

## Remaining work (owner: human operator)
1. Independent review and merge of PR #13 (v0.4.4 head). No donor content lands before this.
2. Gumloop documentation-overlay PR using `gumloop/` prompts; human-review and merge that PR.
3. Repository/product rename per `docs/NAMING_DECISION.md` (GitHub repo rename + in-repo string PR).
4. AWS account bootstrap from the canonical `infra/aws-controlled-beta` IaC; real `tofu plan` reviewed by a human before apply. Provisioning may be quick if prepared; production verification will take longer — do not schedule it as a fixed 60–90 minute task.
5. Operational receipts: identity/MFA proof, backup + restore, rollback, alert delivery, load test, network-negative tests.
6. Counsel review of `legal/` drafts (entity, jurisdiction, grievance contact, retention, processors) before any hosted public instance.
7. Design-partner evidence: 20 personalized messages, 5 workflow interviews, 2 sanitized document tests, 1 signed commitment, 1 paid-pilot condition.

## Wednesday scope
Wednesday is an **open-source repository and synthetic-methodology release** plus
design-partner outreach — not a hosted production launch. Do not represent it otherwise.
