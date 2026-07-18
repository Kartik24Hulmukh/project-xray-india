#!/usr/bin/env python3
"""Fail-closed static admission checks for the plan-only AWS stack."""
from pathlib import Path
import json,re,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];IAC=ROOT/'infra/aws-controlled-beta'
REQUIRED=['aws_vpc','10.20.0.0/16','aws_lb_listener','authenticate-cognito','mfa_configuration = "ON"','software_token_mfa_configuration','aws_ecs_task_definition','assign_public_ip = true','aws_db_instance','publicly_accessible = false','manage_master_user_password = true','aws_s3_bucket_public_access_block','BucketOwnerEnforced','aws_s3_bucket_versioning','aws_s3_bucket_object_lock_configuration','aws_wafv2_web_acl','aws_sns_topic','aws_budgets_budget','AssumeRoleWithWebIdentity','repo:${var.github_repository}:pull_request','sha256:[0-9a-f]{64}']
FORBIDDEN=['resource "aws_nat_gateway"','tofu apply','terraform apply','access_key =','secret_key =','0.0.0.0/0:5432']
def balanced(text):
 out=[];quote=False;escape=False
 for ch in text:
  if quote:
   if escape:escape=False
   elif ch=='\\':escape=True
   elif ch=='"':quote=False
   continue
  if ch=='"':quote=True;continue
  if ch in '{}[]()':out.append(ch)
 pairs={'}':'{',']':'[',')':'('};stack=[]
 for ch in out:
  if ch in '{[(':stack.append(ch)
  elif not stack or stack.pop()!=pairs[ch]:return False
 return not stack and not quote
def main():
 files=sorted(IAC.glob('*.tf'));text='\n'.join(p.read_text() for p in files);errors=[]
 if len(files)<8:errors.append('expected split OpenTofu stack files')
 for token in REQUIRED:
  if token not in text:errors.append('missing '+token)
 for token in FORBIDDEN:
  if token in text:errors.append('forbidden '+token)
 if ';' in text:errors.append('semicolon syntax is forbidden')
 if '{{http' in text:errors.append('malformed URL expression')
 if 'aws_security_group.task' in text:errors.append('shared gateway/app task security group is forbidden')
 if 'resource \"aws_iam_role\" \"task\"' in text:errors.append('shared gateway/app task role is forbidden')
 if not balanced(text):errors.append('unbalanced HCL delimiters')
 buckets=re.findall(r'"(intake-quarantine|evidence-private|dossier-restricted|publication-staging)"',text)
 if set(buckets)!={'intake-quarantine','evidence-private','dossier-restricted','publication-staging'}:errors.append('four custody roles are incomplete')
 result={'status':'error' if errors else 'ok','files':len(files),'errors':errors,'tofu_available':bool(shutil.which('tofu'))}
 if not errors and shutil.which('tofu'):
  for cmd in (['tofu','fmt','-check','-recursive'],['tofu','init','-backend=false'],['tofu','validate']):
   run=subprocess.run(cmd,cwd=IAC,text=True,capture_output=True)
   if run.returncode:errors.append(' '.join(cmd)+': '+(run.stderr or run.stdout)[-1000:])
 result['status']='error' if errors else 'ok';result['errors']=errors;print(json.dumps(result,sort_keys=True))
 return 1 if errors else 0
if __name__=='__main__':raise SystemExit(main())
