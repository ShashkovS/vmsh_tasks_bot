"""Run as root after bootstrap; create independent namespaces for both portals."""

import json
import os
import subprocess
from pathlib import Path


credentials = json.loads(Path("/opt/glitchtip/admin-credentials.json").read_text())
code = """
import json, sys
from django.contrib.auth import get_user_model
from django.db import transaction
from apps.organizations_ext.models import Organization
from apps.projects.models import Project
from apps.teams.models import Team
user = get_user_model().objects.get(email=json.load(sys.stdin)['email'])
result = {}
with transaction.atomic():
    for slug, name, frontend in [('vmsh', 'VMSH', 'vmshpwa'), ('tlf', 'TLF', 'tlfpwa')]:
        org, _ = Organization.objects.get_or_create(slug=slug, defaults={'name':name})
        membership = org.organization_users.filter(user=user).first()
        if membership is None:
            membership = org.add_user(user)
        team, _ = Team.objects.get_or_create(organization=org, slug='developers')
        team.members.add(membership)
        result[slug] = {}
        for project_name, platform in [(frontend, 'javascript-react'), ('backend', 'python-aiohttp')]:
            project, _ = Project.objects.get_or_create(organization=org, name=project_name, defaults={'platform':platform})
            team.projects.add(project)
            result[slug][project_name] = {'id':project.pk, 'dsn':project.projectkey_set.get(is_active=True).get_dsn()}
print(json.dumps(result))
"""
process = subprocess.run(
    ["docker", "compose", "--project-directory", "/opt/glitchtip", "exec", "-T",
     "web", "python", "manage.py", "shell", "-c", code],
    input=json.dumps({"email": credentials["email"]}), text=True, check=True,
    capture_output=True,
)
metadata = json.loads(process.stdout.strip().splitlines()[-1])
path = Path("/opt/glitchtip/projects.json")
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as stream:
    json.dump(metadata, stream, indent=2)
    stream.write("\n")
print(json.dumps({org: {name: item['id'] for name, item in projects.items()}
                  for org, projects in metadata.items()}))
