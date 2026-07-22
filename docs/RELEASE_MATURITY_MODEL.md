# Release Maturity Model

Three independent tracks. None substitutes for another.

| Track | Label | Gate evidence |
| --- | --- | --- |
| 1. Repository release | `Repository-verified` | Green CI at a named SHA: full test suite, secrets scan, vuln scan, SBOM, workflow-security checks |
| 2. Target release | `AWS target-verified` | Reviewed tofu plan + apply receipts, identity/MFA proof, restore + rollback timestamps, alert-delivery proof, load + network-negative tests |
| 3. Use-case release | `Editorial/legal design-partner approved` | Counsel-approved operative terms, editorial workflow sign-off, signed design-partner usage |

Rules:
- A claim of "production" requires all three labels with dated evidence.
- Public copy must state which labels are held and which are pending.
- Wednesday's release holds at most label 1.
