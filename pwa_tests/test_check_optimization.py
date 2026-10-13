"""Real cache invalidation/isolation and the measured release gate contract."""

import json
from contextlib import closing, nullcontext
import sqlite3
from types import SimpleNamespace

import pytest

from db_methods.pwa import DatabaseLifecycleBusyError, runtime_database_lock
from pwa_tests.sqlite_template import create_test_database
from vmshpwa.scripts import check_runner, check_toolchain, e2e_build_cache, prepare_e2e
from vmshpwa.scripts.e2e_runner import run_commands


@pytest.fixture
def built_workspace(tmp_path):
    workspace = tmp_path / "vmshpwa"
    workspace.mkdir()
    (workspace / "package.json").write_text(
        json.dumps({"packageManager": "pnpm@11.15.1"})
    )
    (workspace / "pnpm-lock.yaml").write_text("locked\n")
    installed = workspace / "node_modules/.pnpm"
    installed.mkdir(parents=True)
    (installed / "lock.yaml").write_text("locked\n")
    for application in e2e_build_cache.APPLICATIONS:
        root = workspace / "apps" / application
        (root / "src").mkdir(parents=True)
        (root / "src/main.ts").write_text("export const version = 1\n")
        dist = root / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("<html>built</html>")
        (dist / "build-provenance.json").write_text(
            json.dumps(
                {
                    "application": application,
                    "profile": "verification",
                    "msw": False,
                    "prototype": False,
                    "publicMediaOrigin": None,
                    "sentryConfigured": False,
                }
            )
        )
    return workspace


def test_build_cache_invalidates_source_environment_new_file_and_artifact(
    built_workspace,
):
    workspace = built_workspace
    e2e_build_cache.record_build(workspace, {})
    assert e2e_build_cache.cached_build_is_current(workspace, {})
    assert not e2e_build_cache.cached_build_is_current(
        workspace, {"VITE_PROTOTYPE": "true"}
    )
    source = workspace / "apps/student/src/main.ts"
    source.write_text("export const version = 2\n")
    assert not e2e_build_cache.cached_build_is_current(workspace, {})
    e2e_build_cache.record_build(workspace, {})
    (source.parent / "extra.ts").write_text("export const extra = true\n")
    assert not e2e_build_cache.cached_build_is_current(workspace, {})
    e2e_build_cache.record_build(workspace, {})
    (workspace / "apps/student/dist/index.html").write_text("corrupt")
    assert not e2e_build_cache.cached_build_is_current(workspace, {})


def test_cache_never_accepts_production_artifacts_or_symlink_dist(
    built_workspace, tmp_path
):
    provenance = built_workspace / "apps/staff/dist/build-provenance.json"
    value = json.loads(provenance.read_text())
    value["profile"] = "production"
    provenance.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="Unsafe E2E build provenance"):
        e2e_build_cache.record_build(built_workspace, {})
    value["profile"] = "verification"
    provenance.write_text(json.dumps(value))
    landing = built_workspace / "apps/landing/dist"
    landing.rename(tmp_path / "outside")
    landing.symlink_to(tmp_path / "outside")
    with pytest.raises(RuntimeError, match="must not be a symlink"):
        e2e_build_cache.artifact_manifest(built_workspace)


def test_repeated_run_reuses_build_but_always_runs_playwright(
    built_workspace, monkeypatch
):
    calls = []
    monkeypatch.setattr(
        "vmshpwa.scripts.e2e_runner.subprocess.run",
        lambda command, **kwargs: (
            calls.append(tuple(command)) or SimpleNamespace(returncode=0)
        ),
    )
    commands = (("pnpm", "build"), ("pnpm", "exec", "playwright", "test"))
    for _ in range(2):
        assert (
            run_commands(
                commands, workspace=built_workspace, environment={}, reuse_build=True
            )
            == 0
        )
    assert calls.count(("pnpm", "build")) == 1
    assert calls.count(commands[1]) == 2


def test_toolchain_fails_before_mutation_when_installed_lock_is_stale(
    built_workspace, monkeypatch
):
    monkeypatch.setattr(
        check_toolchain.shutil, "which", lambda *args, **kwargs: "/tools/pnpm"
    )
    monkeypatch.setattr(
        check_toolchain.subprocess,
        "check_output",
        lambda command, **kwargs: "v26.9.0\n" if command[0] == "node" else "11.15.1\n",
    )
    environment = check_toolchain.frontend_environment(
        built_workspace, {"PATH": "/tools"}
    )
    assert environment["VMSH_CHECK_PNPM_VERSION"] == "11.15.1"
    (built_workspace / "node_modules/.pnpm/lock.yaml").write_text("stale")
    with pytest.raises(RuntimeError, match="differ from pnpm-lock"):
        check_toolchain.frontend_environment(built_workspace, {"PATH": "/tools"})


@pytest.fixture
def seed_target(tmp_path, monkeypatch):
    database = tmp_path / "db/e2e.sqlite3"
    media = tmp_path / "media"
    cache = tmp_path / "cache"
    monkeypatch.setattr(prepare_e2e, "DATABASE", database)
    monkeypatch.setattr(prepare_e2e, "MEDIA", media)
    monkeypatch.setattr(prepare_e2e, "CACHE", cache)
    monkeypatch.setattr(prepare_e2e, "seed_digest", lambda **kwargs: "seed-v1")
    calls = []

    def seed(config, **kwargs):
        calls.append(kwargs)
        database.unlink(missing_ok=True)
        create_test_database(database)
        with closing(sqlite3.connect(database)) as db, db:
            db.execute("INSERT INTO kv(key,value) VALUES('seed','pristine')")
        (media / "content").mkdir(parents=True, exist_ok=True)
        (media / "content/probe.txt").write_text("pristine")

    monkeypatch.setattr(prepare_e2e, "seed_all", seed)
    monkeypatch.setenv("PROD", "false")
    config = SimpleNamespace(
        runtime_profile="pwa-e2e", db_filename=str(database), pwa_media_root=str(media)
    )
    return config, database, media, cache, calls


