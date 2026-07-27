"""Phase-2 historical content backfill safety and idempotency tests."""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from db_methods.pwa.migrations import apply_schema_migrations
from vmshpwa.scripts import content_history_backfill as backfill
from vmshpwa.scripts.content_history_backfill import (
    ContentHistoryBackfillError,
    apply_backfill,
    preview_backfill,
)


NOW = "2026-07-27T18:00:00Z"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _isolated_apply_root(tmp_path, monkeypatch):
    monkeypatch.setattr(backfill, "APPLY_DATABASE_ROOT", tmp_path)


def _write_tex(path: Path, *, problem_count: int = 2) -> None:
    body = "\n".join(
        f"\\задача Синтетическая задача {index}. \\кзадача"
        for index in range(1, problem_count + 1)
    )
    path.write_bytes(
        (f"\\begin{{document}}\n{body}\n\\end{{document}}\n").encode("utf-8")
    )


def _seed_database(path: Path, *, include_second_group: bool = False) -> Path:
    apply_schema_migrations(path)
    with sqlite3.connect(path, autocommit=True) as connection:
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute(
            "INSERT INTO seasons "
            "(public_id, code, title, starts_on, ends_on, timezone, "
            "session_expires_on, status, created_at, updated_at) VALUES "
            "('season-history', 'history', 'Synthetic season', '2025-09-01', "
            "'2026-07-01', 'Europe/Moscow', '2026-08-10', 'active', ?, ?)",
            (NOW, NOW),
        )
        season_id = connection.execute(
            "SELECT id FROM seasons WHERE public_id = 'season-history'"
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO courses "
            "(public_id, season_id, code, name, subject_code, status, sort_order, "
            "accent_key, created_at, updated_at) VALUES "
            "('course-history', ?, 'math', 'Synthetic math', 'math', 'active', "
            "1, 'math', ?, ?)",
            (season_id, NOW, NOW),
        )
        course_id = connection.execute(
            "SELECT id FROM courses WHERE public_id = 'course-history'"
        ).fetchone()[0]
        groups = [
            (
                "hist-n",
                "hn",
                "Synthetic N",
                1,
                "group-history-n",
                course_id,
                NOW,
                NOW,
            )
        ]
        if include_second_group:
            groups.append(
                (
                    "hist-p",
                    "hp",
                    "Synthetic P",
                    2,
                    "group-history-p",
                    course_id,
                    NOW,
                    NOW,
                )
            )
        connection.executemany(
            "INSERT INTO groups "
            "(group_id, short_code, public_name, sort_order, is_active, is_default, "
            "allow_self_switch, is_system, score_weight, public_id, course_id, "
            "status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 1, 0, 1, 0, 1.0, ?, ?, 'active', ?, ?)",
            groups,
        )
        lesson_rows = [(501, "hist-n", 1), (538, "hist-n", 38)]
        if include_second_group:
            lesson_rows.append((601, "hist-p", 1))
        connection.executemany(
            "INSERT INTO lessons (id, group_id, lesson) VALUES (?, ?, ?)",
            lesson_rows,
        )
        problems = []
        next_id = 10_000
        for _lesson_id, group_id, lesson in lesson_rows:
            for problem_number in (1, 2):
                next_id += 1
                # Matching titles in two groups intentionally create a synonym
                # candidate, never an automatic merge.
                title = f"Общее название {problem_number}"
                problems.append(
                    (
                        next_id,
                        group_id,
                        lesson,
                        problem_number,
                        "",
                        title,
                        "",
                        1,
                        2,
                        None,
                        "Введите целое число",
                        "17",
                        None,
                        "Нет",
                        "Да",
                        "",
                    )
                )
        connection.executemany(
            "INSERT INTO problems "
            "(id, group_id, lesson, prob, item, title, prob_text, prob_type, "
            "ans_type, ans_validation, validation_error, cor_ans, cor_ans_checker, "
            "wrong_ans, congrat, synonyms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            problems,
        )
        # The production rehearsal is made only after an isolated copy has been
        # anonymized. These synthetic rows model that shape and must never enter
        # the aggregate content report.
        connection.execute(
            "INSERT INTO users "
            "(id, type, name, surname, token, birthday) VALUES "
            "(7001, 1, 'Synthetic', 'Student0001', 'never-report-this-token', "
            "'2012-01-01')"
        )
    path.chmod(0o600)
    return path


def _source_and_target(
    tmp_path: Path, *, include_second_group: bool = False
) -> tuple[Path, Path]:
    target = _seed_database(
        tmp_path / "migrated-copy.sqlite3",
        include_second_group=include_second_group,
    )
    source = tmp_path / "anonymized-source.sqlite3"
    shutil.copyfile(target, source)
    source.chmod(0o400)
    target.chmod(0o600)
    return source, target


