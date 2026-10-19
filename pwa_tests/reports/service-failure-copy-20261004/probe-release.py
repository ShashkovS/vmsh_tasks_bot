"""Read-only release proof; vmshpwa/docs/service-failure-copy-20261004.md."""

import json
import subprocess
import sys
from pathlib import Path

mode, target = sys.argv[1:3]
base = Path('/web/vmsh_tasks_bot')
code = base / 'vmsh_tasks_bot'
revision = subprocess.check_output(
    ['git', '-c', f'safe.directory={code}', '-C', str(code), 'rev-parse', 'HEAD'],
    text=True,
).strip()
assert revision == target
assert 'STUDENT_EFFECTIVE_RESULTS_CTES' in (code / 'db_methods/pwa/content.py').read_text()
assert 'Проблема на нашей стороне' in (code / 'vmshpwa/packages/app-shell/src/service-availability.tsx').read_text()
current = (base / 'vmshpwa/current').resolve()
builds = {audience: json.loads((current / audience / 'build-provenance.json').read_text())
          for audience in ('landing', 'student', 'family', 'staff')}
assert all(build['releaseId'] == current.name and build['profile'] == 'production'
           and not build['prototype'] and not build['msw'] for build in builds.values())
services = ['vmshpwa.service', 'vmsh-analytics.timer']
services += ['gunicorn.vmsh_tasks_bot.service'] if mode == 'vmsh' else ['vmshzoom.service', 'nats.service']
states = {service: subprocess.check_output(['systemctl', 'is-active', service], text=True).strip()
          for service in services}
assert all(state == 'active' for state in states.values())
assert not (base / 'vmshpwa/runtime/service-updating').exists()
report = dict(host=mode, source_revision=revision, frontend_release=current.name,
              production_frontend=True, services=states, maintenance_cleared=True)
if mode == 'tlf':
    record = base / 'deploy/releases' / current.name
    assert current.name == f'tlfprep-20261004-service-copy-{target[:12]}'
    pids = {service: subprocess.check_output(['systemctl', 'show', '-p', 'MainPID', '--value', service], text=True).strip()
            for service in ('vmshpwa.service', 'vmshzoom.service', 'nats.service')}
    assert all(pid == (record / f'{service}.pid-before').read_text().strip() for service, pid in pids.items())
    report['service_pids_unchanged'] = pids
    assert 'OK' in (record / 'credentials-check.log').read_text()
    report.update(credentials_unchanged=True,
                  backup_before=json.loads((record / 'backup-before.json').read_text()),
                  backup_after=json.loads((record / 'backup-after.json').read_text()))
print(json.dumps(report, indent=2))
