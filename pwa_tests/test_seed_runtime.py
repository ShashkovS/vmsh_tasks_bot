from __future__ import annotations

import hashlib
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest

from helpers import checkers
from helpers.config import Config
from helpers.consts import ANS_TYPE, PROB_TYPE
from db_methods.pwa import DatabaseLifecycleBusyError, runtime_database_lock
from pwa_tests.fixtures.seed import load_answer_types_v1, load_baseline_v1
from vmshpwa.scripts import seed_runtime as seed_module
from vmshpwa.scripts.seed_runtime import seed_runtime


def _runtime(
    tmp_path: Path,
    *,
    profile: str = "pwa-agent",
    instance: str = "agent",
    filename: str = "vmshpwa_agent.sqlite3",
    production: bool = False,
) -> tuple[Config, Path, Path]:
    database_root = tmp_path / "db"
    media_root = tmp_path / "media"
    runtime = Config(
        runtime_profile=profile,
        pwa_instance=instance,
        db_filename=str(database_root / filename),
        pwa_media_root=str(media_root / instance),
        production_mode=production,
    )
    return runtime, database_root, media_root


def _seed(tmp_path: Path):
    runtime, database_root, media_root = _runtime(tmp_path)
    report = seed_runtime(runtime, database_root=database_root, media_root=media_root)
    return runtime, database_root, media_root, report


def _fetch_value(connection: sqlite3.Connection, query: str):
    return connection.execute(query).fetchone()[0]


def test_baseline_seed_has_exact_legacy_personas_and_states(tmp_path):
    _runtime_config, _database_root, _media_root, report = _seed(tmp_path)
    fixture = load_baseline_v1()

    assert report.fixture == "baseline-v1"
    assert report.durability_confirmed is True
    assert report.durability_warning is None
    assert report.canonical_digest == fixture["expectedCanonicalDigest"]
    assert report.row_counts == {
        "groups": 5,
        "users": 4,
        "student_strength": 1,
        "lessons": 9,
        "problems": 16,
        "states": 4,
        "user_changes_log": 4,
        "written_tasks_discussions": 6,
        "written_tasks_queue": 2,
        "results": 2,
        "kv": 1,
        "kv_logins": 0,
    }
    # The merged empty-schema migration has a valid FK. Older production
    # histories may retain the malformed legacy reference; that compatibility
    # path is exercised separately below.
    assert report.foreign_key_exclusions == ()
    with sqlite3.connect(report.database_path) as connection:
        assert set(
            connection.execute(
                "SELECT group_id FROM groups WHERE is_active = 1"
            ).fetchall()
        ) == {("н",), ("п",), ("э",), ("testing",)}
        assert connection.execute(
            "SELECT group_id FROM groups WHERE is_system = 1"
        ).fetchall() == [("no_level",)]
        assert connection.execute(
            "SELECT id, online, group_id FROM users WHERE type = 1 ORDER BY id"
        ).fetchall() == [(101, 1, "н"), (102, 2, "п")]
        assert connection.execute(
            "SELECT id, allowed_groups FROM users WHERE id IN (201, 301) ORDER BY id"
        ).fetchall() == [(201, ";н;"), (301, ";н;п;э;testing;")]
        assert connection.execute(
            "SELECT student_id FROM student_strength ORDER BY student_id"
        ).fetchall() == [(101,)]
        assert connection.execute(
            "SELECT DISTINCT lesson, group_id FROM lessons ORDER BY lesson, group_id"
        ).fetchall() == [
            (39, "н"),
            (39, "п"),
            (39, "э"),
            (40, "н"),
            (40, "п"),
            (40, "э"),
            (41, "н"),
            (41, "п"),
            (41, "э"),
        ]
        assert {
            row[0]
            for row in connection.execute("SELECT DISTINCT prob_type FROM problems")
        } == {int(value) for value in PROB_TYPE}
        assert connection.execute(
            "SELECT id, synonyms FROM problems "
            "WHERE id IN (41001, 41101, 41201) ORDER BY id"
        ).fetchall() == [
            (41001, "41001;41101;41201"),
            (41101, "41001;41101;41201"),
            (41201, "41001;41101;41201"),
        ]
        assert connection.execute(
            "SELECT problem_id, cur_status, teacher_id FROM written_tasks_queue "
            "ORDER BY id"
        ).fetchall() == [(41003, 0, None), (41004, 1, 201)]
        assert connection.execute(
            "SELECT problem_id, verdict FROM results ORDER BY id"
        ).fetchall() == [(41005, 17), (41006, 15)]
        assert _fetch_value(connection, "SELECT count(*) FROM kv_logins") == 0
        assert (
            _fetch_value(
                connection,
                "SELECT count(*) FROM users WHERE token IS NOT NULL OR chat_id IS NOT NULL",
            )
            == 0
        )