def _lesson_mapping(
    *,
    group: str,
    lesson: int,
    source_path: str | None,
    known_times: bool,
) -> dict[str, object]:
    publication = f"2026-01-{lesson if lesson < 28 else 28:02d}T13:00:00Z"
    closes = f"2026-01-{lesson if lesson < 28 else 28:02d}T12:00:00Z"
    return {
        "legacyGroupId": group,
        "legacyLessonNumber": lesson,
        "courseLessonNumber": lesson,
        "cycleAnchorDate": f"2026-01-{lesson if lesson < 28 else 28:02d}",
        "businessTimezone": "Europe/Moscow",
        "timestamps": {
            "opensAt": None,
            "submissionClosesAt": closes if known_times else None,
            "hintScheduledAt": None,
            "solutionScheduledAt": None,
        },
        "materials": [
            {
                "kind": "condition",
                "sourcePath": source_path,
                "publishedAt": publication if known_times else None,
            }
        ],
    }


def _mapping(
    tmp_path: Path,
    *,
    known_times: bool = True,
    missing_source: bool = False,
    mismatch_lesson: int | None = None,
    include_second_group: bool = False,
    extra_missing_lesson: bool = False,
) -> Path:
    lesson_mappings: list[dict[str, object]] = []
    for lesson in (1, 38):
        source_name = f"lesson-{lesson}-n.tex"
        _write_tex(
            tmp_path / source_name,
            problem_count=1 if mismatch_lesson == lesson else 2,
        )
        lesson_mappings.append(
            _lesson_mapping(
                group="hist-n",
                lesson=lesson,
                source_path=None if missing_source and lesson == 1 else source_name,
                known_times=known_times,
            )
        )
    groups = [
        {
            "legacyGroupId": "hist-n",
            "targetGroupPublicId": "group-history-n",
        }
    ]
    if include_second_group:
        _write_tex(tmp_path / "lesson-1-p.tex")
        groups.append(
            {
                "legacyGroupId": "hist-p",
                "targetGroupPublicId": "group-history-p",
            }
        )
        lesson_mappings.append(
            _lesson_mapping(
                group="hist-p",
                lesson=1,
                source_path="lesson-1-p.tex",
                known_times=known_times,
            )
        )
    if extra_missing_lesson:
        _write_tex(tmp_path / "lesson-2-n.tex")
        lesson_mappings.append(
            _lesson_mapping(
                group="hist-n",
                lesson=2,
                source_path="lesson-2-n.tex",
                known_times=known_times,
            )
        )
    payload = {
        "schemaVersion": 1,
        "purpose": "phase2-content-history-backfill",
        "backfillId": "history-test-v1",
        "recordedAt": NOW,
        "seasonPublicId": "season-history",
        "coursePublicId": "course-history",
        "legacyLessonRange": {"first": 1, "last": 38},
        "groupMappings": groups,
        "lessonMappings": lesson_mappings,
    }
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    path.chmod(0o600)
    return path


def _legacy_rows(path: Path) -> tuple[list[tuple], list[tuple]]:
    with sqlite3.connect(path) as connection:
        lessons = connection.execute("SELECT * FROM lessons ORDER BY id").fetchall()
        problems = connection.execute("SELECT * FROM problems ORDER BY id").fetchall()
    return lessons, problems


def test_preview_is_deterministic_read_only_generic_1_to_38_and_privacy_safe(
    tmp_path,
):
    source, target = _source_and_target(tmp_path)
    mapping = _mapping(tmp_path)
    source_before = source.read_bytes()
    target_before = target.read_bytes()

    first_plan, first = preview_backfill(source, mapping)
    second_plan, second = preview_backfill(source, mapping)

    assert first == second
    assert first_plan.legacy_fingerprint == second_plan.legacy_fingerprint
    assert first["status"] == "ready"
    assert first["scope"] == {
        "legacyLessonRange": {"first": 1, "last": 38},
        "mappedGroups": 1,
        "discoveredGroupLessons": 2,
        "mappedGroupLessons": 2,
        "legacyProblems": 4,
    }
    assert first["predictedChanges"]["legacyRowsUpdated"] == 0
    serialized = json.dumps(first, ensure_ascii=False)
    for private_value in (
        "Synthetic",
        "Student0001",
        "never-report-this-token",
        "Введите целое число",
        "Общее название",
        "17",
    ):
        assert private_value not in serialized
    assert source.read_bytes() == source_before
    assert target.read_bytes() == target_before


