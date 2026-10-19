"""Approved first mutation: start only the exact Phase 3 PG, then stop at gates."""
import json
import time
from runtime_common import HERE, PRIOR, BASE, NET, ORIGINAL, original, docker, inspect, data_gate
from cold_backup import original_gate

assert not (HERE / "postgres-start.json").exists()
assert json.loads((HERE / "preflight.json").read_text())["status"] == "PASS"
assert json.loads((HERE / "smoke.json").read_text())["status"] == "PASS"
original_gate(BASE)
report = {"container_id": ORIGINAL["pg"]["Id"]}
try:
    docker("start", ORIGINAL["pg"]["Id"])
    for _ in range(45):
        pg = original("pg")
        if pg["State"].get("Health", {}).get("Status") == "healthy":
            break
        assert pg["State"]["Running"]
        time.sleep(1)
    else:
        raise RuntimeError("PG health timeout")
    assert pg["NetworkSettings"]["Networks"][NET]["IPAddress"] == "192.168.0.2"
    assert not pg["HostConfig"]["PortBindings"]
    assert set(pg["NetworkSettings"]["Networks"]) == {NET}
    data_gate("data-before-admin.json")
    report.update(status="PASS", health="healthy", internal_ip="192.168.0.2", original_data_hashes_match=True)
except Exception as error:
    report.update(status="BLOCKED", error_type=type(error).__name__)
finally:
    (HERE / "postgres-start.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["status"] == "PASS" else 1)
