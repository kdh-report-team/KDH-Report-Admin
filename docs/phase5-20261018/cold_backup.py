"""Phase 5 only: read-only original mounts; encrypted backups; no original start.

Run once with --execute. All helpers remain stopped for inspection. No cleanup.
Only sanitized evidence is written into the repository. Backup keys use Windows
DPAPI CurrentUser; encrypted archives/config live in a private directory outside it.
"""
import ctypes
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import uuid

from cryptography.fernet import Fernet

HERE = Path(__file__).resolve().parent
RUN = "20261016-132836-5c512a53"
LABEL = "kdh.phase5.backup"


def command(args, data=None):
    result = subprocess.run(args, input=data, capture_output=True)
    if result.returncode:
        # Never echo subprocess stderr, arguments or decrypted data.
        raise RuntimeError("subprocess failed (output withheld)")
    return result.stdout


def docker(*args, data=None):
    return command(["docker", *args], data)


def inspect(name):
    return json.loads(docker("inspect", name))[0]


def digest(value):
    return hashlib.sha256(value).hexdigest()


class Blob(ctypes.Structure):
    _fields_ = [("length", ctypes.c_ulong), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def dpapi(value, decrypt=False):
    buffer = ctypes.create_string_buffer(value)
    source = Blob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    api = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if not api(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise RuntimeError("DPAPI operation failed")
    try:
        return ctypes.string_at(target.data, target.length)
    finally:
        ctypes.windll.kernel32.LocalFree(target.data)


def original_gate(baseline):
    originals = [inspect(item["Id"]) for item in baseline]
    volumes = set()
    for expected, current in zip(baseline, originals):
        assert current["Name"] == expected["Name"]
        assert current["Image"] == expected["Image"]
        assert not current["State"]["Running"]
        assert current["State"]["StartedAt"] == expected["state"]["StartedAt"]
        assert current["State"]["FinishedAt"] == expected["state"]["FinishedAt"]
        assert current["Mounts"] == expected["mounts"]
        for mount in current["Mounts"]:
            if mount["Type"] == "volume":
                assert RUN in mount["Name"]
                volumes.add(mount["Name"])
    for container_id in docker("ps", "-q").decode().split():
        assert not any(m.get("Name") in volumes for m in inspect(container_id)["Mounts"])
    return originals


ARCHIVE = r'''
import os, pathlib, sys, tarfile
root = pathlib.Path('/source')
for path in root.rglob('*'):
    if path.is_symlink() or not (path.is_file() or path.is_dir()):
        raise SystemExit(71)
with tarfile.open(fileobj=sys.stdout.buffer, mode='w|', format=tarfile.PAX_FORMAT) as archive:
    archive.add(root, arcname='data')
'''


def read_volume(volume, image, prefix, evidence, kind):
    name = prefix + "-" + kind
    assert not json.loads(docker("ps", "-a", "--filter", "name=^/" + name + "$", "--format", "json") or "[]")
    container_id = docker(
        "create", "--name", name, "--label", LABEL + "=" + prefix,
        "--network", "none", "--read-only", "--log-driver", "none",
        "--user", "0:0", "--cap-drop", "ALL", "--cap-add", "DAC_OVERRIDE",
        "--security-opt", "no-new-privileges", "--memory", "256m", "--cpus", "0.5",
        "--mount", "type=volume,src=" + volume + ",dst=/source,readonly,volume-nocopy",
        "--entrypoint", "python", image, "-B", "-c", ARCHIVE,
    ).decode().strip()
    created = inspect(container_id)
    assert created["HostConfig"]["NetworkMode"] == "none"
    assert len(created["Mounts"]) == 1 and created["Mounts"][0]["RW"] is False
    evidence.setdefault("helpers", []).append({"id": container_id, "name": name, "source_read_only": True})
    result = docker("start", "-a", container_id)
    assert inspect(container_id)["State"]["ExitCode"] == 0
    return result


def main():
    assert sys.argv[1:] == ["--execute"]
    assert not (HERE / "backup-result.json").exists(), "Use existing backup; do not repeat blindly"
    assert docker("context", "show").decode().strip() == "desktop-linux"
    baseline = json.loads((HERE / "runtime-baseline.json").read_text(encoding="utf-8-sig"))
    originals = original_gate(baseline)
    pg = next(x for x in originals if "-pg-" in x["Name"])
    admin = next(x for x in originals if "-admin-" in x["Name"])
    assert not json.loads(docker("image", "inspect", admin["Image"]))[0]["Config"].get("Volumes")
    prefix = "kdh-phase5-20261018-" + uuid.uuid4().hex[:8]
    private = Path(os.environ["LOCALAPPDATA"]) / "KDH-Meta-Backups" / prefix
    private.mkdir(parents=True, exist_ok=False)
    acl = "$p=$args[0]; $a=New-Object System.Security.AccessControl.DirectorySecurity; $a.SetAccessRuleProtection($true,$false); $s=[System.Security.Principal.WindowsIdentity]::GetCurrent().User; foreach($i in @($s,[System.Security.Principal.SecurityIdentifier]'S-1-5-18')){$a.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule($i,'FullControl','ContainerInherit,ObjectInherit','None','Allow')))}; Set-Acl -LiteralPath $p -AclObject $a; $b=Get-Acl -LiteralPath $p; if(-not $b.AreAccessRulesProtected){exit 9}"
    os.environ["KDH_PHASE5_BACKUP_DIRECTORY"] = str(private)
    acl = acl.replace("$p=$args[0]", "$ErrorActionPreference='Stop'; $p=$env:KDH_PHASE5_BACKUP_DIRECTORY")
    command(["powershell", "-NoProfile", "-Command", acl])
    key = Fernet.generate_key()
    protected = dpapi(key)
    assert dpapi(protected, decrypt=True) == key
    (private / "backup-key.dpapi").write_bytes(protected)
    cipher = Fernet(key)
    evidence = {"run_id": RUN, "test_prefix": prefix, "private_backup_directory": str(private),
                "encryption": "Fernet; key protected by Windows DPAPI CurrentUser", "private_acl": True,
                "originals_stopped": True, "archives": {}, "helpers": []}
    try:
        for kind, container in (("postgres", pg), ("appdata", admin)):
            original_gate(baseline)
            volume = next(m["Name"] for m in container["Mounts"] if m["Type"] == "volume")
            first = read_volume(volume, admin["Image"], prefix, evidence, kind + "-read1")
            second = read_volume(volume, admin["Image"], prefix, evidence, kind + "-read2")
            assert digest(first) == digest(second), "Source changed between read-only copies"
            with tarfile.open(fileobj=io.BytesIO(first), mode="r:") as archive:
                members = archive.getmembers()
                assert all(m.isfile() or m.isdir() for m in members)
                if kind == "postgres":
                    assert archive.extractfile("data/PG_VERSION").read().strip() == b"16"
                    assert archive.getmember("data/global/pg_control").size > 0
            encrypted = cipher.encrypt(first)
            assert digest(cipher.decrypt(encrypted)) == digest(first)
            filename = kind + ".tar.fernet"
            (private / filename).write_bytes(encrypted)
            evidence["archives"][kind] = {"volume": volume, "file": filename, "archive_sha256": digest(first),
                "encrypted_sha256": digest(encrypted), "bytes": len(first), "entries": len(members),
                "two_independent_reads_match": True, "decrypt_roundtrip": True}
            print(kind + ": READ-ONLY BACKUP PASS", flush=True)
        config = Path(os.environ["LOCALAPPDATA"]) / "KDH-Meta-Acceptance-Secrets" / RUN / "admin.config"
        encrypted = cipher.encrypt(config.read_bytes())
        assert cipher.decrypt(encrypted) == config.read_bytes()
        (private / "admin.config.fernet").write_bytes(encrypted)
        evidence["config_backup"] = {"encrypted_sha256": digest(encrypted), "decrypt_roundtrip": True}
        original_gate(baseline)
        evidence["status"] = "PASS"
    except Exception as error:
        evidence["status"] = "BLOCKED"
        evidence["error_type"] = type(error).__name__
        raise
    finally:
        (HERE / "backup-result.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("BACKUP BLOCKED: " + type(error).__name__ + " (details withheld)")
        sys.exit(1)