def test_baseline_seed_is_repeatable_and_removes_runtime_drift(tmp_path):
    runtime, database_root, media_root, first = _seed(tmp_path)
    with closing(sqlite3.connect(first.database_path)) as connection:
        connection.execute("UPDATE users SET name = 'drift' WHERE id = 101")
        connection.execute("INSERT INTO kv (key, value) VALUES ('drift', '1')")
        connection.commit()

    second = seed_runtime(runtime, database_root=database_root, media_root=media_root)

    assert second.canonical_digest == first.canonical_digest
    assert second.row_counts == first.row_counts
    with sqlite3.connect(second.database_path) as connection:
        assert (
            _fetch_value(connection, "SELECT name FROM users WHERE id = 101")
            == "Алексей"
        )
        assert (
            _fetch_value(connection, "SELECT count(*) FROM kv WHERE key = 'drift'") == 0
        )


def test_seed_build_failure_preserves_previous_database(tmp_path, monkeypatch):
    runtime, database_root, media_root, first = _seed(tmp_path)
    before = hashlib.sha256(first.database_path.read_bytes()).hexdigest()

    def fail_population(*_args, **_kwargs):
        raise RuntimeError("synthetic population failure")

    monkeypatch.setattr(seed_module, "_populate_database", fail_population)
    with pytest.raises(RuntimeError, match="synthetic population failure"):
        seed_runtime(runtime, database_root=database_root, media_root=media_root)

    after = hashlib.sha256(first.database_path.read_bytes()).hexdigest()
    assert after == before
    assert not list(database_root.glob("*.tmp"))


def test_post_replace_directory_fsync_failure_is_reported_without_losing_seed(
    tmp_path,
    monkeypatch,
    capsys,
):
    runtime, database_root, media_root, first = _seed(tmp_path)
    with sqlite3.connect(first.database_path) as connection:
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("UPDATE users SET name = 'drift' WHERE id = 101")
        connection.commit()

    real_fsync_path = seed_module._fsync_path
    fsync_calls: list[Path] = []

    def fail_final_directory_fsync(path: Path) -> None:
        fsync_calls.append(path)
        if len(fsync_calls) == 3:
            raise OSError("synthetic final directory fsync failure")
        real_fsync_path(path)

    monkeypatch.setattr(seed_module, "_fsync_path", fail_final_directory_fsync)
    report = seed_runtime(runtime, database_root=database_root, media_root=media_root)

    assert report.durability_confirmed is False
    assert report.durability_warning == (
        "atomic replacement completed, but the final directory fsync failed "
        "(OSError); crash durability is unconfirmed"
    )
    assert "WARNING: atomic replacement completed" in capsys.readouterr().err
    assert len(fsync_calls) == 3
    assert fsync_calls[0].suffix == ".tmp"
    assert fsync_calls[1:] == [database_root, database_root]
    with sqlite3.connect(report.database_path) as connection:
        assert connection.execute(
            "SELECT name FROM users WHERE id = 101"
        ).fetchone()[0] == "Алексей"


@pytest.mark.parametrize(
    ("profile", "instance", "filename", "message"),
    [
        (
            "legacy",
            "agent",
            "vmshpwa_agent.sqlite3",
            "explicit VMSH_RUNTIME_PROFILE",
        ),
        ("pwa-preview", "preview", "vmshpwa_agent.sqlite3", "supports only"),
        ("pwa-agent", "wrong", "vmshpwa_agent.sqlite3", "requires instance"),
        ("pwa-agent", "agent", "unknown.sqlite3", "Unknown PWA seed database"),
    ],
)
def test_seed_rejects_unknown_profile_instance_or_target(
    tmp_path, profile, instance, filename, message
):
    runtime, database_root, media_root = _runtime(
        tmp_path, profile=profile, instance=instance, filename=filename
    )
    with pytest.raises(RuntimeError, match=message):
        seed_runtime(runtime, database_root=database_root, media_root=media_root)
    assert not (database_root / filename).exists()


