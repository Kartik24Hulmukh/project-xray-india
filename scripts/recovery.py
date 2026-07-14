#!/usr/bin/env python3
import argparse,json,os,sqlite3,sys,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.manifest import create as create_manifest,verify as verify_manifest,file_sha256
from app.audit import verify as verify_audit
from app.database import IS_POSTGRES,connect,db as db_ctx,integrity_check as db_integrity_check,get_schema_version

def integrity(path,audit_key=None):
 if IS_POSTGRES:
  c=connect()
  try:
   result=db_integrity_check(c)
   from app.audit import verify as va
   audit={'events':0,'head':''}
   if audit_key:
    audit=va(c,audit_key)
   return {'integrity':result,'tables':0,'user_version':get_schema_version(c),'audit_events':audit['events'],'audit_head':audit['head']}
  finally:c.close()
 c=sqlite3.connect(path);c.row_factory=sqlite3.Row
 try:
  result=c.execute('PRAGMA integrity_check').fetchone()[0];tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")};required={'projects','sources','documents','claims','claim_reviews','audit_events'}
  if result!='ok' or not required.issubset(tables):raise RuntimeError(f'invalid database: integrity={result}, missing={sorted(required-tables)}')
  audit={'events':0,'head':''}
  if 'audit_checkpoints' in tables:
   if not audit_key:raise RuntimeError('audit key required for checkpoint verification')
   audit=verify_audit(c,audit_key)
  return {'integrity':result,'tables':len(tables),'user_version':c.execute('PRAGMA user_version').fetchone()[0],'audit_events':audit['events'],'audit_head':audit['head']}
 finally:c.close()

def backup(source,destination,key=None,audit_key=None):
 key=key or os.getenv('BACKUP_HMAC_KEY','development-backup-key-not-for-production');audit_key=audit_key or os.getenv('AUDIT_HMAC_KEY','development-audit-key-not-for-production');source=Path(source);destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
 if not source.is_file():raise FileNotFoundError(source)
 if IS_POSTGRES:
  # PostgreSQL backup uses pg_dump
  tmp=destination.with_suffix(destination.suffix+'.creating')
  if tmp.exists():tmp.unlink()
  env={**os.environ,'PGPASSWORD':os.getenv('DATABASE_URL','').split('@')[0].split('//')[-1].split(':')[1] if '://' in os.getenv('DATABASE_URL','') and ':' in os.getenv('DATABASE_URL','').split('@')[0].split('//')[-1] else ''}
  result=subprocess.run(['pg_dump',os.getenv('DATABASE_URL',''),'--format=custom','--file='+str(tmp)],capture_output=True,env=env)
  if result.returncode:raise RuntimeError(f'pg_dump failed: {result.stderr.decode()}')
  checks=integrity(None,audit_key);os.chmod(tmp,0o600);tmp.replace(destination)
 else:
  tmp=destination.with_suffix(destination.suffix+'.creating')
  if tmp.exists():tmp.unlink()
  with sqlite3.connect(source) as src,sqlite3.connect(tmp) as dst:src.backup(dst)
  checks=integrity(tmp,audit_key);os.chmod(tmp,0o600);tmp.replace(destination)
 manifest=destination.with_suffix(destination.suffix+'.manifest.json');create_manifest(manifest,destination,key,checks)
 return {'operation':'backup','path':str(destination),'manifest':str(manifest),'sha256':file_sha256(destination),**checks}

def restore(source,destination,force=False,key=None,audit_key=None,manifest=None):
 key=key or os.getenv('BACKUP_HMAC_KEY','development-backup-key-not-for-production');audit_key=audit_key or os.getenv('AUDIT_HMAC_KEY','development-audit-key-not-for-production');source=Path(source);destination=Path(destination);manifest=Path(manifest) if manifest else source.with_suffix(source.suffix+'.manifest.json')
 verify_manifest(manifest,source,key)
 if IS_POSTGRES:
  # PostgreSQL restore uses pg_restore
  if destination.exists() and not force:raise FileExistsError(f'{destination} exists; pass --force')
  destination.parent.mkdir(parents=True,exist_ok=True)
  result=subprocess.run(['pg_restore','--dbname='+os.getenv('DATABASE_URL',''),'--clean','--if-exists',str(source)],capture_output=True)
  if result.returncode:raise RuntimeError(f'pg_restore failed: {result.stderr.decode()}')
  restored=integrity(None,audit_key)
  source_checks=integrity(None,audit_key)
 else:
  source_checks=integrity(source,audit_key)
  if destination.exists() and not force:raise FileExistsError(f'{destination} exists; pass --force')
  destination.parent.mkdir(parents=True,exist_ok=True);tmp=destination.with_suffix(destination.suffix+'.restoring')
  if tmp.exists():tmp.unlink()
  with sqlite3.connect(source) as src,sqlite3.connect(tmp) as dst:src.backup(dst)
  restored=integrity(tmp,audit_key)
  if restored!=source_checks:raise RuntimeError('restored database verification differs from source')
  os.chmod(tmp,0o600);tmp.replace(destination)
 return {'operation':'restore','path':str(destination),'sha256':file_sha256(destination) if not IS_POSTGRES else 'pg-restore',**restored}

def main():
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
 for name in ('backup','restore'):
  x=sub.add_parser(name);x.add_argument('source');x.add_argument('destination');x.add_argument('--force',action='store_true');x.add_argument('--manifest')
 a=p.parse_args()
 try:result=backup(a.source,a.destination) if a.command=='backup' else restore(a.source,a.destination,a.force,manifest=a.manifest)
 except Exception as e:print(json.dumps({'status':'error','error':str(e)}));return 1
 print(json.dumps({'status':'ok',**result},sort_keys=True));return 0
if __name__=='__main__':sys.exit(main())
