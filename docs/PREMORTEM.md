# Premortem — "It is 22 August 2026 and the launch failed / hurt us. Why?"

Method: 2 adversarial loops (compress → anti-basic → evidence → council →
pre-mortem → mutate → rescore → falsify). Claims labeled [VF]/[SI]/[WI]/[UA].

## Tier 1 — Failure modes that end the project

### 1. A real person/company is named and you get a legal notice
- the launch region allows **criminal** defamation (BNS §356, successor to IPC 499/500) alongside civil suits and fast injunctions [VF].
- One published claim that a named contractor "didn't deliver" — even with a source anchor — invites a notice you cannot afford to fight [SI].
- **Fix (already your policy — enforce it):** Wednesday scope = synthetic + approved sanitized material ONLY. No real-person allegations without separate editorial/legal approval. Ship the legal/ folder before invites.

### 2. Physical/It's-not-a-joke safety risk for operators and users
- CHRI/Wikipedia document 300+ attacks and ~100 killings of RTI users in the launch region since 2006; Maharashtra and Gujarat top the list [VF].
- A tool that makes accountability evidence easier to compile inherits part of that threat model when it touches real cases [SI].
- **Fix:** no anonymous tips, no confidential-source promises (you cannot keep them yet); publish a safety note for future real-case operators; keep real deployments org-controlled, not public-upload.

### 3. PII/canary leak in a public projection
- Your own no-go list makes any leak an automatic launch stop [VF from verdict].
- **Fix:** run the recursive canary suite against the real target (not just localhost) before any public URL is shared; keep it in CI forever.

### 4. Launch copy overclaims and destroys the only asset you have (credibility)
- "high-leverage high value, high traction, high impact" in public copy = instant HN
  demolition and permanent credibility loss with the exact community you need [SI].
- The project's differentiator is its honesty discipline; the copy must match it.
- **Fix:** use the launch kit copy — evidence-workflow framing, explicit
  limitations, "controlled beta, invite-only", receipts linked.

## Tier 2 — Failure modes that waste the launch

### 5. Nobody cares (most likely outcome, plan for it)
- Solo founder, no audience: PH top-5 ≈ 1,500 visitors / ~120 signups; HN front page ≈ 200–500+ visitors — and both are lotteries [VF, 2026 practitioner reports].
- GitHub stars ≠ traction; your own verdict says don't count them [VF].
- Precedent: I Paid A Bribe got 169k reports + 15M visits over a decade with institutional backing (Janaagraha) — and measurable bribery reduction still wasn't demonstrated [VF]. Attention ≠ impact.
- **Fix:** define success as: 1 qualified design partner + 1 approved document pack + booked workflow interviews. Everything else is marketing exhaust.

### 6. AWS deadline slips and you ship a broken "production" story
- As of the snapshot: no IaC files, no AWS account bootstrap, no Cognito/RDS/ECS evidence [VF]. The verdict's own hard deadline: no clean reviewed plan by Mon 6 PM → downgrade to private synthetic demo [VF].
- **Fix:** accept the downgrade path early. A crisp local/docker demo + honest "cloud beta opens when receipts exist" beats a half-deployed AWS story. HN respects "here's what doesn't work yet".

### 7. Independent review theater
- You have no second human reviewer; the verdict's stop-condition triggers [VF].
- Having an AI review (this document) is useful but is NOT an independent
  human approval with write access [VF].
- **Fix:** either recruit one trusted engineer for a 2-hour review by Tuesday,
  or publicly label the merge as self-merged solo-maintainer work. Don't fake it.

### 8. Day-2 collapse
- Launch spike → issues/PRs/DMs → solo maintainer exhausted (your no-go list
  includes operator exhaustion) [VF].
- **Fix:** issue templates exist [VF]; add SUPPORT.md + "maintainer capacity"
  note; pre-write responses; schedule sleep; kill switches tested.

## local-stakeholder reaction simulation [SI/WI — informed by IPAB research, RTI-attack data, civic-tech launches]
- **Politicians/officials:** ignore it while synthetic-only. React (legal/administrative pressure) only if a real named case trends. Your controlled scope makes Wednesday safe; the danger begins with the first real dossier [SI].
- **Police:** no reaction at launch; would engage only via complaints filed by aggrieved parties [WI].
- **Journalists/RTI activists/NGOs:** the real early adopters. They will ask: "can I use this for MY case, offline, without exposing my sources?" Local-first + audit chain resonates; cloud-only would not [SI]. They are also the most burned community — several have seen tools die (IPAB plateaued; civic trackers get crushed — buildbetterbharat.com essay, Jun 2026) [VF].
- **Citizens:** sympathetic likes, near-zero usage. Civic evidence is not a consumer habit (our traction assessment scores organic consumer traction 3/10) [VF].
- **Companies/contractors:** silent until named; then legal notices [SI].
- **Engineers (HN/Reddit):** will respect the two-person review gates, audit chain, honest limitations — and will flame any overclaim within minutes [SI].
- **Trolls/partisans:** will try to weaponize it against opponents; your review gates + prohibited-content rules are the defense; expect bad-faith submissions the day real intake opens [SI].

## Kill criteria (pre-agreed, no vote overrides)
1. Any no-go condition in the co-founder verdict fires → downgrade tier, don't argue.
2. 30 days post-launch: <3 design partners willing to test with real (sanitized) packs → narrow or stop (pre-agreed traction gate).
3. Any legal notice about published content → immediate withdrawal + counsel before any further real-case work.
4. Evidence that the tool is being used to harass individuals → pause public instance.

## Weakest assumption in the whole plan [UA]
That an audience of journalists/civil-society users will adopt a workflow tool
built by an unknown solo developer without an institutional trust anchor
(newsroom, university, NGO). No evidence yet either way. Test it with 20
outreach messages before believing any traction story.
