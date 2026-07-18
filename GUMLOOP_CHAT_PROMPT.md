# Gumloop chat prompt

Integrate the attached Project X-Ray India v0.4.4 controlled-preview release-candidate handoff into:

`https://github.com/Kartik24Hulmukh/project-xray-india.git`

Follow `GUMLOOP_SYSTEM_PROMPT.md` exactly.

## Inputs

- Full source ZIP and `.sha256`
- Overlay ZIP and `.sha256`
- Git bundle and `.sha256`
- Handoff ZIP and `.sha256`
- `HANDOFF_MANIFEST.json`

## Required result

1. Verify all supplied checksums.
2. Clone the current remote and record `origin/main` SHA.
3. Create `gumloop/v0.4.4-controlled-preview-rc` from current `origin/main`.
4. Compare the source/overlay against current main. If current main diverges from the documented base or a deletion conflicts with remote changes, stop and provide a conflict report rather than overwriting.
5. Import only reviewed source changes; never copy `.git`, state, plans, secrets, private evidence or generated credentials.
6. Run the complete verification matrix listed in the system prompt.
7. Confirm the release remains synthetic/controlled-preview only and that public uploads and real-case publication remain blocked.
8. Push the branch and open a PR. Do not merge or force-push.
9. In the PR include:
   - original remote main SHA;
   - resulting branch SHA;
   - all package SHA-256 values;
   - exact test command and pass/skip counts;
   - scanner results;
   - OpenTofu plan-only status;
   - unresolved AWS/human gates;
   - rollback instructions.
10. Return the branch URL, PR URL and all evidence. If any gate fails, do not push a misleading success state.

Do not run AWS deployment or infrastructure mutation. After the PR is reviewed and merged by a human, deployment proceeds separately through the protected staging workflow and eight AWS target receipts.
