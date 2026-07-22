# Gumloop integration runbook

## Handoff artifacts

- Full source ZIP: authoritative tracked source snapshot.
- Overlay ZIP: files added or changed relative to the supplied v0.4.1 synthetic-preview package plus `DELETE_PATHS.txt`.
- Git bundle: local checkpoint history for forensic comparison; do not merge it blindly into an unrelated remote history.
- Deployment pack: OpenTofu, workflows, AWS receipt validator and deployment documentation.
- Handoff ZIP: prompts, checksums, manifest and this runbook.

## Safe import

1. Verify every `.sha256`.
2. Clone `Kartik24Hulmukh/project-xray-india` and record current `origin/main`.
3. Create `gumloop/v0.4.4-controlled-preview-rc` from current main.
4. Compare the full source and overlay against current main.
5. If the remote diverged from the handoff base, resolve file-by-file and report conflicts; do not overwrite or force-push.
6. Never copy a supplied `.git` directory.
7. Run all tests and security/release gates from `GUMLOOP_SYSTEM_PROMPT.md`.
8. Push only the new branch and open a PR. Do not merge.

## Rollback

Before import, record the branch base SHA. If integration checks fail, reset only the temporary Gumloop branch to that SHA or delete the temporary branch. Never reset or rewrite remote main. If a reviewed PR is later merged and must be reverted, use a normal revert PR tied to the merge commit and rerun all required checks.

## Release boundary

This package is a repository-verified controlled synthetic preview / controlled-beta release candidate. It is not AWS-production-certified, legal advice, evidence of adoption, or proof of impact. Public uploads and real-case publication remain blocked until the target and human gates pass.
