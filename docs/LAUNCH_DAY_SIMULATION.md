# Launch-Day Simulation — Scenario Matrix (run 2026-07-20)

Method: persona-based adversarial simulation across parallel analysis tracks
(HN/engineer crowd, security researchers, journalist-users, trolls/partisans,
ops/infra, day-2 maintainer). Probabilities are calibrated estimates, not measurements.

## Baseline expectations (evidence-backed)
- Show HN is a lottery: roughly a 1-in-10 chance of a real audience; many good
  submissions die. Post life is ~48–72h. Reposting weeks later with a better
  title is allowed and often works.
- HN admin guidance: neutral factual title, no marketing tone, talk as a peer,
  never be defensive, NEVER ask friends for upvotes/booster comments
  (voting-ring detection kills the post).
- Front-page traffic is survivable by design: static content + CDN. Failure
  mode to avoid is anything that hits a database per page view.

## Scenario matrix
| # | Scenario | Prob. | Impact | Pre-launch fix | Live response |
|---|---|---|---|---|---|
| 1 | **Silence** — post dies, <10 visitors | ~55% | Morale, not product | Success metric = 20 outreach messages sent, not stars | Repost in 2–3 weeks with better title; write it up as a build log |
| 2 | Fresh-clone failure reported by a stranger (OS/Python version) | ~35% | First-impression kill | Fresh-clone drill on a clean container; pin supported Python; quickstart tested end-to-end | Reproduce, fix within hours, thank reporter publicly |
| 3 | Top comment: "AI + evidence = hallucination risk" | ~70% if traction | Credibility | FAQ answer ready (AI proposes candidates only; every claim requires a human-anchored source span; two-reviewer gate) | Agree with the concern first, then explain the gate design; never defensive |
| 4 | "Why not Aleph / Datashare?" | ~60% | Positioning | FAQ comparison ready (see LAUNCH_FAQ) | Position as complement (claim→anchor discipline + publication gates), not replacement |
| 5 | Security researcher probes repo + demo (scanners, SECURITY.md check, endpoint poking) | ~40% | High if unprepared | SECURITY.md with CVD policy + contact (Google OSS-CVD template); rate-limit demo; run canary suite against the real demo target | Acknowledge within hours; treat reporters as allies; fix-and-credit |
| 6 | Demo dies under load (hug of death) | ~30% if front page | Embarrassing, recoverable | Demo GIF in README (survives anything); read-only demo behind CDN caching; no signup wall | Swap README link to GIF; post status comment; keep answering |
| 7 | Bad-faith/troll submission attempts on day one | ~25% day 1, near-certain eventually | Legal/reputation | Intake stays invite-only; prohibited-content rules published; publication requires two reviewers | Quarantine + document; do not engage publicly |
| 8 | License / "who maintains this?" / sustainability questions | ~50% | Trust | LICENSE clear in repo; honest solo-maintainer note ("independent review invited") | Answer factually; point to release maturity model |
| 9 | A flaky test fails for a stranger who runs the suite | ~15% | Undermines core claim | Run full suite 3× on clean env before tagging | Reproduce, fix or mark known-issue same day |
| 10 | Self-inflicted: booster comments / hype language | avoidable | Post killed, account flagged | Banned-words list; no friends voting; one author account | — |

## Post-deployment product simulation (first 7 days after AWS apply)
What exists when deployment succeeds: gateway service (no custody access) +
app service behind ALB/WAF; invite-only sign-in; quarantine intake →
two-reviewer gate → allowlisted public projection; tamper-evident audit chain;
trust-record JSON published per release.

Most likely first-week incidents (fix = rehearse before launch):
1. Identity/OIDC misconfiguration locks out the only admin — rehearse recovery path; document break-glass procedure offline.
2. DNS/TLS certificate validation stalls — provision certs before launch day, not during.
3. Alerts configured but never delivered — send a real test alert to your phone/email and confirm receipt (receipt required by the maturity model).
4. Backup exists, restore never tested — do one timed restore before any real data enters the system.
5. Cost surprise — NAT + ALB + WAF + Fargate + RDS baseline is real money monthly even at zero traffic (estimate range, verify with your own bill after 48h; set a billing alarm at 2× estimate).
6. Alarm fatigue or silent failure — start with 3 alarms that matter (5xx rate, task restarts, DB storage), not 30.

## Timeline (IST)
- T–24h: code freeze; suite 3×; canary suite vs demo target; no-go checklist
- T–12h: certs/DNS live; test alert received; restore drill done; GIF recorded
- T0 Wed 10:00: repo public + tagged release with evidence bundle
- 17:30–18:30: Show HN (Tue–Thu window); 4h in comments, founder voice, never defensive
- T+4h: send all 20 design-partner messages (this is the actual launch)
- T+24h: issue triage block; thank every reporter
- T+48–72h: post life ends; log outcomes in design-partner scorecard
- T+7d: retro against kill criteria (<3 partner conversations trending → narrow)
