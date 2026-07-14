# Privacy-safe activation events

Emit only counters / durations, never content:

- `pilot.project_created` {synthetic: bool}
- `pilot.claim_anchored` {claim_type}
- `pilot.review_submitted` {decision}
- `pilot.claim_published`
- `pilot.dossier_published`
- `pilot.capsule_exported`
- `pilot.capsule_verified_offline` {ok: bool}
- `pilot.session_returned_7d`

Forbidden: document bytes, passage text, Authorization headers, subject emails in analytics sinks.
