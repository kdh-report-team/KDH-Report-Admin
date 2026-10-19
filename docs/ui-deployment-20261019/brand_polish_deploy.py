"""Presentation-only follow-up using the verified sandbox deployment procedure."""
import json
from pathlib import Path
import subprocess
import sys
import traceback

import multiplatform_deploy as deployment

deployment.EXPECTED_ADMIN_ID = '3081d4b8d34970759f82d341697d3f0decd2f74ae714bdde476cead499f28ca8'
deployment.EXPECTED_ADMIN_IMAGE = 'sha256:926d563949e1ecfa70aca33e0aff42f1e73f9f184178a27a099107833ea8c626'
deployment.PREVIOUS_EVIDENCE = 'multiplatform-deployment-result.json'
deployment.ROLLBACK_SUFFIX = '-before-brand-polish-20261019'
deployment.ARTIFACTS = {key: 'brand-polish-' + key + '.json' for key in deployment.ARTIFACTS}
BASE_TAG = 'kdh-admin-meta:multiplatform-20261019-36536d720762-r3'


def prepare():
    d = deployment
    if any(d.artifact(key).exists() for key in d.ARTIFACTS):
        raise RuntimeError('evidence already exists')
    baseline = d.original_preflight()
    files = d.source_files()
    previous = d.prior.app_hashes(d.EXPECTED_ADMIN_ID)
    current = {name: d.digest(raw) for name, raw in files.items()}
    changed = sorted(name for name in set(previous) | set(current) if previous.get(name) != current.get(name))
    allowed = {'static/ui.js', 'static/views.js', 'static/admin-refinement.css'}
    if any(name not in allowed and not name.startswith('static/brands/') for name in changed):
        raise RuntimeError('deployment includes changes beyond presentation scope')
    if d.docker_json('image', 'inspect', BASE_TAG)[0]['Id'] != d.EXPECTED_ADMIN_IMAGE:
        raise RuntimeError('base image changed')
    baseline['presentation_files_changed'] = changed
    d.save('preflight', baseline)
    d.save('backup', d.backup_and_restore(baseline))
    context, manifest = d.context_tar(files, BASE_TAG)
    tag = 'kdh-admin-meta:brand-polish-20261019-' + manifest['aggregate_sha256'][:12]
    if d.docker('image', 'ls', '-q', tag).strip():
        raise RuntimeError('immutable tag exists')
    manifest.update({'tag': tag, 'file_count': len(files), 'base_image_id': d.EXPECTED_ADMIN_IMAGE,
                     'build_context_sha256': d.digest(context), 'secrets_included': False})
    d.save('manifest', manifest)
    result = subprocess.run(['docker', 'build', '--network=none', '--pull=false', '--label',
                             'kdh.foundation.source-sha256=' + manifest['aggregate_sha256'], '-t', tag, '-'],
                            input=context, capture_output=True)
    (d.HERE / 'brand-polish-build.log').write_bytes(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError('image build failed')
    image_id = d.docker_json('image', 'inspect', tag)[0]['Id']
    if d.docker_json('image', 'inspect', BASE_TAG)[0]['Id'] != d.EXPECTED_ADMIN_IMAGE:
        raise RuntimeError('base image changed during build')
    d.save('build', {'status': 'PASS', 'tag': tag, 'image_id': image_id,
                     'source_sha256': manifest['aggregate_sha256']})
    d.save('smoke', d.create_smoke(image_id, manifest))
    print(json.dumps({'stage': 'PREPARED', 'build': 'PASS', 'smoke': 'PASS', 'tag': tag}))


if __name__ == '__main__':
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in {'prepare', 'deploy'}:
            raise RuntimeError('invalid stage')
        {'prepare': prepare, 'deploy': deployment.deploy}[sys.argv[1]]()
    except Exception as exc:
        frames = [{'file': Path(frame.filename).name, 'line': frame.lineno}
                  for frame in traceback.extract_tb(exc.__traceback__)]
        print(json.dumps({'status': 'BLOCKED', 'type': type(exc).__name__, 'frames': frames}))
        raise SystemExit(1)
