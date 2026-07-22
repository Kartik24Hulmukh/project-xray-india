# Launch FAQ — pre-written answers (use founder voice, adapt, never paste robotically)

**"AI in an evidence workflow? It will hallucinate."**
Agreed — that's the design constraint, not an afterthought. The AI layer only
proposes candidates. Nothing is publishable unless a human reviewer anchors the
claim to an exact source span, and a second reviewer approves. Unsupported
claims are rejected by default, and the audit chain records every decision.
The benchmark fixture in the repo scores exactly this: anchor accuracy and
unsupported-claim rejection.

**"Why not just use Aleph or Datashare?"**
Different job. Aleph (OCCRP) is an investigative data archive — search across
government records and leaks, access-gated for journalists. Datashare (ICIJ)
is document search/analysis over your own files, local-first, open source.
Both answer "what's in these documents?" This tool answers a later question:
"which specific claims can we defend, anchored to which exact source, and who
approved publishing them?" It's the discipline layer between research and
publication — use it alongside those tools, not instead of them.

**"Where's the real data? This is all synthetic."**
Deliberate. Publishing real allegations without editorial and legal gates is
how projects like this hurt people and die. The synthetic fixture demonstrates
the methodology; real workflows start with design partners under sanitized
conditions. If that makes it less viral, fine — wrong kind of viral kills this
category of tool.

**"Does it protect sources / whistleblowers?"**
No, and it doesn't claim to. It is not an anonymous submission system. Source
protection requires operational security this tool does not provide. What it
does: tamper-evident audit of what entered review and what got published.

**"Who's behind this? What happens when you get bored?"**
Solo maintainer right now, honestly labeled. The release maturity model in the
repo states exactly which verification labels each release holds. Independent
reviewers are invited — the two-reviewer gate is real and needs more humans.

**"What's the license / can I self-host?"**
Yes — self-hosting locally is the primary supported mode today; the cloud
deployment is for the hosted controlled beta. License is in the repo root.

**"The demo is down."**
Static GIF in the README shows the full flow. The read-only demo is cached
behind a CDN; if it's struggling, the repo + GIF are the demo.
