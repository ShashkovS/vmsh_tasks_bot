"""Read-only release proof; vmshpwa/docs/lesson-statistics.md#staff-violin-polish-2026-10-05."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

mode, target = sys.argv[1:3]
base = Path('/web/vmsh_tasks_bot')
code = base / 'vmsh_tasks_bot'

def command(*args):
    return subprocess.check_output(args, text=True).strip()

revision = command('git', '-c', f'safe.directory={code}', '-C', str(code), 'rev-parse', 'HEAD')
assert revision == target
current = (base / 'vmshpwa/current').resolve()
expected_release = f'tlfprep-20261005-violin-polish-{target[:12]}'
assert current.name == expected_release if mode == 'tlf' else current.name.startswith(target[:12] + '-')
builds = {audience: json.loads((current / audience / 'build-provenance.json').read_text())
          for audience in ('landing', 'student', 'family', 'staff')}
assert all(build['releaseId'] == current.name and build['profile'] == 'production'
           and not build['prototype'] and not build['msw'] for build in builds.values())
source_paths = [
    'vmshpwa/packages/product/src/progress-charts.tsx',
    'vmshpwa/apps/staff/src/staff-distribution-colors.ts',
    'vmshpwa/apps/staff/src/lesson-statistics.tsx',
    'vmshpwa/apps/staff/src/staff-statistics-page.tsx',
]
chart = (code / source_paths[0]).read_text()
assert 'integerTicks = false' in chart and 'yScale.ticks(8).filter(Number.isInteger)' in chart
assert 'x1={cx - 10}' in chart and 'x2={cx + 10}' in chart
assert ' / 2) * 0.7]' in chart
for source_path in source_paths[2:]:
    source = (code / source_path).read_text()
    assert 'bandwidth={0.75}' in source and 'integerTicks' in source
    assert 'staffDistributionColorIndex' in source
services = ['vmshpwa.service', 'vmsh-analytics.timer']
services += ['gunicorn.vmsh_tasks_bot.service'] if mode == 'vmsh' else ['vmshzoom.service', 'nats.service']
states = {service: dict(state=command('systemctl','is-active',service),
                       pid=command('systemctl','show','-p','MainPID','--value',service))
          for service in services}
assert all(item['state'] == 'active' for item in states.values())
assert not (base / 'vmshpwa/runtime/service-updating').exists()
report = dict(host=mode, source_revision=revision, frontend_release=current.name,
              production_frontend=True, builds=builds, services=states, maintenance_cleared=True,
              source_sha256={source_path:hashlib.sha256((code/source_path).read_bytes()).hexdigest()
                             for source_path in source_paths})
if mode == 'tlf':
    record = base / 'deploy/releases' / current.name
    assert all(states[service]['pid'] == (record / f'{service}.pid-before').read_text().strip()
               for service in ('vmshpwa.service','vmshzoom.service','nats.service'))
    assert 'OK' in (record / 'credentials-check.log').read_text()
    report.update(service_pids_unchanged=True, credentials_unchanged=True,
                  backup_before=json.loads((record / 'backup-before.json').read_text()),
                  backup_after=json.loads((record / 'backup-after.json').read_text()))
print(json.dumps(report, indent=2))
