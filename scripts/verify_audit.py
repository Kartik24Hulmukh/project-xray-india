#!/usr/bin/env python3
import argparse,hashlib,json,sqlite3,sys

def verify(path):
 c=sqlite3.connect(path);c.row_factory=sqlite3.Row;previous=''
 try:
  count=0
  for r in c.execute('SELECT * FROM audit_events ORDER BY id'):
   expected=hashlib.sha256('|'.join((previous,r['event_id'],r['actor'],r['action'],r['object_type'],r['object_id'],r['detail'],r['created_at'])).encode()).hexdigest()
   if r['previous_hash']!=previous or r['event_hash']!=expected:raise RuntimeError(f'audit chain broken at id={r["id"]}')
   previous=r['event_hash'];count+=1
  return {'status':'ok','events':count,'head':previous}
 finally:c.close()
def main():
 p=argparse.ArgumentParser();p.add_argument('database');a=p.parse_args()
 try:print(json.dumps(verify(a.database),sort_keys=True));return 0
 except Exception as e:print(json.dumps({'status':'error','error':str(e)}));return 1
if __name__=='__main__':sys.exit(main())
