# Naming Decision — Tracepaper

## Requirements
- No country or region name anywhere in the brand, repo, or public copy
- No collision with live products, major cloud services, or registered software marks
- Descriptive of the product: claims traced to an anchored paper trail

## Candidates evaluated (2026-07-20 web check)
| Candidate | Verdict | Evidence |
| --- | --- | --- |
| Anchoryx | REJECT | Live product at anchoryx.com (trading discipline software) |
| project-xray / X-Ray | REJECT | AWS X-Ray is a major AWS tracing service; X-RAY US trademark (ser. 75925124) exists for software |
| Provara | REJECT | provara.net (client verification) + two active GitHub projects |
| Verifold | REJECT | verifold.net (hosting/digital services company) |
| **Tracepaper** | **SELECTED** | No exact software collision found in two search passes; nearest matches are unrelated image-tracing drawing apps |
| Anchorem | Backup | No collision found |

Note: GetProofAnchor (getproofanchor.com) is an adjacent web-evidence-capture product —
a competitor to monitor, not a name conflict.

## Before first public use (15-minute human check)
- [ ] GitHub org/repo `tracepaper` availability or acceptable variant (e.g. `tracepaper-app`)
- [ ] Domain (tracepaper.dev / .io / .org)
- [ ] npm + PyPI package names if publishing packages
- [ ] Trademark database search in the operator's jurisdiction(s)
- [ ] Social handles used in the launch kit

## Rename kit (execute AFTER PR #13 merge, as its own small PR)
1. Rename the GitHub repository (old URLs redirect automatically).
2. In-repo replace, case-aware: `project-xray-india` → `tracepaper`, `Project X-Ray India`/`Project X-Ray`/`X-Ray` → `Tracepaper`, `xray` → `tracepaper` (also update badge URLs, image names, tfvars prefixes, Cognito domain prefix, bucket-name prefixes).
3. Remove remaining country references from README and public docs; compliance obligations move to the private operator note, they are NOT removed by renaming.
4. Update CI variables (`STAGING_URL`, image names) and any registered OIDC `sub` claims that embed the repo name.
5. Run the full test suite + release checker; version-consistency tests must stay green.
6. Update release notes with a rename entry; do not rewrite git history.