def test_apply_is_transactional_and_idempotent_and_never_rewrites_legacy_rows(
    tmp_path,
):
    source, target = _source_and_target(tmp_path)
    mapping = _mapping(tmp_path)
    source_before = source.read_bytes()
    legacy_before = _legacy_rows(target)
    _plan, preview = preview_backfill(source, mapping)
    with sqlite3.connect(target) as connection:
        foreign_keys_before = connection.execute("PRAGMA foreign_key_check").fetchall()

    _first_plan, first = apply_backfill(
        source,
        target,
        mapping,
        expected_preview_sha256=preview["previewSha256"],
    )
    first_counts = {}
    with sqlite3.connect(target) as connection:
        for table in (
            "course_lessons",
            "group_lessons",
            "lesson_windows",
            "content_sources",
            "content_revisions",
            "content_derivatives",
            "content_problem_matches",
            "problem_revisions",
            "lesson_publications",
        ):
            first_counts[table] = connection.execute(
                f"SELECT count(*) FROM {table}"
            ).fetchone()[0]
        assert (
            connection.execute("PRAGMA foreign_key_check").fetchall()
            == foreign_keys_before
        )
        publication_provenance = connection.execute(
            "SELECT DISTINCT provenance_kind, created_by_user_id, "
            "published_by_user_id FROM lesson_publications"
        ).fetchall()
        assert publication_provenance == [("legacy_backfill", None, None)]

    _second_plan, second = apply_backfill(
        source,
        target,
        mapping,
        expected_preview_sha256=preview["previewSha256"],
    )
    with sqlite3.connect(target) as connection:
        second_counts = {
            table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in first_counts
        }

    assert first["status"] == "applied"
    assert second["status"] == "already-applied"
    assert sum(second["insertedRows"].values()) == 0
    assert second_counts == first_counts
    assert _legacy_rows(target) == legacy_before
    assert source.read_bytes() == source_before


def test_unknown_historical_times_remain_null_with_manual_backfill_provenance(
    tmp_path,
):
    source, target = _source_and_target(tmp_path)
    mapping = _mapping(tmp_path, known_times=False)
    _plan, preview = preview_backfill(source, mapping)

    assert preview["status"] == "ready"
    assert preview["diagnostics"]["byCode"] == {
        "unknownPublicationTimestamp": 2,
        "unknownSubmissionTimestamp": 2,
    }
    apply_backfill(
        source,
        target,
        mapping,
        expected_preview_sha256=preview["previewSha256"],
    )

    with sqlite3.connect(target) as connection:
        assert (
            connection.execute("SELECT count(*) FROM lesson_windows").fetchone()[0] == 0
        )
        assert (
            connection.execute("SELECT count(*) FROM lesson_publications").fetchone()[0]
            == 0
        )
        provenance_rows = connection.execute(
            "SELECT provenance_json FROM content_revisions ORDER BY id"
        ).fetchall()
    assert len(provenance_rows) == 2
    for (raw_provenance,) in provenance_rows:
        provenance = json.loads(raw_provenance)
        for timestamp_name in ("publicationAt", "submissionClosesAt"):
            timestamp = provenance["historicalTimestamps"][timestamp_name]
            assert timestamp == {
                "precision": "unknown",
                "source": "manual_backfill",
                "value": None,
            }


def test_task_count_mismatch_blocks_apply(tmp_path):
    source, target = _source_and_target(tmp_path)
    mapping = _mapping(tmp_path, mismatch_lesson=38)
    _plan, preview = preview_backfill(source, mapping)

    assert preview["status"] == "blocked"
    assert preview["diagnostics"]["byCode"]["taskCountMismatch"] == 1
    with pytest.raises(ContentHistoryBackfillError, match="Blocked preview"):
        apply_backfill(
            source,
            target,
            mapping,
            expected_preview_sha256=preview["previewSha256"],
        )


def test_missing_source_and_missing_group_lesson_are_explicit(tmp_path):
    source, _target = _source_and_target(tmp_path)
    mapping = _mapping(tmp_path, missing_source=True, extra_missing_lesson=True)
    _plan, preview = preview_backfill(source, mapping)

    assert preview["status"] == "blocked"
    assert preview["diagnostics"]["byCode"]["missingSource"] == 1
    assert preview["diagnostics"]["byCode"]["missingGroupLesson"] == 1


def test_unsupported_source_encoding_is_explicit(tmp_path):
    source, _target = _source_and_target(tmp_path)
    mapping = _mapping(tmp_path)
    (tmp_path / "lesson-1-n.tex").write_bytes(b"\x98")
    _plan, preview = preview_backfill(source, mapping)

    assert preview["status"] == "blocked"
    assert preview["diagnostics"]["byCode"]["unsupportedEncoding"] == 1


def test_duplicate_titles_across_groups_are_candidates_not_automatic_merges(tmp_path):
    source, target = _source_and_target(tmp_path, include_second_group=True)
    mapping = _mapping(tmp_path, include_second_group=True)
    _plan, preview = preview_backfill(source, mapping)

    assert preview["status"] == "ready"
    assert preview["diagnostics"]["byCode"]["duplicateTitleCandidate"] == 1
    assert preview["diagnostics"]["duplicateTitleCandidateGroups"] == 2
    apply_backfill(
        source,
        target,
        mapping,
        expected_preview_sha256=preview["previewSha256"],
    )
    with sqlite3.connect(target) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM problem_synonym_groups"
            ).fetchone()[0]
            == 0
        )


