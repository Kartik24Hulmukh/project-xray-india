import os,tempfile,threading,json,urllib.request,urllib.error,unittest,sys,sqlite3,hashlib
from pathlib import Path
TMP=tempfile.TemporaryDirectory();os.environ.update({'DB_PATH':TMP.name+'/test.db','ADMIN_TOKEN':'test-admin-secret-long-enough','REVIEWER_TOKENS':'reviewer-a:review-token-a,reviewer-b:review-token-b','PORT':'18081','APP_ENV':'test'})
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import server

class TestCore(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  server.init();cls.http=server.ThreadingHTTPServer(('127.0.0.1',18081),server.H);threading.Thread(target=cls.http.serve_forever,daemon=True).start()
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();TMP.cleanup()
 def req(self,path,method='GET',data=None,token=None,ctype='application/json'):
  h={'Content-Type':ctype}
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
 def test_health_and_ready(self):self.assertEqual(self.req('/health')[0],200);self.assertEqual(self.req('/ready')[0],200)
if __name__=='__main__':unittest.main()
