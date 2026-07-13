# Project X-Ray India

**What was promised. What changed. What was built. Show the evidence.**

Open-source public-infrastructure evidence and implementation-integrity engine for India.

**Release planning date:** 12 July 2026 (Asia/Kolkata)
**Repository status:** hardened public-beta reference implementation. Code-level gates are green; operator/environment production gates remain explicitly blocked in `docs/IMPLEMENTATION_AUDIT.md`.
**Licence:** Apache-2.0.

## Honest scope

Project X-Ray does **not** determine whether a person or organization is corrupt, move public funds, replace PFMS/GeM/PAIMANA, or treat news reports as proof. It creates source-linked project dossiers, classifies claims, records missing evidence, compares project events, and generates review/RTI material for human investigation.

## What works in this package

- Create and list public-infrastructure projects.
- Add source-linked candidate claims with explicit evidence states.
- Require two distinct reviewers before claim publication and after corrections.
- Register document/evidence records with SHA-256 hashes and quarantine state.
- Record missing required documents.
- Publish authority responses beside allegations.
- Generate a downloadable evidence report and draft RTI request.
- SQLite persistence and database initialization.
- JSON API and responsive public dashboard.
- Security headers, body/rate limits, hash-chained immutable audit events, health/readiness endpoints.
- Tested restart persistence, backup/restore, legacy migration and end-to-end smoke path.
- Unit tests, release checks, reproducible SBOM/checksums, Docker image and CI templates.

## Quick start

```bash
cp .env.example .env
python3 app/server.py
# open http://localhost:8080
```

Run tests:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check_release.py
python3 scripts/smoke_e2e.py
```

Run with Docker:

```bash
docker compose up --build
```

## First production deployment gate

Do not publish as “production ready” merely because it runs. All `P0` gates in `docs/PRODUCTION_READINESS.md` must pass on the target deployment, including independent factual review of every published case, HTTPS, backups, incident ownership, privacy review, abuse handling and recovery testing.

## Start here

1. `AGENTS.md` — rules for Codex/GPT coding agents.
2. `docs/ROADMAP_72_HOURS.md` — hour-by-hour plan.
3. `docs/ACCEPTANCE_CRITERIA.md` — non-negotiable definition of done.
4. `docs/PRD.md` — users, scope and product requirements.
5. `docs/EVIDENCE_POLICY.md` — publication and claim-safety rules.
6. `docs/PRODUCTION_READINESS.md` — release gate.
7. `docs/LAUNCH_AND_IMPACT.md` — traction and impact plan.

## Architecture

The supplied app is intentionally dependency-light so it runs offline and gives Codex a stable reference. During the sprint, Codex may migrate the service to FastAPI/PostgreSQL and the UI to Next.js only if the existing vertical slice remains green and the migration passes the same contract tests.

## No-fake-claims rule

- Synthetic records must display `SYNTHETIC` prominently.
- “Not found” means “not located in searched sources,” never “does not exist.”
- An official statement is an official claim, not independent verification.
- A risk indicator is a review prompt, not evidence of corruption.
- No case may be public until two-person source review passes.
