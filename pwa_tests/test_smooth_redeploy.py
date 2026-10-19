"""Release maintenance contract; browser recovery runs via the isolated gateway."""

from pathlib import Path
import subprocess
import pytest
from vmshpwa.scripts.static_release import retain_release_assets

ROOT = Path(__file__).resolve().parents[1]


def test_cutover_order_and_no_unsafe_proxy_replay():
    source = (ROOT / "docs/deploy/deploy-vmsh-tasks-bot.sh").read_text()
    assert source.index('CURRENT_STEP="building frontend"') < source.index(
        'touch "$MAINTENANCE_FILE"'
    )
    assert source.index('touch "$MAINTENANCE_FILE"') < source.index(
        "systemctl stop vmshpwa.service"
    )
    rehearsal = source.index(
        'CURRENT_STEP="rehearsing database migrations and query performance"'
    )
    maintenance = source.index('CURRENT_STEP="enabling service maintenance"')
    assert rehearsal < maintenance
    assert source.index(
        "python -m vmshpwa.scripts.database_performance_guard", rehearsal
    ) < maintenance
    production_migration = source.index(
        "python -m vmshpwa.scripts.migrate_runtime", maintenance
    )
    assert source.index("systemctl stop vmsh-analytics.timer") < production_migration
    assert source.index("systemctl stop vmsh-analytics.service") < production_migration
    production_guard = source.index(
        'CURRENT_STEP="checking production database query performance"'
    )
    assert production_migration < production_guard
    assert production_guard < source.index(
        'CURRENT_STEP="starting backend services"'
    )
    assert source.index('CURRENT_STEP="activating frontend release"') < source.index(
        'rm -- "$MAINTENANCE_FILE"'
    )
    assert "http://127.0.0.1:8000/student/api/v1/runtime" in source
    on_error = source[source.index("on_error()") : source.index("trap on_error ERR")]
    assert "cleanup_migration_rehearsal" in on_error
    assert "trap cleanup_migration_rehearsal EXIT" in source
    assert 'rm -- "$MAINTENANCE_FILE"' not in on_error
    assert 'rm -- "$ANALYTICS_TIMER_STATE"' not in on_error
    subprocess.run(
        ["bash", "-n", str(ROOT / "docs/deploy/deploy-vmsh-tasks-bot.sh")], check=True
    )
    nginx = (ROOT / "vmshpwa/deploy/nginx/vmshpwa.conf.template").read_text()
    assert "non_idempotent" not in nginx
    assert nginx.count("if ($vmshpwa_service_state = updating) { return 503; }") == 6
    assert "location = /service-status" in nginx
    assert '"code":"service_updating"' in nginx
    assert "add_header X-VMSH-Service-State $vmshpwa_service_state always;" in nginx


def test_analytics_permissions_are_narrow_and_timer_state_is_durable():
    sudoers = (ROOT / "docs/deploy/vmsh-webhook-sudoers").read_text()
    assert "/usr/bin/systemctl stop vmsh-analytics.service" in sudoers
    assert "/usr/bin/systemctl start vmsh-analytics.timer" in sudoers
    assert "systemctl *" not in sudoers
    source = (ROOT / "docs/deploy/deploy-vmsh-tasks-bot.sh").read_text()
    assert 'if [[ ! -f "$ANALYTICS_TIMER_STATE" ]]' in source
    assert 'if [[ "$(<"$ANALYTICS_TIMER_STATE")" == active ]]' in source


def test_old_lazy_chunks_survive_and_collisions_fail_closed(tmp_path):
    old = tmp_path / "old" / "student" / "assets"
    old.mkdir(parents=True)
    (old / "task-abc123.js").write_text("old chunk")
    new = tmp_path / "new" / "student" / "assets"
    new.mkdir(parents=True)
    (new / "task-def456.js").write_text("new chunk")
    retain_release_assets(tmp_path / "old", tmp_path)
    retain_release_assets(tmp_path / "new", tmp_path)
    assets = tmp_path / "immutable-assets" / "student" / "assets"
    assert (assets / "task-abc123.js").read_text() == "old chunk"
    assert (assets / "task-def456.js").read_text() == "new chunk"
    (new / "task-abc123.js").write_text("different bytes")
    with pytest.raises(ValueError, match="collision"):
        retain_release_assets(tmp_path / "new", tmp_path)
    assert (assets / "task-abc123.js").read_text() == "old chunk"


@pytest.mark.parametrize("audience", ["student", "family", "staff", "metrics", "public"])
def test_health_probe_uses_trusted_socket_only_for_private_runtime(tmp_path, audience):
    import json
    import os

    source = (ROOT / "docs/deploy/deploy-vmsh-tasks-bot.sh").read_text()
    function = source[source.index("check_http_200()") : source.index("check_public_media_csp()")]
    # Exercise shell argument construction, not a text-only assertion.
    fake = tmp_path / "curl"
    fake.write_text("#!/usr/bin/env python3\nimport json,os,sys\n"
                    "open(os.environ['CAPTURE'], 'w').write(json.dumps(sys.argv[1:]))\n"
                    "print('200', end='')\n")
    fake.chmod(0o755)
    output = tmp_path / "arguments.json"
    url = ("https://vmsh.shashkovs.ru/student/" if audience == "public" else
           "http://127.0.0.1:8000/metrics" if audience == "metrics" else
           f"http://127.0.0.1:8000/{audience}/api/v1/runtime")
    script = function.replace("/usr/bin/curl", '"$FAKE_CURL"') + '\ncheck_http_200 test "$URL"\n'
    subprocess.run(["bash", "-eu", "-c", script], check=True, env={
        **os.environ, "FAKE_CURL": str(fake), "CAPTURE": str(output), "URL": url,
        "DEPLOY_DIR": str(tmp_path), "RELEASE_ROOT": "/release",
    }, capture_output=True)
    args = json.loads(output.read_text())
    if audience in {"student", "family", "staff"}:
        assert args[args.index("--unix-socket") + 1] == "/release/runtime/vmshpwa.sock"
        assert 'Forwarded: for="127.0.0.1";proto=https;host="vmsh.shashkovs.ru"' in args
        assert args[-1] == f"http://vmsh.shashkovs.ru/{audience}/api/v1/runtime"
    else:
        assert "--unix-socket" not in args
        assert not any("Forwarded:" in arg for arg in args)
        assert args[-1] == url
