#!/usr/bin/env python3
"""Static fail-closed policy for GitHub Actions workflows."""
from pathlib import Path
import json,re,sys
ROOT=Path(__file__).resolve().parents[1];WF=ROOT/'.github/workflows'
FULL_SHA=re.compile(r'^[0-9a-f]{40}$')
FORBIDDEN=('eval ','|| true','continue-on-error: true','tofu apply','terraform apply',':latest')
def main():
 errors=[];files=sorted(WF.glob('*.yml'))+sorted(WF.glob('*.yaml'))
 for path in files:
  text=path.read_text();low=text.lower()
  for line_no,line in enumerate(text.splitlines(),1):
   match=re.search(r'\buses:\s*([^\s#]+)',line)
   if match:
    value=match.group(1)
    if '@' not in value or not FULL_SHA.fullmatch(value.rsplit('@',1)[1]):errors.append(f'{path.name}:{line_no}: action not pinned to a full SHA: {value}')
  for token in FORBIDDEN:
   if token in low:errors.append(f'{path.name}: forbidden token: {token}')
  if re.search(r'(?im)^\s*aws_(access_key_id|secret_access_key):\s*[A-Za-z0-9/+]{8,}\s*$', text):
   errors.append(f'{path.name}: literal AWS credential detected')
 if not files:errors.append('no workflows found')
 deploy=(WF/'deploy.yml').read_text() if (WF/'deploy.yml').exists() else ''
 for token in ('image_digest','git_sha','services-stable','imageDigest','id-token: write','environment:'):
  if token not in deploy:errors.append('deploy.yml missing '+token)
 plan=(WF/'infra-plan.yml').read_text() if (WF/'infra-plan.yml').exists() else ''
 if 'pull_request_target' in plan:errors.append('infra plan must not use pull_request_target')
 if 'id-token: write' not in plan:errors.append('infra plan lacks OIDC permission')
 result={'status':'error' if errors else 'ok','workflows':len(files),'errors':errors};print(json.dumps(result,sort_keys=True));return 1 if errors else 0
if __name__=='__main__':raise SystemExit(main())
