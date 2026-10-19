"""Host-only deployment proof. Uses generated credentials without printing them."""

import http.cookiejar
import json
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


ROOT = Path("/opt/glitchtip")
ORIGIN = "https://glitch.leaders.tech"


def django(code: str, payload: dict) -> dict:
    process = subprocess.run(
        ["docker", "compose", "--project-directory", str(ROOT), "exec", "-T",
         "web", "python", "manage.py", "shell", "-c", code],
        input=json.dumps(payload), text=True, capture_output=True, check=True,
    )
    return json.loads(process.stdout.strip().splitlines()[-1])


def main() -> None:
    credentials = json.loads((ROOT / "admin-credentials.json").read_text())
    projects = json.loads((ROOT / "projects.json").read_text())
    settings = json.load(urllib.request.urlopen(ORIGIN + "/api/settings/", timeout=15))
    assert settings["version"] == "6.2.6"
    assert not settings["enableUserRegistration"]
    assert not settings["enableSocialAppsUserRegistration"]
    assert not settings["billingEnabled"]
    assert "mcp" in settings["enabledFeatures"]
    assert "email" not in settings["enabledFeatures"]
    with urllib.request.urlopen(ORIGIN + "/_health/", timeout=15) as response:
        assert response.read() == b"ok"
    with urllib.request.urlopen(ORIGIN + "/", timeout=15) as response:
        html = response.read().decode()
    scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
    assert scripts
    for script in scripts:
        url = urllib.parse.urljoin(ORIGIN + "/", script)
        assert urllib.parse.urlparse(url).netloc == "glitch.leaders.tech"
        with urllib.request.urlopen(url, timeout=15) as response:
            assert len(response.read()) > 100

    # Authenticate through the SPA's allauth endpoint; cookie values never leave this process.
    cookies = http.cookiejar.CookieJar()
    session = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
    session.open(ORIGIN + "/login", timeout=15).close()
    try:
        session.open(ORIGIN + "/_allauth/browser/v1/auth/session", timeout=15).close()
    except urllib.error.HTTPError as error:
        assert error.code == 401
    csrf = next(cookie.value for cookie in cookies if cookie.name == "csrftoken")
    request = urllib.request.Request(ORIGIN + "/_allauth/browser/v1/auth/login", data=json.dumps({
        "email": credentials["email"], "password": credentials["password"],
    }).encode(), headers={"Content-Type":"application/json", "Origin": ORIGIN,
                        "Referer": ORIGIN + "/login", "X-CSRFToken":csrf})
    session.open(request, timeout=15).close()
    organizations = json.load(session.open(ORIGIN + "/api/0/organizations/", timeout=15))
    assert {org["slug"] for org in organizations} == {"vmsh", "tlf"}
    assert any(cookie.name == "sessionid" and cookie.secure for cookie in cookies)

    initialize = {"jsonrpc":"2.0", "id":1, "method":"initialize", "params":{
        "protocolVersion":"2025-03-26", "capabilities":{},
        "clientInfo":{"name":"deployment-check", "version":"1"},
    }}
    request = urllib.request.Request(ORIGIN + "/mcp", data=json.dumps(initialize).encode(), headers={
        "Content-Type":"application/json", "Accept":"application/json, text/event-stream",
    })
    try:
        urllib.request.urlopen(request, timeout=15)
        raise AssertionError("MCP unexpectedly permitted unauthenticated access")
    except urllib.error.HTTPError as error:
        assert error.code == 401

    event_path = ROOT / "verification-event-ids.json"
    if event_path.exists():
        events = json.loads(event_path.read_text())
    else:
        events = []
        for org, name in [("vmsh", "vmshpwa"), ("tlf", "tlfpwa")]:
            project = projects[org][name]
            event_id = uuid4().hex
            key = urllib.parse.urlparse(project["dsn"]).username
            event = {
                "event_id": event_id, "timestamp": datetime.now(UTC).isoformat(),
                "platform":"javascript", "level":"error", "environment":"deployment-check",
                "release":"glitchtip-deploy-20261011",
                "exception":{"values":[{"type":"DeploymentCheckError",
                    "value":"GlitchTip deployment verification",
                    "stacktrace":{"frames":[{"filename":"https://prep.leaders.tech/student/assets/deployment-check.js",
                        "function":"verifyDeployment", "lineno":1, "colno":1, "in_app":True}]}}]},
            }
            envelope = "\n".join([json.dumps({"event_id":event_id, "dsn":project["dsn"]}),
                                  json.dumps({"type":"event"}), json.dumps(event)]) + "\n"
            source = "https://vmsh.shashkovs.ru" if org == "vmsh" else "https://prep.leaders.tech"
            request = urllib.request.Request(
                ORIGIN + f'/api/{project["id"]}/envelope/?sentry_key={key}&sentry_version=7',
                data=envelope.encode(), headers={"Content-Type":"application/x-sentry-envelope", "Origin":source},
            )
            with urllib.request.urlopen(request, timeout=15) as response:
                assert response.status == 200
                assert response.headers["Access-Control-Allow-Origin"] in {source, "*"}, "Ingest CORS missing"
            events.append({"organization":org, "project":project["id"], "event_id":event_id})

        # Also exercise an actual Sentry SDK against the independent backend project.
        result = django("""
import json, sys, sentry_sdk
payload = json.load(sys.stdin)
sentry_sdk.init(dsn=payload['dsn'], default_integrations=False, auto_enabling_integrations=False,
    auto_session_tracking=False, send_default_pii=False, environment='deployment-check',
    release='glitchtip-deploy-20261011', traces_sample_rate=0)
try:
    raise RuntimeError('GlitchTip SDK deployment verification')
except RuntimeError as error:
    event_id = sentry_sdk.capture_exception(error)
sentry_sdk.flush(timeout=15)
print(json.dumps({'event_id':event_id}))
""", {"dsn":projects["tlf"]["backend"]["dsn"]})
        assert result["event_id"]
        events.append({"organization":"tlf", "project":projects["tlf"]["backend"]["id"],
                       "event_id":result["event_id"]})
        event_path.write_text(json.dumps(events, indent=2) + "\n")
        event_path.chmod(0o600)

    checks = {"events":[]}
    for attempt in range(30):
        checks = django("""
import json, sys
from apps.issue_events.models import IssueEvent
expected = json.load(sys.stdin)['events']
result = []
for item in expected:
    event = IssueEvent.objects.filter(event_id=item['event_id']).select_related('issue', 'organization').first()
    if event is not None:
        frames = event.data.get('exception', {}).get('values', [{}])[0].get('stacktrace', {}).get('frames', [])
        result.append({'event_id':str(event.event_id).replace('-', ''), 'project':event.issue.project_id,
            'organization':event.organization.slug, 'has_stack':bool(frames)})
print(json.dumps({'events':result}))
""", {"events":events})
        if len(checks["events"]) == len(events):
            break
        time.sleep(1)
    assert len(checks["events"]) == len(events), "Worker did not persist every test event"
    assert all(event["has_stack"] for event in checks["events"])
    expected = {(event["event_id"], event["organization"], event["project"]) for event in events}
    actual = {(event["event_id"], event["organization"], event["project"]) for event in checks["events"]}
    assert actual == expected
    proof = {
        "verified_at":datetime.now(UTC).isoformat(), "origin":ORIGIN, "version":settings["version"],
        "https_login":True, "secure_session_cookie":True, "public_registration":False,
        "billing_enabled":False, "mcp_requires_authentication":True,
        "frontend_javascript_files":len(scripts), "organizations":["vmsh", "tlf"],
        "email_configured":False, **checks,
    }
    (ROOT / "verification.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
