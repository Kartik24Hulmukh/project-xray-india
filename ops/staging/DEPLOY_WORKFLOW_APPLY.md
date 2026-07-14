# Operator-applied deploy workflow (workflow scope required)

GitHub OAuth/token used by this agent **cannot** modify `.github/workflows/*`
without the `workflow` scope (`CreateCommitOnBranch` denied).

## Apply after merge of PR #10 security code

```bash
cp ops/staging/deploy.yml.proposed .github/workflows/deploy.yml
git add .github/workflows/deploy.yml
git commit -m "fix(deploy): fail closed on configured health checks"
git push
```

Or paste the contents of `deploy.yml.proposed` over `.github/workflows/deploy.yml`
using a token/app with `workflow` permission.

## Semantics encoded in proposed file

- Unconfigured staging (`STAGING_URL` empty) → `deployment_status=deployment_skipped` (not success)
- Configured staging → mandatory health + smoke; failure fails job and triggers rollback step
- Production health never uses continue-on-error
- Receipt distinguishes skipped / succeeded / attempted_failed / rollback

