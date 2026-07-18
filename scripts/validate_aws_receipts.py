#!/usr/bin/env python3
"""Validate the complete same-SHA/same-digest AWS production evidence set."""
from __future__ import annotations
import argparse,datetime,json,re,sys
from pathlib import Path
CATEGORIES=('identity','deployment','storage','database_restore','rollback','alert','network','load')
SHA=re.compile(r'^[0-9a-f]{40}$');DIGEST=re.compile(r'^sha256:[0-9a-f]{64}$');ACCOUNT=re.compile(r'^[0-9]{12}$')
def validate(directory:Path,environment:str):
 errors=[];receipts=[]
 for category in CATEGORIES:
  path=directory/f'{category}.json'
  if not path.exists():errors.append(f'missing {path.name}');continue
  try:value=json.loads(path.read_text())
  except Exception as exc:errors.append(f'{path.name}: invalid JSON');continue
  if not isinstance(value,dict):errors.append(f'{path.name}: receipt must be an object');continue
  allowed={'category','status','environment','account_id','region','git_sha','image_digest','observed_at','operator','evidence'}
  extra=set(value)-allowed
  if extra:errors.append(f'{path.name}: unexpected fields {sorted(extra)}')
  checks=((value.get('category')==category,'category'),(value.get('status')=='passed','status'),(value.get('environment')==environment,'environment'),(value.get('region')=='ap-south-1','region'),(bool(ACCOUNT.fullmatch(str(value.get('account_id','')))),'account_id'),(bool(SHA.fullmatch(str(value.get('git_sha','')))),'git_sha'),(bool(DIGEST.fullmatch(str(value.get('image_digest','')))),'image_digest'),(isinstance(value.get('evidence'),dict) and bool(value.get('evidence')),'evidence'))
  for ok,name in checks:
   if not ok:errors.append(f'{path.name}: invalid {name}')
  try:
   observed=str(value.get('observed_at','')).replace('Z','+00:00');parsed=datetime.datetime.fromisoformat(observed)
   if parsed.tzinfo is None:raise ValueError
  except Exception:errors.append(f'{path.name}: invalid observed_at')
  receipts.append(value)
 if receipts:
  for field in ('account_id','region','git_sha','image_digest','environment'):
   values={item.get(field) for item in receipts}
   if len(values)!=1:errors.append(f'receipts disagree on {field}')
 return {'status':'blocked' if errors else 'passed','environment':environment,'receipt_count':len(receipts),'required_count':len(CATEGORIES),'errors':errors,'git_sha':receipts[0].get('git_sha') if receipts and not errors else None,'image_digest':receipts[0].get('image_digest') if receipts and not errors else None}
def main():
 parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);parser.add_argument('--environment',choices=('staging','production'),required=True);args=parser.parse_args();result=validate(args.directory,args.environment);print(json.dumps(result,sort_keys=True));return 0 if result['status']=='passed' else 1
if __name__=='__main__':raise SystemExit(main())
