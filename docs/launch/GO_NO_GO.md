# Monday go / no-go — 20 July 2026

## Default decision

**GO-SYNTHETIC-PREVIEW** if hard technical safety gates pass.
**NO-GO-HOSTED** if target authentication, public allowlist, or kill switch fails — fall back to repository + local synthetic demo + recorded walkthrough.
**NO-GO-REAL-CASES** always for Monday unless independent legal/editorial owners explicitly approve, which is not expected.

## Hard gates for hosted synthetic preview

- [ ] Frozen SHA / tag `v0.4.1-synthetic-preview`
- [ ] Clean clone tests green
- [ ] `scripts/check_release.py` green on package
- [ ] Synthetic smoke path green
- [ ] Public allowlist / PII canary green
- [ ] Unsupported publication blocked
- [ ] Two distinct reviewers required
- [ ] SYNTHETIC markers visible
- [ ] Real-case publication disabled
- [ ] Public uploads disabled or invite-only and empty of real data
- [ ] Kill switch drilled
- [ ] Named incident owner reachable
- [ ] Known limitations published

## Additional gates for any broader claim

- Target Cognito/MFA proof
- Fresh-target PostgreSQL restore
- Human alert acknowledgement
- Managed private storage receipts
- Legal/privacy/source-terms owners
- Independent editorial review of real dossiers

## Decision record

Record the final decision in `ops/preview/monday-go-no-go.yaml`.