def test_seed_rejects_production_and_authoritative_database(tmp_path):
    runtime, database_root, media_root = _runtime(tmp_path, production=True)
    with pytest.raises(RuntimeError, match="forbidden in production"):
        seed_runtime(runtime, database_root=database_root, media_root=media_root)

    authoritative = seed_module.AUTHORITATIVE_DATABASE
    runtime.production_mode = False
    runtime.db_filename = str(authoritative)
    with pytest.raises(RuntimeError, match="authoritative db/vmsh.db"):
        seed_runtime(
            runtime,
            database_root=authoritative.parent,
            media_root=media_root,
        )


def test_seed_rejects_a_hard_link_to_authoritative_database(tmp_path, monkeypatch):
    authoritative = tmp_path / "authoritative.sqlite3"
    authoritative.write_bytes(b"must remain unchanged")
    monkeypatch.setattr(seed_module, "AUTHORITATIVE_DATABASE", authoritative)
    runtime, database_root, media_root = _runtime(tmp_path / "runtime")
    database_root.mkdir(parents=True)
    Path(runtime.db_filename).hardlink_to(authoritative)

    with pytest.raises(RuntimeError, match="hard link to authoritative"):
        seed_runtime(runtime, database_root=database_root, media_root=media_root)

    assert authoritative.read_bytes() == b"must remain unchanged"


def test_seed_cli_rejects_prod_environment_before_loading_config(monkeypatch):
    monkeypatch.setenv("PROD", "true")
    monkeypatch.setenv("VMSH_RUNTIME_PROFILE", "pwa-agent")
    with pytest.raises(RuntimeError, match="PROD=true"):
        seed_module.main([])


@pytest.mark.parametrize(
    ("profile", "instance", "filename"),
    [
        ("pwa-human", "human", "vmshpwa_dev.sqlite3"),
        ("pwa-agent", "agent", "vmshpwa_agent.sqlite3"),
        ("pwa-e2e", "e2e", "vmshpwa_e2e.sqlite3"),
    ],
)
def test_all_three_isolated_seed_profiles_are_supported(
    tmp_path, profile, instance, filename
):
    runtime, database_root, media_root = _runtime(
        tmp_path, profile=profile, instance=instance, filename=filename
    )
    report = seed_runtime(runtime, database_root=database_root, media_root=media_root)
    assert report.database_path == database_root / filename
    assert report.canonical_digest == load_baseline_v1()["expectedCanonicalDigest"]


def test_seed_rejects_symlink_target_and_existing_sidecar(tmp_path):
    runtime, database_root, media_root = _runtime(tmp_path)
    database_root.mkdir(parents=True)
    real_database = tmp_path / "other.sqlite3"
    real_database.touch()
    Path(runtime.db_filename).symlink_to(real_database)

    with pytest.raises(RuntimeError, match="symlink database target"):
        seed_runtime(runtime, database_root=database_root, media_root=media_root)

    Path(runtime.db_filename).unlink()
    Path(str(runtime.db_filename) + "-wal").touch()
    with pytest.raises(RuntimeError, match="may be open"):
        seed_runtime(runtime, database_root=database_root, media_root=media_root)


def test_seed_recovers_stale_wal_sidecars_via_sqlite(tmp_path):
    runtime, database_root, media_root, first = _seed(tmp_path)
    wal = Path(str(first.database_path) + "-wal")
    shm = Path(str(first.database_path) + "-shm")
    # A read-only/crashed last client can leave these files behind. Empty files
    # model the no-uncheckpointed-frame case without ever deleting them by hand.
    wal.touch()
    shm.touch()

    second = seed_runtime(runtime, database_root=database_root, media_root=media_root)

    assert second.canonical_digest == first.canonical_digest
    assert not wal.exists()
    assert not shm.exists()


def test_seed_refuses_sidecars_while_target_has_an_active_writer(tmp_path):
    runtime, database_root, media_root, first = _seed(tmp_path)
    before = hashlib.sha256(first.database_path.read_bytes()).hexdigest()
    holder = sqlite3.connect(first.database_path, autocommit=True)
    try:
        holder.execute("PRAGMA journal_mode = WAL")
        holder.execute("BEGIN IMMEDIATE")
        holder.execute("INSERT OR REPLACE INTO kv (key, value) VALUES ('held', '1')")

        with pytest.raises(RuntimeError, match="busy|stop the runtime"):
            seed_runtime(runtime, database_root=database_root, media_root=media_root)
    finally:
        holder.execute("ROLLBACK")
        holder.close()

    assert hashlib.sha256(first.database_path.read_bytes()).hexdigest() == before


