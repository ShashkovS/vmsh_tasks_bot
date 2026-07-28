from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from vmshpwa.scripts.e2e_runner import (
    E2E_API_ORIGIN,
    E2E_BROWSER_BUILD_ENVIRONMENT,
    E2eSuiteAlreadyRunning,
    commands_for_mode,
    exclusive_e2e_run,
    run_commands,
    sanitized_e2e_environment,
)


def test_second_e2e_suite_fails_before_entering_shared_workspace(tmp_path):
    lock_path = tmp_path / "e2e-suite.lock"

    with exclusive_e2e_run(lock_path):
        with pytest.raises(E2eSuiteAlreadyRunning, match="Another vmshpwa E2E"):
            with exclusive_e2e_run(lock_path):
                pytest.fail("a second suite must not acquire the shared lock")


def test_visual_modes_keep_build_before_playwright():
    assert commands_for_mode("all") == (
        ("pnpm", "build"),
        ("pnpm", "exec", "playwright", "test"),
    )
    assert commands_for_mode("visual")[-1][-2:] == ("--grep", "@visual")
    assert commands_for_mode("visual-update")[-1][-3:] == (
        "--grep",
        "@visual",
        "--update-snapshots",
    )


def test_diagnostic_modes_keep_the_same_exclusive_build_boundary():
    assert commands_for_mode("authentication") == (
        ("pnpm", "build"),
        ("pnpm", "exec", "playwright", "test", "e2e/authentication.spec.ts"),
    )
    assert commands_for_mode("runtime-isolation") == (
        ("pnpm", "build"),
        ("pnpm", "exec", "playwright", "test", "e2e/runtime-isolation.spec.ts"),
    )
    assert commands_for_mode("content") == (
        ("pnpm", "build"),
        ("pnpm", "exec", "playwright", "test", "e2e/content-publication.spec.ts"),
    )
    assert commands_for_mode("submissions") == (
        ("pnpm", "build"),
        ("pnpm", "exec", "playwright", "test", "e2e/test-submission.spec.ts"),
    )
    assert commands_for_mode("review") == (
        ("pnpm", "build"),
        ("pnpm", "exec", "playwright", "test", "e2e/review-workspace.spec.ts"),
    )
    assert commands_for_mode("realtime") == (
        ("pnpm", "build"),
        (
            "pnpm",
            "exec",
            "playwright",
            "test",
            "e2e/runtime-isolation.spec.ts",
            "--grep",
            "product realtime|current-session revoke",
        ),
    )
    assert commands_for_mode("nonvisual")[-1][-2:] == ("--grep-invert", "@visual")


def test_failed_build_stops_before_playwright(monkeypatch, tmp_path):
    calls: list[tuple[str, ...]] = []

    def fake_run(command, **_kwargs):
        calls.append(tuple(command))
        return SimpleNamespace(returncode=9)

    monkeypatch.setattr("vmshpwa.scripts.e2e_runner.subprocess.run", fake_run)

    assert run_commands(commands_for_mode("all"), workspace=Path(tmp_path)) == 9
    assert calls == [("pnpm", "build")]


def test_e2e_environment_replaces_every_inherited_browser_build_value():
    inherited = {
        "PATH": "/tools",
        "CI": "true",
        "VITE_SENTRY_DSN": "https://public@example.invalid/42",
        "VITE_SENTRY_RELEASE": "production-release",
        "VITE_PUBLIC_MEDIA_ORIGIN": "https://media.example.invalid",
        "VITE_ENABLE_MSW": "true",
        "VITE_PROTOTYPE": "true",
        "VITE_FUTURE_BROWSER_INPUT": "must-not-enter-the-build",
        "VMSH_API_ORIGIN": "https://api.example.invalid",
        "VMSH_PWA_DEV_SW": "1",
    }

    environment = sanitized_e2e_environment(inherited)

    assert environment["PATH"] == "/tools"
    assert environment["CI"] == "true"
    assert {
        name: value for name, value in environment.items() if name.startswith("VITE_")
    } == E2E_BROWSER_BUILD_ENVIRONMENT
    assert environment["VMSH_API_ORIGIN"] == E2E_API_ORIGIN
    assert environment["VMSH_PWA_DEV_SW"] == "0"


def test_every_subprocess_receives_the_same_sanitized_environment(
    monkeypatch, tmp_path
):
    calls: list[tuple[tuple[str, ...], dict[str, str]]] = []

    def fake_run(command, **kwargs):
        calls.append((tuple(command), kwargs["env"]))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("vmshpwa.scripts.e2e_runner.subprocess.run", fake_run)

    inherited = {
        "PATH": "/tools",
        "VITE_SENTRY_DSN": "https://public@example.invalid/42",
        "VITE_UNREVIEWED": "unsafe",
    }
    assert (
        run_commands(
            commands_for_mode("runtime-isolation"),
            workspace=Path(tmp_path),
            environment=inherited,
        )
        == 0
    )

    assert [command for command, _environment in calls] == [
        ("pnpm", "build"),
        ("pnpm", "exec", "playwright", "test", "e2e/runtime-isolation.spec.ts"),
    ]
    assert calls[0][1] == calls[1][1] == sanitized_e2e_environment(inherited)


def test_every_e2e_spec_uses_the_network_guard_fixture():
    e2e_directory = Path(__file__).parents[1] / "vmshpwa/e2e"
    specs = sorted(e2e_directory.glob("*.spec.ts"))

    assert specs
    for spec in specs:
        source = spec.read_text(encoding="utf-8")
        assert "from './fixtures'" in source, spec
        assert "from '@playwright/test'" not in source, spec


def test_every_browser_source_vite_input_has_an_explicit_safe_e2e_value():
    workspace = Path(__file__).parents[1] / "vmshpwa"
    source_inputs: set[str] = set()
    pattern = re.compile(r"import\.meta\.env\.(VITE_[A-Z0-9_]+)")

    for app_source in sorted((workspace / "apps").glob("*/src/**/*")):
        if app_source.suffix not in {".ts", ".tsx"}:
            continue
        source_inputs.update(pattern.findall(app_source.read_text(encoding="utf-8")))

    assert source_inputs
    assert source_inputs <= E2E_BROWSER_BUILD_ENVIRONMENT.keys()
