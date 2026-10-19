"""Execute approved Phase 5 plan with application-only rollback on failure."""
import json
import subprocess
import sys
import time
from runtime_common import HERE, PRIOR, NET, ORIGINAL, original, docker, inspect, data_gate

POLICY = r'''
import json,pathlib
status=dict(line.split(':',1) for line in pathlib.Path('/proc/1/status').read_text().splitlines() if ':' in line)
assert status['Uid'].split()[0]=='10001'
assert int(status['CapEff'].strip(),16)==0 and int(status['CapBnd'].strip(),16)==0
assert status['NoNewPrivs'].strip()=='1'
assert pathlib.Path('/proc/sys/net/ipv4/ip_forward').read_text().strip()=='0'
assert pathlib.Path('/proc/sys/net/ipv6/conf/all/disable_ipv6').read_text().strip()=='1'
routes=[line.split() for line in pathlib.Path('/proc/net/route').read_text().splitlines()[1:]]
assert not any(r[1]=='00000000' for r in routes)
print(json.dumps({'uid':10001,'effective_capabilities':0,'bounding_capabilities':0,'no_new_privileges':True,'ip_forward':False,'default_route':False}))
'''


def policy(cid):
    for _ in range(25):
        assert inspect(cid)["State"]["Running"]
        try:
            return json.loads(docker("exec", "-i", cid, "python", "-B", "-", data=POLICY.encode()))
        except RuntimeError:
            time.sleep(1)
    raise RuntimeError("gateway/relay security policy gate")


def healthy(cid):
    for _ in range(45):
        info = inspect(cid)
        assert info["State"]["Running"]
        if info["State"].get("Health", {}).get("Status") == "healthy":
            return info
        time.sleep(1)
    raise RuntimeError("Admin health timeout")


def create(image, rollback=False):
    args = [sys.executable, "-B", str(HERE / "create_admin_after_approval.py"), "--approved-create", "--image-id", image]
    if rollback:
        args.append("--rollback")
    completed = subprocess.run(args, capture_output=True)
    if completed.returncode:
        raise RuntimeError("approved Admin create gate failed")


def main():
    assert not (HERE / "deployment.json").exists()
    assert json.loads((HERE / "postgres-start.json").read_text())["status"] == "PASS"
    smoke = json.loads((HERE / "smoke.json").read_text())
    assert smoke["status"] == "PASS"
    image = smoke["image_id"]
    admin_name = ORIGINAL["admin"]["Name"].lstrip("/")
    before_name = admin_name + "-before-phase5"
    assert not docker("ps", "-aq", "--filter", "name=^/" + before_name + "$").strip()
    assert not original("admin")["State"]["Running"]
    assert not original("gateway")["State"]["Running"]
    assert not original("relay")["State"]["Running"]
    for cid in docker("ps", "-aq", "--filter", "network=" + NET).decode().split():
        attach = inspect(cid)["NetworkSettings"]["Networks"].get(NET, {})
        if (attach.get("IPAMConfig") or {}).get("IPv4Address") == "192.168.0.3":
            candidate = inspect(cid)
            net_state = json.loads(docker("network", "inspect", NET))[0]
            retained_inactive = (candidate["Id"] == "af2d1346b5bfc2b544b0ccf844469d2dfbf98715aa289ade3e54ab778d76b86f"
                and not candidate["State"]["Running"] and not attach.get("EndpointID") and not attach.get("IPAddress")
                and candidate["Id"] not in net_state.get("Containers", {}))
            assert candidate["Id"] == ORIGINAL["admin"]["Id"] or retained_inactive
    report = {"image_id": image, "stage": "gateway", "rollback": "NOT REQUIRED"}
    new_id = None
    admin_replaced = False
    try:
        gateway = original("gateway")
        docker("start", gateway["Id"])
        report["gateway_policy"] = policy(gateway["Id"])
        assert original("gateway")["NetworkSettings"]["Networks"][NET]["IPAddress"] == "192.168.0.10"
        assert not original("gateway")["HostConfig"]["PortBindings"]
        report["stage"] = "retain_old_admin"
        docker("rename", ORIGINAL["admin"]["Id"], before_name)
        docker("network", "disconnect", "--force", NET, before_name)
        admin_replaced = True
        report["stage"] = "create_admin"
        create(image)
        new = inspect(admin_name)
        new_id = new["Id"]
        report["admin_id"] = new_id
        report["admin_name"] = admin_name
        assert new["Image"] == image and not new["HostConfig"]["PortBindings"]
        report["stage"] = "start_admin"
        docker("start", new_id)
        new = healthy(new_id)
        assert new["NetworkSettings"]["Networks"][NET]["IPAddress"] == "192.168.0.3"
        assert set(new["NetworkSettings"]["Networks"]) == {NET}
        assert dict(v.split("=",1) for v in new["Config"]["Env"])["JOB_MODE"] == "request"
        report["admin_health"] = "healthy"
        report["admin_ip"] = "192.168.0.3"
        report["stage"] = "data_after_startup"
        data_gate("data-after-admin.json")
        report["stage"] = "relay"
        # Upstream verified above, before relay is started.
        relay = original("relay")
        assert relay["HostConfig"]["PortBindings"] == {"8090/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8191"}]}
        docker("start", relay["Id"])
        report["relay_policy"] = policy(relay["Id"])
        assert original("relay")["NetworkSettings"]["Networks"]["kdh-meta-2b-ingress-20261016-132836-5c512a53"]["IPAddress"] == "192.168.16.2"
        import requests
        session = requests.Session(); session.trust_env = False
        for _ in range(20):
            try:
                response = session.get("http://localhost:8191/health", timeout=3)
                assert response.status_code == 200
                break
            except (requests.RequestException, AssertionError):
                time.sleep(1)
        else:
            raise RuntimeError("relay HTTP health failed")
        report.update(status="PASS", stage="deployed_pending_full_verification", http_health=200)
    except Exception as error:
        report.update(status="BLOCKED", error_type=type(error).__name__)
        if admin_replaced:
            try:
                # A create gate may have created a stopped container before returning failure.
                if not new_id:
                    candidate = docker("ps", "-aq", "--filter", "name=^/" + admin_name + "$").decode().strip()
                    if candidate:
                        new_id = inspect(candidate)["Id"]
                if new_id:
                    info = inspect(new_id)
                    assert info["Image"] == image and info["Name"] == "/" + admin_name
                    if info["State"]["Running"]:
                        docker("stop", "-t", "20", new_id)
                    if NET in inspect(new_id)["NetworkSettings"]["Networks"]:
                        docker("network", "disconnect", "--force", NET, new_id)
                # Data mismatch requires a separate decision; never repair/overwrite DB.
                if report["stage"] == "data_after_startup":
                    report["rollback"] = "STOPPED: data mismatch requires separate approval"
                else:
                    create(ORIGINAL["admin"]["Image"], rollback=True)
                    rollback = inspect(admin_name + "-rollback-phase5")
                    docker("start", rollback["Id"])
                    healthy(rollback["Id"])
                    data_gate("data-after-rollback.json")
                    report["rollback"] = "PASS"
                    report["rollback_admin_id"] = rollback["Id"]
            except Exception as rollback_error:
                report["rollback"] = "BLOCKED: " + type(rollback_error).__name__
    finally:
        (HERE / "deployment.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("DEPLOYMENT PREFLIGHT BLOCKED: " + type(error).__name__ + "; no details logged")
        raise SystemExit(1)
