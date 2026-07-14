#!/usr/bin/env python3
import argparse,json,os,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.audit import verify

def main():
 p=argparse.ArgumentParser();p.add_argument('database');p.add_argument('--key-env',default='AUDIT_HMAC_KEY');a=p.parse_args();key=os.getenv(a.key_env,'')
 if not key:print(json.dumps({'status':'error','error':f'{a.key_env} is required'}));return 1
 c=sqlite3.connect(a.database);c.row_factory=sqlite3.Row
 try:result=verify(c,key);print(json.dumps({'status':'ok',**result},sort_keys=True));return 0
 except Exception as e:print(json.dumps({'status':'error','error':str(e)}));return 1
 finally:c.close()
if __name__=='__main__':sys.exit(main())
