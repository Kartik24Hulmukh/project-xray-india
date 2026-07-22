# Wednesday Runbook — 22 Jul 2026, 10:00 AM IST

## Decision framework (from co-founder verdict, unchanged — it is correct)
- **Tier 1** (cloud controlled beta): only if IaC plan reviewed clean + staging
  deployed + restore drill evidenced + smoke E2E green on real domain.
- **Tier 2** (local/docker controlled beta, invite-only, synthetic data):
  DEFAULT PLAN. Achievable with what exists today [VF: 130 tests green].
- **Tier 3** (private synthetic demo, no public repo yet): fallback if any
  no-go fires.

As of Sun 20 Jul: no IaC in snapshot, no AWS bootstrap evidence, no second
reviewer → **plan for Tier 2, treat Tier 1 as a stretch, don't chase it past
Monday 6 PM.**

## Monday 21 Jul
- 09:00–11:00 — Fix the 5 blocking workflow items (PR13_REVIEW.md): real CI
  gate, remove eval-on-vars, SHA-pin actions (scripts/pin-actions.sh), gitleaks
  checksum, drop `|| true`. Add zizmor job. Run everything green.
- 11:00–12:00 — Reconcile version to one value (VERSION file), regenerate
  SBOM, re-tag. Reviewed SHA recorded.
- 12:00–14:00 — Try to recruit ONE human reviewer for a 2-hour review
  (ex-colleague, community engineer). If none by EOD: label release
  "solo-maintainer, self-merged; independent review invited" — honestly.
- 14:00–17:00 — Legal folder: adapt the 4 templates in booster/legal/, fill
  operator name, grievance contact. Add SUPPORT.md.
- 17:00–18:00 — AWS checkpoint: if account bootstrap + reviewed plan not
  done → formally drop Tier 1. No exceptions (verdict rule).
- Evening — Fresh-clone drill on a clean machine: README quickstart to running
  app + demo pack in <10 min, or fix the README.

## Tuesday 22 Jul (prep day)
- Morning — Freeze code. Run full no-go checklist (below). Record demo GIF
  (upload→review→publish→audit verify). Prepare demo instance WITHOUT signup
  wall (HN requirement) — read-only public projection is enough.
- Afternoon — Stage all launch copy (booster/launch/LAUNCH_KIT.md). Prepare
  20 design-partner outreach messages (booster/launch/DESIGN_PARTNER_OUTREACH.md).
- Evening — Sleep. Post-launch you will be answering comments for hours.

## Wednesday 23 Jul — wait, launch day is Wed 22 Jul? NO — 22 Jul 2026 is a WEDNESDAY. Launch sequence:
- 09:00 IST — Final no-go check. Make repo public. Tag release with evidence
  bundle (SBOM, scan outputs, audit report, reviewed SHA).
- 10:00 IST — LinkedIn + X + Threads posts (the launch region audience awake).
- 17:30–18:30 IST (8–9 AM ET) — Show HN. Then stay online 4 hours replying.
- Parallel — Send the 20 design-partner messages. These matter more than
  every social post combined.
- Skip Product Hunt today (see launch kit).

## No-go checklist (any "no" → drop a tier, do not argue)
- [ ] All CI/security workflows green on the release SHA (no `|| true` anywhere)
- [ ] PII canary suite green against the actual demo target
- [ ] Kill switches (publication freeze) tested this week
- [ ] Legal folder present (terms, privacy, AUP, grievance) with a real contact
- [ ] Launch copy contains zero prohibited claims (traction/uptime/verified-truth)
- [ ] Public uploads + anonymous tips DISABLED and verified disabled
- [ ] You have slept ≥ 6 hours
- [ ] If Tier 1: reviewed tofu plan + restore drill evidence exists (else Tier 2)

## Success metrics for the week (write these down BEFORE launch)
- ≥3 qualified design-partner conversations booked
- ≥1 external engineer files a substantive issue/review
- 0 legal/safety incidents, 0 canary failures
- Stars/upvotes: recorded but not a goal
