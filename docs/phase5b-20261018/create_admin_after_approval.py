"""REVIEW ARTIFACT ONLY. Creates (does not start) Admin after explicit approval.

Caller must first retain/rename the old Admin and release its network endpoint as
documented. No database calls, migrations, provider calls or automatic rollback.
Credentials are inherited only by the docker child process; no env file/log.
"""
import argparse
import json
import os
import subprocess

import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent / 'phase5-20261018'))
from cold_backup import HERE, RUN, docker, inspect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--approved-create", action="store_true")
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()
    assert args.approved_create, "Requires separate user deployment approval"
    assert docker("context", "show").decode().strip() == "desktop-linux"
    baseline = json.loads((HERE / "runtime-baseline.json").read_text(encoding="utf-8-sig"))
    original = next(x for x in baseline if "-admin-" in x["Name"])
    old = inspect(original["Id"])
    assert old["Image"] == original["Image"] and not old["State"]["Running"]
    assert old["Mounts"] == original["mounts"]
    image = json.loads(docker("image", "inspect", args.image_id))[0]
    assert image["Id"] == args.image_id and not image["Config"].get("Volumes")
    manifest = json.loads((HERE / "deployment-manifest.json").read_text())
    if args.rollback:
        assert args.image_id == original["Image"]
    else:
        assert image["Config"]["Labels"]["kdh.phase5.source-sha256"] == manifest["aggregate_sha256"]
        assert json.loads(docker("image", "inspect", manifest["proposed_tag"]))[0]["Id"] == args.image_id
    network = "kdh-meta-2b-net-" + RUN
    net = json.loads(docker("network", "inspect", network))[0]
    assert net["Internal"] and net["Id"] == original["networks"][network]["NetworkID"]
    # Stopped old endpoints must already be explicitly detached by the operator.
    for cid in docker("ps", "-aq", "--filter", "network=" + network).decode().split():
        attachment = inspect(cid)["NetworkSettings"]["Networks"].get(network, {})
        requested = (attachment.get("IPAMConfig") or {}).get("IPv4Address")
        # A retained before-E2 container has the same desired address but no
        # allocated endpoint. Preserve it unchanged; only this exact historical
        # inactive container is exempt from the configuration-only check.
        legacy = inspect(cid)
        inactive_retained = (
            legacy["Id"] == "af2d1346b5bfc2b544b0ccf844469d2dfbf98715aa289ade3e54ab778d76b86f"
            and not legacy["State"]["Running"]
            and not attachment.get("EndpointID") and not attachment.get("IPAddress")
            and legacy["Id"] not in net.get("Containers", {})
        )
        assert inactive_retained or (requested != "192.168.0.3" and attachment.get("IPAddress") != "192.168.0.3")
    name = original["Name"].lstrip("/") + ("-rollback-phase5" if args.rollback else "")
    assert not docker("ps", "-aq", "--filter", "name=^/" + name + "$").strip()
    values = dict(item.split("=", 1) for item in old["Config"]["Env"])
    assert values["JOB_MODE"] == "request" and values["META_CLIENT_ID"] == "client_meta_sandbox"
    child_env = dict(os.environ)
    child_env.update(values)
    command = ["docker", "create", "--pull", "never", "--name", name,
        "--label", "kdh.phase5.run=" + RUN,
        "--network", network, "--ip", "192.168.0.3", "--dns", "127.0.0.1",
        "--user", "kdh", "--workdir", "/app", "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--memory", "512m", "--cpus", "1",
        "--restart", "no", "--shm-size", "64m", "--log-driver", "json-file",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
        "--mount", "type=volume,src=kdh-meta-2b-appdata-" + RUN + ",dst=/app/instance,volume-nocopy",
        "--health-cmd", old["Config"]["Healthcheck"]["Test"][1],
        "--health-interval", "3s", "--health-timeout", "4s", "--health-retries", "10"]
    for key in sorted(values):
        command.extend(["--env", key])
    command.extend([args.image_id, "python", "run.py"])
    completed = subprocess.run(command, env=child_env, capture_output=True)
    if completed.returncode:
        raise RuntimeError("Admin create failed; output withheld; retain stopped resources")
    created = inspect(completed.stdout.decode().strip())
    assert not created["HostConfig"]["PortBindings"]
    assert set(created["NetworkSettings"]["Networks"]) == {network}
    assert created["HostConfig"]["ReadonlyRootfs"]
    assert dict(item.split("=", 1) for item in created["Config"]["Env"]) == values
    assert created["Image"] == args.image_id and not created["State"]["Running"]
    print("Admin created STOPPED; no published ports; environment equality PASS.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("STOP: " + type(error).__name__ + "; sensitive command details withheld")
        raise SystemExit(1)
