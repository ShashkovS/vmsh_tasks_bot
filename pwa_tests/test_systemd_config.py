from __future__ import annotations

from pathlib import Path

import pytest

from vmshpwa.scripts.systemd_config_check import (
    SystemdProfileError,
    check_systemd_profile,
)


ROOT = Path(__file__).resolve().parents[1]
UNIT_TEMPLATE = ROOT / "vmshpwa/deploy/systemd/vmshpwa.service.template"
ENV_TEMPLATE = ROOT / "vmshpwa/deploy/systemd/vmshpwa.env.example"


def _render(tmp_path: Path) -> tuple[Path, Path]:
    socket = tmp_path / "run/vmshpwa.sock"
    environment = tmp_path / "vmshpwa.env"
    replacements = {
        "@@REPOSITORY_DIR@@": str(ROOT),
        "@@ENV_FILE@@": str(environment),
        "@@SERVICE_USER@@": "vmshpwa",
        "@@SERVICE_GROUP@@": "nginx",
        "@@VENV_DIR@@": "/opt/vmshpwa/venv",
        "@@BACKEND_UNIX_SOCKET@@": str(socket),
        "@@DATABASE_DIR@@": "/srv/vmshpwa/db",
        "@@DATABASE_PATH@@": "/srv/vmshpwa/db/vmsh.sqlite3",
        "@@MEDIA_ROOT@@": "/srv/vmshpwa/media",
        "@@RUNTIME_WRITE_DIR@@": "/srv/vmshpwa/runtime",
        "@@SOCKET_DIR@@": str(socket.parent),
        "@@PUBLIC_HOST@@": "vmsh.example.test",
        "@@AUTH_SIGNING_KEY@@": "s" * 32,
        "@@REFRESH_PEPPER_B64@@": "c" * 44,
        "@@THROTTLE_PEPPER_B64@@": "d" * 44,
        "@@SENTRY_DSN@@": "https://public@example.test/1",
        "@@RELEASE@@": "revision-test",
        "@@VAPID_PUBLIC_KEY@@": "public-vapid-test",
        "@@VAPID_PRIVATE_KEY@@": "private-vapid-test",
        "@@OPERATOR_EMAIL@@": "operator@example.test",
    }

    def rendered(path: Path) -> str:
        value = path.read_text(encoding="utf-8")
        for marker, replacement in replacements.items():
            value = value.replace(marker, replacement)
        return value

    unit = tmp_path / "vmshpwa.service"
    unit.write_text(rendered(UNIT_TEMPLATE), encoding="utf-8")
    environment.write_text(rendered(ENV_TEMPLATE), encoding="utf-8")
    environment.chmod(0o600)
    return unit, environment


def test_rendered_profile_is_separate_two_worker_pwa_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unit, environment = _render(tmp_path)
    monkeypatch.setattr("shutil.which", lambda _name: None)

    report = check_systemd_profile(
        unit_path=unit,
        env_path=environment,
        require_systemd_analyze=False,
    )

    assert report == {
        "schemaVersion": 1,
        "profile": "pwa-production",
        "workers": 2,
        "systemdAnalyze": False,
        "environmentMode": "0600",
    }


@pytest.mark.parametrize("mode", [0o400, 0o640, 0o644])
def test_profile_requires_exact_secret_file_mode(tmp_path: Path, mode: int) -> None:
    unit, environment = _render(tmp_path)
    environment.chmod(mode)

    with pytest.raises(SystemdProfileError, match="mode 0600"):
        check_systemd_profile(
            unit_path=unit,
            env_path=environment,
            require_systemd_analyze=False,
        )


@pytest.mark.parametrize("name", ["VMSH_RUNTIME_PROFILE", "VMSH_PWA_PROTOTYPE", "PROD"])
def test_profile_rejects_environment_adapter_overrides(
    tmp_path: Path, name: str
) -> None:
    unit, environment = _render(tmp_path)
    environment.write_text(
        environment.read_text(encoding="utf-8") + f"\n{name}=unsafe\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemdProfileError, match="must not select"):
        check_systemd_profile(
            unit_path=unit,
            env_path=environment,
            require_systemd_analyze=False,
        )


def test_profile_rejects_unresolved_unit_marker(tmp_path: Path) -> None:
    unit, environment = _render(tmp_path)
    unit.write_text(
        unit.read_text(encoding="utf-8") + "\n# @@UNRESOLVED@@\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemdProfileError, match="unresolved"):
        check_systemd_profile(
            unit_path=unit,
            env_path=environment,
            require_systemd_analyze=False,
        )


def test_profile_requires_systemd_analyze_on_production_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unit, environment = _render(tmp_path)
    monkeypatch.setattr("shutil.which", lambda _name: None)

    with pytest.raises(SystemdProfileError, match="required"):
        check_systemd_profile(
            unit_path=unit,
            env_path=environment,
            require_systemd_analyze=True,
        )


def test_profile_does_not_expose_secret_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unit, environment = _render(tmp_path)
    monkeypatch.setattr("shutil.which", lambda _name: None)
    report = check_systemd_profile(
        unit_path=unit,
        env_path=environment,
        require_systemd_analyze=False,
    )

    serialized = repr(report)
    assert "private-vapid-test" not in serialized
    assert "public@example.test" not in serialized
    assert "operator@example.test" not in serialized
    assert str(environment) not in serialized
