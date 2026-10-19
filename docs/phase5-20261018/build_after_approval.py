"""REVIEW ONLY: build the frozen allowlisted context after explicit approval."""
import json
from pathlib import Path
import subprocess
import sys
from cold_backup import HERE, digest, docker


def main():
    assert sys.argv[1:] == ["--approved-build"]
    assert docker("context", "show").decode().strip() == "desktop-linux"
    manifest = json.loads((HERE / "deployment-manifest.json").read_text())
    context = Path(manifest["build_context"])
    data = context.read_bytes()
    assert digest(data) == manifest["build_context_sha256"]
    assert not docker("image", "ls", "-q", manifest["proposed_tag"]).strip(), "Never overwrite a prepared tag"
    output = subprocess.run(["docker", "build", "--label", "kdh.phase5.source-sha256=" + manifest["aggregate_sha256"],
        "--label", "kdh.phase5.head=" + manifest["head"], "-t", manifest["proposed_tag"], "-"],
        input=data, capture_output=True)
    (context.parent / "image-build.log").write_bytes(output.stdout + output.stderr)
    if output.returncode:
        raise RuntimeError("build failed; inspect private build log")
    image = json.loads(docker("image", "inspect", manifest["proposed_tag"]))[0]
    record = {"image_id": image["Id"], "tag": manifest["proposed_tag"], "source_sha256": manifest["aggregate_sha256"],
              "created": image["Created"], "runtime_acceptance": "NOT TESTED"}
    (HERE / "approved-image-result.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print("IMAGE BUILT; runtime and deployment gates remain pending")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("BUILD STOPPED: " + type(error).__name__)
        raise SystemExit(1)
