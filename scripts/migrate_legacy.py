#!/usr/bin/env python3
import argparse,hashlib,json,shutil,sqlite3,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SCHEMA=(ROOT/'db/schema.sql').read_text()
def uid(p):return p+'_'+uuid.uuid4().hex[:16]
def migrate(path):
 path=Path(path);backup=path.with_suffix(path.suffix+'.pre-v2.bak');tmp=path.with_suffix(path.suffix+'.v2.tmp')
 if not path.is_file():raise FileNotFoundError(path)
 old=sqlite3.connect(path);old.row_factory=sqlite3.Row
 cols={r['name'] for r in old.execute('PRAGMA table_info(sources)')}
 if 'created_at' in cols:return {'status':'already_v2','database':str(path)}
 if backup.exists() or tmp.exists():raise FileExistsError('migration artifacts already exist; inspect them before retrying')
 shutil.copy2(path,backup);new=sqlite3.connect(tmp);new.row_factory=sqlite3.Row;new.executescript(SCHEMA)
 try:
  for r in old.execute('SELECT * FROM projects'):new.execute('INSERT INTO projects VALUES(?,?,?,?,?,?,?,?,?)',tuple(r))
  source_by_key={}
  for r in old.execute('SELECT * FROM claims'):
   url=r['source_url'] if str(r['source_url']).startswith(('http://','https://')) else f"https://invalid.local/legacy/{r['id']}"
   key=(r['project_id'],url);sid=source_by_key.get(key)
   if not sid:
    sid=uid('src');source_by_key[key]=sid;created=r['created_at'];new.execute('INSERT INTO sources VALUES(?,?,?,?,?,?,?,?,?,?)',(sid,r['project_id'],r['publisher'] or 'Legacy import',url,'legacy_import',created,hashlib.sha256(url.encode()).hexdigest(),r['passage'],r['page_ref'],created))
   new.execute('INSERT INTO claims VALUES(?,?,?,?,?,?,?,?,?,?,?)',(r['id'],r['project_id'],sid,r['claim_type'],'candidate',r['text'],r['passage'],r['page_ref'],'legacy-migration',r['created_at'],r['created_at']))
  for r in old.execute('SELECT * FROM gaps'):new.execute('INSERT INTO gaps VALUES(?,?,?,?,?,?,?)',tuple(r))
  for r in old.execute('SELECT * FROM responses'):new.execute('INSERT INTO responses VALUES(?,?,?,?,?,?)',(r['id'],r['project_id'],r['responder'],r['text'],None,r['created_at']))
  new.commit();check=new.execute('PRAGMA integrity_check').fetchone()[0]
  if check!='ok':raise RuntimeError(check)
 finally:old.close();new.close()
 tmp.replace(path);return {'status':'migrated','database':str(path),'backup':str(backup),'claims_demoted_to_candidate':True}
def main():
 p=argparse.ArgumentParser(description='Migrate v1 SQLite data to the v2 evidence-review schema');p.add_argument('database');a=p.parse_args()
 try:print(json.dumps(migrate(a.database),sort_keys=True));return 0
 except Exception as e:print(json.dumps({'status':'error','error':str(e)}));return 1
if __name__=='__main__':sys.exit(main())
