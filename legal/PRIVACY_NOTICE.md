> **DRAFT TEMPLATE — NOT LEGAL ADVICE — requires qualified counsel review in the operator's jurisdiction before use as operative terms. Jurisdiction-specific statute references are intentionally omitted here; see private operator compliance note.**

# Privacy Notice — Tracepaper (TEMPLATE — requires counsel review)

**Data Fiduciary:** [legal name, address] · **Contact / Grievance Officer:** [name, email] (see GRIEVANCE_AND_TAKEDOWN.md)

## What we collect
- **Account data:** name, email, authentication identifiers (via Cognito), MFA status.
- **Operational data:** audit logs of reviewer actions (kept for integrity of the evidence chain), IP addresses and access logs (security; retained per CERT-In direction — rolling 180 days minimum for ICT logs).
- **Content you submit:** documents and claims you upload into the controlled workflow. During the controlled preview, only synthetic or explicitly approved public/sanitized material is permitted.

## Why (purpose limitation)
Authentication and access control; evidence-workflow integrity (immutable audit
history); security monitoring and incident response; legal compliance.
We do not sell personal data or use it for advertising.

## Legal basis and your rights (DPDP Act 2023 / DPDP Rules 2025)
We process personal data with consent or for legitimate uses permitted by the
DPDP Act. You may: access a summary of your personal data; request correction
and erasure (subject to audit-integrity and legal retention constraints, which
we will explain when they apply); nominate a person to exercise rights on your
behalf; and complain to our Grievance Officer and thereafter to the Data
Protection Board of the operator jurisdiction.

## Retention
Account data: life of account + [N] months. Security logs: ≥180 days (CERT-In).
Audit chain entries: retained for evidence integrity; personal identifiers are
minimized in public projections (allowlisted fields only, verified by
automated PII canary tests before each release).

## Security
Encryption in transit (TLS) and at rest (KMS); private storage with Block
Public Access; MFA; role separation; two-person review before publication;
incident response per INCIDENT_RESPONSE runbook; CERT-In reportable incidents
notified within required timelines.

## Transfers
Data is stored in AWS ap-south-1 (Mumbai). Sub-processors: [list].

*Template drafted 20 Jul 2026. Not legal advice.*