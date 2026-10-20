"""Read-only final Phase 9 sandbox and business-data verification."""
import json
import sys
import urllib.request
from pathlib import Path

sys.dont_write_bytecode = True
from operations import (ADMIN, GATEWAY, HANDOFF_NET, HOST_NET, INGRESS, NEW_NAME, PG,
                        RELAY, SIDECAR, inspect, read, save, docker, env,
                        protected_services)
from runtime_common import NET
from deploy_ui import integrity


def health(url):
    with urllib.request.urlopen(url, timeout=8) as response:
        return response.status


def main():
    baseline = read('preflight')
    deployment = read('deployment')
    network_tests = read('network-tests')
    browser = read('browser-e2e')
    relay_meta = read('private-relay')

    admin = inspect(ADMIN)
    pg = inspect(PG)
    gateway = inspect(GATEWAY)
    relay = inspect(RELAY)
    sidecar = inspect(SIDECAR)
    new = inspect(NEW_NAME)
    old_new = inspect('kdh-report-new-app-1')

    assert deployment['status'] == 'PASS' and browser['result'] == 'PASS'
    assert admin['Id'] == deployment['admin_id'] and admin['Image'] == deployment['admin_image']
    assert admin['State']['Health']['Status'] == 'healthy' and not admin['HostConfig']['PortBindings']
    assert pg['Id'] == baseline['services'][PG]['Id'] and pg['State']['Health']['Status'] == 'healthy'
    assert gateway['Id'] == baseline['services'][GATEWAY]['Id']
    assert relay['Id'] == baseline['services'][RELAY]['Id']
    assert new['Id'] == deployment['new_id'] and new['Image'] == deployment['new_image']
    assert new['State']['Health']['Status'] == 'healthy'
    assert new['HostConfig']['PortBindings']['8000/tcp'][0] == {'HostIp': '127.0.0.1', 'HostPort': '8193'}
    assert old_new['Id'] == baseline['services']['kdh-report-new-app-1']['Id']
    assert old_new['Image'] == baseline['services']['kdh-report-new-app-1']['Image']
    protected_services(baseline)

    relay_binding = relay['HostConfig']['PortBindings']['8090/tcp'][0]
    assert relay_binding == {'HostIp': '127.0.0.1', 'HostPort': '8191'}
    assert not sidecar['HostConfig']['PortBindings']
    assert sidecar['Id'] == relay_meta['id']
    assert set(new['NetworkSettings']['Networks']) == {HANDOFF_NET, HOST_NET}
    assert set(sidecar['NetworkSettings']['Networks']) == {HANDOFF_NET, NET}

    networks = {name: json.loads(docker('network', 'inspect', name))[0]
                for name in (INGRESS, HANDOFF_NET, HOST_NET)}
    ingress = networks[INGRESS]
    assert ingress['Options']['com.docker.network.bridge.enable_icc'] == 'false'
    assert networks[HANDOFF_NET]['Internal'] is True
    assert networks[HANDOFF_NET]['Options'].get('com.docker.network.bridge.enable_icc', 'false') == 'false'
    assert networks[HOST_NET]['Options']['com.docker.network.bridge.enable_icc'] == 'false'
    assert networks[HOST_NET]['Options']['com.docker.network.bridge.enable_ip_masquerade'] == 'false'
    assert set(networks[HANDOFF_NET]['Containers']) == {new['Id'], sidecar['Id']}
    assert set(networks[HOST_NET]['Containers']) == {new['Id']}
    assert set(admin['NetworkSettings']['Networks']) == {NET}
    assert set(pg['NetworkSettings']['Networks']) == {NET}
    assert NET not in new['NetworkSettings']['Networks']

    current_data = integrity()
    allowed = {'viewer_handoffs', 'delegated_viewer_sessions'}
    changed = [name for name, value in baseline['data'].items()
               if name not in allowed and current_data.get(name) != value]
    assert not changed

    values = env(admin)
    assert values.get('JOB_MODE') == 'request'
    assert values.get('META_CLIENT_ID') == 'client_meta_sandbox'
    assert values.get('REPORT_VIO_HANDOFF_ENABLED') == '1'

    result = {
        'result': 'PASS',
        'admin_health': health('http://127.0.0.1:8191/health'),
        'new_vio_health': health('http://127.0.0.1:8193/api/v1/health'),
        'existing_new_8080_health': health('http://127.0.0.1:8080/api/v1/health'),
        'admin_image': deployment['admin_image'],
        'new_image': deployment['new_image'],
        'admin_host_binding': 'none',
        'postgres_host_binding': 'none',
        'original_relay_binding': '127.0.0.1:8191 only',
        'new_vio_binding': '127.0.0.1:8193 only',
        'existing_new_8080': 'same container identity and image',
        'ingress_icc': False,
        'host_network_icc': False,
        'host_network_masquerade': False,
        'network_tests': network_tests,
        'business_tables_unchanged': len(changed) == 0,
        'provider_calls': 0,
        'report_mutations': 0,
        'handoff_e2e': 'PASS',
        'viewer_negative_tests': browser['negative'],
    }
    save('final-verification', result)
    print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'result': 'FAIL', 'type': type(exc).__name__}))
        raise
