"""Approved isolation probes. TLS handshake only; no Graph/Marketing HTTP/API."""
import json
from runtime_common import HERE, PRIOR, NET, ORIGINAL, original, docker, inspect

ADMIN_PROBE = r'''
import json,pathlib,socket,ssl
def tunnel(authority):
    s=socket.create_connection(('192.168.0.10',3128),timeout=4)
    s.settimeout(5)
    s.sendall(('CONNECT '+authority+' HTTP/1.1\r\nHost: '+authority+'\r\n\r\n').encode())
    header=b''
    while not header.endswith(b'\r\n\r\n'):
        part=s.recv(1)
        assert part
        header+=part
        assert len(header)<4096
    return s,int(header.split()[1])
out={}
for authority in ('example.invalid:443','graph.facebook.com:80','57.144.14.141:443'):
    s,status=tunnel(authority); s.close(); assert status==403
out['deny_nonallowlisted_authority_port_and_ip']='PASS'
s,status=tunnel('graph.facebook.com:443'); assert status==200
try:
    secure=ssl.create_default_context().wrap_socket(s,server_hostname='example.invalid')
except (OSError,ssl.SSLError):
    out['deny_wrong_sni']='PASS'
else:
    secure.close(); raise AssertionError('wrong SNI allowed')
finally:
    s.close()
for ip in ('8.8.8.8','57.144.14.141'):
    try:
        s=socket.create_connection((ip,443),timeout=3)
    except OSError:
        pass
    else:
        s.close(); raise AssertionError('direct egress allowed')
out['deny_direct_internet_and_proxy_bypass']='PASS'
s,status=tunnel('graph.facebook.com:443'); assert status==200
with ssl.create_default_context().wrap_socket(s,server_hostname='graph.facebook.com') as secure:
    assert secure.version() and secure.getpeercert()
    # Deliberately send NO application bytes/HTTP/API after verified TLS.
out['allow_meta_tls_certificate_verified']='PASS'
out['provider_http_requests']=0
print(json.dumps(out))
'''

AUX_PROBE = r'''
import json,socket,pathlib
out={}
for ip,port in (('192.168.0.2',5432),('8.8.8.8',443)):
    try:
        s=socket.create_connection((ip,port),timeout=3)
    except OSError:
        pass
    else:
        s.close(); raise AssertionError('auxiliary container escaped route restriction')
out['deny_postgres_and_unrestricted_internet']='PASS'
out['default_route_absent']=not any(line.split()[1]=='00000000' for line in pathlib.Path('/proc/net/route').read_text().splitlines()[1:])
assert out['default_route_absent']
print(json.dumps(out))
'''


def main():
    deployed=json.loads((HERE/'deployment.json').read_text())
    assert deployed['status']=='PASS'
    admin=inspect(deployed['admin_id'])
    pg=original('pg'); gateway=original('gateway'); relay=original('relay')
    network=json.loads(docker('network','inspect',NET))[0]
    assert network['Internal']
    assert set(admin['NetworkSettings']['Networks'])==set(pg['NetworkSettings']['Networks'])=={NET}
    assert admin['NetworkSettings']['Networks'][NET]['IPAddress']=='192.168.0.3'
    assert pg['NetworkSettings']['Networks'][NET]['IPAddress']=='192.168.0.2'
    assert not admin['HostConfig']['PortBindings'] and not pg['HostConfig']['PortBindings'] and not gateway['HostConfig']['PortBindings']
    owners=[]
    for cid in docker('ps','-q').decode().split():
        running=inspect(cid)
        for port,bindings in (running['NetworkSettings'].get('Ports') or {}).items():
            for binding in bindings or []:
                if binding['HostPort']=='8191':
                    owners.append({'id':running['Id'],'port':port,'host_ip':binding['HostIp']})
    assert owners==[{'id':relay['Id'],'port':'8090/tcp','host_ip':'127.0.0.1'}]
    report={'internal_network':True,'only_active_8191_binding':owners,'provider_api_requests':0}
    try:
        report['admin']=json.loads(docker('exec','-i',admin['Id'],'python','-B','-',data=ADMIN_PROBE.encode()))
        for kind,container in (('gateway',gateway),('relay',relay)):
            report[kind]=json.loads(docker('exec','-i',container['Id'],'python','-B','-',data=AUX_PROBE.encode()))
        report['status']='PASS'
    except Exception as error:
        report['status']='FAIL'; report['error_type']=type(error).__name__
        raise
    finally:
        (HERE/'network-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        print('NETWORK VERIFICATION BLOCKED: '+type(error).__name__+'; details withheld')
        raise SystemExit(1)
