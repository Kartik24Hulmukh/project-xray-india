import os,tempfile,threading,json,urllib.request,urllib.error,unittest,sys,sqlite3,hashlib,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
TMP=tempfile.TemporaryDirectory();os.environ.update({'DB_PATH':TMP.name+'/test.db','ADMIN_TOKEN':'test-admin-secret-long-enough','REVIEWER_TOKENS':'reviewer-a:review-token-a,reviewer-b:review-token-b','PORT':'18081','APP_ENV':'test','TOKEN_PEPPER':'test-token-pepper-12345678901234567890','AUDIT_HMAC_KEY':'test-audit-key-123456789012345678901','BACKUP_HMAC_KEY':'test-backup-key-12345678901234567890','SCANNER_TOKENS':'scanner-a:scan-token-a','WRITE_RATE_LIMIT':'1000'})
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import server

class TestCore(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  server.init();cls.http=server.ThreadingHTTPServer(('127.0.0.1',18081),server.H);threading.Thread(target=cls.http.serve_forever,daemon=True).start()
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();TMP.cleanup()
 def req(self,path,method='GET',data=None,token=None,ctype='application/json',headers=None):
  h={'Content-Type':ctype,**(headers or {})}
  if token:h['Authorization']='Bearer '+token
  q=urllib.request.Request('http://127.0.0.1:18081'+path,data=json.dumps(data).encode() if data is not None else None,headers=h,method=method)
  try:
   with urllib.request.urlopen(q) as r:return r.status,json.loads(r.read()) if 'json' in r.headers.get('Content-Type','') else r.read().decode(),dict(r.headers)
  except urllib.error.HTTPError as e:return e.code,json.loads(e.read()),dict(e.headers)
 def create_project_source_claim(self):
  s,p,_=self.req('/api/projects','POST',{'title':'Synthetic bridge','authority':'Example Authority','synthetic':True},'test-admin-secret-long-enough');self.assertEqual(s,201);pid=p['id']
  s,src,_=self.req(f'/api/projects/{pid}/sources','POST',{'publisher':'Synthetic Publisher','url':'https://example.invalid/source','source_class':'official','retrieved_at':'2026-07-14T00:00:00Z','sha256':'a'*64,'passage':'Synthetic passage'},'test-admin-secret-long-enough');self.assertEqual(s,201)
  s,c,_=self.req(f'/api/projects/{pid}/claims','POST',{'claim_type':'official_claim','text':'Synthetic claim','source_id':src['id'],'passage':'Synthetic passage'},'test-admin-secret-long-enough');self.assertEqual(s,201)
  return pid,src['id'],c['id']
 def test_complete_publication_path(self):
  pid,src,cid=self.create_project_source_claim()
  self.assertEqual(self.req(f'/api/projects/{pid}/claims/{cid}/reviews','POST',{'decision':'approve'},'review-token-a')[1]['approvals'],1)
  reviewed=self.req(f'/api/projects/{pid}/claims/{cid}/reviews','POST',{'decision':'approve'},'review-token-b')[1];self.assertEqual(reviewed['publication_state'],'reviewed')
  self.assertEqual(self.req(f'/api/projects/{pid}/claims/{cid}/publish','POST',{},'test-admin-secret-long-enough')[0],200)
  self.req(f'/api/projects/{pid}/gaps','POST',{'document_name':'Synthetic test report','search_scope':'Synthetic fixture only'},'test-admin-secret-long-enough')
  self.req(f'/api/projects/{pid}/responses','POST',{'responder':'Example Authority','text':'Synthetic response','source_id':src},'test-admin-secret-long-enough')
  self.assertEqual(self.req(f'/api/projects/{pid}/publish','POST',{},'test-admin-secret-long-enough')[0],200)
  status,b,_=self.req('/api/projects/'+pid);self.assertEqual(status,200);self.assertEqual(len(b['claims']),1);self.assertEqual(len(b['gaps']),1)
  self.assertIn('SHA-256',self.req('/api/projects/'+pid+'/report')[1]);self.assertIn('not legal advice',self.req('/api/projects/'+pid+'/rti')[1])
  events=self.req('/api/projects/'+pid+'/audit',token='test-admin-secret-long-enough')[1]['events'];self.assertGreaterEqual(len(events),6)
 def test_public_api_hides_research_and_candidate(self):
  pid,_,_=self.create_project_source_claim();self.assertEqual(self.req('/api/projects/'+pid)[0],404);self.assertFalse(any(x['id']==pid for x in self.req('/api/projects')[1]['projects']))
  self.assertEqual(self.req('/api/projects/'+pid+'?include_private=1',token='review-token-a')[0],200)
 def test_two_person_gate_and_role_separation(self):
  pid,_,cid=self.create_project_source_claim()
  self.assertEqual(self.req(f'/api/projects/{pid}/claims/{cid}/publish','POST',{},'test-admin-secret-long-enough')[0],409)
  self.assertEqual(self.req(f'/api/projects/{pid}/claims/{cid}/reviews','POST',{'decision':'approve'},'test-admin-secret-long-enough')[0],403)
  self.req(f'/api/projects/{pid}/claims/{cid}/reviews','POST',{'decision':'approve'},'review-token-a')
  self.assertEqual(self.req(f'/api/projects/{pid}/claims/{cid}/reviews','POST',{'decision':'approve'},'review-token-a')[0],409)
 def test_validation_security_headers_and_auth(self):
  self.assertEqual(self.req('/api/projects','POST',{'title':'x'})[0],401)
  self.assertEqual(self.req('/api/projects','POST',{'title':'x'},'test-admin-secret-long-enough','text/plain')[0],400)
  status,_,headers=self.req('/health');self.assertEqual(status,200);self.assertEqual(headers['X-Frame-Options'],'DENY');self.assertTrue(headers['X-Request-ID'].startswith('req_'))
 def test_audit_immutability_and_chain(self):
  pid,_,_=self.create_project_source_claim()
  c=sqlite3.connect(server.DB);row=c.execute('SELECT previous_hash,event_hash FROM audit_events ORDER BY id DESC LIMIT 1').fetchone();self.assertEqual(len(row[1]),64)
  with self.assertRaises(sqlite3.IntegrityError):c.execute("DELETE FROM audit_events")
  c.close()
 def test_document_quarantine_and_deduplication(self):
  pid,src,_=self.create_project_source_claim();doc={'source_id':src,'filename':'fixture.pdf','media_type':'application/pdf','size_bytes':128,'sha256':'b'*64}
  s,r,_=self.req(f'/api/projects/{pid}/documents','POST',doc,'test-admin-secret-long-enough');self.assertEqual(s,201);self.assertEqual(r['storage_state'],'quarantined')
  self.assertEqual(self.req(f'/api/projects/{pid}/documents','POST',doc,'test-admin-secret-long-enough')[0],409)
 def test_correction_requires_fresh_two_person_review(self):
  pid,_,cid=self.create_project_source_claim();self.req(f'/api/projects/{pid}/claims/{cid}/reviews','POST',{'decision':'approve'},'review-token-a');self.req(f'/api/projects/{pid}/claims/{cid}/reviews','POST',{'decision':'approve'},'review-token-b');self.req(f'/api/projects/{pid}/claims/{cid}/publish','POST',{},'test-admin-secret-long-enough')
  corrected=self.req(f'/api/projects/{pid}/claims/{cid}/correct','POST',{'text':'Corrected synthetic claim','reason':'Synthetic correction fixture'},'test-admin-secret-long-enough')[1];self.assertEqual(corrected['publication_state'],'candidate')
  self.assertEqual(self.req(f'/api/projects/{pid}/claims/{cid}/publish','POST',{},'test-admin-secret-long-enough')[0],409)
  self.req(f'/api/projects/{pid}/claims/{cid}/reviews','POST',{'decision':'approve'},'review-token-a');self.req(f'/api/projects/{pid}/claims/{cid}/reviews','POST',{'decision':'approve'},'review-token-b')
  self.assertEqual(self.req(f'/api/projects/{pid}/claims/{cid}/publish','POST',{},'test-admin-secret-long-enough')[1]['publication_state'],'corrected')
 def test_quarantine_fails_closed_until_scanner_clears(self):
  pid,src,cid=self.create_project_source_claim();doc={'source_id':src,'filename':'evidence.pdf','media_type':'application/pdf','size_bytes':128,'sha256':'d'*64}
  did=self.req(f'/api/projects/{pid}/documents','POST',doc,'test-admin-secret-long-enough')[1]['id'];self.req(f'/api/projects/{pid}/claims/{cid}/reviews','POST',{'decision':'approve'},'review-token-a');self.req(f'/api/projects/{pid}/claims/{cid}/reviews','POST',{'decision':'approve'},'review-token-b')
  self.assertEqual(self.req(f'/api/projects/{pid}/claims/{cid}/publish','POST',{},'test-admin-secret-long-enough')[0],409)
  self.assertEqual(self.req(f'/api/projects/{pid}/documents/{did}/scan','POST',{'result':'clean'},'scan-token-a')[0],200)
  self.assertEqual(self.req(f'/api/projects/{pid}/claims/{cid}/publish','POST',{},'test-admin-secret-long-enough')[0],200)
 def test_idempotency_replay_and_conflict(self):
  headers={'Idempotency-Key':'create-project-once'};body={'title':'Idempotent fixture','synthetic':True}
  first=self.req('/api/projects','POST',body,'test-admin-secret-long-enough',headers=headers);second=self.req('/api/projects','POST',body,'test-admin-secret-long-enough',headers=headers)
  self.assertEqual(first[0],201);self.assertEqual(second[0],201);self.assertEqual(first[1]['id'],second[1]['id'])
  self.assertEqual(self.req('/api/projects','POST',{'title':'Different'},'test-admin-secret-long-enough',headers=headers)[0],409)
 def test_token_expiry_revocation_and_rotation(self):
  created=self.req('/api/auth/tokens','POST',{'principal':'temporary-reviewer','role':'reviewer','ttl_seconds':600},'test-admin-secret-long-enough')[1];old_token=created['token'];old_id=created['id']
  self.assertEqual(server.auth({'Authorization':'Bearer '+old_token}),('reviewer','temporary-reviewer'))
  rotated=self.req('/api/auth/tokens','POST',{'principal':'temporary-reviewer','role':'reviewer','ttl_seconds':600,'rotated_from':old_id},'test-admin-secret-long-enough')[1]
  self.assertEqual(server.auth({'Authorization':'Bearer '+old_token}),(None,None));self.assertEqual(server.auth({'Authorization':'Bearer '+rotated['token']}),('reviewer','temporary-reviewer'))
  with server.db(True) as c:c.execute("UPDATE auth_tokens SET expires_at='2000-01-01T00:00:00+00:00' WHERE id=?",(rotated['id'],))
  self.assertEqual(server.auth({'Authorization':'Bearer '+rotated['token']}),(None,None))
 def test_explicit_token_revocation_endpoint(self):
  created=self.req('/api/auth/tokens','POST',{'principal':'temp-scanner','role':'scanner','ttl_seconds':600},'test-admin-secret-long-enough')[1];tok=created['token'];tid=created['id']
  self.assertEqual(server.auth({'Authorization':'Bearer '+tok}),('scanner','temp-scanner'))
  s,r,_=self.req(f'/api/auth/tokens/{tid}/revoke','POST',{},'test-admin-secret-long-enough')
  self.assertEqual(s,200);self.assertTrue(r['revoked'])
  self.assertEqual(server.auth({'Authorization':'Bearer '+tok}),(None,None))
  s2,r2,_=self.req(f'/api/auth/tokens/{tid}/revoke','POST',{},'test-admin-secret-long-enough')
  self.assertEqual(s2,404)
 def test_concurrent_publication_is_single_transition(self):
  pid,_,cid=self.create_project_source_claim();self.req(f'/api/projects/{pid}/claims/{cid}/reviews','POST',{'decision':'approve'},'review-token-a');self.req(f'/api/projects/{pid}/claims/{cid}/reviews','POST',{'decision':'approve'},'review-token-b')
  with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(lambda _:self.req(f'/api/projects/{pid}/claims/{cid}/publish','POST',{},'test-admin-secret-long-enough')[0],range(8)))
  self.assertTrue(all(x==200 for x in results))
  with server.db() as c:self.assertEqual(c.execute("SELECT COUNT(*) n FROM audit_events WHERE action='publish' AND object_type='claim' AND object_id=?",(cid,)).fetchone()['n'],1)
 def test_concurrent_correction_allows_one_version_advance(self):
  pid,_,cid=self.create_project_source_claim();self.req(f'/api/projects/{pid}/claims/{cid}/reviews','POST',{'decision':'approve'},'review-token-a');self.req(f'/api/projects/{pid}/claims/{cid}/reviews','POST',{'decision':'approve'},'review-token-b');self.req(f'/api/projects/{pid}/claims/{cid}/publish','POST',{},'test-admin-secret-long-enough')
  bodies=[{'text':f'Correction {i}','reason':'concurrency fixture'} for i in range(6)]
  with ThreadPoolExecutor(max_workers=6) as pool:codes=list(pool.map(lambda b:self.req(f'/api/projects/{pid}/claims/{cid}/correct','POST',b,'test-admin-secret-long-enough')[0],bodies))
  self.assertEqual(codes.count(200),1);self.assertEqual(codes.count(409),5)
  with server.db() as c:self.assertEqual(c.execute('SELECT version FROM claims WHERE id=?',(cid,)).fetchone()['version'],2)
 def test_external_audit_checkpoint_detects_rehashed_fork(self):
  self.create_project_source_claim()
  copy=tempfile.NamedTemporaryFile(suffix='.db',delete=False);copy.close()
  with server.db() as src,sqlite3.connect(copy.name) as dst:src.backup(dst)
  c=sqlite3.connect(copy.name);c.execute('DROP TRIGGER checkpoint_no_update');c.execute("UPDATE audit_checkpoints SET signature=? WHERE id=(SELECT max(id) FROM audit_checkpoints)",('0'*64,));c.commit();c.close()
  from app.audit import verify
  bad=server.connect(copy.name)
  with self.assertRaises(RuntimeError):verify(bad,server.AUDIT_KEY)
  bad.close();os.unlink(copy.name)
 def test_oidc_proxy_requires_mfa_freshness_and_signature(self):
  from app.security import proxy_signature,verify_proxy
  stamp=str(int(time.time()));secret='proxy-secret-1234567890123456789012';headers={'X-Auth-Subject':'reviewer@example.org','X-Auth-Roles':'reviewer','X-Auth-MFA':'true','X-Auth-Timestamp':stamp};headers['X-Auth-Signature']=proxy_signature(headers['X-Auth-Subject'],headers['X-Auth-Roles'],headers['X-Auth-MFA'],stamp,secret)
  self.assertEqual(verify_proxy(headers,secret),('reviewer','reviewer@example.org'));headers['X-Auth-MFA']='false';self.assertIsNone(verify_proxy(headers,secret))
 def test_health_and_ready(self):self.assertEqual(self.req('/health')[0],200);self.assertEqual(self.req('/ready')[0],200)
if __name__=='__main__':unittest.main()
