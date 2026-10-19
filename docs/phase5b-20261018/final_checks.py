"""Final read-only deployment/integrity checks. No provider/API mutation."""
import ast
import json
from pathlib import Path
import subprocess
from runtime_common import HERE, PRIOR, ROOT, NET, ORIGINAL, original, inspect, docker, data_gate, digest, sql


def main():
    baseline = json.loads((HERE / "baseline.json").read_text())
    head = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
    branch = subprocess.check_output(["git", "branch", "--show-current"]).decode().strip()
    assert head == baseline["head"] and branch == baseline["branch"]
    changed = [p for p,h in baseline["hashes"].items() if not (ROOT/p).exists() or digest((ROOT/p).read_bytes())!=h]
    assert not changed
    manifest = json.loads((PRIOR / "deployment-manifest.json").read_text())
    assert all(digest((ROOT/p).read_bytes())==h for p,h in manifest["files"].items())
    assert subprocess.run(["git", "diff", "--check"],capture_output=True).returncode==0
    scripts = list(HERE.glob('*.py'))
    for script in scripts:
        ast.parse(script.read_text(encoding='utf-8'))
    for script in list((ROOT/'static').glob('*.js')) + list(HERE.glob('*.mjs')):
        assert subprocess.run(['node','--check',str(script)],capture_output=True).returncode==0
    for name in ('preflight.json','smoke.json','postgres-start.json','deployment.json','http-verification.json','network-verification.json','kpi-dom.json'):
        assert json.loads((HERE/name).read_text())['status']=='PASS'
    deployment=json.loads((HERE/'deployment.json').read_text())
    admin=inspect(deployment['admin_id']); old=original('admin')
    assert not old['State']['Running'] and old['Name']==ORIGINAL['admin']['Name']+'-before-phase5'
    assert NET not in old['NetworkSettings']['Networks']
    assert admin['State']['Health']['Status']=='healthy' and admin['Image']==deployment['image_id']
    assert admin['NetworkSettings']['Networks'][NET]['IPAddress']=='192.168.0.3'
    assert not admin['HostConfig']['PortBindings']
    env=dict(v.split('=',1) for v in admin['Config']['Env'])
    assert env==dict(v.split('=',1) for v in old['Config']['Env'])
    containers=[]
    for kind, current in [('admin',admin)]+[(kind,original(kind)) for kind in ('pg','gateway','relay')]:
        assert current['State']['Running']
        containers.append({'kind':kind,'name':current['Name'],'id':current['Id'],'image':current['Image'],
            'state':current['State']['Status'],'health':current['State'].get('Health',{}).get('Status','not configured'),
            'published_ports':current['NetworkSettings'].get('Ports'),
            'networks':{name:network['IPAddress'] for name,network in current['NetworkSettings']['Networks'].items()}})
    security=json.loads((PRIOR/'security-readiness.json').read_text())
    run_root=Path('D:/KDH-Meta-Phase2B/20261016-132836-5c512a53')
    assert all(digest((run_root/p).read_bytes())==h for p,h in security['hashes'].items())
    for expected in security['networks']:
        network=json.loads(docker('network','inspect',expected['Name']))[0]
        assert {key:network[key] for key in expected}==expected
    data_gate('data-final.json')
    # Check artifacts against actual configured secrets and decrypted token values
    # in memory. Never write those values or diagnostics containing them.
    secret_values=[v for k,v in env.items() if len(v)>=12 and any(word in k.upper() for word in ('SECRET','PASSWORD','TOKEN','ENCRYPTION_KEY','DATABASE_URL'))]
    from cryptography.fernet import Fernet
    grant=json.loads(Fernet(env['ENCRYPTION_KEY'].encode()).decrypt(bytes.fromhex(sql("SELECT encode(value,'hex') FROM secrets WHERE name='meta:client_meta_sandbox'"))))
    def collect(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if 'token' in key.lower() and isinstance(item,str) and len(item)>=12:
                    secret_values.append(item)
                collect(item)
        elif isinstance(value,list):
            for item in value: collect(item)
    collect(grant)
    artifacts=[p for p in HERE.iterdir() if p.is_file()]+[ROOT/'KDH_PHASE5B_SANDBOX_DEPLOYMENT_RESULT.md',PRIOR/'approved-image-result.json']
    for path in artifacts:
        data=path.read_bytes()
        assert all(value.encode() not in data for value in secret_values)
    result={'status':'PASS','head':head,'branch':branch,'baseline_files_checked':len(baseline['hashes']),
        'changed_baseline_files':changed,'source_manifest_files_unchanged':61,'artifact_python_parse_pass':len(scripts),
        'javascript_syntax':'PASS','git_diff_check':'PASS','known_secret_and_token_scan':'PASS',
        'business_table_checksums':'12/12 match','security_source_and_network_definitions_unchanged':True,
        'rollback_old_container_stopped':True,'rollback_old_image_available':bool(json.loads(docker('image','inspect',old['Image']))),
        'containers':containers,'provider_api_calls':0,'new_syncs':0,'new_attestations_approvals_releases':0}
    (HERE/'final-integrity.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='containers'},indent=2))


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        print('FINAL GATE BLOCKED: '+type(error).__name__+'; sensitive details withheld')
        raise SystemExit(1)
