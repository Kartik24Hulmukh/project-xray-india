# Synthetic technical preview guide

## Access rules

- Invited evaluators only for any hosted surface.
- Synthetic data only.
- No real names, firms, contracts, or allegations.

## 7-step demo path

1. Open or create a synthetic project.
2. Register a synthetic source.
3. Attach/register a document with SHA-256 and quarantine state.
4. Create a candidate claim with exact anchor.
5. Attempt direct publication and observe rejection.
6. Obtain two distinct reviewer approvals, then publish.
7. Export/verify capsule and run a correction or withdrawal drill.

## Evaluator script

```bash
python3 scripts/external_evaluator.py --base-url http://127.0.0.1:8080 --out artifacts/preview/external-evaluator.json
```

## Success criteria for an evaluator

- Explains candidate vs reviewed vs published
- Finds exact source/anchor for a public statement
- Understands why blocked publication failed
- Completes correction or withdrawal awareness check
- Files at least one friction or safety observation
