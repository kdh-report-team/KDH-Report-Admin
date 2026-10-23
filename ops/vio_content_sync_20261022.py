"""One authorized VIO Content sync through authenticated existing Admin APIs."""
import hashlib
import json
from pathlib import Path
import requests
import deploy_tonight_content as night

OUT = night.u.ROOT / 'docs/vio-insights-live-20261022'
BASE = 'http://localhost:8191'
ASSET = 'cff1f3d5e6f433e021850fbde5b1d3f3'
REPORT = 'rpt_4909119771c69125897d8bca84444abe'
QUERY = r'''
import os,json,hashlib,psycopg
from psycopg.rows import dict_row
from cryptography.fernet import Fernet
from werkzeug.security import check_password_hash
with psycopg.connect(os.environ['DATABASE_URL'],options='-c default_transaction_read_only=on',row_factory=dict_row) as db:
 token=json.loads(Fernet(os.environ['ENCRYPTION_KEY'].encode()).decrypt(bytes(db.execute('SELECT value FROM secrets WHERE name=%s',('meta:client_meta_sandbox',)).fetchone()['value'])))
 a=db.execute("SELECT a.id,a.enabled,a.external_id,a.client_id,a.asset_type,c.status,c.external_account_id FROM source_assets a JOIN connections c ON c.id=a.connection_id WHERE a.id=%s",('cff1f3d5e6f433e021850fbde5b1d3f3',)).fetchone()
 assert a['enabled']==1 and a['external_id']=='2188688654687066' and a['client_id']=='client_meta_sandbox' and a['asset_type']=='facebook_page'
 assert a['status']=='connected' and a['external_account_id']==token['account_id'] and 'read_insights' in token['scopes']
 user=db.execute("SELECT password FROM users WHERE email=%s AND active=1 AND role='admin'",(os.environ['INITIAL_ADMIN_EMAIL'],)).fetchone()
 assert user and check_password_hash(user['password'],os.environ['INITIAL_ADMIN_PASSWORD'])
 report='rpt_4909119771c69125897d8bca84444abe'
 rows=db.execute('SELECT * FROM report_bundles WHERE (id=%s OR bundle_key=%s) AND revision=1 AND client_id=%s',(report,report,'client_meta_sandbox')).fetchall()
 assert len(rows)==1 and rows[0]['status']=='provisional'
 grants=db.execute('SELECT * FROM report_viewer_grants WHERE report_id=%s AND client_id=%s ORDER BY user_id',(report,'client_meta_sandbox')).fetchall()
 seal=hashlib.sha256(json.dumps({'bundle':rows,'grants':grants},sort_keys=True,default=str).encode()).hexdigest()
 runs=db.execute("SELECT id,status,job_id,created_at FROM sync_runs WHERE client_id='client_meta_sandbox' AND asset_id=%s AND requested_start='2026-09-21' AND requested_end='2026-10-18' AND created_at>%s ORDER BY created_at DESC",(a['id'],token['connected_at'])).fetchall()
 print(json.dumps({'asset':a,'connected_at':token['connected_at'],'published_and_grants_hash':seal,'new_runs':runs}))
'''

def save(name, value):
    (OUT / (name+'.json')).write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')

def main():
    night.configure_admin()
    live=night.u.inspect(night.d.ADMIN)
    assert live['Id']==night.read('deployment')['admin']['service']['id']
    assert live['Image']==night.d.read('build')['image']
    expected=night.d.read('build')['files']['kdh/meta_reporting.py']
    actual=night.u.code(night.d.ADMIN,"import hashlib;print(hashlib.sha256(open('/app/kdh/meta_reporting.py','rb').read()).hexdigest())").decode().strip()
    assert actual==expected
    diag=json.loads((OUT/'diagnostic.json').read_text(encoding='utf-8'))
    assert diag['insights']['status']=='available' and diag['requests_used']<=20
    before=json.loads(night.u.code(night.d.ADMIN,QUERY));save('sync-preflight',before)
    assert not before['new_runs'], 'A run already exists after reconnect; inspect/reuse instead of resync'
    with (OUT/'sync-started.json').open('x',encoding='utf-8') as handle:
        json.dump({'asset_id':ASSET,'start':'2026-09-21','end':'2026-10-18','max_requests':100},handle)
    values=night.u.env(live)
    session=requests.Session()
    session.headers.update({'Origin':BASE,'X-KDH-Request':'1'})
    response=session.post(BASE+'/api/auth/login',json={'email':values['INITIAL_ADMIN_EMAIL'],'password':values['INITIAL_ADMIN_PASSWORD']},timeout=15)
    assert response.status_code==200,'Valid existing Admin session required'
    session.headers['X-CSRF-Token']=response.json()['csrf']
    try:
        meta=session.get(BASE+'/api/meta',timeout=15).json()
        assert meta['connected'] and meta['insights_permission'] and meta['client_id']=='client_meta_sandbox'
        response=session.post(BASE+'/api/meta/reporting/sync',json={'asset_id':ASSET,'start':'2026-09-21','end':'2026-10-18'},timeout=20)
        assert response.status_code==202, 'Sync enqueue rejected: '+str(response.status_code)
        queued=response.json();save('sync-job',queued)
        print(json.dumps({'queued':queued}),flush=True)
        assert queued['created'] is True
        response=session.post(BASE+'/api/jobs/'+queued['job_id']+'/process',json={},timeout=250)
        assert response.status_code==200,'Sync processing response unavailable; do not retry'
        job=response.json()
        summary={k:job.get(k) for k in ('id','status','created_at','started_at','finished_at','steps','error')}
        save('sync-result',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)
        assert job['status']=='succeeded','Sync did not succeed; do not retry'
        response=session.post(BASE+'/api/marketing/preview',json={'source':'facebook_content','asset_id':ASSET,'start':'2026-09-21','end':'2026-10-18'},timeout=30)
        assert response.status_code==200,'Preview rejected: '+str(response.status_code)
        preview=response.json();save('new-preview',preview)
        content=preview['content_report']
        assert len(content['sections'])==7 and content['review_status']=='pending_review'
        summary={'sections':len(content['sections']),'snapshot':preview['meta_snapshot'],
                 'metrics':[{k:m.get(k) for k in ('key','value','status')} for m in content['metrics']],
                 'insights_status':content.get('insights',{}).get('status'),
                 'requests_used':content.get('insights',{}).get('requests_used')}
        save('preview-summary',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)
    finally:
        session.post(BASE+'/api/auth/logout',json={},timeout=15)
        after=json.loads(night.u.code(night.d.ADMIN,QUERY));save('sync-postflight',after)
        assert after['published_and_grants_hash']==before['published_and_grants_hash']
        print('Published revision 1 and grants unchanged',flush=True)

if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        # Never print request headers, provider responses, credentials or cookies.
        save('sync-interruption',{'type':type(exc).__name__})
        raise SystemExit('Stopped safely: '+type(exc).__name__+'; inspect saved evidence, do not repeat sync')
