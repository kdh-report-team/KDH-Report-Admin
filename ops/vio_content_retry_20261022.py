"""One additional retry explicitly approved by user after Docker interruption."""
import json
import requests
import vio_content_sync_20261022 as s

def main():
    n=s.night;n.configure_admin()
    live=n.u.inspect(n.d.ADMIN)
    assert live['Image']==n.d.read('build')['image'] and live['State']['Health']['Status']=='healthy'
    before=json.loads(n.u.code(n.d.ADMIN,s.QUERY))
    assert len(before['new_runs'])==1
    s.save('retry-preflight',before)
    values=n.u.env(live)
    client=requests.Session();client.headers.update({'Origin':s.BASE,'X-KDH-Request':'1'})
    r=client.post(s.BASE+'/api/auth/login',json={'email':values['INITIAL_ADMIN_EMAIL'],'password':values['INITIAL_ADMIN_PASSWORD']},timeout=15)
    assert r.status_code==200
    client.headers['X-CSRF-Token']=r.json()['csrf']
    try:
        old='b1589509581f925ed3a325f320ea3ef2'
        r=client.get(s.BASE+'/api/jobs/'+old,timeout=15);assert r.status_code==200
        job=r.json();assert job['status']=='interrupted'
        assert job['params']['asset_id']==s.ASSET and job['params']['start']=='2026-09-21' and job['params']['end']=='2026-10-18'
        with (s.OUT/'retry-started.json').open('x',encoding='utf-8') as f:
            json.dump({'parent_job':old,'max_requests':100,'authorization':'User approved one additional retry'},f)
        r=client.post(s.BASE+'/api/jobs/'+old+'/retry',json={},timeout=20);assert r.status_code==202
        queued=r.json();s.save('retry-job',queued);assert queued['created']
        print(json.dumps({'queued':queued}),flush=True)
        # HTTP timeout does not cancel/retry the job. Always inspect persisted state.
        try:
            r=client.post(s.BASE+'/api/jobs/'+queued['job_id']+'/process',json={},timeout=250)
            s.save('retry-http',{'status_code':r.status_code})
        except requests.RequestException:
            s.save('retry-http',{'status':'response_interrupted; inspect job, no automatic retry'})
        r=client.get(s.BASE+'/api/jobs/'+queued['job_id'],timeout=20);assert r.status_code==200
        job=r.json();result={k:job.get(k) for k in ('id','status','steps','error','started_at','finished_at')}
        s.save('retry-result',result);print(json.dumps(result,ensure_ascii=False),flush=True)
    finally:
        client.post(s.BASE+'/api/auth/logout',json={},timeout=15)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        s.save('retry-interruption',{'type':type(exc).__name__})
        raise SystemExit('Stopped safely: '+type(exc).__name__+'; do not repeat retry')
