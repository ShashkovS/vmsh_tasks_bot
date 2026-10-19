"""Run as root on the host; credentials stay in /opt/glitchtip, never stdout."""

import argparse
import json
import os
import secrets
import subprocess
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email")
    args = parser.parse_args()
    path = Path("/opt/glitchtip/admin-credentials.json")
    if path.exists():
        credentials = json.loads(path.read_text())
    else:
        credentials = {"email": args.email or "admin@glitch.leaders.tech", "password": secrets.token_urlsafe(32)}
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(credentials, stream)
            stream.write("\n")
    target_email = args.email or credentials["email"]
    code = """
import json, sys
from django.contrib.auth import get_user_model
from django.db import transaction
from allauth.account.models import EmailAddress
payload = json.load(sys.stdin)
credentials, target_email = payload['credentials'], payload['target_email']
User = get_user_model()
with transaction.atomic():
    user = User.objects.filter(email=credentials['email']).first()
    created = user is None
    if created:
        user = User.objects.create_superuser(**credentials)
    if user.email != target_email:
        if User.objects.filter(email=target_email).exists():
            raise ValueError('Target email already belongs to another user')
        EmailAddress.objects.filter(user=user, email=user.email).delete()
        user.email = target_email
        user.save(update_fields=['email'])
    EmailAddress.objects.get_or_create(user=user, email=user.email, defaults={'verified':True, 'primary':True})
print(json.dumps({'administrator_created':created, 'email':user.email, 'superuser':user.is_superuser}))
"""
    subprocess.run(
        ["docker", "compose", "--project-directory", "/opt/glitchtip", "exec", "-T",
         "web", "python", "manage.py", "shell", "-c", code],
        input=json.dumps({"credentials": credentials, "target_email": target_email}), text=True, check=True,
    )
    if credentials["email"] != target_email:
        credentials["email"] = target_email
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".admin-credentials.")
        with os.fdopen(fd, "w") as stream:
            json.dump(credentials, stream)
            stream.write("\n")
        os.replace(temporary, path)


if __name__ == "__main__":
    main()
