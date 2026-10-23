"""Prepare one pending Dataset from verified persistence; no review/publication."""
import json
import requests
import vio_content_sync_20261022 as s
import vio_content_verify_20261022 as verify

def main():
    n=s.night;n.configure_admin()
    evidence=json.loads(n.u.code(n.d.ADMIN,verify.CODE.replace('b1589509581f925ed3a325f320ea3ef2','5e320fe5250726ec421829fceedcb94f')))
    assert evidence['receipt_valid'] and evidence['daily_consistent'] and evidence['requests_used']<=100
    assert evidence['job']['status']=='succeeded'
    values=n.u.env(n.u.inspect(n.d.ADMIN))
    client=requests.Session();client.headers.update({'Origin':s.BASE,'X-KDH-Request':'1'})
    r=client.post(s.BASE+'/api/auth/login',json={'email':values['INITIAL_ADMIN_EMAIL'],'password':values['INITIAL_ADMIN_PASSWORD']},timeout=15);assert r.status_code==200
    client.headers['X-CSRF-Token']=r.json()['csrf']
    try:
        body={'source':'facebook_content','asset_id':s.ASSET,'start':'2026-09-21','end':'2026-10-18'}
        r=client.post(s.BASE+'/api/marketing/preview',json=body,timeout=25);assert r.status_code==200
        preview=r.json();assert preview['meta_snapshot']['snapshot_id']==evidence['snapshot_id']
        content=preview['content_report'];assert len(content['sections'])==7 and content['review_status']=='pending_review'
        s.save('new-preview',preview)
        summary={'snapshot':preview['meta_snapshot'],'metrics':content['metrics'],
                 'sections':{k:{field:v.get(field) for field in ('status','reason','coverage')} for k,v in content['sections'].items()},
                 'page_insights':[{k:m.get(k) for k in ('metric','status','report_status','coverage','value')} for m in content['insights']['measurements'] if m['scope']=='page']}
        s.save('preview-summary',summary)
        matches=[d for d in evidence['matching_datasets'] if d['kind']=='marketing_internal_preview_v1']
        if matches:
            assert len(matches)==1;result={'dataset_id':matches[0]['id'],'reused':True,'review_status':matches[0]['review_status']}
        else:
            with (s.OUT/'dataset-create-started.json').open('x',encoding='utf-8') as f:json.dump({'snapshot_id':evidence['snapshot_id']},f)
            r=client.post(s.BASE+'/api/marketing/datasets',json=dict(body,client_id='client_meta_sandbox'),timeout=30)
            assert r.status_code==201,'Dataset creation rejected: '+str(r.status_code)
            result=r.json();assert result['review_status']=='pending' and result['publishable'] is False
        s.save('new-dataset',result);print(json.dumps(result,ensure_ascii=False))
        print(json.dumps({'metrics':[{k:m.get(k) for k in ('key','value','status')} for m in content['metrics']],'sections':summary['sections'],'page_insights':summary['page_insights']},ensure_ascii=False))
    finally:client.post(s.BASE+'/api/auth/logout',json={},timeout=15)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        s.save('prepare-interruption',{'type':type(exc).__name__})
        raise SystemExit('Stopped safely: '+type(exc).__name__+'; inspect existing Dataset before retry')
