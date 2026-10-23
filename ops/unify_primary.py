"""Controlled primary application update; no provider calls or business mutations."""
import os,sys,json,subprocess,hashlib,io,tarfile,time,secrets,uuid
from pathlib import Path
from urllib.parse import urlsplit
from cryptography.fernet import Fernet
ROOT=Path(__file__).resolve().parents[1]; NEW=ROOT.parent/'KDH-Report-New';OUT=ROOT/'docs/unified-admin-20261020'
sys.path.insert(0,str(ROOT/'docs/phase5-20261018'))
from cold_backup import dpapi
A='kdh-report-admin-admin-1';N='kdh-report-new-app-1';PG='kdh-report-admin-postgres-1'
PRIVATE=Path(os.environ['LOCALAPPDATA'])/'KDH-Primary-Deployment'/'unified-20261020'

def call(*args,data=None,env=None):
 p=subprocess.run(list(args),input=data,capture_output=True,env=env)
 if p.returncode:raise RuntimeError('Command failed; sensitive output withheld: '+args[0])
 return p.stdout

def docker(*args,**kw):return call('docker',*args,**kw)
def inspect(name):return json.loads(docker('inspect',name))[0]
def env(item):return dict(v.split('=',1) for v in item['Config']['Env'])
def save(name,data): (OUT/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def read(name):return json.loads((OUT/(name+'.json')).read_text(encoding='utf-8'))
def sha(b):return hashlib.sha256(b).hexdigest()
def crypt():return Fernet(dpapi((PRIVATE/'key.dpapi').read_bytes(),True))
def sealed(name):return json.loads(crypt().decrypt((PRIVATE/(name+'.fernet')).read_bytes()))
def code(container,source):return docker('exec','-i',container,'python','-B','-',data=source.encode())

INTEGRITY="""import os,json,hashlib
import psycopg
from psycopg import sql
with psycopg.connect(os.environ['DATABASE_URL'],options='-c default_transaction_read_only=on') as db:
 names=[r[0] for r in db.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]
 out={}
 for n in names:
  rows=db.execute(sql.SQL('SELECT row_to_json(t)::text FROM {} t').format(sql.Identifier(n))).fetchall()
  out[n]={'count':len(rows),'sha256':hashlib.sha256(('\\n'.join(sorted(r[0] for r in rows))).encode()).hexdigest()}
 print(json.dumps(out))
"""
def integrity():return json.loads(code(A,INTEGRITY))
def signature(x):
 return {'id':x['Id'],'image':x['Image'],'mounts':x['Mounts'],'networks':list(x['NetworkSettings']['Networks']),'running':x['State']['Running']}

def preflight():
 assert not (OUT/'preflight.json').exists()
 a,n,pg=(inspect(x) for x in (A,N,PG));av,nv=env(a),env(n)
 assert all(x['State'].get('Health',{}).get('Status')=='healthy' for x in (a,n,pg))
 assert av['META_CLIENT_ID']=='client_meta_sandbox' and av['JOB_MODE']=='worker'
 assert av['REPORT_NEW_BASE_URL']=='http://localhost:8080'
 assert nv['REPORT_ADMIN_PUBLIC_URL']=='http://localhost:8090' and nv['REPORT_NEW_PUBLIC_URL']=='http://localhost:8080'
 assert av.get('REPORT_SERVICE_TOKEN') and secrets.compare_digest(av['REPORT_SERVICE_TOKEN'],nv['REPORT_SERVICE_TOKEN'])
 assert urlsplit(av['DATABASE_URL']).hostname=='postgres'
 assert urlsplit(av['DATABASE_URL']).path=='/'+env(pg)['POSTGRES_DB']
 assert {m['Name'] for m in pg['Mounts'] if m['Type']=='volume'}=={'kdh-report-admin_postgres-data'}
 assert {m['Name'] for m in a['Mounts'] if m['Type']=='volume'}=={'kdh-report-admin_admin-data'}
 assert a['HostConfig']['PortBindings']=={'8090/tcp':[{'HostIp':'127.0.0.1','HostPort':'8090'}]}
 assert n['HostConfig']['PortBindings']=={'8000/tcp':[{'HostIp':'127.0.0.1','HostPort':'8080'}]}
 checks=json.loads(code(A,"""import os,json,psycopg
with psycopg.connect(os.environ['DATABASE_URL'],options='-c default_transaction_read_only=on') as db:
 print(json.dumps({'migrations':[x[0] for x in db.execute('SELECT version FROM schema_migrations ORDER BY version')], 'pending_jobs':db.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0], 'schedules':db.execute('SELECT count(*) FROM schedules WHERE enabled=1').fetchone()[0]}))"""))
 assert checks=={'migrations':list(range(1,9)),'pending_jobs':0,'schedules':0}
 for local,container,filename in [(ROOT,A,'requirements.lock'),(NEW,N,'requirements.txt')]:
  assert code(container,"from pathlib import Path;import sys;sys.stdout.buffer.write(Path('/app/"+filename+"').read_bytes())")== (local/filename).read_bytes(),'Dependency baseline differs'
 for filename in ('kdh/migrations.py',):
  assert code(A,"from pathlib import Path;import sys;sys.stdout.buffer.write(Path('/app/"+filename+"').read_bytes())")== (ROOT/filename).read_bytes(),'Migration source changed'
 PRIVATE.mkdir(parents=True,exist_ok=True)
 assert not (PRIVATE/'key.dpapi').exists()
 key=Fernet.generate_key();(PRIVATE/'key.dpapi').write_bytes(dpapi(key));box=Fernet(key)
 original={'admin':a,'new':n,'postgres':pg}
 (PRIVATE/'original.f ernet'.replace(' ','')).write_bytes(box.encrypt(json.dumps(original).encode()))
 raw={'database.dump':docker('exec',PG,'pg_dump','-U',env(pg)['POSTGRES_USER'],'-d',env(pg)['POSTGRES_DB'],'-Fc'),
      'appdata.tar':docker('exec',A,'tar','-C','/app/instance','-cf','-','.')}
 assert raw['database.dump'].startswith(b'PGDMP')
 backup={}
 for name,content in raw.items():
  value=box.encrypt(content);(PRIVATE/(name+'.fernet')).write_bytes(value)
  assert box.decrypt(value)==content
  backup[name]={'sha256':sha(content),'encrypted_sha256':sha(value),'bytes':len(content)}
 protected={x['Name'].lstrip('/'):signature(x) for x in json.loads(docker('inspect',*docker('ps','-aq').decode().split())) if x['Name'].startswith(('/kdh-meta','/kdh-vio'))}
 save('preflight',{'services':{A:signature(a),N:signature(n),PG:signature(pg)},'protected':protected,'checks':checks,'data':integrity(),'backup':backup,'private_backup':str(PRIVATE),'scope':'client_meta_sandbox unchanged','off_host_backup':False})
 print('Primary identity, schema 1-8, idle jobs, paired backend token and encrypted backup PASS')

def build():
 p=read('preflight');result={}
 for label,root,container,folders,extra in [('admin',ROOT,A,('kdh','templates','static'),['run.py']),('new',NEW,N,('app','templates','static'),['main.py'])]:
  base=p['services'][container]['image'];base_tag='kdh-'+label+':unified-baseline-'+base.split(':')[1][:12]
  docker('tag',base,base_tag)
  files={str(f.relative_to(root)).replace('\\','/'):f.read_bytes() for folder in folders for f in (root/folder).rglob('*') if f.is_file() and '__pycache__' not in f.parts and f.suffix not in ('.pyc','.map')}
  files.update({f:(root/f).read_bytes() for f in extra})
  manifest={k:sha(v) for k,v in sorted(files.items())};tag='kdh-'+label+':unified-20261020-'+sha(json.dumps(manifest,sort_keys=True).encode())[:12]
  df='FROM '+base_tag+'\n'+''.join('COPY --chown=10001:10001 '+f+' /app/'+f+'\n' for f in files)
  buf=io.BytesIO()
  with tarfile.open(fileobj=buf,mode='w') as tf:
   for f,data in {'Dockerfile':df.encode(),**files}.items():
    info=tarfile.TarInfo(f);info.size=len(data);info.mode=0o644;tf.addfile(info,io.BytesIO(data))
  proc=subprocess.run(['docker','build','--pull=false','--network=none','-t',tag,'-'],input=buf.getvalue(),capture_output=True)
  (OUT/(label+'-build.log')).write_bytes(proc.stdout+proc.stderr);assert proc.returncode==0
  result[label]={'tag':tag,'image':inspect(tag)['Id'],'files':manifest}
 save('build',result);print('Both immutable source-manifest images built')

def isolated():
 original=sealed('original');builds=read('build');pre=read('preflight')
 owner='kdh-unified-20261020';network=owner+'-test'
 pg=owner+'-postgres';app=owner+'-admin-smoke'
 assert not docker('ps','-aq','--filter','name=^/'+pg+'$').strip()
 docker('network','create','--internal','--label','kdh.owner='+owner,network)
 password=secrets.token_urlsafe(40)
 pgvalues={'POSTGRES_USER':'isolated','POSTGRES_PASSWORD':password,'POSTGRES_DB':'restored'}
 args=['run','-d','--name',pg,'--network',network,'--network-alias','testdb','--label','kdh.owner='+owner,
       '--tmpfs','/var/lib/postgresql/data:rw']
 for key in pgvalues:args+=['--env',key]
 docker(*args,original['postgres']['Image'],env={**os.environ,**pgvalues})
 for _ in range(30):
  r=subprocess.run(['docker','exec',pg,'pg_isready','-U','isolated','-d','restored'],capture_output=True)
  if r.returncode==0:break
  time.sleep(1)
 else:raise RuntimeError('Isolated PostgreSQL not ready')
 raw=crypt().decrypt((PRIVATE/'database.dump.fernet').read_bytes())
 assert sha(raw)==pre['backup']['database.dump']['sha256']
 docker('exec','-i',pg,'pg_restore','--exit-on-error','--no-owner','--no-privileges','-U','isolated','-d','restored',data=raw)
 docker('exec',pg,'createdb','-U','isolated','regression')
 values=env(original['admin'])
 values.update(DATABASE_URL='postgresql://isolated:'+password+'@testdb:5432/restored',
               JOB_MODE='request',REPORT_VIO_HANDOFF_ENABLED='1')
 # Own tmpfs appdata; never mount the original volume into the test.
 args=['create','--name',app,'--network',network,'--label','kdh.owner='+owner,
       '--tmpfs','/app/instance:rw,uid=10001,gid=10001']
 for key in values:args+=['--env',key]
 args += [builds['admin']['tag'],'python','-c','import time; time.sleep(3600)']
 docker(*args,env={**os.environ,**values});docker('start',app)
 backup=crypt().decrypt((PRIVATE/'appdata.tar.fernet').read_bytes())
 assert sha(backup)==pre['backup']['appdata.tar']['sha256']
 docker('exec','-i',app,'tar','-C','/app/instance','-xf','-',data=backup)
 isolated_validate()

def isolated_validate():
 owner='kdh-unified-20261020';network=owner+'-test'
 pg=owner+'-postgres';app=owner+'-admin-smoke'
 pre=read('preflight');builds=read('build')
 assert inspect(app)['Config']['Labels']['kdh.owner']==owner
 assert inspect(pg)['Config']['Labels']['kdh.owner']==owner
 assert inspect(network)['Internal'] is True
 password=env(inspect(pg))['POSTGRES_PASSWORD']
 before=json.loads(code(app,INTEGRITY))
 assert before==pre['data'],'Backup does not match captured data'
 smoke=json.loads(code(app,"""import json
from kdh.app import create_app
app=create_app()
c=app.test_client()
checks={'health':c.get('/health').status_code,'login':c.get('/').status_code,
 'marketing_anonymous':c.get('/marketing').status_code,
 'csrf_rejection':c.post('/api/auth/login',json={}).status_code,
 'bundle_anonymous':c.get('/api/internal/v1/viewer/report-bundles/rpt_missing?revision=1').status_code}
print(json.dumps(checks))
"""))
 assert smoke['health']==200 and smoke['login']==200
 assert smoke['marketing_anonymous'] in (302,303,401)
 assert smoke['csrf_rejection'] in (400,401,403) and smoke['bundle_anonymous'] in (401,403)
 after=json.loads(code(app,INTEGRITY))
 changed=[k for k in before if before[k]!=after[k]]
 assert not changed, 'Clone startup altered persisted records: '+','.join(changed)
 save('restore-smoke',{'network':network,'postgres':pg,'app':app,'restore_hashes_match':True,'appdata_restore':True,
                      'smoke':smoke,'startup_data_unchanged':True,'migrations':'existing 1-8 unchanged'})
 print('Backup restore, isolated application startup and data integrity PASS',flush=True)
 testvalues={'TEST_DATABASE_URL':'postgresql://isolated:'+password+'@testdb:5432/regression'}
 args=['run','--name',owner+'-postgres-tests','--network',network,'--label','kdh.owner='+owner,
       '--mount','type=bind,source='+str(ROOT/'tests')+',target=/app/tests,readonly']
 for key in testvalues:args+=['--env',key]
 args += [builds['admin']['tag'],'python','-B','-m','unittest','discover','-s','tests','-v']
 with (OUT/'admin-postgres-tests.log').open('wb') as log:
  p=subprocess.run(['docker',*args],env={**os.environ,**testvalues},stdout=log,stderr=subprocess.STDOUT)
 save('postgres-tests-exit',{'exit_code':p.returncode})
 assert p.returncode==0,'Isolated PostgreSQL tests failed; see log'
 print('Isolated full PostgreSQL suite PASS')

def new_smoke():
 from shlex import join
 values=env(sealed('original')['new'])
 cli=['run','--name','kdh-unified-new-offline-20261020','--network','none']
 for key in values:cli+=['--env',key]
 script="""import json
from fastapi.testclient import TestClient
from main import app
c=TestClient(app)
r={p:c.get(p,follow_redirects=False).status_code for p in
 ('/api/v1/health','/','/overview','/demo-bundle','/api/v1/reports/facebook-content')}
assert r=={'/api/v1/health':200,'/':303,'/overview':404,'/demo-bundle':404,'/api/v1/reports/facebook-content':404},r
print(json.dumps(r))
"""
 cli += [read('build')['new']['tag'],'python','-c',script]
 output=docker(*cli,env={**os.environ,**values})
 save('new-smoke',json.loads(output))
 print('New image health, Admin entry redirect and demo denial PASS')

def facebook_postgres():
 pg=inspect('kdh-unified-20261020-postgres')
 assert pg['Config']['Labels']['kdh.owner']=='kdh-unified-20261020'
 password=env(pg)['POSTGRES_PASSWORD']
 values={'TEST_DATABASE_URL':'postgresql://isolated:'+password+'@testdb:5432/regression',
         'KDH_PHASE4_ISOLATED':'1','PYTHONPATH':'/app:/app/tests'}
 args=['run','--name','kdh-unified-facebook-postgres-20261020','--network','kdh-unified-20261020-test',
       '--mount','type=bind,source='+str(ROOT/'tests')+',target=/app/tests,readonly']
 for key in values:args+=['--env',key]
 args += [read('build')['admin']['tag'],'python','-B','-m','unittest','test_facebook_bundles_postgres','-v']
 with (OUT/'facebook-postgres-tests.log').open('wb') as log:
  p=subprocess.run(['docker',*args],env={**os.environ,**values},stdout=log,stderr=subprocess.STDOUT)
 save('facebook-postgres-exit',{'exit_code':p.returncode})
 assert p.returncode==0
 print('Guarded Facebook Content/Ads PostgreSQL tests PASS')

def collect_postgres():
 item=inspect('kdh-unified-20261020-postgres-tests')
 assert item['State']['Status']=='exited','Tests still running'
 result=subprocess.run(['docker','logs',item['Id']],capture_output=True)
 (OUT/'admin-postgres-tests.log').write_bytes(result.stdout+result.stderr)
 save('postgres-tests-exit',{'exit_code':item['State']['ExitCode']})
 assert item['State']['ExitCode']==0
 print((result.stdout+result.stderr).decode()[-250:])

def extra_postgres():
 pg=inspect('kdh-unified-20261020-postgres')
 assert pg['Config']['Labels']['kdh.owner']=='kdh-unified-20261020'
 values={'TEST_DATABASE_URL':'postgresql://isolated:'+env(pg)['POSTGRES_PASSWORD']+'@testdb:5432/regression',
         'KDH_PHASE4_ISOLATED':'1','TEST_META_POSTGRES':'1','PYTHONPATH':'/app:/app/tests'}
 args=['run','--name','kdh-unified-extra-postgres-20261020','--network','kdh-unified-20261020-test',
       '--mount','type=bind,source='+str(ROOT/'tests')+',target=/app/tests,readonly']
 for key in values:args+=['--env',key]
 args += [read('build')['admin']['tag'],'python','-B','-m','unittest',
          'test_meta_diagnostics.PostgresMetaDiagnosticsTests','test_vio_handoff.PostgresVioHandoffTests','-v']
 with (OUT/'extra-postgres-tests.log').open('wb') as log:
  p=subprocess.run(['docker',*args],env={**os.environ,**values},stdout=log,stderr=subprocess.STDOUT)
 save('extra-postgres-exit',{'exit_code':p.returncode})
 assert p.returncode==0
 print('Additional VIO handoff and Meta diagnostics PostgreSQL tests PASS')

def protected():
 p=read('preflight')
 for name,expected in p['protected'].items():
  assert signature(inspect(name))==expected,'Separate sandbox changed: '+name
 assert signature(inspect(PG))==p['services'][PG],'Primary PostgreSQL changed'

def wait_health(name):
 for _ in range(45):
  item=inspect(name)
  if item['State'].get('Health',{}).get('Status')=='healthy':return
  if not item['State']['Running']:raise RuntimeError(name+' stopped during health check')
  time.sleep(1)
 raise RuntimeError(name+' did not become healthy')

def create_replacement(name,label):
 import shlex
 original=sealed('original')[label];h=original['HostConfig'];c=original['Config']
 image=read('build')[label]
 assert not h['Privileged'] and not h.get('CapAdd')
 values=env(original)
 if label=='admin':values['REPORT_VIO_HANDOFF_ENABLED']='1'
 args=['create','--name',name,'--init','--restart',h['RestartPolicy']['Name'],
       '--network',h['NetworkMode'],'--user',c['User'],'--workdir',c['WorkingDir']]
 health=c.get('Healthcheck')
 if health:
  command=health['Test'][1] if health['Test'][0]=='CMD-SHELL' else shlex.join(health['Test'][1:])
  args+=['--health-cmd',command,'--health-interval',str(health['Interval'])+'ns',
         '--health-timeout',str(health['Timeout'])+'ns',
         '--health-start-period',str(health.get('StartPeriod',0))+'ns',
         '--health-retries',str(health['Retries'])]
 for alias in original['NetworkSettings']['Networks'][h['NetworkMode']]['Aliases'] or []:
  args+=['--network-alias',alias]
 for port,bindings in h['PortBindings'].items():
  for b in bindings:
   assert b['HostIp']=='127.0.0.1'
   args+=['--publish',b['HostIp']+':'+b['HostPort']+':'+port]
 for mount in h.get('Binds') or []:args+=['--volume',mount]
 for mount in h.get('Mounts') or []:
  assert mount['Type']=='bind'
  args+=['--mount','type=bind,source='+mount['Source']+',target='+mount['Target']+(',readonly' if mount.get('ReadOnly') else '')]
 for label_key,value in c.get('Labels',{}).items():
  if label_key=='com.docker.compose.config-hash':continue
  if label_key=='com.docker.compose.image':value=image['image']
  args+=['--label',label_key+'='+value]
 args+=['--label','kdh.deployment=unified-20261020']
 for key in values:args+=['--env',key]
 args += [image['tag'],*c['Cmd']]
 docker(*args,env={**os.environ,**values})
 for network,settings in original['NetworkSettings']['Networks'].items():
  if network==h['NetworkMode']:continue
  extra=[]
  for alias in settings.get('Aliases') or []:extra+=['--alias',alias]
  docker('network','connect',*extra,network,name)
 created=inspect(name)
 assert created['Image']==image['image']
 assert env(created)==values
 assert created['HostConfig']['PortBindings']==h['PortBindings']
 def mounts(x):
  return sorted((m['Type'],m['Source'],m['Destination'],m['RW']) for m in x['Mounts'])
 assert mounts(created)==mounts(original),'Mounts differ'
 assert set(created['NetworkSettings']['Networks'])==set(original['NetworkSettings']['Networks'])

def deploy():
 import re
 assert read('postgres-tests-exit')['exit_code']==0
 assert read('facebook-postgres-exit')['exit_code']==0 and read('extra-postgres-exit')['exit_code']==0
 assert read('restore-smoke')['startup_data_unchanged'] and read('new-smoke')['/api/v1/health']==200
 offline=(OUT/'admin-isolated-tests.log').read_text(encoding='utf-16' if (OUT/'admin-isolated-tests.log').read_bytes().startswith(b'\xff\xfe') else 'utf-8')
 assert 'OK (skipped=141)' in offline
 protected()
 p=read('preflight');builds=read('build')
 for label,name,root in [('admin',A,ROOT),('new',N,NEW)]:
  assert signature(inspect(name))==p['services'][name],'Runtime baseline drift'
  assert env(inspect(name))==env(sealed('original')[label])
  for path,expected in builds[label]['files'].items():
   assert sha((root/path).read_bytes())==expected,'Source drift: '+path
 before=integrity()
 assert before==p['data'],'Database changed since backup; refresh gate required'
 backups={name:name+'-rollback-unified-20261020' for name in (A,N)}
 for name in backups.values():
  assert not docker('ps','-aq','--filter','name=^/'+name+'$').strip()
 done=[]
 try:
  for label,name in [('admin',A),('new',N)]:
   docker('stop','--time','30',name)
   docker('rename',name,backups[name]);done.append(name)
   create_replacement(name,label)
   docker('start',name);wait_health(name)
  checks=json.loads(code(N,"""import os,json,urllib.request,urllib.error
out={}
for path in ('/health','/api/internal/v1/viewer/report-bundles/rpt_missing?revision=1'):
 req=urllib.request.Request(os.environ['REPORT_ADMIN_BASE_URL']+path)
 if path!='/health':req.add_header('Authorization','Bearer '+os.environ['REPORT_SERVICE_TOKEN'])
 try:
  with urllib.request.urlopen(req,timeout=10) as r:out[path]=r.status
 except urllib.error.HTTPError as e:out[path]=e.code
print(json.dumps(out))
"""))
  assert checks['/health']==200
  assert checks['/api/internal/v1/viewer/report-bundles/rpt_missing?revision=1']==401
  after=integrity()
  assert before==after,'Business data changed during deployment'
  protected()
  save('deployment',{'status':'PASS','services':{name:signature(inspect(name)) for name in (A,N)},
                    'rollback':backups,'backend_checks':checks,'data_unchanged':True,
                    'client_id':'client_meta_sandbox','vio_handoff_flag':True,
                    'admin_url':'http://localhost:8090','new_url':'http://localhost:8080'})
  print('Primary Admin/New application deployment PASS; data and separate sandbox unchanged')
 except Exception:
  for name in reversed(done):
   if docker('ps','-aq','--filter','name=^/'+name+'$').strip():
    docker('stop','--time','20',name)
    docker('rename',name,name+'-failed-unified-'+uuid.uuid4().hex[:6])
   docker('rename',backups[name],name);docker('start',name);wait_health(name)
  save('deployment',{'status':'ROLLED_BACK','original_services_restored':done})
  raise

def final_verify():
 assert read('deployment')['status']=='PASS'
 protected()
 p=read('preflight')
 assert integrity()==p['data'],'Database changed since deployment'
 results={}
 for label,name in [('admin',A),('new',N)]:
  b=read('build')[label];item=inspect(name)
  assert item['Image']==b['image'] and item['State']['Health']['Status']=='healthy'
  script="import json,hashlib\nfrom pathlib import Path\nfiles="+repr(list(b['files']))+"\nprint(json.dumps({p:hashlib.sha256((Path('/app')/p).read_bytes()).hexdigest() for p in files}))"
  hashes=json.loads(code(name,script))
  assert hashes==b['files']
  results[label]={'image':item['Image'],'source_files_matched':len(hashes),'health':'healthy'}
 original=sealed('original')
 assert env(inspect(A))['ENCRYPTION_KEY']==env(original['admin'])['ENCRYPTION_KEY']
 assert env(inspect(A))['META_CLIENT_ID']=='client_meta_sandbox'
 assert env(inspect(A))['JOB_MODE']=='worker'
 assert env(inspect(A))['REPORT_SERVICE_TOKEN']==env(inspect(N))['REPORT_SERVICE_TOKEN']
 for name in ('kdh-unified-20261020-admin-smoke','kdh-unified-20261020-postgres'):
  item=inspect(name)
  assert item['Config']['Labels'].get('kdh.owner')=='kdh-unified-20261020'
  assert list(item['NetworkSettings']['Networks'])==['kdh-unified-20261020-test']
  docker('stop','--time','20',name)
 results.update(database='all table hashes unchanged',separate_vio='unchanged',
                encryption_key='unchanged',client='client_meta_sandbox',test_resources='stopped; no deletion')
 save('final-verification',results)
 print(json.dumps(results))

if __name__=='__main__':globals()[sys.argv[1]]()
