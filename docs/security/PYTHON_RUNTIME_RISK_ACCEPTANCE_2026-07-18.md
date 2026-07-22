# Python Runtime Risk Acceptance — Controlled Synthetic Preview

**Date:** 2026-07-18
**Accepted by:** Kartik Hulmukh, repository owner
**Scope:** controlled synthetic preview / controlled-beta release candidate only
**Expiry:** 2026-08-18, or earlier if a fixed stable Python release becomes available
**PR:** https://github.com/Kartik24Hulmukh/project-xray-india/pull/13

## Alpine Migration Evidence

The container base was migrated from `python:3.13-slim-bookworm` (Debian Bookworm) to a multi-stage `python:3.13-alpine` build. This reduced Grype HIGH findings from 23 to 3 — an 87% reduction.

| Metric | Before (Bookworm) | After (Alpine) |
|---|---|---|
| HIGH findings | 23 | 3 |
| OS package CVEs | 20 | 0 |
| Python binary CVEs | 3 | 3 (unchanged) |
| "won't fix" OS CVEs | 16 | 0 |

All 20 Debian OS package CVEs (perl-base, libc6, ncurses, gzip, libsqlite3, libacl, libtasn1) were eliminated by switching to Alpine. No OS package vulnerabilities remain.

## Accepted CVEs

The following three HIGH vulnerabilities are in the Python 3.13.14 runtime binary itself. They exist in every Python 3.13.x image regardless of base OS (Debian, Alpine, or distroless).

| CVE | Severity | EPSS | Fixed In | Status |
|---|---|---|---|---|
| CVE-2026-11940 | High | 0.6% | — | No fix version listed |
| CVE-2026-15308 | High | 0.6% | 3.15.0 | Fix exists but 3.15.0 is beta only |
| CVE-2026-11972 | High | 0.4% | — | No fix version listed |

All three have low EPSS scores (0.3–0.5%), indicating low exploit probability.

## Why Distroless Will Not Solve These

A distroless final stage (e.g., `gcr.io/distroless/python3`) still ships the same Python 3.13.14 binary. The three CVEs are in the Python interpreter's C code, not in OS packages. Switching to distroless would not change the vulnerability count for these three findings. The only fix is a patched Python release (3.15.0 stable or a backport to 3.13.x).

## Compensating Controls

This risk acceptance is granted only because the following compensating controls are in place:

1. **No public uploads** — public uploads and real-case publication remain blocked
2. **Private originals** — all evidence originals are private with explicit public projections only
3. **Gateway authentication** — ALB OIDC gateway with ES256 identity verification
4. **Non-root container** — runs as UID 10001, no root access
5. **Minimal Alpine multi-stage image** — no compilers, git, package caches, tests, or docs in final image
6. **Read-only posture** — filesystem writable only for `/app/data/uploads`
7. **Kill switches** — documented kill-switch runbook and checklist
8. **Controlled preview only** — no production certification, no real-person/real-case publication, no unrestricted public access

## Expiry and Revalidation

- **Expiry date:** 2026-08-18
- **Early expiry trigger:** if Python 3.15.0 stable or a patched 3.13.x is released before the expiry date
- **Revalidation action:** rebuild the container image with the fixed Python release, rerun the complete Security workflow (Gitleaks, Trivy, Syft, Grype), and remove the accepted CVEs from `security/grype-exceptions.yaml`
- **CI guard:** `scripts/check_grype_exceptions.py` fails if the expiry date has passed or if the exception file grows beyond three CVE IDs without explicit review

## Exception File

The narrow Grype exception is in `security/grype-exceptions.yaml` and loaded via `.grype.yaml`. It targets exactly three CVE IDs on the `python` package at version `3.13.14` with type `binary`. No OS package CVEs, app dependency CVEs, or unrelated findings are ignored.

The `--fail-on high` threshold is preserved. Any new HIGH or CRITICAL finding that is not in the accepted set will still fail the Security workflow.
