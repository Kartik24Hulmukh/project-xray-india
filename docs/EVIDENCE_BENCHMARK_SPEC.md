# Evidence Dossier Benchmark — Specification

Status: specification only; the fixture set is not yet built.

Synthetic public fixture:
- 20 documents; 25 candidate claims; 10 exact source anchors
- 5 planted contradictions; 5 missing-record gaps; 2 corrections; 1 withdrawal
- Expected machine-readable output committed beside the fixture

Scored metrics:
- Anchor accuracy (claims linked to the correct exact source span)
- Missing-evidence detection rate
- Unsupported-claim rejection rate
- Reviewer reconstruction time vs. baseline

Rules: fixtures must be fully synthetic; no real people, entities, or documents.
Contributors run the tool against the fixture and publish comparable scores.
