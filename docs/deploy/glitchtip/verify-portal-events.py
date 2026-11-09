"""Host-only proof for known synthetic event IDs, without printing event payloads."""
import argparse
import json
import subprocess
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--events', type=Path, required=True)
args = parser.parse_args()
expected = json.loads(args.events.read_text())
code = '''
import json,sys
from apps.issue_events.models import IssueEvent
expected=json.load(sys.stdin)
result=[]
for item in expected:
 event=IssueEvent.objects.filter(event_id=item['event_id']).select_related('issue','organization').first()
 if event is None: continue
 frames=event.data.get('exception',{}).get('values',[{}])[0].get('stacktrace',{}).get('frames',[])
 result.append(dict(event_id=str(event.event_id).replace('-',''),organization=event.organization.slug,project=event.issue.project_id,
                    frames=[{key:frame.get(key) for key in ('filename','lineno','colno','function')} for frame in frames]))
print(json.dumps(result))
'''
for attempt in range(30):
    process = subprocess.run(
        ['docker', 'compose', '--project-directory', '/opt/glitchtip', 'exec', '-T',
         'web', 'python', 'manage.py', 'shell', '-c', code],
        input=json.dumps(expected), text=True, capture_output=True, check=True,
    )
    result = json.loads(process.stdout.strip().splitlines()[-1])
    if len(result) == len(expected):
        break
    time.sleep(1)
assert len(result) == len(expected), 'Not every synthetic event persisted'
for item, actual in zip(expected, result):
    assert item['organization'] == actual['organization'] and item['project'] == actual['project']
    assert actual['frames']
    if item['project'] in (1, 3):
        assert any((frame['filename'] or '').endswith(item['expected_source']) and frame['lineno'] == item['expected_line'] for frame in actual['frames']), 'Original TypeScript location not resolved'
print(json.dumps(result, indent=2))