def test_apply_refuses_authoritative_database_and_source_target_alias(
    tmp_path, monkeypatch
):
    source, target = _source_and_target(tmp_path)
    monkeypatch.setattr(backfill, "AUTHORITATIVE_DATABASE", target)

    with pytest.raises(ContentHistoryBackfillError, match="authoritative"):
        backfill._reject_apply_target(target, source)
    with pytest.raises(ContentHistoryBackfillError, match="must be different"):
        backfill._reject_apply_target(source, source)


def test_apply_requires_the_exact_reviewed_preview_hash(tmp_path):
    source, target = _source_and_target(tmp_path)
    mapping = _mapping(tmp_path)

    with pytest.raises(ContentHistoryBackfillError, match="does not match"):
        apply_backfill(
            source,
            target,
            mapping,
            expected_preview_sha256="0" * 64,
        )


@pytest.mark.parametrize("changed_input", ["timestamp", "scope", "tex"])
def test_reviewed_preview_binds_exact_mapping_and_source_inputs(
    tmp_path, changed_input
):
    source, target = _source_and_target(tmp_path)
    mapping = _mapping(tmp_path)
    _plan, reviewed = preview_backfill(source, mapping)

    if changed_input == "tex":
        tex_path = tmp_path / "lesson-1-n.tex"
        tex_path.write_text(
            tex_path.read_text(encoding="utf-8").replace(
                "Синтетическая задача 1.", "Изменённая задача 1."
            ),
            encoding="utf-8",
        )
    else:
        payload = json.loads(mapping.read_text(encoding="utf-8"))
        if changed_input == "timestamp":
            payload["lessonMappings"][0]["materials"][0]["publishedAt"] = (
                "2026-01-01T14:00:00Z"
            )
        else:
            payload["groupMappings"][0]["targetGroupPublicId"] = "group-history-other"
        mapping.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    _changed_plan, changed = preview_backfill(source, mapping)
    assert changed["status"] == "ready"
    assert changed["inputBindingSha256"] != reviewed["inputBindingSha256"]
    assert changed["previewSha256"] != reviewed["previewSha256"]
    with pytest.raises(ContentHistoryBackfillError, match="does not match"):
        apply_backfill(
            source,
            target,
            mapping,
            expected_preview_sha256=reviewed["previewSha256"],
        )


def test_cp1251_historical_example_uses_flat_problem_and_subpart_count(tmp_path):
    target = _seed_database(tmp_path / "example-target.sqlite3")
    with sqlite3.connect(target, autocommit=True) as connection:
        connection.execute("DELETE FROM problems")
        connection.execute("DELETE FROM lessons")
        connection.execute(
            "INSERT INTO lessons (id, group_id, lesson) VALUES (521, 'hist-n', 21)"
        )
        connection.executemany(
            "INSERT INTO problems "
            "(id, group_id, lesson, prob, item, title, prob_text, prob_type, "
            "ans_type, synonyms) VALUES (?, 'hist-n', 21, ?, '', ?, '', 1, 2, '')",
            (
                (20_000 + index, index, f"Synthetic title {index}")
                for index in range(1, 17)
            ),
        )
    source = tmp_path / "anonymized-example-source.sqlite3"
    shutil.copyfile(target, source)
    source.chmod(0o400)
    shutil.copyfile(
        REPOSITORY_ROOT / "_vmsh_examples" / "usl-21-n.tex",
        tmp_path / "usl-21-n.tex",
    )
    payload = {
        "schemaVersion": 1,
        "purpose": "phase2-content-history-backfill",
        "backfillId": "history-cp1251-v1",
        "recordedAt": NOW,
        "seasonPublicId": "season-history",
        "coursePublicId": "course-history",
        "legacyLessonRange": {"first": 1, "last": 38},
        "groupMappings": [
            {
                "legacyGroupId": "hist-n",
                "targetGroupPublicId": "group-history-n",
            }
        ],
        "lessonMappings": [
            _lesson_mapping(
                group="hist-n",
                lesson=21,
                source_path="usl-21-n.tex",
                known_times=False,
            )
        ],
    }
    mapping = tmp_path / "cp1251-mapping.json"
    mapping.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    mapping.chmod(0o600)

    plan, report = preview_backfill(source, mapping)

    assert report["status"] == "ready"
    assert report["scope"]["legacyProblems"] == 16
    assert plan.group_lessons[0].materials[0].compile_result.source.encoding.value == (
        "windows-1251"
    )