def test_cached_seed_restores_db_media_and_keeps_lifecycle_lock_inode(seed_target):
    config, database, media, cache, calls = seed_target
    assert prepare_e2e.prepare(config)["seed_cache_hit"] is False
    lock = media / ".analytics.sqlite3.vmshpwa-lifecycle.lock"
    inode = lock.stat().st_ino
    with closing(sqlite3.connect(database)) as db, db:
        db.execute("UPDATE kv SET value='dirty' WHERE key='seed'")
    (media / "content/probe.txt").write_text("dirty")
    assert prepare_e2e.prepare(config)["seed_cache_hit"] is True
    assert list(database.parent.glob("e2e-restore-*")) == []
    assert len(calls) == 1
    with closing(sqlite3.connect(database)) as db, db:
        assert (
            db.execute("SELECT value FROM kv WHERE key='seed'").fetchone()[0]
            == "pristine"
        )
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert (media / "content/probe.txt").read_text() == "pristine"
    assert lock.stat().st_ino == inode


def test_corrupt_seed_is_rebuilt_and_running_backend_is_never_reseeded(seed_target):
    config, database, media, cache, calls = seed_target
    prepare_e2e.prepare(config)
    (cache / "seed-v1/media/content/probe.txt").write_text("corrupt")
    assert prepare_e2e.prepare(config)["seed_cache_hit"] is False
    assert len(calls) == 2
    with runtime_database_lock(database):
        with pytest.raises(DatabaseLifecycleBusyError):
            prepare_e2e.prepare(config)
    assert len(calls) == 2
    assert (media / "content/probe.txt").read_text() == "pristine"


def test_seed_rejects_human_or_foreign_database_without_writes(seed_target, tmp_path):
    config, database, media, cache, calls = seed_target
    config.runtime_profile = "pwa-human"
    with pytest.raises(RuntimeError, match="isolated pwa-e2e"):
        prepare_e2e.prepare(config)
    config.runtime_profile = "pwa-e2e"
    config.db_filename = str(tmp_path / "production.sqlite3")
    with pytest.raises(RuntimeError, match="non-E2E"):
        prepare_e2e.prepare(config)
    assert not calls and not database.exists() and not cache.exists()


def test_pipeline_runs_python_once_and_browser_coverage_is_explicit(tmp_path):
    fast = check_runner.steps("fast", ["review"], 4, tmp_path)
    release = check_runner.steps("release", ["all"], 4, tmp_path)
    assert sum(name == "python" for name, _, _ in fast) == 1
    python = next(command for name, command, _ in fast if name == "python")
    assert python[-2:] == ["tests", "pwa_tests"]
    assert "chromium" in fast[-1][1]
    assert "all" in release[-1][1]
    assert len({name for name, _, _ in fast}) == len(fast)


def test_typed_lint_cache_invalidates_dependency_types(built_workspace):
    original = check_runner.lint_program_digest(built_workspace)
    (built_workspace / "apps/student/src/types.ts").write_text(
        "export type Value = string"
    )
    assert check_runner.lint_program_digest(built_workspace) != original


def test_receipt_tracks_configuration_and_untracked_code_but_not_test_reports(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(check_runner, "ROOT", tmp_path)
    names = ["app.py", "pyproject.toml", "extra.py", "pwa_tests/reports/run.json"]
    monkeypatch.setattr(
        check_runner.subprocess,
        "check_output",
        lambda *args, **kwargs: "\0".join(names).encode(),
    )
    (tmp_path / "app.py").write_text("value = 1\n")
    config = tmp_path / "pyproject.toml"
    config.write_text("[project]\nversion = '1'\n")
    report = tmp_path / "pwa_tests/reports/run.json"
    report.parent.mkdir(parents=True)
    report.write_text('{"pass": 1}')
    original = check_runner.source_digest()
    report.write_text('{"pass": 2}')
    assert check_runner.source_digest() == original
    config.write_text("[project]\nversion = '2'\n")
    configured = check_runner.source_digest()
    assert configured != original
    (tmp_path / "extra.py").write_text("new_code = True\n")
    assert check_runner.source_digest() != configured


@pytest.mark.parametrize("failure", [KeyboardInterrupt, FileNotFoundError])
def test_interrupted_or_failed_launcher_cannot_record_previous_pass(
    tmp_path, monkeypatch, failure
):
    monkeypatch.setattr(check_runner, "exclusive_e2e_run", lambda _path: nullcontext())
    monkeypatch.setattr(check_runner, "frontend_environment", lambda _path, env: env)
    monkeypatch.setattr(check_runner, "source_digest", lambda: "tested-source")
    monkeypatch.setattr(check_runner.subprocess, "check_output", lambda *a, **k: "a" * 40)
    monkeypatch.setattr(
        check_runner, "steps",
        lambda *args: [("first", ["pass"], tmp_path), ("second", ["fail"], tmp_path)],
    )

    def run(command, **kwargs):
        if command == ["fail"]:
            raise failure()
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(check_runner.subprocess, "run", run)
    arguments = ["--report-dir", str(tmp_path)]
    if failure is KeyboardInterrupt:
        assert check_runner.main(arguments) == 130
    else:
        with pytest.raises(FileNotFoundError):
            check_runner.main(arguments)
    receipt = json.loads((tmp_path / "summary.json").read_text())
    assert receipt["steps"][0]["exit_code"] == 0
    assert receipt["exit_code"] == (130 if failure is KeyboardInterrupt else 1)
