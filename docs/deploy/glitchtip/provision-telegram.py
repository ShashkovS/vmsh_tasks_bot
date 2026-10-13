"""Root-only, owner-authorized VMSH bot reuse; migration-20261011.md."""
import json
import os
import secrets
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path('/opt/glitchtip')
handoff = ROOT / 'telegram-handoff.json'
credentials = json.loads(handoff.read_text())
path = ROOT / 'telegram.json'
existing = json.loads(path.read_text()) if path.exists() else {}
config = dict(credentials, projects={})
for key, org, project, label in [
    ('vmsh-frontend', 'vmsh', 'vmshpwa', 'ВМШ · frontend'),
    ('vmsh-backend', 'vmsh', 'backend', 'ВМШ · backend'),
    ('tlf-frontend', 'tlf', 'tlfpwa', 'TLF · frontend'),
    ('tlf-backend', 'tlf', 'backend', 'TLF · backend'),
]:
    previous = existing.get('projects', {}).get(key, {})
    config['projects'][key] = dict(organization=org, project=project, label=label,
                                  secret=previous.get('secret') or secrets.token_hex(32))
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, 'w') as stream:
    json.dump(config, stream, indent=2)
    stream.write('\n')
path.chmod(0o600)
subprocess.run(['systemctl', 'enable', '--now', 'glitchtip-telegram.service'], check=True, capture_output=True)
url = 'https://glitch.leaders.tech/_telegram/' + config['projects']['vmsh-frontend']['secret']
for attempt in range(30):
    try:
        request = urllib.request.Request(url, data=b'{"attachments":[]}', headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status == 202
        break
    except Exception:
        time.sleep(1)
else:
    raise RuntimeError('Telegram webhook did not become ready')
code = '''
import json, sys
from django.db import transaction
from apps.projects.models import Project
from apps.alerts.models import ProjectAlert, AlertRecipient
payload=json.load(sys.stdin)
result=[]
with transaction.atomic():
 for key,item in payload['projects'].items():
  project=Project.objects.get(organization__slug=item['organization'], slug=item['project'])
  alert,_=ProjectAlert.objects.update_or_create(project=project,name='Telegram new issues',defaults={'timespan_minutes':15,'quantity':1,'uptime':False})
  url='https://glitch.leaders.tech/_telegram/'+item['secret']
  AlertRecipient.objects.filter(alert=alert).exclude(recipient_type='webhook',url=url).delete()
  AlertRecipient.objects.update_or_create(alert=alert,recipient_type='webhook',url=url,defaults={'tags_to_add':[],'config':{}})
  result.append({'project':project.pk,'alert':alert.pk})
print(json.dumps(result))
'''
process = subprocess.run(
    ['docker', 'compose', '--project-directory', str(ROOT), 'exec', '-T', 'web',
     'python', 'manage.py', 'shell', '-c', code],
    input=json.dumps({'projects': config['projects']}), text=True, capture_output=True, check=True,
)
handoff.unlink()
print(json.dumps({'alerts': json.loads(process.stdout.strip().splitlines()[-1]),
                  'transport': 'Telegram', 'cooldown_seconds': 900}))
