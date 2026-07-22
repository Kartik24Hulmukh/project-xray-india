# Launch Kit — honest-copy pack (controlled beta, 22 Jul 2026)

## Rules for every channel
- Never write "high-leverage", "revolutionary", "game-changing", "guaranteed", "anti-corruption platform".
- Frame: **evidence-workflow system**, controlled beta, synthetic data, invite-only.
- Lead with what it does NOT do. This is the differentiator, not a weakness.
- Link receipts: test count, audit report, SBOM, review-gate demo GIF.
- Realistic expectations [VF, 2026 practitioner data]: HN front page ≈ 200–500+ visitors; PH top-5 ≈ 1,500 visitors / ~120 signups; both are lotteries. Success metric = design-partner conversations, not stars.

## Show HN (post Tue–Thu, 8–11 AM ET = 5:30–8:30 PM IST)
**Title:** Show HN: An evidence-workflow engine for public-accountability documents (the launch region)

**First comment (post immediately):**
I built this solo over the last few weeks. It's a workflow system for handling
accountability documents (tenders, budgets, audit reports): quarantine →
extraction → claim/anchor linking → two-person review → allowlisted public
projection, with an HMAC-chained audit history.

What it deliberately does NOT do: it doesn't score corruption, doesn't verify
truth, doesn't accept anonymous tips, and doesn't publish anything a second
reviewer hasn't approved. "Not found" means "not located in searched sources",
never "doesn't exist".

Stack: pure-stdlib Python (no runtime deps), ~1,900 LOC, 130 tests, SQLite or
Postgres. Runs with one command. The current beta is synthetic-data only while
the editorial/legal layer matures — that's a policy choice, not a technical
limitation. I'd genuinely value critique of the review-gate and audit-chain
design. [repo link]

**HN rules:** no signup wall on the demo, reply to every comment for 3–4 hours,
concede valid criticism immediately, never argue tone.

## LinkedIn / X / Threads (same day, after HN)
I open-sourced Tracepaper today — an evidence-workflow engine for
public-accountability documents.

It will not tell you who is corrupt. That's the point. It gives journalists
and civil-society teams a disciplined pipeline: quarantined intake, source
anchors, two-person review before anything goes public, and a tamper-evident
audit trail.

Controlled beta, synthetic data only for now. If you work with tenders, RTI
responses, or audit documents and want to shape it, I'm looking for 3 design
partners. [link]

## Reddit (r/opensource, r/selfhosted, r/datacurator — read each sub's self-promo rules first)
Angle for r/selfhosted: "pure-stdlib Python, zero runtime dependencies,
single-command run, SQLite mode" — that community values this genuinely.
Angle for r/opensource: workflow discipline for public-records documents; ask for
critique, not upvotes.

## Product Hunt — recommendation: SKIP on Wednesday [SI]
PH rewards consumer polish + hunter networks; a synthetic-data civic-infra
beta will bury. Post later (or use Peerlist Launchpad / Uneed / Fazier /
Dev Hunt, which are friendlier to dev tools) after you have a design partner
quote and a real demo instance.

## What NOT to publish Wednesday
- Any real-person or real-company case study
- "Production on AWS" claims unless the receipts exist (plan review, restore drill)
- Any uptime/SLA promise
- Follower-bait ("the launch region's first…", "ending corruption…")
