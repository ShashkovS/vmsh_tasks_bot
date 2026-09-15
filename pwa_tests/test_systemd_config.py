from __future__ import annotations

import re
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
    environment = tmp_path / "vmshpwa.env"
    unit = tmp_path / "vmshpwa.service"
    unit.write_text(
        UNIT_TEMPLATE.read_text(encoding="utf-8").replace(
            "/web/vmsh_tasks_bot/vmshpwa/runtime/vmshpwa.env", str(environment)
        ),
        encoding="utf-8",
    )
    environment.write_text(ENV_TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    environment.chmod(0o600)
    return unit, environment


def test_profile_uses_required_prometheus_multiprocess_boundary(tmp_path: Path) -> None:
    unit, _environment = _render(tmp_path)
    source = unit.read_text(encoding="utf-8")

    assert "RuntimeDirectory=vmsh-prometheus" in source
    assert "RuntimeDirectoryMode=0750" in source
    assert "Environment=PROMETHEUS_MULTIPROC_DIR=/run/vmsh-prometheus" in source
    assert (
        "ExecStartPre=/usr/bin/find /run/vmsh-prometheus -mindepth 1 "
        "-maxdepth 1 -type f -delete"
    ) in source
    assert "@@" not in source
    assert "--config /web/vmsh_tasks_bot/vmsh_tasks_bot/gunicorn.conf.py" in source
    assert "--bind unix:/web/vmsh_tasks_bot/vmshpwa/runtime/vmshpwa.sock" in source
    assert "--bind 127.0.0.1:8000" in source


@pytest.mark.parametrize(
    ("name", "value", "message"),
    (
        (
            "VMSH_PWA_TRUSTED_PROXY_UNIX_SOCKETS_JSON",
            "[]",
            "one absolute Unix socket",
        ),
    ),
)
def test_profile_rejects_transport_boundary_drift(
    tmp_path: Path, name: str, value: str, message: str
) -> None:
    unit, environment = _render(tmp_path)
    source = environment.read_text(encoding="utf-8")
    source = re.sub(rf"^{name}=.*$", f"{name}={value}", source, flags=re.MULTILINE)
    environment.write_text(source, encoding="utf-8")

    with pytest.raises(SystemdProfileError, match=message):
        check_systemd_profile(
            unit_path=unit,
            env_path=environment,
            require_systemd_analyze=False,
        )


def test_profile_rejects_an_additional_network_listener(tmp_path: Path) -> None:
    unit, environment = _render(tmp_path)
    unit.write_text(
        unit.read_text(encoding="utf-8").replace(
            "--bind 127.0.0.1:8000",
            "--bind 127.0.0.1:8000 --bind 10.0.0.1:8000",
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemdProfileError, match="exactly the Unix and loopback"):
        check_systemd_profile(
            unit_path=unit,
            env_path=environment,
            require_systemd_analyze=False,
        )


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


@pytest.mark.parametrize(
    "name",
    [
        "VMSH_RUNTIME_PROFILE",
        "VMSH_PWA_PROTOTYPE",
        "PROD",
        "PROMETHEUS_MULTIPROC_DIR",
    ],
)
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
