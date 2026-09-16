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
    assert source.index("systemctl stop vmsh-analytics.timer") < source.index(
        "python -m vmshpwa.scripts.migrate_runtime"
    )
    assert source.index("systemctl stop vmsh-analytics.service") < source.index(
        "python -m vmshpwa.scripts.migrate_runtime"
    )
    assert source.index('CURRENT_STEP="activating frontend release"') < source.index(
        'rm -- "$MAINTENANCE_FILE"'
    )
    assert "http://127.0.0.1:8000/student/api/v1/runtime" in source
    on_error = source[source.index("on_error()") : source.index("trap on_error ERR")]
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
