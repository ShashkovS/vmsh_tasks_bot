"""Run on the GlitchTip host as root; isolated, non-login release uploaders."""
import json
import subprocess
from pathlib import Path

code = '''
import json
from django.contrib.auth import get_user_model
from apps.organizations_ext.models import Organization
from apps.projects.models import Project
from apps.teams.models import Team
from apps.api_tokens.models import APIToken
result = {}
for slug, frontend, origin in [('vmsh', 'vmshpwa', 'https://vmsh.shashkovs.ru'),
                                ('tlf', 'tlfpwa', 'https://prep.leaders.tech')]:
    org = Organization.objects.get(slug=slug)
    user, _ = get_user_model().objects.get_or_create(email='glitchtip-uploader-'+slug+'@leaders.tech')
    user.set_unusable_password()
    user.is_staff = False
    user.is_superuser = False
    user.save()
    member = org.organization_users.filter(user=user).first() or org.add_user(user)
    Team.objects.get(organization=org, slug='developers').members.add(member)
    token, _ = APIToken.objects.get_or_create(user=user, label='production release sourcemaps')
    token.scopes = 0
    token.add_permissions(['project:releases', 'project:read', 'org:read'])
    front = Project.objects.get(organization=org, slug=frontend)
    back = Project.objects.get(organization=org, slug='backend')
    result[slug] = dict(organization=slug, project=frontend, portal_origin=origin,
                       frontend_dsn=front.projectkey_set.get(is_active=True).get_dsn(),
                       backend_dsn=back.projectkey_set.get(is_active=True).get_dsn(),
                       token=token.token)
print(json.dumps(result))
'''
process = subprocess.run(
    ['docker', 'compose', '--project-directory', '/opt/glitchtip', 'exec', '-T',
     'web', 'python', 'manage.py', 'shell', '-c', code],
    check=True, capture_output=True, text=True,
)
metadata = json.loads(process.stdout.strip().splitlines()[-1])
for slug, item in metadata.items():
    path = Path('/opt/glitchtip/portal-' + slug + '.json')
    path.touch(mode=0o600, exist_ok=True)
    path.chmod(0o600)
    path.write_text(json.dumps(item, indent=2) + '\n')
print('Two isolated release uploaders provisioned; private server files only')
