# Operator onboarding checklist (design partner pilot)

1. Receive staging URL and role (admin / reviewer / scanner) from pilot lead.
2. Complete IdP login with MFA (no shared passwords).
3. Create a **synthetic** project only (mark synthetic=true).
4. Add a non-sensitive public-source document (or synthetic fixture).
5. Wait for scanner clearance of quarantine.
6. Anchor one claim with passage + source SHA.
7. Request two independent reviewers.
8. Publish claim → publish dossier only after dual approval.
9. Export capsule and run `scripts/verify_capsule.py` offline.
10. Record times on the pilot scorecard (no document text in metrics).
