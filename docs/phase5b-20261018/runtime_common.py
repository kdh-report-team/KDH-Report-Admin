"""Sanitized read-only probes for the exact approved Phase 3 PostgreSQL."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "phase5-20261018"
ROOT = HERE.parents[1]
sys.path.insert(0, str(PRIOR))
from cold_backup import RUN, digest, docker, inspect

BASE = json.loads((PRIOR / "runtime-baseline.json").read_text(encoding="utf-8-sig"))
ORIGINAL = {kind: next(c for c in BASE if marker in c["Name"]) for kind, marker in
            (("pg", "-pg-"), ("admin", "-admin-"), ("gateway", "-egress-"), ("relay", "-relay-"))}
NET = "kdh-meta-2b-net-" + RUN


def original(kind):
    expected = ORIGINAL[kind]
    current = inspect(expected["Id"])
    assert current["Image"] == expected["Image"] and current["Mounts"] == expected["mounts"]
    return current


def sql(query):
    pg = original("pg")
    assert pg["State"]["Running"]
    assert set(pg["NetworkSettings"]["Networks"]) == {NET}
    assert not pg["HostConfig"]["PortBindings"]
    role = dict(x.split("=", 1) for x in pg["Config"]["Env"])["POSTGRES_USER"]
    return docker("exec", "-i", pg["Id"], "psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-U", role,
        "-d", "meta_acceptance_20261016_132836", data=("BEGIN READ ONLY; " + query + "; COMMIT;").encode()).decode().strip()


def rows(query):
    return json.loads(sql("SELECT coalesce(json_agg(t),'[]'::json) FROM (" + query + ") t"))


def data_gate(filename):
    baseline = json.loads((PRIOR / "restore-result.json").read_text())
    evidence = {"database": sql("SELECT current_database()"), "read_only": sql("SHOW transaction_read_only"), "tables": {}}
    assert evidence["database"] == baseline["database"] and evidence["read_only"] == "on"
    for table, expected in baseline["table_integrity"].items():
        raw = sql("SELECT coalesce(jsonb_agg(t ORDER BY to_jsonb(t)::text),'[]'::jsonb) FROM " + table + " t")
        actual = {"rows": len(json.loads(raw)), "sha256": digest(raw.encode())}
        evidence["tables"][table] = actual
        assert actual == expected, "business data differs from approved backup"
    migrations = rows("SELECT version,name,applied_at FROM schema_migrations ORDER BY version")
    assert migrations == baseline["migrations"]
    evidence["migrations"] = [r["version"] for r in migrations]
    assets = rows("SELECT id,client_id,provider,asset_type,external_id,name,enabled FROM source_assets ORDER BY id")
    assert assets == baseline["assets"]
    evidence["assets"] = assets
    assert sql("SELECT count(*) FROM clients WHERE id='client_meta_sandbox' AND active=1") == "1"
    where = "client_id='client_meta_sandbox' AND asset_id='cff1f3d5e6f433e021850fbde5b1d3f3' AND metric_date BETWEEN '2026-09-19' AND '2026-10-16'"
    evidence["period_counts"] = rows("SELECT entity_type,count(*) AS rows,count(DISTINCT entity_id) AS entities,count(DISTINCT metric_date) AS days FROM daily_metrics WHERE " + where + " GROUP BY entity_type ORDER BY entity_type")
    assert evidence["period_counts"] == json.loads((PRIOR / "period-verification.json").read_text())["period_counts"]
    assert sql("SELECT count(*) FROM jobs WHERE status IN ('queued','running')") == "0"
    assert sql("SELECT count(*) FROM (SELECT 1 FROM daily_metrics GROUP BY asset_id,entity_type,entity_id,metric_date,dimension_key HAVING count(*)>1) t") == "0"
    from cryptography.fernet import Fernet
    admin_env = dict(x.split("=", 1) for x in original("admin")["Config"]["Env"])
    ciphertext = sql("SELECT encode(value,'hex') FROM secrets WHERE name='meta:client_meta_sandbox'")
    grant = json.loads(Fernet(admin_env["ENCRYPTION_KEY"].encode()).decrypt(bytes.fromhex(ciphertext)))
    evidence["oauth"] = {"decrypt_with_existing_key": True, "access_token_present": bool(grant.get("access_token")),
        "stored_scopes": grant.get("scopes", []), "live_validity_checked": False}
    evidence["new_jobs_snapshots_attestations_releases"] = 0
    evidence["status"] = "PASS"
    (HERE / filename).write_text(json.dumps(evidence, indent=2) + "\n")
    return evidence
