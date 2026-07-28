from pathlib import Path
from types import SimpleNamespace

import pytest

from db_methods.pwa import PwaConnectionFactory, apply_schema_migrations
from vmshpwa.scripts.seed_e2e_review import (
    TARGETS,
    _insert_review_cases,
    _require_e2e_target,
)


def test_review_seed_creates_one_complete_case_per_browser(tmp_path):
    database_path = tmp_path / "review-seed.sqlite3"
    apply_schema_migrations(database_path)
    factory = PwaConnectionFactory(database_path)
    # The insertion helper intentionally depends on the stable Phase-1 baseline.
    with pytest.raises(RuntimeError, match="owner is missing"):
        factory.run_write(_insert_review_cases)


def test_review_seed_target_guard_is_exact():
    allowed = SimpleNamespace(
        runtime_profile="pwa-e2e",
        pwa_instance="e2e",
        db_filename="db/vmshpwa_e2e.sqlite3",
        pwa_media_root=".runtime/vmshpwa/e2e",
    )
    assert _require_e2e_target(allowed).name == "vmshpwa_e2e.sqlite3"

    for changed in (
        SimpleNamespace(
            runtime_profile="pwa-agent",
            pwa_instance="agent",
            db_filename="db/vmshpwa_agent.sqlite3",
            pwa_media_root=".runtime/vmshpwa/agent",
        ),
        SimpleNamespace(
            runtime_profile="pwa-e2e",
            pwa_instance="e2e",
            db_filename=str(Path("db") / "another.sqlite3"),
            pwa_media_root=".runtime/vmshpwa/e2e",
        ),
        SimpleNamespace(
            runtime_profile="pwa-e2e",
            pwa_instance="e2e",
            db_filename="db/vmshpwa_e2e.sqlite3",
            pwa_media_root=".runtime/vmshpwa/another",
        ),
    ):
        with pytest.raises(RuntimeError):
            _require_e2e_target(changed)

    assert {project for project, _lesson in TARGETS} == {
        "chromium",
        "webkit",
        "firefox",
    }
