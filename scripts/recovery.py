#!/usr/bin/env python3
import argparse,hashlib,json,shutil,sqlite3,sys
from pathlib import Path

def integrity(path):
 c=sqlite3.connect(path)
 try:
  result=c.execute('PRAGMA integrity_check').fetchone()[0]
  tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
  required={'projects','sources','documents','claims','claim_reviews','audit_events'}
  if result!='ok' or not required.issubset(tables):raise RuntimeError(f'invalid database: integrity={result}, missing={sorted(required-tables)}')
  return {'integrity':result,'tables':len(tables)}
 finally:c.close()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def backup(source,destination):
 source=Path(source);destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
 if not source.is_file():raise FileNotFoundError(source)
 with sqlite3.connect(source) as src,sqlite3.connect(destination) as dst:src.backup(dst)
 result=integrity(destination);result.update({'operation':'backup','path':str(destination),'sha256':sha(destination)});return result
def restore(source,destination,force=False):
 source=Path(source);destination=Path(destination);integrity(source)
 if destination.exists() and not force:raise FileExistsError(f'{destination} exists; pass --force')
 destination.parent.mkdir(parents=True,exist_ok=True);tmp=destination.with_suffix(destination.suffix+'.restoring');shutil.copy2(source,tmp);integrity(tmp);tmp.replace(destination)
 result=integrity(destination);result.update({'operation':'restore','path':str(destination),'sha256':sha(destination)});return result
def main():
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
 for name in ('backup','restore'):
  x=sub.add_parser(name);x.add_argument('source');x.add_argument('destination');x.add_argument('--force',action='store_true')
 a=p.parse_args()
 try:result=backup(a.source,a.destination) if a.command=='backup' else restore(a.source,a.destination,a.force)
 except Exception as e:print(json.dumps({'status':'error','error':str(e)}));return 1
 print(json.dumps({'status':'ok',**result},sort_keys=True));return 0
if __name__=='__main__':sys.exit(main())
