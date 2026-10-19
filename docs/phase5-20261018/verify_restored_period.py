"""Read-only period and restart checks against the Phase 5 copy only."""
import json
import time
from cold_backup import HERE, LABEL, digest, docker, inspect, original_gate

result = json.loads((HERE / "restore-result.json").read_text())
assert result["status"] == "PASS"
container_id = result["container_id"]
clone = inspect(container_id)
assert clone["Config"]["Labels"][LABEL] == result["test_prefix"]
assert clone["HostConfig"]["NetworkMode"] == "none"
assert len(clone["Mounts"]) == 1 and clone["Mounts"][0]["Name"] == result["volumes"]["postgres"]["name"]
originals = original_gate(json.loads((HERE / "runtime-baseline.json").read_text(encoding="utf-8-sig")))
pg = next(x for x in originals if "-pg-" in x["Name"])
role = dict(x.split("=", 1) for x in pg["Config"]["Env"])["POSTGRES_USER"]


def sql(query):
    return docker("exec", "-i", container_id, "psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1",
        "-h", "/tmp", "-U", role, "-d", result["database"],
        data=("BEGIN READ ONLY; " + query + "; COMMIT;").encode()).decode().strip()


def rows(query):
    return json.loads(sql("SELECT coalesce(json_agg(t),'[]'::json) FROM (" + query + ") t"))


evidence = {}
try:
    docker("start", container_id)
    for _ in range(30):
        try:
            docker("exec", container_id, "pg_isready", "-h", "/tmp")
            break
        except RuntimeError:
            time.sleep(1)
    assert sql("SHOW transaction_read_only") == "on"
    for table, expected in result["table_integrity"].items():
        raw = sql("SELECT coalesce(jsonb_agg(t ORDER BY to_jsonb(t)::text),'[]'::jsonb) FROM " + table + " t")
        assert digest(raw.encode()) == expected["sha256"]
    evidence["all_table_hashes_unchanged_after_clone_restart"] = True
    where = "client_id='client_meta_sandbox' AND asset_id='cff1f3d5e6f433e021850fbde5b1d3f3' AND metric_date BETWEEN '2026-09-19' AND '2026-10-16'"
    evidence["period_counts"] = rows("SELECT entity_type,count(*) AS rows,count(DISTINCT entity_id) AS entities,count(DISTINCT metric_date) AS days FROM daily_metrics WHERE " + where + " GROUP BY entity_type ORDER BY entity_type")
    counts = {r["entity_type"]: r for r in evidence["period_counts"]}
    assert counts["post"]["rows"] == counts["post"]["entities"] == 14
    assert counts["page"]["rows"] == counts["page"]["days"] == 28
    metrics = rows("SELECT entity_type,metrics FROM daily_metrics WHERE " + where)
    evidence["metric_field_names"] = {kind: sorted({key for row in metrics if row["entity_type"] == kind for key in json.loads(row["metrics"])}) for kind in ("post", "page")}
    snapshots = rows("SELECT id,payload FROM source_snapshots ORDER BY id")
    evidence["snapshots"] = []
    for row in snapshots:
        payload = json.loads(row["payload"])
        evidence["snapshots"].append({"id": row["id"], "payload_sha256": digest(row["payload"].encode()),
            "top_level_field_names": sorted(payload), "json_valid": True})
    evidence["status"] = "PASS"
finally:
    docker("stop", "-t", "30", container_id)
    evidence["clone_final_state"] = inspect(container_id)["State"]["Status"]
    (HERE / "period-verification.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
print("14 posts / 28 Page dates / restart table integrity: PASS")