def test_seed_refuses_to_replace_database_while_runtime_lock_is_held(tmp_path):
    runtime, database_root, media_root, first = _seed(tmp_path)
    before = hashlib.sha256(first.database_path.read_bytes()).hexdigest()

    with runtime_database_lock(first.database_path):
        with pytest.raises(DatabaseLifecycleBusyError, match="runtime workers"):
            seed_runtime(runtime, database_root=database_root, media_root=media_root)

    assert hashlib.sha256(first.database_path.read_bytes()).hexdigest() == before


def test_runtime_cannot_open_between_final_seed_check_and_replace(
    tmp_path, monkeypatch
):
    runtime, database_root, media_root, first = _seed(tmp_path)
    real_replace = seed_module.os.replace
    attempts: list[str] = []

    def replace_after_runtime_attempt(source, target):
        # This is the former TOCTOU window: without the process-lifetime lock a
        # worker could open the old inode after the last sidecar check and then
        # share its pathname-derived WAL with the replacement database.
        script = """
import sqlite3
import sys
from db_methods.pwa import DatabaseLifecycleBusyError, runtime_database_lock

lock = runtime_database_lock(sys.argv[1])
try:
    lock.acquire()
except DatabaseLifecycleBusyError:
    print('BLOCKED')
else:
    try:
        with sqlite3.connect(sys.argv[1]) as connection:
            connection.execute(
                "INSERT OR REPLACE INTO kv (key, value) VALUES ('race', 'opened')"
            )
        print('OPENED')
    finally:
        lock.release()
"""
        result = subprocess.run(
            [sys.executable, "-c", script, str(target)],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        attempts.append(result.stdout.strip())
        assert attempts[-1] == "BLOCKED", result.stderr
        real_replace(source, target)

    monkeypatch.setattr(seed_module.os, "replace", replace_after_runtime_attempt)

    report = seed_runtime(runtime, database_root=database_root, media_root=media_root)

    assert attempts == ["BLOCKED"]
    with sqlite3.connect(report.database_path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM kv WHERE key = 'race'"
        ).fetchone()[0] == 0


def test_compaction_removes_deleted_synthetic_credential_bytes(tmp_path):
    database_path = tmp_path / "compact.sqlite3"
    sentinel = b"SYNTHETIC_CREDENTIAL_MUST_NOT_SURVIVE_COMPACTION"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE secrets(value BLOB)")
        connection.execute("INSERT INTO secrets(value) VALUES (?)", (sentinel,))
        connection.commit()
        connection.execute("DELETE FROM secrets")
        connection.commit()

    assert sentinel in database_path.read_bytes()
    seed_module._compact_database(database_path)
    assert sentinel not in database_path.read_bytes()


def test_family_is_manifest_only_until_phase_one(tmp_path):
    _runtime_config, _database_root, _media_root, report = _seed(tmp_path)
    family = load_baseline_v1()["seedMetadata"]["familyPersona"]
    assert family == {
        "fixtureKey": "fixture-family-1",
        "studentUserIds": [101, 102],
        "materializeInPhase": 1,
    }

    with sqlite3.connect(report.database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table'"
            )
        }
    assert not {
        "courses",
        "course_enrollments",
        "course_group_access",
        "auth_accounts",
        "family_student_links",
        "auth_sessions",
        "staff_scopes",
    }.intersection(tables)


