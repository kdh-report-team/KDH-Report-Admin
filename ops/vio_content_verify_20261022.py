"""Read-only persistence verification of the one authorized Content job."""
import json
import vio_content_sync_20261022 as sync

CODE = r'''
import os,json,psycopg
from psycopg.rows import dict_row
from cryptography.fernet import Fernet
from kdh.marketing_provenance import verify_adapter_receipt,sha
from kdh.meta_contract import daily_consistent
class Reader:
 def __init__(self,db):self.db=db
 def execute(self,sql,params=()):return self.db.execute(sql.replace('?', '%s'),params)
with psycopg.connect(os.environ['DATABASE_URL'],options='-c default_transaction_read_only=on',row_factory=dict_row) as db:
 job=db.execute('SELECT id,status,created_at,started_at,finished_at,steps,error,params FROM jobs WHERE id=%s',('b1589509581f925ed3a325f320ea3ef2',)).fetchone()
 assert job
 params=json.loads(job.pop('params'));assert params['asset_id']=='cff1f3d5e6f433e021850fbde5b1d3f3' and params['source']=='facebook_content'
 result={'job':job}
 run=db.execute("SELECT * FROM sync_runs WHERE job_id=%s AND client_id='client_meta_sandbox'",(job['id'],)).fetchone()
 if run:
  result['run']={k:run.get(k) for k in ('id','status','record_count','created_at','finished_at','error_code','requested_start','requested_end')}
  snap=db.execute('SELECT * FROM source_snapshots WHERE sync_run_id=%s',(run['id'],)).fetchone()
  if snap:
   payload=json.loads(snap['payload']);raw=payload.get('insights',{})
   reader=Reader(db)
   result.update(snapshot_id=snap['id'],snapshot_sha256=sha(payload),
     receipt_valid=verify_adapter_receipt(reader,Fernet(os.environ['ENCRYPTION_KEY'].encode()),run,snap),
     daily_consistent=daily_consistent(reader,run,payload),totals=payload['totals'],
     insights_status=raw.get('status'),requests_used=raw.get('requests_used'),
     measurements=[{'metric':m['metric'],'object_id':m['object_id'],'status':m['status'],'point_count':len(m['values'])} for m in raw.get('measurements',[])],
     post_count=len(payload['entries']),metadata_coverage={k:sum(bool(p.get(k)) for p in payload['entries']) for k in ('message','permalink_url','format')})
   matches=[]
   for row in db.execute("SELECT id,data FROM datasets WHERE report_type='facebook-content' ORDER BY created_at DESC").fetchall():
    data=json.loads(row['data'])
    if data.get('client_id')!='client_meta_sandbox':continue
    preview=data.get('marketing',{}).get('preview',{})
    if preview.get('meta_snapshot',{}).get('snapshot_id')==snap['id']:
     matches.append({'id':row['id'],'kind':data.get('dataset_kind'),'review_status':data.get('marketing',{}).get('review_status')})
   result['matching_datasets']=matches
 print(json.dumps(result))
'''

if __name__=='__main__':
    sync.night.configure_admin()
    result=json.loads(sync.night.u.code(sync.night.d.ADMIN,CODE))
    sync.save('persistence-check',result)
    after=json.loads(sync.night.u.code(sync.night.d.ADMIN,sync.QUERY))
    before=json.loads((sync.OUT/'sync-preflight.json').read_text(encoding='utf-8'))
    assert after['published_and_grants_hash']==before['published_and_grants_hash']
    sync.save('sync-postflight',after)
    print(json.dumps(result,ensure_ascii=False))
