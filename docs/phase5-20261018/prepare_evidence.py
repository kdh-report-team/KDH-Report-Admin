"""Read-only source/runtime inspection; produce sanitized deployment artifacts."""
import io
import json
import os
from pathlib import Path
import re
import tarfile

from cold_backup import HERE, RUN, digest, docker, inspect, original_gate

ROOT = HERE.parent.parent
baseline = json.loads((HERE / "runtime-baseline.json").read_text(encoding="utf-8-sig"))
originals = original_gate(baseline)
admin = next(x for x in originals if "-admin-" in x["Name"])
previous = json.loads((ROOT / "docs/phase4-20261018/build-manifest.json").read_text())
files = {p: digest((ROOT / p).read_bytes()) for p in previous["files"]}
assert files == previous["files"], "Production source changed since Phase 4"
actual = {str(p.relative_to(ROOT)).replace("\\", "/") for directory in ("kdh", "static", "templates")
          for p in (ROOT / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
actual.update(("Dockerfile", ".dockerignore", "requirements.lock", "run.py"))
assert actual == set(files), "Deployment manifest missing or extra files"
for path in files:
    assert not any(part in (".env", "instance", ".git", "node_modules") for part in Path(path).parts)
tag = "kdh-admin-meta:phase5-20261018-" + previous["aggregate_sha256"][:12]
manifest = {**previous, "proposed_tag": tag, "built": False, "file_count": len(files),
            "matches_phase4": True, "all_production_paths_included": True,
            "existing_admin_image": admin["Image"]}
backup = json.loads((HERE / "backup-result.json").read_text())
context = Path(backup["private_backup_directory"]) / "source-context.tar"
assert not context.exists()
with tarfile.open(context, "w", format=tarfile.PAX_FORMAT) as archive:
    for path in sorted(files):
        content = (ROOT / path).read_bytes()
        info = tarfile.TarInfo(path)
        info.size = len(content)
        info.mode = 0o644
        archive.addfile(info, io.BytesIO(content))
manifest["build_context"] = str(context)
manifest["build_context_sha256"] = digest(context.read_bytes())
(HERE / "deployment-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

env = dict(item.split("=", 1) for item in admin["Config"]["Env"])
config_path = Path(os.environ["LOCALAPPDATA"]) / "KDH-Meta-Acceptance-Secrets" / RUN / "admin.config"
raw = config_path.read_text(encoding="utf-8-sig")
try:
    config = json.loads(raw)
except ValueError:
    config = dict(line.split("=", 1) for line in raw.splitlines() if "=" in line and not line.lstrip().startswith("#"))
safe_keys = ("JOB_MODE", "META_CLIENT_ID", "APP_URL", "META_REDIRECT_URI", "META_APP_ID", "META_CONFIG_ID", "ADMIN_SESSION_COOKIE_NAME", "COOKIE_SECURE")
config_evidence = {"safe_values": {k: env.get(k) for k in safe_keys},
    "presence": {k: "PRESENT" if env.get(k) else "MISSING" for k in ("ENCRYPTION_KEY", "META_APP_SECRET", "DATABASE_URL")},
    "config_matches_container": {k: config.get(k) == env.get(k) for k in (*safe_keys, "ENCRYPTION_KEY", "META_APP_SECRET", "DATABASE_URL")}}
assert all(config_evidence["config_matches_container"].values())
assert env["JOB_MODE"] == "request" and env["META_CLIENT_ID"] == "client_meta_sandbox"
(HERE / "config-compatibility.json").write_text(json.dumps(config_evidence, indent=2) + "\n", encoding="utf-8")

host_fields = ("ReadonlyRootfs", "CapDrop", "CapAdd", "SecurityOpt", "Memory", "NanoCpus", "PidsLimit", "Tmpfs", "RestartPolicy", "Init", "ShmSize", "Dns", "ExtraHosts", "LogConfig")
desired = {"name": admin["Name"].lstrip("/"), "image_tag": tag,
    "image_id_required_after_build": True,
    "Config": {k: admin["Config"].get(k) for k in ("User", "WorkingDir", "Cmd", "Entrypoint", "Healthcheck")},
    "HostConfig": {k: admin["HostConfig"].get(k) for k in host_fields},
    "env_source": "Copy ALL values from original Admin inspect into child process memory; do not log/write plaintext",
    "environment_keys": sorted(env),
    "mounts": [{"type": "volume", "source": "kdh-meta-2b-appdata-" + RUN, "target": "/app/instance", "read_only": False}],
    "network": {"name": "kdh-meta-2b-net-" + RUN, "ipv4": "192.168.0.3", "internal": True},
    "host_port_bindings": {}, "only_relay_publishes": "127.0.0.1:8191 -> 8090/tcp",
    "rollback_image": admin["Image"], "applied": False}
(HERE / "admin-desired-config.json").write_text(json.dumps(desired, indent=2) + "\n", encoding="utf-8")

run_root = Path("D:/KDH-Meta-Phase2B") / RUN
security_before = json.loads((ROOT / "docs/phase4-20261018/security-config-hashes.json").read_text())
security_now = {path: digest((run_root / path).read_bytes()) for path in security_before}
assert security_now == security_before
networks = []
for name in sorted({name for item in originals for name in item["NetworkSettings"]["Networks"]}):
    network = json.loads(docker("network", "inspect", name))[0]
    networks.append({k: network[k] for k in ("Name", "Id", "Internal", "IPAM")})
assert next(n for n in networks if "-net-" in n["Name"])["Internal"] is True
(HERE / "security-readiness.json").write_text(json.dumps({"security_files_unchanged": True, "hashes": security_now, "networks": networks}, indent=2) + "\n", encoding="utf-8")

# Only matching fixed phrases/timestamps, never full Docker Desktop log lines.
log = Path(os.environ["LOCALAPPDATA"]) / "Docker/log/host/com.docker.backend.exe.log"
signals = []
for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
    if "2026-10-18T11:48:" not in line:
        continue
    phrases = re.findall(r"starting WSL|starting Linux|starting the engine|starting engine|starting backend|starting Docker|Docker Desktop|WSL distro|engine started|engine is running|initializing|booting|restoring containers|Loading containers: start|Loading containers: done", line, flags=re.I)
    if phrases:
        timestamp = re.search(r"2026-10-18T11:48:[0-9:.]+Z?", line)
        signals.append({"timestamp": timestamp.group(0) if timestamp else None, "signals": phrases})
(HERE / "desktop-startup-signals.json").write_text(json.dumps(signals, indent=2) + "\n", encoding="utf-8")
print("61-file source context / corrected Admin config / isolation hashes: PASS")