def test_known_legacy_reactions_fk_is_scoped_without_hiding_other_violations(
    tmp_path,
):
    _runtime_config, _database_root, _media_root, report = _seed(tmp_path)
    with closing(sqlite3.connect(report.database_path)) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("DROP TABLE reactions")
        connection.execute(
            """
            CREATE TABLE reactions (
                id INTEGER PRIMARY KEY,
                ts TEXT,
                result_id INT REFERENCES results(id),
                zoom_conversation_id INT
                    REFERENCES zoom_conversation(zoom_conversation_id),
                reaction_id INT NOT NULL REFERENCES reaction_enum(reaction_id),
                reaction_type_id INT NOT NULL
                    REFERENCES reaction_type_enum(reaction_type_id)
            )
            """
        )
        connection.commit()

    assert seed_module._validate_database(report.database_path) == (
        "reactions.zoom_conversation_id -> "
        "zoom_conversation.zoom_conversation_id (legacy schema defect)",
    )

    with closing(sqlite3.connect(report.database_path)) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            "INSERT INTO reactions "
            "(id, result_id, zoom_conversation_id, reaction_id, reaction_type_id) "
            "VALUES (1, 999999, NULL, 0, 0)"
        )
        connection.commit()
    with pytest.raises(RuntimeError, match=r"reactions\.result_id -> results\.id"):
        seed_module._validate_database(report.database_path)

    with closing(sqlite3.connect(report.database_path)) as connection:
        connection.execute("DELETE FROM reactions")
        result_id = connection.execute("SELECT id FROM results LIMIT 1").fetchone()[0]
        connection.execute(
            "INSERT INTO reactions "
            "(id, result_id, zoom_conversation_id, reaction_id, reaction_type_id) "
            "VALUES (2, ?, NULL, 999999, 0)",
            (result_id,),
        )
        connection.commit()
    with pytest.raises(
        RuntimeError,
        match=r"reactions\.reaction_id -> reaction_enum\.reaction_id",
    ):
        seed_module._validate_database(report.database_path)

    with closing(sqlite3.connect(report.database_path)) as connection:
        connection.execute("DELETE FROM reactions")
        result_id = connection.execute("SELECT id FROM results LIMIT 1").fetchone()[0]
        connection.execute(
            "INSERT INTO reactions "
            "(id, result_id, zoom_conversation_id, reaction_id, reaction_type_id) "
            "VALUES (3, ?, NULL, 0, 999999)",
            (result_id,),
        )
        connection.commit()
    with pytest.raises(
        RuntimeError,
        match=(
            r"reactions\.reaction_type_id -> "
            r"reaction_type_enum\.reaction_type_id"
        ),
    ):
        seed_module._validate_database(report.database_path)


def test_answer_type_fixture_matches_the_complete_legacy_enum():
    fixture = load_answer_types_v1()
    answer_types = fixture["answerTypes"]
    assert fixture["contract"].startswith("legacy answer format validation")
    assert {(row["name"], row["value"]) for row in answer_types} == {
        (answer_type.name, int(answer_type)) for answer_type in ANS_TYPE
    }
    assert all(row["valid"] for row in answer_types)
    assert all(
        row["invalid"]
        for row in answer_types
        if ANS_TYPE[row["name"]]
        not in {
            ANS_TYPE.SYMB_EXPRESSION,
            ANS_TYPE.SYMB_EQUIV,
            ANS_TYPE.STRING,
        }
    )


def _answer_type_fixture_examples():
    examples = []
    for row in load_answer_types_v1()["answerTypes"]:
        for expected_key, expected in (("valid", True), ("invalid", False)):
            examples.extend(
                pytest.param(
                    ANS_TYPE[row["name"]],
                    answer,
                    expected,
                    tuple(row.get("options", ())),
                    id=f'{row["name"]}-{expected_key}-{index}',
                )
                for index, answer in enumerate(row[expected_key], start=1)
            )
    return examples


@pytest.mark.parametrize(
    ("answer_type", "answer", "expected", "options"),
    _answer_type_fixture_examples(),
)
def test_every_answer_type_fixture_example_matches_legacy_validation(
    answer_type: ANS_TYPE,
    answer: str,
    expected: bool,
    options: tuple[str, ...],
):
    validation = checkers.ANS_REGEX[answer_type]
    if answer_type is ANS_TYPE.SELECT_ONE:
        # The handler sends and accepts exactly the visible option text; there
        # is intentionally no hidden machine value behind the selection.
        accepted = answer.strip() in options
    else:
        # STRING deliberately has no format validation. Symbolic expressions
        # use an accept-all regex and are validated only by their checker.
        accepted = True if validation is None else validation.fullmatch(answer.strip())
    assert bool(accepted) is expected


def test_clock_fixture_straddles_cutoff_before_solution_publication():
    fixture = load_baseline_v1()
    metadata = fixture["seedMetadata"]
    messages = fixture["tables"]["written_tasks_discussions"]
    before = next(row["ts"] for row in messages if row["id"] == 6001)
    after = next(row["ts"] for row in messages if row["id"] == 6005)

    assert before < metadata["submissionClosesAt"] < after
    assert after < metadata["solutionPublishesAt"]
