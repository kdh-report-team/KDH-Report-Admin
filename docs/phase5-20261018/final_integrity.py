"""Read-only final gates; no resource mutation."""
import ast
import io
import json
from pathlib import Path
import subprocess
import tarfile

from cold_backup import HERE, RUN, digest, docker, original_gate

root = HERE.parent.parent
baseline = json.loads((HERE / "baseline.json").read_text(encoding="utf-8-sig"))
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root).decode().strip()
branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=root).decode().strip()
assert head == baseline["head"] and branch == baseline["branch"]
changed = [path for path, expected in baseline["hashes"].items()
           if not (root / path).is_file() or digest((root / path).read_bytes()) != expected]
assert not changed, "Existing files changed"
assert subprocess.run(["git", "diff", "--check"], cwd=root, capture_output=True).returncode == 0
scripts = list(HERE.glob("*.py"))
for script in scripts:
    ast.parse(script.read_text(encoding="utf-8"))
runtime = json.loads((HERE / "runtime-baseline.json").read_text(encoding="utf-8-sig"))
originals = original_gate(runtime)
for expected, current in zip(runtime, originals):
    assert current["RestartCount"] == expected["RestartCount"]
    assert {key: current["State"][key] for key in expected["state"]} == expected["state"]
    assert current["HostConfig"]["PortBindings"] == expected["bindings"]
    assert current["HostConfig"]["RestartPolicy"] == expected["restart_policy"]
    assert set(current["NetworkSettings"]["Networks"]) == set(expected["networks"])
    for name, network in expected["networks"].items():
        assert {key: current["NetworkSettings"]["Networks"][name][key] for key in network} == network
admin = next(x for x in originals if "-admin-" in x["Name"])
env = dict(item.split("=", 1) for item in admin["Config"]["Env"])
artifacts = [p for p in HERE.iterdir() if p.is_file()] + [root / "KDH_PHASE5_SANDBOX_DEPLOYMENT_PLAN.md"]
sensitive_keys = [key for key in env if any(word in key.upper() for word in ("SECRET", "PASSWORD", "ENCRYPTION_KEY", "DATABASE_URL", "TOKEN"))]
for artifact in artifacts:
    content = artifact.read_bytes()
    for key in sensitive_keys:
        if len(env[key]) >= 12:
            assert env[key].encode() not in content, "Sensitive value detected; do not publish evidence"
# Copy only known source file from stopped Admin, in memory; no container start.
archive_data = docker("cp", admin["Id"] + ":/app/kdh/migrations.py", "-")
with tarfile.open(fileobj=io.BytesIO(archive_data)) as archive:
    members = [m for m in archive.getmembers() if m.isfile()]
    assert len(members) == 1
    migration_bytes = archive.extractfile(members[0]).read()
assert migration_bytes == (root / "kdh/migrations.py").read_bytes()
result = {"head": head, "branch": branch, "baseline_files_checked": len(baseline["hashes"]),
    "changed_existing_files": changed, "all_original_runtime_projections_unchanged": True,
    "scripts_syntax_pass": len(scripts), "git_diff_check": "PASS", "known_secret_value_scan": "PASS",
    "migration_bytes_match_stopped_admin": True, "migration_sha256": digest(migration_bytes),
    "new_files_scope": ["KDH_PHASE5_SANDBOX_DEPLOYMENT_PLAN.md", "docs/phase5-20261018/"],
    "new_image_built": False, "original_resources_started": False, "status": "PASS"}
(HERE / "git-integrity.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
