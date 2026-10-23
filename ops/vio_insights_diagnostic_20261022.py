"""One explicitly authorized read-only VIO diagnostic, capped at 20 requests."""
import json
from pathlib import Path
import deploy_tonight_content as night

OUT = night.u.ROOT / 'docs/vio-insights-live-20261022'
CODE = r'''
import os,json,psycopg
from psycopg.rows import dict_row
from cryptography.fernet import Fernet
from kdh.meta import Meta
from kdh.core import load_config
from kdh.meta_reporting import MetaReportingReader
from kdh.meta_content_insights import project
from kdh.meta_diagnostics import MetaRequestError

class ReadOnlyStore:
 def one(self,sql,params=()):
  with psycopg.connect(os.environ['DATABASE_URL'],options='-c default_transaction_read_only=on',row_factory=dict_row) as db:
   return db.execute(sql.replace('?', '%s'),params).fetchone()

m=Meta.__new__(Meta)
m.config=load_config();m.client_id=m.config['META_CLIENT_ID']
assert m.client_id=='client_meta_sandbox' and m.config['JOB_MODE']=='request'
m.secret_name='meta:'+m.client_id;m.store=ReadOnlyStore()
m.cipher=Fernet(m.config['ENCRYPTION_KEY'].encode())
i=m.info();assert i['connected'] and i['insights_permission']
page='2188688654687066'
asset=m.store.one("SELECT a.id,a.enabled,a.connection_id,c.status,c.external_account_id FROM source_assets a JOIN connections c ON c.id=a.connection_id WHERE a.client_id=? AND a.provider='meta' AND a.external_id=? AND a.asset_type='facebook_page'",(m.client_id,page))
assert asset and asset['status']=='connected' and asset['external_account_id']==i['account_id']
snap=m.store.one("SELECT payload FROM source_snapshots WHERE client_id=? AND asset_id=? AND source_key='facebook_content' AND requested_start='2026-09-21' AND requested_end='2026-10-18' ORDER BY created_at DESC LIMIT 1",(m.client_id,asset['id']))
entries=json.loads(snap['payload'])['entries']
posts=[p['post_id'] for p in entries if '2026-10-15'<=p['date']<='2026-10-17'][:3]
assert len(posts)==3
allowed={'me/accounts',page+'/insights',*[p+'/insights' for p in posts]}
calls=[];original=m.call
def limited_call(method,path,*,token=None,params=None):
 assert method=='GET' and path in allowed and len(calls)<20
 entry={'path':path,'metric':(params or {}).get('metric')};calls.append(entry)
 try:
  value=original(method,path,token=token,params=params)
  if path.endswith('/insights'):
   entry['response_shape']=[{'name':r.get('name'),'period':r.get('period'),'id_matches':r.get('id')==path+'/'+str((params or {}).get('metric'))+'/'+str((params or {}).get('period')),'values_count':len(r.get('values',[]))} for r in value.get('data',[]) if isinstance(r,dict)]
  return value
 except MetaRequestError as exc:
  entry['error']=exc.safe_metadata();raise
m.call=limited_call
reader=MetaReportingReader(m,request_budget=20)
result={'client_id':m.client_id,'page_id':page,'asset_enabled':bool(asset['enabled']),
        'connected_at':i['connected_at'],'scopes':i['scopes'],'diagnostic_only':True}
try:
 raw=reader.content_insights_diagnostic(page,posts,'2026-10-15','2026-10-17')
 result['insights']=project(raw)
except Exception as exc:
 result['failure']={'type':type(exc).__name__,'code':getattr(exc,'code',None)}
finally:
 result['requests_used']=len(calls);result['calls']=calls
 print(json.dumps(result))
'''

if __name__ == '__main__':
    night.configure_admin()
    live = night.u.inspect(night.d.ADMIN)
    expected = night.read('deployment')['admin']['service']
    assert live['Id'] == expected['id'] and live['Image'] == expected['image']
    assert live['State']['Health']['Status'] == 'healthy'
    OUT.mkdir(exist_ok=True)
    # A crash must not silently cause another provider run.
    with (OUT / 'diagnostic-started.json').open('x', encoding='utf-8') as handle:
        json.dump({'max_requests':20,'start':'2026-10-15','end':'2026-10-17','max_posts':3},handle)
    result=json.loads(night.u.code(night.d.ADMIN,CODE))
    (OUT/'diagnostic.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
