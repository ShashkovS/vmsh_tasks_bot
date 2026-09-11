"""Repository contracts for the first Phase-2 content increment."""

from __future__ import annotations

import asyncio
import hashlib
import sqlite3
import threading
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta

import pytest
from multidict import CIMultiDict

from apps.pwa_api import content_routes as content_routes_module
from db_methods.pwa import PwaConnectionFactory, apply_schema_migrations
from db_methods.pwa.content import (
    ContentConflict,
    ContentNotFound,
    ContentVersionConflict,
    PwaContentRepository,
    TextDerivativeDraft,
)
from models.pwa.content import (
    ContentInvariantError,
    ContentKind,
    LessonWindowDraft,
    ProblemMatchDecision,
    ProblemMatchDraft,
    ProblemMetadataDraft,
    ProblemRevisionDraft,
    PublicationState,
    RevisionStatus,
    ScheduleField,
    ScheduleOverrideMode,
    ScheduleRuleValue,
    SourceRevisionPayload,
    format_utc_timestamp,
)


NOW = datetime(2026, 9, 20, 13, tzinfo=UTC)
CYCLE_ANCHOR_DATE = date(2026, 9, 14)
BUSINESS_TIMEZONE = "Europe/Moscow"


@dataclass(frozen=True, slots=True)
class ContentFixture:
    database_path: object
    factory: PwaConnectionFactory
    repository: PwaContentRepository
    actor_user_id: int
    course_id: int
    other_course_id: int
    problem_a_id: int
    problem_a2_id: int
    problem_b_id: int
    problem_other_id: int


@pytest.fixture()
def content_fixture(tmp_path) -> ContentFixture:
    database_path = tmp_path / "content-repository.sqlite3"
    apply_schema_migrations(database_path)
    factory = PwaConnectionFactory(database_path)
    repository = PwaContentRepository(factory, clock=lambda: NOW)
    timestamp = NOW.isoformat(timespec="microseconds").replace("+00:00", "Z")

    def seed(connection):
        connection.execute("DELETE FROM kv_logins")
        actor_user_id = -930_001
        connection.execute(
            "INSERT INTO users (id, type, name, surname) "
            "VALUES (?, 2, 'Content', 'Administrator')",
            (actor_user_id,),
        )
        season_id = connection.execute(
            "INSERT INTO seasons "
            "(code, title, starts_on, ends_on, session_expires_on, "
            "status, created_at, updated_at) VALUES "
            "('content-repository', 'Content repository', "
            "'2026-09-01', '2027-05-31', '2027-08-10', 'active', ?, ?) RETURNING id",
            (timestamp, timestamp),
        ).fetchone()["id"]
        course_id = connection.execute(
            "INSERT INTO courses "
            "(season_id, code, name, subject_code, status, sort_order, "
            "accent_key, created_at, updated_at) VALUES "
            "(?, 'math', 'Math', 'math', 'active', 1, "
            "'math', ?, ?) RETURNING id",
            (season_id, timestamp, timestamp),
        ).fetchone()["id"]
        other_course_id = connection.execute(
            "INSERT INTO courses "
            "(season_id, code, name, subject_code, status, sort_order, "
            "accent_key, created_at, updated_at) VALUES "
            "(?, 'physics', 'Physics', 'physics', "
            "'active', 2, 'physics', ?, ?) RETURNING id",
            (season_id, timestamp, timestamp),
        ).fetchone()["id"]
        connection.executemany(
            "INSERT INTO groups "
            "(group_id, short_code, public_name, sort_order, is_active, is_default, "
            "allow_self_switch, is_system, score_weight, course_id, status, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 1, 0, 1, 0, 1.0, ?, 'active', ?, ?)",
            (
                (
                    "content-a",
                    "a",
                    "A",
                    1,
                    course_id,
                    timestamp,
                    timestamp,
                ),
                (
                    "content-b",
                    "b",
                    "B",
                    2,
                    course_id,
                    timestamp,
                    timestamp,
                ),
                (
                    "content-other",
                    "o",
                    "Other",
                    1,
                    other_course_id,
                    timestamp,
                    timestamp,
                ),
            ),
        )
        problem_ids = (-930_101, -930_102, -930_201, -930_301)
        connection.executemany(
            "INSERT INTO problems "
            "(id, group_id, lesson, prob, item, title, prob_text, prob_type, synonyms) "
            "VALUES (?, ?, 41, ?, '', ?, 'Synthetic condition', 2, '')",
            (
                (problem_ids[0], "content-a", 1, "Metric A"),
                (problem_ids[1], "content-a", 2, "Metric A2"),
                (problem_ids[2], "content-b", 1, "Metric B"),
                (problem_ids[3], "content-other", 1, "Metric other"),
            ),
        )
        return actor_user_id, course_id, other_course_id, problem_ids

    actor_user_id, course_id, other_course_id, problem_ids = factory.run_write(seed)
    return ContentFixture(
        database_path=database_path,
        factory=factory,
        repository=repository,
        actor_user_id=actor_user_id,
        course_id=course_id,
        other_course_id=other_course_id,
        problem_a_id=problem_ids[0],
        problem_a2_id=problem_ids[1],
        problem_b_id=problem_ids[2],
        problem_other_id=problem_ids[3],
    )


async def _create_group_lesson(
    fixture: ContentFixture,
    *,
    course_lesson_public_id: str,
    course_id: int,
    lesson_number: int,
    group_id: str,
    group_lesson_public_id: str,
):
    course_lesson = await fixture.repository.create_course_lesson(
        public_id=course_lesson_public_id,
        course_id=course_id,
        lesson_number=lesson_number,
        title=f"Lesson {lesson_number}",
        actor_user_id=fixture.actor_user_id,
    )
    group_lesson = await fixture.repository.create_group_lesson(
        public_id=group_lesson_public_id,
        course_lesson_id=course_lesson.id,
        course_id=course_id,
        group_id=group_id,
        cycle_anchor_date=CYCLE_ANCHOR_DATE,
        business_timezone=BUSINESS_TIMEZONE,
        actor_user_id=fixture.actor_user_id,
    )
    return course_lesson, group_lesson


async def _create_source_revision(
    fixture: ContentFixture,
    *,
    group_lesson_id: int,
    suffix: str,
    kind: ContentKind = ContentKind.CONDITION,
    canonical_document: object | None = None,
):
    source = await fixture.repository.create_content_source(
        public_id=f"source-{suffix}",
        group_lesson_id=group_lesson_id,
        kind=kind,
        logical_filename=f"{suffix}.tex",
        source_encoding="utf-8",
        actor_user_id=fixture.actor_user_id,
    )
    payload = SourceRevisionPayload.from_bytes(
        f"\\section*{{{suffix}}}".encode(),
        encoding="utf-8",
        provenance={"logicalFilename": f"{suffix}.tex", "upload": "synthetic-test"},
    )
    revision = await fixture.repository.append_revision(
        public_id=f"revision-{suffix}",
        source_id=source.id,
        payload=payload,
        actor_user_id=fixture.actor_user_id,
        expected_previous_revision_number=0,
    )
    compiling = await fixture.repository.transition_revision(
        public_id=revision.public_id,
        expected_version=revision.version,
        target=RevisionStatus.COMPILING,
        parser_version="fixture-parser-v1",
    )
    revision = await fixture.repository.transition_revision(
        public_id=revision.public_id,
        expected_version=compiling.version,
        target=RevisionStatus.READY,
        parser_version="fixture-parser-v1",
        canonical_document=(
            {"children": [], "type": "document"}
            if canonical_document is None
            else canonical_document
        ),
    )
    return source, revision


async def _append_ready_revision(
    fixture: ContentFixture,
    *,
    source_id: int,
    suffix: str,
    expected_previous_revision_number: int,
):
    payload = SourceRevisionPayload.from_bytes(
        f"\\section*{{{suffix}}}".encode(),
        encoding="utf-8",
        provenance={"logicalFilename": f"{suffix}.tex", "upload": "synthetic-test"},
    )
    uploaded = await fixture.repository.append_revision(
        public_id=f"revision-{suffix}",
        source_id=source_id,
        payload=payload,
        actor_user_id=fixture.actor_user_id,
        expected_previous_revision_number=expected_previous_revision_number,
    )
    compiling = await fixture.repository.transition_revision(
        public_id=uploaded.public_id,
        expected_version=uploaded.version,
        target=RevisionStatus.COMPILING,
        parser_version="fixture-parser-v1",
    )
    return await fixture.repository.transition_revision(
        public_id=uploaded.public_id,
        expected_version=compiling.version,
        target=RevisionStatus.READY,
        parser_version="fixture-parser-v1",
        canonical_document={"children": [], "type": "document"},
    )


async def _confirm_course_schedule(
    fixture: ContentFixture,
    *,
    suffix: str,
    values: dict[ScheduleField, ScheduleRuleValue],
):
    records = {}
    for field, value in values.items():
        draft = await fixture.repository.create_course_schedule_rule_draft(
            public_id=f"schedule-{suffix}-{field.value}",
            course_id=fixture.course_id,
            schedule_field=field,
            value=value,
            actor_user_id=fixture.actor_user_id,
        )
        records[field] = await fixture.repository.confirm_course_schedule_rule(
            draft_public_id=draft.public_id,
            expected_version=draft.version,
            actor_user_id=fixture.actor_user_id,
        )
    return records


async def test_course_lesson_uniqueness_and_cross_course_group_guard(content_fixture):
    fixture = content_fixture
    course_lesson = await fixture.repository.create_course_lesson(
        public_id="course-lesson-41",
        course_id=fixture.course_id,
        lesson_number=41,
        title="Занятие 41",
        actor_user_id=fixture.actor_user_id,
    )

    with pytest.raises(ContentConflict):
        await fixture.repository.create_course_lesson(
            public_id="course-lesson-41-duplicate",
            course_id=fixture.course_id,
            lesson_number=41,
            title=None,
            actor_user_id=fixture.actor_user_id,
        )
    with pytest.raises(ContentConflict):
        await fixture.repository.create_group_lesson(
            public_id="group-lesson-cross-course",
            course_lesson_id=course_lesson.id,
            course_id=fixture.course_id,
            group_id="content-other",
            cycle_anchor_date=CYCLE_ANCHOR_DATE,
            business_timezone=BUSINESS_TIMEZONE,
            actor_user_id=fixture.actor_user_id,
        )


async def test_group_windows_and_publication_kinds_are_independent(content_fixture):
    fixture = content_fixture
    course_lesson = await fixture.repository.create_course_lesson(
        public_id="course-lesson-independent",
        course_id=fixture.course_id,
        lesson_number=41,
        title=None,
        actor_user_id=fixture.actor_user_id,
    )
    group_a = await fixture.repository.create_group_lesson(
        public_id="group-lesson-independent-a",
        course_lesson_id=course_lesson.id,
        course_id=fixture.course_id,
        group_id="content-a",
        cycle_anchor_date=CYCLE_ANCHOR_DATE,
        business_timezone=BUSINESS_TIMEZONE,
        actor_user_id=fixture.actor_user_id,
    )
    group_b = await fixture.repository.create_group_lesson(
        public_id="group-lesson-independent-b",
        course_lesson_id=course_lesson.id,
        course_id=fixture.course_id,
        group_id="content-b",
        cycle_anchor_date=CYCLE_ANCHOR_DATE,
        business_timezone=BUSINESS_TIMEZONE,
        actor_user_id=fixture.actor_user_id,
    )
    _, revision_a = await _create_source_revision(
        fixture, group_lesson_id=group_a.id, suffix="independent-a-condition"
    )
    _, revision_b = await _create_source_revision(
        fixture, group_lesson_id=group_b.id, suffix="independent-b-condition"
    )
    _, hint_a = await _create_source_revision(
        fixture,
        group_lesson_id=group_a.id,
        suffix="independent-a-hint",
        kind=ContentKind.HINT,
    )
    window_a = await fixture.repository.create_lesson_window(
        public_id="window-independent-a",
        group_lesson_id=group_a.id,
        draft=LessonWindowDraft(
            opens_at=NOW,
            submission_closes_at=NOW + timedelta(days=5),
            hint_scheduled_at=NOW + timedelta(days=2),
            solution_scheduled_at=NOW + timedelta(days=5, hours=1),
            timezone="Europe/Moscow",
        ),
        actor_user_id=fixture.actor_user_id,
    )
    window_b = await fixture.repository.create_lesson_window(
        public_id="window-independent-b",
        group_lesson_id=group_b.id,
        draft=LessonWindowDraft(
            opens_at=NOW + timedelta(days=1),
            submission_closes_at=NOW + timedelta(days=7),
            hint_scheduled_at=None,
            solution_scheduled_at=NOW + timedelta(days=8),
            timezone="Europe/Moscow",
        ),
        actor_user_id=fixture.actor_user_id,
    )

    updated_a = await fixture.repository.update_lesson_window(
        public_id=window_a.public_id,
        expected_version=window_a.version,
        draft=LessonWindowDraft(
            opens_at=NOW,
            submission_closes_at=NOW + timedelta(days=6),
            hint_scheduled_at=NOW + timedelta(days=2),
            solution_scheduled_at=NOW + timedelta(days=5, hours=1),
            timezone="Europe/Moscow",
        ),
        actor_user_id=fixture.actor_user_id,
    )
    with pytest.raises(ContentVersionConflict):
        await fixture.repository.update_lesson_window(
            public_id=window_a.public_id,
            expected_version=window_a.version,
            draft=LessonWindowDraft(
                opens_at=NOW,
                submission_closes_at=NOW + timedelta(days=9),
                hint_scheduled_at=None,
                solution_scheduled_at=None,
                timezone="Europe/Moscow",
            ),
            actor_user_id=fixture.actor_user_id,
        )

    publication_a = await fixture.repository.create_publication(
        public_id="publication-independent-a-condition",
        group_lesson_id=group_a.id,
        kind=ContentKind.CONDITION,
        revision_id=revision_a.id,
        state=PublicationState.SCHEDULED,
        scheduled_at=NOW,
        actor_user_id=fixture.actor_user_id,
    )
    hint_publication_a = await fixture.repository.create_publication(
        public_id="publication-independent-a-hint",
        group_lesson_id=group_a.id,
        kind=ContentKind.HINT,
        revision_id=hint_a.id,
        state=PublicationState.PUBLISHED,
        actor_user_id=fixture.actor_user_id,
    )
    publication_b = await fixture.repository.create_publication(
        public_id="publication-independent-b-condition",
        group_lesson_id=group_b.id,
        kind=ContentKind.CONDITION,
        revision_id=revision_b.id,
        state=PublicationState.PUBLISHED,
        actor_user_id=fixture.actor_user_id,
    )
    published_a = await fixture.repository.activate_scheduled_publication(
        scheduled_public_id=publication_a.public_id,
        expected_version=publication_a.version,
        published_public_id="publication-independent-a-condition-active",
        actor_user_id=fixture.actor_user_id,
    )

    assert updated_a.submission_closes_at == NOW + timedelta(days=6)
    assert window_b.submission_closes_at == NOW + timedelta(days=7)
    assert published_a.state is PublicationState.PUBLISHED
    assert published_a.supersedes_publication_id is None
    assert published_a.activated_from_schedule_id == publication_a.id
    assert hint_publication_a.kind is ContentKind.HINT
    assert publication_b.group_lesson_id == group_b.id


async def test_schedule_rules_materialize_once_with_override_provenance(
    content_fixture,
):
    fixture = content_fixture
    course_lesson, group_lesson = await _create_group_lesson(
        fixture,
        course_lesson_public_id="course-lesson-materialized-schedule",
        course_id=fixture.course_id,
        lesson_number=46,
        group_id="content-a",
        group_lesson_public_id="group-lesson-materialized-schedule",
    )
    assert group_lesson.cycle_anchor_date == CYCLE_ANCHOR_DATE
    first_rules = await _confirm_course_schedule(
        fixture,
        suffix="materialized-v1",
        values={
            ScheduleField.OPENS_AT: ScheduleRuleValue(0, time(16), BUSINESS_TIMEZONE),
            ScheduleField.HINT_SCHEDULED_AT: ScheduleRuleValue(
                4, time(12), BUSINESS_TIMEZONE
            ),
            ScheduleField.SUBMISSION_CLOSES_AT: ScheduleRuleValue(
                5, time(20, 50), BUSINESS_TIMEZONE
            ),
            ScheduleField.SOLUTION_SCHEDULED_AT: ScheduleRuleValue(
                5, time(21), BUSINESS_TIMEZONE
            ),
        },
    )
    hint_override = await fixture.repository.create_group_schedule_override_draft(
        public_id="override-materialized-hint-disabled",
        course_id=fixture.course_id,
        group_id="content-a",
        schedule_field=ScheduleField.HINT_SCHEDULED_AT,
        mode=ScheduleOverrideMode.DISABLED,
        value=None,
        based_on_schedule_rule_id=first_rules[ScheduleField.HINT_SCHEDULED_AT].id,
        actor_user_id=fixture.actor_user_id,
    )
    await fixture.repository.confirm_group_schedule_override(
        draft_public_id=hint_override.public_id,
        expected_version=hint_override.version,
        actor_user_id=fixture.actor_user_id,
    )
    solution_override = await fixture.repository.create_group_schedule_override_draft(
        public_id="override-materialized-solution",
        course_id=fixture.course_id,
        group_id="content-a",
        schedule_field=ScheduleField.SOLUTION_SCHEDULED_AT,
        mode=ScheduleOverrideMode.OVERRIDE,
        value=ScheduleRuleValue(6, time(9), BUSINESS_TIMEZONE),
        based_on_schedule_rule_id=first_rules[ScheduleField.SOLUTION_SCHEDULED_AT].id,
        actor_user_id=fixture.actor_user_id,
    )
    await fixture.repository.confirm_group_schedule_override(
        draft_public_id=solution_override.public_id,
        expected_version=solution_override.version,
        actor_user_id=fixture.actor_user_id,
    )
    window = await fixture.repository.create_materialized_lesson_window(
        public_id="window-materialized-schedule",
        group_lesson_id=group_lesson.id,
        actor_user_id=fixture.actor_user_id,
    )
    sources_before = await fixture.repository.get_lesson_window_schedule_sources(
        lesson_window_id=window.id
    )

    assert window.opens_at == datetime(2026, 9, 14, 13, tzinfo=UTC)
    assert window.submission_closes_at == datetime(2026, 9, 19, 17, 50, tzinfo=UTC)
    assert window.hint_scheduled_at is None
    assert window.solution_scheduled_at == datetime(2026, 9, 20, 6, tzinfo=UTC)
    assert len(sources_before) == 4
    by_field = {source.schedule_field: source for source in sources_before}
    assert (
        by_field[ScheduleField.HINT_SCHEDULED_AT].resolution_mode
        is ScheduleOverrideMode.DISABLED
    )
    assert (
        by_field[ScheduleField.SOLUTION_SCHEDULED_AT].resolution_mode
        is ScheduleOverrideMode.OVERRIDE
    )

    changed_draft = await fixture.repository.create_course_schedule_rule_draft(
        public_id="schedule-materialized-v2-opens",
        course_id=fixture.course_id,
        schedule_field=ScheduleField.OPENS_AT,
        value=ScheduleRuleValue(1, time(10), BUSINESS_TIMEZONE),
        actor_user_id=fixture.actor_user_id,
    )
    preview = await fixture.repository.preview_course_schedule_rule_change(
        draft_public_id=changed_draft.public_id
    )
    await fixture.repository.confirm_course_schedule_rule(
        draft_public_id=changed_draft.public_id,
        expected_version=changed_draft.version,
        actor_user_id=fixture.actor_user_id,
    )
    stored = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT * FROM lesson_windows WHERE id = ?", (window.id,)
        ).fetchone()
    )
    sources_after = await fixture.repository.get_lesson_window_schedule_sources(
        lesson_window_id=window.id
    )

    assert preview.group_lesson_count == 1
    assert preview.materialized_window_count == 1
    assert stored["opens_at"] == "2026-09-14T13:00:00.000000Z"
    assert sources_after == sources_before
    manually_changed = await fixture.repository.update_lesson_window(
        public_id=window.public_id,
        expected_version=window.version,
        draft=LessonWindowDraft(
            opens_at=NOW,
            submission_closes_at=NOW + timedelta(days=2),
            hint_scheduled_at=None,
            solution_scheduled_at=None,
            timezone=BUSINESS_TIMEZONE,
        ),
        actor_user_id=fixture.actor_user_id,
    )
    assert manually_changed.opens_at == NOW
    assert manually_changed.submission_closes_at == NOW + timedelta(days=2)
    assert course_lesson.course_id == fixture.course_id


async def test_group_schedule_override_rejects_stale_base_rule(content_fixture):
    fixture = content_fixture
    initial = await fixture.repository.create_course_schedule_rule_draft(
        public_id="schedule-stale-base-v1",
        course_id=fixture.course_id,
        schedule_field=ScheduleField.OPENS_AT,
        value=ScheduleRuleValue(0, time(16), BUSINESS_TIMEZONE),
        actor_user_id=fixture.actor_user_id,
    )
    initial = await fixture.repository.confirm_course_schedule_rule(
        draft_public_id=initial.public_id,
        expected_version=initial.version,
        actor_user_id=fixture.actor_user_id,
    )
    stale_override = await fixture.repository.create_group_schedule_override_draft(
        public_id="override-stale-base",
        course_id=fixture.course_id,
        group_id="content-a",
        schedule_field=ScheduleField.OPENS_AT,
        mode=ScheduleOverrideMode.OVERRIDE,
        value=ScheduleRuleValue(1, time(10), BUSINESS_TIMEZONE),
        based_on_schedule_rule_id=initial.id,
        actor_user_id=fixture.actor_user_id,
    )
    replacement = await fixture.repository.create_course_schedule_rule_draft(
        public_id="schedule-stale-base-v2",
        course_id=fixture.course_id,
        schedule_field=ScheduleField.OPENS_AT,
        value=ScheduleRuleValue(0, time(17), BUSINESS_TIMEZONE),
        actor_user_id=fixture.actor_user_id,
    )
    await fixture.repository.confirm_course_schedule_rule(
        draft_public_id=replacement.public_id,
        expected_version=replacement.version,
        actor_user_id=fixture.actor_user_id,
    )

    with pytest.raises(ContentVersionConflict, match="base rule changed"):
        await fixture.repository.confirm_group_schedule_override(
            draft_public_id=stale_override.public_id,
            expected_version=stale_override.version,
            actor_user_id=fixture.actor_user_id,
        )

    stored_state = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT state FROM group_schedule_overrides WHERE id = ?",
            (stale_override.id,),
        ).fetchone()["state"]
    )
    assert stored_state == "draft"


async def test_schedule_boundaries_reject_invalid_anchor_timezone_and_cutoff_disable(
    content_fixture,
):
    fixture = content_fixture
    course_lesson = await fixture.repository.create_course_lesson(
        public_id="course-lesson-invalid-schedule",
        course_id=fixture.course_id,
        lesson_number=47,
        title=None,
        actor_user_id=fixture.actor_user_id,
    )
    with pytest.raises(ContentInvariantError, match="must be a date"):
        await fixture.repository.create_group_lesson(
            public_id="group-lesson-datetime-anchor",
            course_lesson_id=course_lesson.id,
            course_id=fixture.course_id,
            group_id="content-a",
            cycle_anchor_date=datetime(2026, 9, 14),  # type: ignore[arg-type]
            business_timezone=BUSINESS_TIMEZONE,
            actor_user_id=fixture.actor_user_id,
        )
    with pytest.raises(ContentInvariantError, match="timezone is unknown"):
        await fixture.repository.create_group_lesson(
            public_id="group-lesson-invalid-timezone",
            course_lesson_id=course_lesson.id,
            course_id=fixture.course_id,
            group_id="content-a",
            cycle_anchor_date=CYCLE_ANCHOR_DATE,
            business_timezone="Mars/Olympus",
            actor_user_id=fixture.actor_user_id,
        )
    rules = await _confirm_course_schedule(
        fixture,
        suffix="invalid-cutoff",
        values={
            ScheduleField.OPENS_AT: ScheduleRuleValue(0, time(16), BUSINESS_TIMEZONE),
            ScheduleField.HINT_SCHEDULED_AT: ScheduleRuleValue(
                4, time(12), BUSINESS_TIMEZONE
            ),
            ScheduleField.SUBMISSION_CLOSES_AT: ScheduleRuleValue(
                5, time(20, 50), BUSINESS_TIMEZONE
            ),
            ScheduleField.SOLUTION_SCHEDULED_AT: ScheduleRuleValue(
                5, time(21), BUSINESS_TIMEZONE
            ),
        },
    )
    with pytest.raises(ContentInvariantError, match="cannot be disabled"):
        await fixture.repository.create_group_schedule_override_draft(
            public_id="override-invalid-cutoff-disabled",
            course_id=fixture.course_id,
            group_id="content-a",
            schedule_field=ScheduleField.SUBMISSION_CLOSES_AT,
            mode=ScheduleOverrideMode.DISABLED,
            value=None,
            based_on_schedule_rule_id=rules[ScheduleField.SUBMISSION_CLOSES_AT].id,
            actor_user_id=fixture.actor_user_id,
        )


async def test_revision_source_is_immutable_and_append_is_optimistic(content_fixture):
    fixture = content_fixture
    _, group_lesson = await _create_group_lesson(
        fixture,
        course_lesson_public_id="course-lesson-revision",
        course_id=fixture.course_id,
        lesson_number=42,
        group_id="content-a",
        group_lesson_public_id="group-lesson-revision",
    )
    source, revision = await _create_source_revision(
        fixture, group_lesson_id=group_lesson.id, suffix="revision-immutable"
    )
    loaded = await fixture.repository.get_revision(revision.public_id)
    second_payload = SourceRevisionPayload.from_bytes(
        b"second source",
        encoding="utf-8",
        provenance={"logicalFilename": "revision-immutable.tex", "upload": "test"},
    )

    assert loaded.source_sha256 == revision.source_sha256
    assert loaded.provenance["sourceByteLength"] > 0
    with pytest.raises(ContentVersionConflict):
        await fixture.repository.append_revision(
            public_id="revision-immutable-stale",
            source_id=source.id,
            payload=second_payload,
            actor_user_id=fixture.actor_user_id,
            expected_previous_revision_number=0,
        )
    with pytest.raises(ContentConflict):
        await fixture.repository.append_revision(
            public_id="revision-immutable-duplicate",
            source_id=source.id,
            payload=SourceRevisionPayload.from_bytes(
                loaded.latex_text.encode(),
                encoding="utf-8",
                provenance={"logicalFilename": "revision-immutable.tex"},
            ),
            actor_user_id=fixture.actor_user_id,
            expected_previous_revision_number=1,
        )

    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        fixture.factory.run_write(
            lambda connection: connection.execute(
                "UPDATE content_revisions SET latex_text = 'changed' WHERE id = ?",
                (revision.id,),
            )
        )
    with pytest.raises(sqlite3.IntegrityError, match="deletion is forbidden"):
        fixture.factory.run_write(
            lambda connection: connection.execute(
                "DELETE FROM content_revisions WHERE id = ?", (revision.id,)
            )
        )


async def test_revision_compiler_state_is_optimistic_and_append_keeps_ready_lineage(
    content_fixture,
):
    fixture = content_fixture
    _, group_lesson = await _create_group_lesson(
        fixture,
        course_lesson_public_id="course-lesson-compiler-state",
        course_id=fixture.course_id,
        lesson_number=45,
        group_id="content-a",
        group_lesson_public_id="group-lesson-compiler-state",
    )
    source, first = await _create_source_revision(
        fixture, group_lesson_id=group_lesson.id, suffix="compiler-state-first"
    )
    second_payload = SourceRevisionPayload.from_bytes(
        b"second compiler source",
        encoding="utf-8",
        provenance={"logicalFilename": "compiler-state-first.tex", "upload": "test"},
    )
    second = await fixture.repository.append_revision(
        public_id="revision-compiler-state-second",
        source_id=source.id,
        payload=second_payload,
        actor_user_id=fixture.actor_user_id,
        expected_previous_revision_number=1,
    )
    with pytest.raises(sqlite3.OperationalError, match="generated column"):
        fixture.factory.run_write(
            lambda connection: connection.execute(
                "UPDATE content_revisions SET public_id = ? WHERE id = ?",
                ("revision-compiler-state-renamed", second.id),
            )
        )
    compiling = await fixture.repository.transition_revision(
        public_id=second.public_id,
        expected_version=second.version,
        target=RevisionStatus.COMPILING,
        parser_version="fixture-parser-v2",
        diagnostics=({"code": "parsing"},),
    )
    ready = await fixture.repository.transition_revision(
        public_id=second.public_id,
        expected_version=compiling.version,
        target=RevisionStatus.READY,
        parser_version="fixture-parser-v2",
        canonical_document={"type": "document", "children": [{"type": "text"}]},
        diagnostics=(),
    )

    first_after_append = await fixture.repository.get_revision(first.public_id)
    assert first_after_append.status is RevisionStatus.READY
    assert second.supersedes_revision_id == first.id
    assert ready.canonical_document == {
        "children": [{"type": "text"}],
        "type": "document",
    }
    with pytest.raises(ContentVersionConflict):
        await fixture.repository.transition_revision(
            public_id=second.public_id,
            expected_version=compiling.version,
            target=RevisionStatus.INVALID,
            parser_version="fixture-parser-v2",
            diagnostics=({"code": "late"},),
        )
    with pytest.raises(ContentInvariantError, match="canonical document"):
        uploaded = await fixture.repository.append_revision(
            public_id="revision-compiler-state-third",
            source_id=source.id,
            payload=SourceRevisionPayload.from_bytes(
                b"third compiler source",
                encoding="utf-8",
                provenance={"logicalFilename": "compiler-state-first.tex"},
            ),
            actor_user_id=fixture.actor_user_id,
            expected_previous_revision_number=2,
        )
        third_compiling = await fixture.repository.transition_revision(
            public_id=uploaded.public_id,
            expected_version=uploaded.version,
            target=RevisionStatus.COMPILING,
            parser_version="fixture-parser-v2",
        )
        await fixture.repository.transition_revision(
            public_id=uploaded.public_id,
            expected_version=third_compiling.version,
            target=RevisionStatus.READY,
            parser_version="fixture-parser-v2",
        )


async def test_content_assets_are_deduplicated_and_derivatives_keep_provenance(
    content_fixture,
):
    fixture = content_fixture
    _, group_lesson = await _create_group_lesson(
        fixture,
        course_lesson_public_id="course-lesson-assets",
        course_id=fixture.course_id,
        lesson_number=43,
        group_id="content-a",
        group_lesson_public_id="group-lesson-assets",
    )
    _, revision = await _create_source_revision(
        fixture, group_lesson_id=group_lesson.id, suffix="assets"
    )
    content = b"synthetic-svg"
    digest = hashlib.sha256(content).hexdigest()
    with pytest.raises(ContentInvariantError, match="dimensions valid"):
        await fixture.repository.register_media_asset(
            public_id="asset-too-wide",
            sha256=hashlib.sha256(b"too-wide").hexdigest(),
            storage_namespace="content",
            object_key="content/too-wide.webp",
            media_type="image/webp",
            byte_size=8,
            width=20_001,
            height=1,
            actor_user_id=fixture.actor_user_id,
        )
    first = await fixture.repository.register_media_asset(
        public_id="asset-synthetic-svg",
        sha256=digest,
        storage_namespace="content",
        object_key=f"content/{digest}.svg",
        media_type="image/svg+xml",
        byte_size=len(content),
        actor_user_id=fixture.actor_user_id,
    )
    deduplicated = await fixture.repository.register_media_asset(
        public_id="asset-synthetic-svg-second-upload",
        sha256=digest,
        storage_namespace="content",
        object_key="content/ignored-second-key.svg",
        media_type="image/svg+xml",
        byte_size=len(content),
        actor_user_id=fixture.actor_user_id,
    )
    with pytest.raises(ContentConflict, match="metadata contradicts"):
        await fixture.repository.register_media_asset(
            public_id="asset-synthetic-svg-wrong-size",
            sha256=digest,
            storage_namespace="content",
            object_key="content/wrong-size.svg",
            media_type="image/svg+xml",
            byte_size=len(content) + 1,
            actor_user_id=fixture.actor_user_id,
        )
    await fixture.repository.attach_asset(
        revision_id=revision.id,
        asset_id=first.id,
        logical_name="diagram.svg",
        role="figure",
        alt_text="Synthetic diagram",
    )
    with pytest.raises(ContentNotFound, match="revision media asset"):
        await fixture.repository.attach_asset(
            revision_id=revision.id,
            asset_id=999_999,
            logical_name="missing.svg",
            role="figure",
        )
    derivative = await fixture.repository.add_derivative(
        revision_id=revision.id,
        kind="web_html",
        renderer_version="fixture-renderer-v1",
        content_text="<p>Rendered</p>",
        provenance={"compilerVersion": "fixture-v1"},
    )
    asset_derivative = await fixture.repository.add_derivative(
        revision_id=revision.id,
        kind="thumbnail",
        renderer_version="fixture-renderer-v1",
        asset_id=first.id,
        sha256=digest,
        provenance={"compilerVersion": "fixture-v1"},
    )

    assert deduplicated.id == first.id
    assert derivative.sha256 == hashlib.sha256(b"<p>Rendered</p>").hexdigest()
    assert asset_derivative.asset_id == first.id
    with pytest.raises(ContentConflict):
        await fixture.repository.add_derivative(
            revision_id=revision.id,
            kind="web_html",
            renderer_version="fixture-renderer-v1",
            content_text="<p>Different</p>",
            provenance={"compilerVersion": "fixture-v1"},
        )
    with pytest.raises(ContentInvariantError, match="does not match"):
        await fixture.repository.add_derivative(
            revision_id=revision.id,
            kind="telegram_html",
            renderer_version="fixture-renderer-v1",
            content_text="<b>Telegram</b>",
            sha256="0" * 64,
            provenance={"compilerVersion": "fixture-v1"},
        )
    derivative_count = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT count(*) AS count FROM content_derivatives"
        ).fetchone()["count"]
    )
    with pytest.raises(ContentConflict, match="does not match media asset"):
        await fixture.repository.add_derivative(
            revision_id=revision.id,
            kind="pdf",
            renderer_version="fixture-renderer-v1",
            asset_id=first.id,
            sha256="0" * 64,
            provenance={"compilerVersion": "fixture-v1"},
        )
    assert (
        fixture.factory.run_read(
            lambda connection: connection.execute(
                "SELECT count(*) AS count FROM content_derivatives"
            ).fetchone()["count"]
        )
        == derivative_count
    )

    await fixture.repository.invalidate_derivative(derivative_id=derivative.id)
    with pytest.raises(ContentConflict, match="already invalidated"):
        await fixture.repository.invalidate_derivative(derivative_id=derivative.id)
    with pytest.raises(sqlite3.IntegrityError, match="deletion is forbidden"):
        fixture.factory.run_write(
            lambda connection: connection.execute(
                "DELETE FROM content_derivatives WHERE id = ?", (derivative.id,)
            )
        )
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        fixture.factory.run_write(
            lambda connection: connection.execute(
                "UPDATE content_revision_assets SET ordinal = 1 "
                "WHERE revision_id = ? AND logical_name = 'diagram.svg'",
                (revision.id,),
            )
        )
    fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE media_assets SET deleted_at = ? WHERE id = ?",
            (NOW.isoformat().replace("+00:00", "Z"), first.id),
        )
    )
    with pytest.raises(ContentNotFound, match="revision media asset"):
        await fixture.repository.attach_asset(
            revision_id=revision.id,
            asset_id=first.id,
            logical_name="deleted.svg",
            role="figure",
        )


async def test_media_asset_input_boundary_rejects_empty_unsafe_or_credential_url(
    content_fixture,
):
    fixture = content_fixture
    digest = hashlib.sha256(b"asset").hexdigest()
    for object_key in ("/absolute.svg", "content/../asset.svg", "content//asset.svg"):
        with pytest.raises(ContentInvariantError, match="object key"):
            await fixture.repository.register_media_asset(
                public_id="asset-invalid-key",
                sha256=digest,
                storage_namespace="content",
                object_key=object_key,
                media_type="image/svg+xml",
                byte_size=5,
                actor_user_id=fixture.actor_user_id,
            )
    with pytest.raises(ContentInvariantError, match="size must be positive"):
        await fixture.repository.register_media_asset(
            public_id="asset-empty",
            sha256=hashlib.sha256(b"").hexdigest(),
            storage_namespace="content",
            object_key="content/empty.svg",
            media_type="image/svg+xml",
            byte_size=0,
            actor_user_id=fixture.actor_user_id,
        )
    with pytest.raises(ContentInvariantError, match="without credentials"):
        await fixture.repository.register_media_asset(
            public_id="asset-url-credentials",
            sha256=digest,
            storage_namespace="content",
            object_key="content/asset.svg",
            media_type="image/svg+xml",
            byte_size=5,
            public_url="https://user:pass@example.test/asset.svg",
            actor_user_id=fixture.actor_user_id,
        )


async def test_uploaded_revision_asset_attach_is_versioned_idempotent_and_public(
    content_fixture,
):
    fixture = content_fixture
    _, group_lesson = await _create_group_lesson(
        fixture,
        course_lesson_public_id="course-lesson-asset-attach",
        course_id=fixture.course_id,
        lesson_number=72,
        group_id="content-a",
        group_lesson_public_id="group-lesson-asset-attach",
    )
    source = await fixture.repository.create_content_source(
        public_id="source-asset-attach",
        group_lesson_id=group_lesson.id,
        kind=ContentKind.CONDITION,
        logical_filename="asset-attach.tex",
        source_encoding="utf-8",
        actor_user_id=fixture.actor_user_id,
    )
    revision = await fixture.repository.append_revision(
        public_id="revision-asset-attach",
        source_id=source.id,
        payload=SourceRevisionPayload.from_bytes(
            b"asset attach",
            encoding="utf-8",
            provenance={"logicalFilename": "asset-attach.tex"},
        ),
        actor_user_id=fixture.actor_user_id,
        expected_previous_revision_number=0,
    )
    payload = b"synthetic-webp"
    asset = await fixture.repository.register_media_asset(
        public_id="asset-attach-public",
        sha256=hashlib.sha256(payload).hexdigest(),
        storage_namespace="content",
        object_key="content/sha256/asset-attach.webp",
        public_url="https://assets.example.test/asset-attach.webp",
        media_type="image/webp",
        byte_size=len(payload),
        width=320,
        height=240,
        source_filename="source.heic",
        actor_user_id=fixture.actor_user_id,
    )

    version, created = await fixture.repository.attach_asset_to_uploaded_revision(
        revision_id=revision.id,
        expected_revision_version=revision.version,
        asset_id=asset.id,
        logical_name="figures/source.heic",
        role="figure",
        alt_text="Рисунок",
    )
    assert (version, created) == (revision.version + 1, True)
    (
        retry_version,
        retry_created,
    ) = await fixture.repository.attach_asset_to_uploaded_revision(
        revision_id=revision.id,
        expected_revision_version=revision.version,
        asset_id=asset.id,
        logical_name="figures/source.heic",
        role="figure",
        alt_text="Рисунок",
    )
    assert (retry_version, retry_created) == (version, False)

    listed = await fixture.repository.list_revision_assets(revision_id=revision.id)
    assert len(listed) == 1
    assert listed[0].logical_name == "figures/source.heic"
    assert listed[0].asset.public_url == (
        "https://assets.example.test/asset-attach.webp"
    )
    assert listed[0].asset.width == 320
    assert listed[0].asset.height == 240
    assert listed[0].asset.source_filename == "source.heic"
    assert await fixture.repository.get_media_asset(asset.public_id) == listed[0].asset

    compiling = await fixture.repository.claim_revision_compilation(
        public_id=revision.public_id,
        expected_version=version,
        claim_token="asset-attach-compile-claim",
        parser_version="asset-test-v1",
    )
    with pytest.raises(ContentConflict, match="uploaded revisions"):
        await fixture.repository.attach_asset_to_uploaded_revision(
            revision_id=revision.id,
            expected_revision_version=compiling.version,
            asset_id=asset.id,
            logical_name="figures/second.heic",
            role="figure",
        )


async def test_publication_replace_activation_and_rollback_are_atomic(
    content_fixture,
):
    fixture = content_fixture
    _, group_lesson = await _create_group_lesson(
        fixture,
        course_lesson_public_id="course-lesson-publication-atomic",
        course_id=fixture.course_id,
        lesson_number=48,
        group_id="content-a",
        group_lesson_public_id="group-lesson-publication-atomic",
    )
    source, first_revision = await _create_source_revision(
        fixture, group_lesson_id=group_lesson.id, suffix="publication-atomic-first"
    )
    second_revision = await _append_ready_revision(
        fixture,
        source_id=source.id,
        suffix="publication-atomic-second",
        expected_previous_revision_number=1,
    )
    current = await fixture.repository.create_publication(
        public_id="publication-atomic-current",
        group_lesson_id=group_lesson.id,
        kind=ContentKind.CONDITION,
        revision_id=first_revision.id,
        state=PublicationState.PUBLISHED,
        actor_user_id=fixture.actor_user_id,
    )

    with pytest.raises(ContentConflict):
        await fixture.repository.replace_publication(
            public_id="publication-atomic-invalid",
            group_lesson_id=group_lesson.id,
            kind=ContentKind.CONDITION,
            revision_id=999_999,
            state=PublicationState.PUBLISHED,
            expected_current_public_id=current.public_id,
            expected_current_version=current.version,
            actor_user_id=fixture.actor_user_id,
            cancel_scheduled=True,
        )
    current_state = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT state FROM lesson_publications WHERE id = ?", (current.id,)
        ).fetchone()["state"]
    )
    assert current_state == "published"

    replacement = await fixture.repository.replace_publication(
        public_id="publication-atomic-replacement",
        group_lesson_id=group_lesson.id,
        kind=ContentKind.CONDITION,
        revision_id=second_revision.id,
        state=PublicationState.PUBLISHED,
        expected_current_public_id=current.public_id,
        expected_current_version=current.version,
        actor_user_id=fixture.actor_user_id,
        cancel_scheduled=True,
    )
    rollback = await fixture.repository.replace_publication(
        public_id="publication-atomic-rollback",
        group_lesson_id=group_lesson.id,
        kind=ContentKind.CONDITION,
        revision_id=first_revision.id,
        state=PublicationState.PUBLISHED,
        expected_current_public_id=replacement.public_id,
        expected_current_version=replacement.version,
        actor_user_id=fixture.actor_user_id,
        cancel_scheduled=True,
    )
    states = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT public_id, state, supersedes_publication_id "
            "FROM lesson_publications ORDER BY id"
        ).fetchall()
    )
    by_public_id = {row["public_id"]: row for row in states}
    assert by_public_id[current.public_id]["state"] == "superseded"
    assert by_public_id[replacement.public_id]["state"] == "superseded"
    assert by_public_id[rollback.public_id]["state"] == "published"
    assert rollback.revision_id == first_revision.id
    assert (
        by_public_id[rollback.public_id]["supersedes_publication_id"] == replacement.id
    )

    scheduled = await fixture.repository.create_publication(
        public_id="publication-atomic-scheduled",
        group_lesson_id=group_lesson.id,
        kind=ContentKind.CONDITION,
        revision_id=second_revision.id,
        state=PublicationState.SCHEDULED,
        scheduled_at=NOW,
        actor_user_id=fixture.actor_user_id,
    )
    with pytest.raises(ContentInvariantError, match="atomic activation"):
        await fixture.repository.transition_publication(
            public_id=scheduled.public_id,
            expected_version=scheduled.version,
            target=PublicationState.PUBLISHED,
            actor_user_id=fixture.actor_user_id,
        )
    activated = await fixture.repository.activate_scheduled_publication(
        scheduled_public_id=scheduled.public_id,
        expected_version=scheduled.version,
        published_public_id="publication-atomic-activated",
        actor_user_id=fixture.actor_user_id,
    )
    assert activated.state is PublicationState.PUBLISHED
    activated_lineage = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT supersedes_publication_id, activated_from_schedule_id "
            "FROM lesson_publications WHERE id = ?",
            (activated.id,),
        ).fetchone()
    )
    assert activated_lineage["supersedes_publication_id"] == rollback.id
    assert activated_lineage["activated_from_schedule_id"] == scheduled.id
    assert activated.supersedes_publication_id == rollback.id
    assert activated.activated_from_schedule_id == scheduled.id
    with pytest.raises(sqlite3.IntegrityError, match="activation schedule is outside"):
        fixture.factory.run_write(
            lambda connection: connection.execute(
                "INSERT INTO lesson_publications "
                    "(group_lesson_id, kind, revision_id, state, "
                "scheduled_at, published_at, activated_from_schedule_id, "
                "created_by_user_id, published_by_user_id, created_at, updated_at) "
                    "VALUES (?, 'condition', ?, 'published', ?, ?, ?, ?, ?, ?, ?)",
                    (
                    group_lesson.id,
                    first_revision.id,
                    format_utc_timestamp(NOW + timedelta(hours=1)),
                    format_utc_timestamp(NOW),
                    scheduled.id,
                    fixture.actor_user_id,
                    fixture.actor_user_id,
                    format_utc_timestamp(NOW),
                    format_utc_timestamp(NOW),
                ),
            )
        )
    with pytest.raises(sqlite3.IntegrityError, match="terminal audit"):
        fixture.factory.run_write(
            lambda connection: connection.execute(
                "UPDATE lesson_publications SET activated_from_schedule_id = NULL "
                "WHERE id = ?",
                (activated.id,),
            )
        )
    with pytest.raises(sqlite3.IntegrityError, match="terminal audit"):
        fixture.factory.run_write(
            lambda connection: connection.execute(
                "UPDATE lesson_publications SET revision_id = ? WHERE id = ?",
                (first_revision.id, activated.id),
            )
        )
    with pytest.raises(sqlite3.IntegrityError, match="deletion is forbidden"):
        fixture.factory.run_write(
            lambda connection: connection.execute(
                "DELETE FROM lesson_publications WHERE id = ?", (activated.id,)
            )
        )


async def test_hint_and_solution_reveals_are_scoped_while_metadata_is_editable(
    content_fixture,
):
    fixture = content_fixture
    _, group_lesson = await _create_group_lesson(
        fixture,
        course_lesson_public_id="course-lesson-reveals",
        course_id=fixture.course_id,
        lesson_number=41,
        group_id="content-a",
        group_lesson_public_id="group-lesson-reveals",
    )
    _, condition_revision = await _create_source_revision(
        fixture, group_lesson_id=group_lesson.id, suffix="reveals-condition"
    )
    problem_revision = await fixture.repository.add_problem_revision(
        content_revision_id=condition_revision.id,
        draft=ProblemRevisionDraft(
            problem_id=fixture.problem_a_id,
            source_ordinal=0,
            source_item="a",
            display_number="1",
            title="Reveal scope",
            problem_type=2,
            answer_type=None,
            answer_config={},
            attempt_policy={},
        ),
        decision=ProblemMatchDecision.AUTO_POSITION,
        actor_user_id=fixture.actor_user_id,
    )
    problem_match_id = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT id FROM content_problem_matches WHERE content_revision_id = ?",
            (condition_revision.id,),
        ).fetchone()["id"]
    )
    fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE content_problem_matches SET diagnostics_json = '[1]' "
            "WHERE id = ?",
            (problem_match_id,),
        )
    )
    assert fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT diagnostics_json FROM content_problem_matches WHERE id = ?",
            (problem_match_id,),
        ).fetchone()["diagnostics_json"]
    ) == "[1]"
    with pytest.raises(sqlite3.IntegrityError, match="deletion is forbidden"):
        fixture.factory.run_write(
            lambda connection: connection.execute(
                "DELETE FROM content_problem_matches WHERE id = ?", (problem_match_id,)
            )
        )
    fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE problem_revisions SET title = 'Corrected reveal scope', "
            "normalized_title = 'corrected reveal scope' WHERE id = ?",
            (problem_revision.id,),
        )
    )
    assert fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT title FROM problem_revisions WHERE id = ?",
            (problem_revision.id,),
        ).fetchone()["title"]
    ) == "Corrected reveal scope"
    _, hint_revision = await _create_source_revision(
        fixture,
        group_lesson_id=group_lesson.id,
        suffix="reveals-hint",
        kind=ContentKind.HINT,
        canonical_document={
            "problems": [
                {"ordinal": 1, "source_item": "1", "source_title": "Reveal scope"}
            ]
        },
    )
    _, solution_revision = await _create_source_revision(
        fixture,
        group_lesson_id=group_lesson.id,
        suffix="reveals-solution",
        kind=ContentKind.SOLUTION,
        canonical_document={
            "problems": [
                {"ordinal": 1, "source_item": "1", "source_title": "Reveal scope"}
            ]
        },
    )
    for material_revision in (hint_revision, solution_revision):
        await fixture.repository.resolve_problem_matches(
            revision_public_id=material_revision.public_id,
            expected_review_version=1,
            drafts=(
                ProblemMatchDraft(
                    source_ordinal=1,
                    source_item="1",
                    decision=ProblemMatchDecision.AUTO_POSITION,
                    problem_id=fixture.problem_a_id,
                ),
            ),
            actor_user_id=fixture.actor_user_id,
        )
    hint = await fixture.repository.create_publication(
        public_id="publication-reveals-hint",
        group_lesson_id=group_lesson.id,
        kind=ContentKind.HINT,
        revision_id=hint_revision.id,
        state=PublicationState.PUBLISHED,
        actor_user_id=fixture.actor_user_id,
    )
    solution = await fixture.repository.create_publication(
        public_id="publication-reveals-solution",
        group_lesson_id=group_lesson.id,
        kind=ContentKind.SOLUTION,
        revision_id=solution_revision.id,
        state=PublicationState.PUBLISHED,
        actor_user_id=fixture.actor_user_id,
    )

    hint_reveal_id = fixture.factory.run_write(
        lambda connection: connection.execute(
            "INSERT INTO hint_reveals "
            "(student_user_id, problem_id, publication_id, revealed_at, request_id) "
            "VALUES (?, ?, ?, ?, 'request-hint') RETURNING id",
            (fixture.actor_user_id, fixture.problem_a_id, hint.id, NOW.isoformat()),
        ).fetchone()["id"]
    )
    solution_reveal_id = fixture.factory.run_write(
        lambda connection: connection.execute(
            "INSERT INTO solution_reveals "
            "(student_user_id, problem_id, publication_id, revealed_at, request_id) "
            "VALUES (?, ?, ?, ?, 'request-solution') RETURNING id",
            (
                fixture.actor_user_id,
                fixture.problem_a_id,
                solution.id,
                NOW.isoformat(),
            ),
        ).fetchone()["id"]
    )
    with pytest.raises(sqlite3.IntegrityError, match="published matched hint"):
        fixture.factory.run_write(
            lambda connection: connection.execute(
                "INSERT INTO hint_reveals "
                "(student_user_id, problem_id, publication_id, revealed_at, request_id) "
                "VALUES (?, ?, ?, ?, 'request-wrong-problem')",
                (
                    fixture.actor_user_id,
                    fixture.problem_other_id,
                    hint.id,
                    NOW.isoformat(),
                ),
            )
        )
    for table, reveal_id in (
        ("hint_reveals", hint_reveal_id),
        ("solution_reveals", solution_reveal_id),
    ):
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            fixture.factory.run_write(
                lambda connection, table=table, reveal_id=reveal_id: connection.execute(
                    f"UPDATE {table} SET request_id = 'changed' WHERE id = ?",
                    (reveal_id,),
                )
            )
        with pytest.raises(sqlite3.IntegrityError, match="deletion is forbidden"):
            fixture.factory.run_write(
                lambda connection, table=table, reveal_id=reveal_id: connection.execute(
                    f"DELETE FROM {table} WHERE id = ?", (reveal_id,)
                )
            )


async def test_problem_matching_is_complete_scoped_and_idempotent(content_fixture):
    fixture = content_fixture
    _, group_lesson = await _create_group_lesson(
        fixture,
        course_lesson_public_id="course-lesson-match-review",
        course_id=fixture.course_id,
        lesson_number=41,
        group_id="content-a",
        group_lesson_public_id="group-lesson-match-review",
    )
    _, revision = await _create_source_revision(
        fixture,
        group_lesson_id=group_lesson.id,
        suffix="match-review",
        canonical_document={
            "problems": [
                {"ordinal": 1, "source_item": None, "source_title": "Первая"},
                {"ordinal": 2, "source_item": "named", "source_title": None},
            ]
        },
    )

    initial = await fixture.repository.get_problem_match_review(
        revision_public_id=revision.public_id
    )
    assert initial.review_version == 1
    assert [item.source.source_item for item in initial.items] == ["1", "named"]
    assert [item.suggested_problem_id for item in initial.items] == [
        fixture.problem_a_id,
        fixture.problem_a2_id,
    ]
    with pytest.raises(ContentInvariantError, match="outside the group lesson"):
        await fixture.repository.resolve_problem_matches(
            revision_public_id=revision.public_id,
            expected_review_version=initial.review_version,
            drafts=(
                ProblemMatchDraft(
                    source_ordinal=1,
                    source_item="1",
                    decision=ProblemMatchDecision.AUTO_POSITION,
                    problem_id=fixture.problem_a_id,
                ),
                ProblemMatchDraft(
                    source_ordinal=2,
                    source_item="named",
                    decision=ProblemMatchDecision.AUTO_POSITION,
                    problem_id=fixture.problem_other_id,
                ),
            ),
            actor_user_id=fixture.actor_user_id,
        )
    assert (
        fixture.factory.run_read(
            lambda connection: connection.execute(
                "SELECT count(*) AS value FROM content_problem_matches "
                "WHERE content_revision_id = ?",
                (revision.id,),
            ).fetchone()["value"]
        )
        == 0
    )
    drafts = (
        ProblemMatchDraft(
            source_ordinal=1,
            source_item="1",
            decision=ProblemMatchDecision.AUTO_POSITION,
            problem_id=fixture.problem_a_id,
        ),
        ProblemMatchDraft(
            source_ordinal=2,
            source_item="named",
            decision=ProblemMatchDecision.MANUAL_MATCH,
            problem_id=fixture.problem_a2_id,
        ),
    )
    resolved = await fixture.repository.resolve_problem_matches(
        revision_public_id=revision.public_id,
        expected_review_version=initial.review_version,
        drafts=drafts,
        actor_user_id=fixture.actor_user_id,
    )
    assert resolved.review_version == 3
    assert [item.match.decision for item in resolved.items if item.match] == [
        ProblemMatchDecision.AUTO_POSITION,
        ProblemMatchDecision.MANUAL_MATCH,
    ]

    retried = await fixture.repository.resolve_problem_matches(
        revision_public_id=revision.public_id,
        expected_review_version=initial.review_version,
        drafts=drafts,
        actor_user_id=fixture.actor_user_id,
    )
    assert retried == resolved
    with pytest.raises(ContentVersionConflict):
        await fixture.repository.resolve_problem_matches(
            revision_public_id=revision.public_id,
            expected_review_version=initial.review_version,
            drafts=(
                drafts[0],
                ProblemMatchDraft(
                    source_ordinal=2,
                    source_item="named",
                    decision=ProblemMatchDecision.OMIT,
                    problem_id=None,
                ),
            ),
            actor_user_id=fixture.actor_user_id,
        )
    corrected = await fixture.repository.resolve_problem_matches(
        revision_public_id=revision.public_id,
        expected_review_version=resolved.review_version,
        drafts=(
            drafts[0],
            ProblemMatchDraft(
                source_ordinal=2,
                source_item="named",
                decision=ProblemMatchDecision.OMIT,
                problem_id=None,
            ),
        ),
        actor_user_id=fixture.actor_user_id,
    )
    assert corrected.review_version == resolved.review_version + 1


async def test_problem_review_flattens_subparts_and_keeps_predicted_type(
    content_fixture,
):
    fixture = content_fixture
    _, group_lesson = await _create_group_lesson(
        fixture,
        course_lesson_public_id="course-lesson-points",
        course_id=fixture.course_id,
        lesson_number=43,
        group_id="content-a",
        group_lesson_public_id="group-lesson-points",
    )
    _, revision = await _create_source_revision(
        fixture,
        group_lesson_id=group_lesson.id,
        suffix="points",
        canonical_document={
            "problems": [
                {
                    "ordinal": 1,
                    "source_item": None,
                    "source_title": "Два независимых пункта",
                    "problem_type": 1,
                    "statement": [
                        {"kind": "subpart", "label": "а", "children": []},
                        {"kind": "subpart", "label": "б", "children": []},
                    ],
                }
            ]
        },
    )

    review = await fixture.repository.get_problem_match_review(
        revision_public_id=revision.public_id
    )
    assert [item.source.source_item for item in review.items] == ["а", "б"]
    assert [item.source.display_number for item in review.items] == ["1а", "1б"]

    await fixture.repository.resolve_problem_matches(
        revision_public_id=revision.public_id,
        expected_review_version=review.review_version,
        drafts=tuple(
            ProblemMatchDraft(
                source_ordinal=1,
                source_item=item,
                decision=ProblemMatchDecision.INSERT_NEW,
                problem_id=None,
            )
            for item in ("а", "б")
        ),
        actor_user_id=fixture.actor_user_id,
    )
    grid = await fixture.repository.get_problem_metadata_grid(
        revision_public_id=revision.public_id
    )

    assert [row.problem.item for row in grid.rows] == ["а", "б"]
    assert [row.problem.problem_type for row in grid.rows] == [1, 1]

    # docs/task-titles.md: independent names follow source items, not array order.
    await fixture.repository.save_problem_metadata_grid(
        revision_public_id=revision.public_id,
        expected_review_version=grid.review_version,
        drafts=tuple(
            ProblemMetadataDraft(
                problem_id=row.problem.problem_id,
                source_ordinal=1, source_item=row.source.source_item,
                display_number=row.source.display_number, title=title,
                problem_type=2, answer_type=None, answer_validation=None,
                validation_error=None, correct_answer=None, correct_answer_checker=None,
                wrong_answer=None, congratulation=None,
            )
            for row, title in zip(grid.rows, ("Первый квадрат", "Второй квадрат"))
        ),
        actor_user_id=fixture.actor_user_id,
    )
    document = {"problems": [{
        "ordinal": 1, "sourceItem": None, "title": "Общее условие",
        "blocks": [{"type": "callout", "blocks": [
            {"type": "subpart", "label": "б", "blocks": []},
            {"type": "subpart", "label": "а", "blocks": []},
        ]}],
    }]}
    await fixture.repository.apply_problem_titles(document=document, revision_id=revision.id)
    problem = document["problems"][0]
    assert problem["title"] == "Общее условие"
    assert [block["title"] for block in problem["blocks"][0]["blocks"]] == [
        "Второй квадрат", "Первый квадрат",
    ]


async def test_metadata_grid_updates_projection_and_keeps_revision_history(
    content_fixture,
):
    fixture = content_fixture
    _, group_lesson = await _create_group_lesson(
        fixture,
        course_lesson_public_id="course-lesson-metadata-grid",
        course_id=fixture.course_id,
        lesson_number=42,
        group_id="content-a",
        group_lesson_public_id="group-lesson-metadata-grid",
    )
    _, revision = await _create_source_revision(
        fixture,
        group_lesson_id=group_lesson.id,
        suffix="metadata-grid",
        canonical_document={
            "problems": [
                {"ordinal": 1, "source_item": None, "source_title": "Орехи"},
                {"ordinal": 2, "source_item": None, "source_title": "Ладьи"},
            ]
        },
    )
    matched = await fixture.repository.resolve_problem_matches(
        revision_public_id=revision.public_id,
        expected_review_version=1,
        drafts=tuple(
            ProblemMatchDraft(
                source_ordinal=ordinal,
                source_item=str(ordinal),
                decision=ProblemMatchDecision.INSERT_NEW,
                problem_id=None,
            )
            for ordinal in (1, 2)
        ),
        actor_user_id=fixture.actor_user_id,
    )
    grid = await fixture.repository.get_problem_metadata_grid(
        revision_public_id=revision.public_id
    )
    assert grid.review_version == matched.review_version == 3
    assert [row.problem.item for row in grid.rows] == ["", ""]
    assert not any(row.reviewed for row in grid.rows)

    first, second = grid.rows
    drafts = (
        ProblemMetadataDraft(
            problem_id=first.problem.problem_id,
            source_ordinal=first.source.source_ordinal,
            source_item=first.source.source_item,
            display_number=first.source.display_number,
            title="Сколько орехов",
            problem_type=1,
            answer_type=2,
            answer_validation=None,
            validation_error="Введите число орехов, например 7",
            correct_answer="7;семь",
            correct_answer_checker=None,
            wrong_answer="Нет, не столько орехов",
            congratulation="Да, всё верно!",
        ),
        ProblemMetadataDraft(
            problem_id=second.problem.problem_id,
            source_ordinal=second.source.source_ordinal,
            source_item=second.source.source_item,
            display_number=second.source.display_number,
            title="Расстановка ладей",
            problem_type=2,
            answer_type=None,
            answer_validation=None,
            validation_error=None,
            correct_answer=None,
            correct_answer_checker=None,
            wrong_answer=None,
            congratulation=None,
        ),
    )
    saved = await fixture.repository.save_problem_metadata_grid(
        revision_public_id=revision.public_id,
        expected_review_version=grid.review_version,
        drafts=drafts,
        actor_user_id=fixture.actor_user_id,
    )
    assert saved.review_version == 5
    assert all(row.reviewed for row in saved.rows)
    assert saved.rows[0].problem.correct_answer == "7;семь"
    assert saved.rows[1].problem.answer_type is None

    persisted = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT title, prob_type, ans_type, validation_error, cor_ans "
            "FROM problems WHERE id = ?",
            (first.problem.problem_id,),
        ).fetchone()
    )
    assert persisted == {
        "title": "Сколько орехов",
        "prob_type": 1,
        "ans_type": 2,
        "validation_error": "Введите число орехов, например 7",
        "cor_ans": "7;семь",
    }
    readiness = await fixture.repository.get_revision_publication_readiness(
        revision_id=revision.id
    )
    assert readiness.is_ready

    retried = await fixture.repository.save_problem_metadata_grid(
        revision_public_id=revision.public_id,
        expected_review_version=grid.review_version,
        drafts=drafts,
        actor_user_id=fixture.actor_user_id,
    )
    assert retried == saved
    with pytest.raises(ContentVersionConflict):
        await fixture.repository.save_problem_metadata_grid(
            revision_public_id=revision.public_id,
            expected_review_version=grid.review_version,
            drafts=(
                replace(drafts[0], title="Другое название"),
                drafts[1],
            ),
            actor_user_id=fixture.actor_user_id,
        )
    corrected = await fixture.repository.save_problem_metadata_grid(
        revision_public_id=revision.public_id,
        expected_review_version=saved.review_version,
        drafts=(
            replace(drafts[0], title="Другое название"),
            drafts[1],
        ),
        actor_user_id=fixture.actor_user_id,
    )
    assert corrected.review_version == saved.review_version + 1


async def test_synonym_candidates_do_not_merge_and_membership_is_versioned(
    content_fixture,
):
    fixture = content_fixture
    course_lesson = await fixture.repository.create_course_lesson(
        public_id="course-lesson-synonyms",
        course_id=fixture.course_id,
        lesson_number=41,
        title=None,
        actor_user_id=fixture.actor_user_id,
    )
    group_a = await fixture.repository.create_group_lesson(
        public_id="group-lesson-synonyms-a",
        course_lesson_id=course_lesson.id,
        course_id=fixture.course_id,
        group_id="content-a",
        cycle_anchor_date=CYCLE_ANCHOR_DATE,
        business_timezone=BUSINESS_TIMEZONE,
        actor_user_id=fixture.actor_user_id,
    )
    group_b = await fixture.repository.create_group_lesson(
        public_id="group-lesson-synonyms-b",
        course_lesson_id=course_lesson.id,
        course_id=fixture.course_id,
        group_id="content-b",
        cycle_anchor_date=CYCLE_ANCHOR_DATE,
        business_timezone=BUSINESS_TIMEZONE,
        actor_user_id=fixture.actor_user_id,
    )
    _, revision_a = await _create_source_revision(
        fixture, group_lesson_id=group_a.id, suffix="synonyms-a"
    )
    _, revision_b = await _create_source_revision(
        fixture, group_lesson_id=group_b.id, suffix="synonyms-b"
    )
    for revision, problem_id, ordinal, item, title in (
        (revision_a, fixture.problem_a_id, 0, "a", "Метрик и число"),
        (revision_a, fixture.problem_a2_id, 1, "b", "Другая задача"),
        (revision_b, fixture.problem_b_id, 0, "a", "  МЕТРИК  И ЧИСЛО "),
    ):
        await fixture.repository.add_problem_revision(
            content_revision_id=revision.id,
            draft=ProblemRevisionDraft(
                problem_id=problem_id,
                source_ordinal=ordinal,
                source_item=item,
                display_number=str(ordinal + 1),
                title=title,
                problem_type=2,
                answer_type=None,
                answer_config={},
                attempt_policy={},
            ),
            decision=ProblemMatchDecision.AUTO_POSITION,
            actor_user_id=fixture.actor_user_id,
        )

    candidates = await fixture.repository.discover_synonym_candidates(
        course_lesson_id=course_lesson.id
    )
    member_count_before = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT count(*) AS count FROM problem_synonym_members"
        ).fetchone()["count"]
    )

    assert len(candidates) == 1
    assert {
        candidates[0].first_problem_id,
        candidates[0].second_problem_id,
    } == {fixture.problem_a_id, fixture.problem_b_id}
    assert member_count_before == 0

    synonym_group = await fixture.repository.create_synonym_group(
        public_id="synonym-group-metric",
        course_lesson_id=course_lesson.id,
        group_key="metric-number",
        display_title="Метрик и число",
        actor_user_id=fixture.actor_user_id,
    )
    member_a = await fixture.repository.add_synonym_member(
        synonym_group_id=synonym_group.id,
        group_lesson_id=group_a.id,
        problem_id=fixture.problem_a_id,
        actor_user_id=fixture.actor_user_id,
    )
    await fixture.repository.add_synonym_member(
        synonym_group_id=synonym_group.id,
        group_lesson_id=group_b.id,
        problem_id=fixture.problem_b_id,
        actor_user_id=fixture.actor_user_id,
    )
    with pytest.raises(ContentConflict):
        await fixture.repository.add_synonym_member(
            synonym_group_id=synonym_group.id,
            group_lesson_id=group_a.id,
            problem_id=fixture.problem_a2_id,
            actor_user_id=fixture.actor_user_id,
        )

    removed = await fixture.repository.remove_synonym_member(
        member_id=member_a.id,
        actor_user_id=fixture.actor_user_id,
        reason="Ошибочное совпадение",
    )
    restored = await fixture.repository.add_synonym_member(
        synonym_group_id=synonym_group.id,
        group_lesson_id=group_a.id,
        problem_id=fixture.problem_a_id,
        actor_user_id=fixture.actor_user_id,
    )
    assert removed.removed_at == NOW
    assert restored.membership_version == 2
    with pytest.raises(sqlite3.IntegrityError, match="deletion is forbidden"):
        fixture.factory.run_write(
            lambda connection: connection.execute(
                "DELETE FROM problem_synonym_members WHERE id = ?", (restored.id,)
            )
        )


async def test_synonym_member_cannot_cross_course_lesson(content_fixture):
    fixture = content_fixture
    course_lesson, group_a = await _create_group_lesson(
        fixture,
        course_lesson_public_id="course-lesson-scope-math",
        course_id=fixture.course_id,
        lesson_number=44,
        group_id="content-a",
        group_lesson_public_id="group-lesson-scope-math",
    )
    _, other_group = await _create_group_lesson(
        fixture,
        course_lesson_public_id="course-lesson-scope-physics",
        course_id=fixture.other_course_id,
        lesson_number=44,
        group_id="content-other",
        group_lesson_public_id="group-lesson-scope-physics",
    )
    _, revision_a = await _create_source_revision(
        fixture, group_lesson_id=group_a.id, suffix="scope-math"
    )
    _, revision_other = await _create_source_revision(
        fixture, group_lesson_id=other_group.id, suffix="scope-physics"
    )
    for revision, problem_id in (
        (revision_a, fixture.problem_a_id),
        (revision_other, fixture.problem_other_id),
    ):
        await fixture.repository.add_problem_revision(
            content_revision_id=revision.id,
            draft=ProblemRevisionDraft(
                problem_id=problem_id,
                source_ordinal=0,
                source_item="a",
                display_number="1",
                title="Same title",
                problem_type=2,
                answer_type=None,
                answer_config={},
                attempt_policy={},
            ),
            decision=ProblemMatchDecision.AUTO_POSITION,
            actor_user_id=fixture.actor_user_id,
        )
    synonym_group = await fixture.repository.create_synonym_group(
        public_id="synonym-group-course-scope",
        course_lesson_id=course_lesson.id,
        group_key="scope",
        display_title="Same title",
        actor_user_id=fixture.actor_user_id,
    )
    await fixture.repository.add_synonym_member(
        synonym_group_id=synonym_group.id,
        group_lesson_id=group_a.id,
        problem_id=fixture.problem_a_id,
        actor_user_id=fixture.actor_user_id,
    )

    with pytest.raises(ContentConflict):
        await fixture.repository.add_synonym_member(
            synonym_group_id=synonym_group.id,
            group_lesson_id=other_group.id,
            problem_id=fixture.problem_other_id,
            actor_user_id=fixture.actor_user_id,
        )


async def test_compiled_derivative_set_rolls_back_as_one_transaction(content_fixture):
    fixture = content_fixture
    _, group_lesson = await _create_group_lesson(
        fixture,
        course_lesson_public_id="course-lesson-atomic-derivatives",
        course_id=fixture.course_id,
        lesson_number=57,
        group_id="content-a",
        group_lesson_public_id="group-lesson-atomic-derivatives",
    )
    source = await fixture.repository.create_content_source(
        public_id="source-atomic-derivatives",
        group_lesson_id=group_lesson.id,
        kind=ContentKind.CONDITION,
        logical_filename="atomic.tex",
        source_encoding="utf-8",
        actor_user_id=fixture.actor_user_id,
    )
    uploaded = await fixture.repository.append_revision(
        public_id="revision-atomic-derivatives",
        source_id=source.id,
        payload=SourceRevisionPayload.from_bytes(
            b"atomic",
            encoding="utf-8",
            provenance={"logicalFilename": "atomic.tex"},
        ),
        actor_user_id=fixture.actor_user_id,
        expected_previous_revision_number=0,
    )
    claim_token = "atomic-derivatives-claim-token"
    compiling = await fixture.repository.claim_revision_compilation(
        public_id=uploaded.public_id,
        expected_version=uploaded.version,
        claim_token=claim_token,
        parser_version="atomic-compiler-v1",
    )
    await fixture.repository.add_derivative(
        revision_id=uploaded.id,
        kind="web_html",
        renderer_version="web-renderer-v1",
        provenance={"fixture": "preexisting-conflict"},
        content_text="preexisting",
    )

    with pytest.raises(ContentConflict):
        await fixture.repository.complete_revision_compilation(
            public_id=uploaded.public_id,
            expected_version=compiling.version,
            claim_token=claim_token,
            parser_version="atomic-compiler-v1",
            canonical_document={"type": "document", "children": []},
            diagnostics=[],
            derivatives=(
                TextDerivativeDraft(
                    kind="web_ast",
                    renderer_version="document-v1",
                    content_text="{}",
                    provenance={"fixture": "atomic"},
                ),
                TextDerivativeDraft(
                    kind="web_html",
                    renderer_version="web-renderer-v1",
                    content_text="new",
                    provenance={"fixture": "atomic"},
                ),
                TextDerivativeDraft(
                    kind="telegram_html",
                    renderer_version="telegram-renderer-v1",
                    content_text="new",
                    provenance={"fixture": "atomic"},
                ),
            ),
        )

    state = fixture.factory.run_read(
        lambda connection: {
            "revision": connection.execute(
                "SELECT status, version FROM content_revisions WHERE id = ?",
                (uploaded.id,),
            ).fetchone(),
            "derivatives": connection.execute(
                "SELECT kind, content_text FROM content_derivatives "
                "WHERE revision_id = ? ORDER BY kind",
                (uploaded.id,),
            ).fetchall(),
        }
    )
    assert state["revision"] == {"status": "compiling", "version": compiling.version}
    assert state["derivatives"] == [{"kind": "web_html", "content_text": "preexisting"}]


async def test_first_upload_race_keeps_one_active_source_lineage(content_fixture):
    fixture = content_fixture
    _, group_lesson = await _create_group_lesson(
        fixture,
        course_lesson_public_id="course-lesson-source-race",
        course_id=fixture.course_id,
        lesson_number=58,
        group_id="content-a",
        group_lesson_public_id="group-lesson-source-race",
    )

    async def upload(suffix: str):
        filename = f"race/{suffix}.tex"
        return await fixture.repository.resolve_source_and_append_revision(
            source_public_id=f"source-race-{suffix}",
            revision_public_id=f"revision-race-{suffix}",
            group_lesson_id=group_lesson.id,
            kind=ContentKind.CONDITION,
            logical_filename=filename,
            payload=SourceRevisionPayload.from_bytes(
                f"\\задача {suffix} \\кзадача".encode(),
                encoding="utf-8",
                provenance={"logicalFilename": filename},
            ),
            actor_user_id=fixture.actor_user_id,
        )

    results = await asyncio.gather(
        upload("first"), upload("second"), return_exceptions=True
    )

    assert all(not isinstance(result, BaseException) for result in results)
    counts = fixture.factory.run_read(
        lambda connection: (
            connection.execute(
                "SELECT count(*) AS count FROM content_sources "
                "WHERE group_lesson_id = ? AND kind = 'condition' "
                "AND archived_at IS NULL",
                (group_lesson.id,),
            ).fetchone()["count"],
            connection.execute(
                "SELECT count(*) AS count FROM content_revisions AS revision "
                "JOIN content_sources AS source ON source.id = revision.source_id "
                "WHERE source.group_lesson_id = ? AND source.kind = 'condition'",
                (group_lesson.id,),
            ).fetchone()["count"],
        )
    )
    assert counts == (1, 2)


async def test_existing_material_slot_accepts_corrected_filename(content_fixture):
    fixture = content_fixture
    _, group_lesson = await _create_group_lesson(
        fixture,
        course_lesson_public_id="course-lesson-corrected-source",
        course_id=fixture.course_id,
        lesson_number=59,
        group_id="content-a",
        group_lesson_public_id="group-lesson-corrected-source",
    )
    first = await fixture.repository.resolve_source_and_append_revision(
        source_public_id="source-corrected-source",
        revision_public_id="revision-corrected-source-1",
        group_lesson_id=group_lesson.id,
        kind=ContentKind.HINT,
        logical_filename="usl-00-n-sol.tex",
        payload=SourceRevisionPayload.from_bytes(
            b"first", encoding="utf-8", provenance={"logicalFilename": "wrong"}
        ),
        actor_user_id=fixture.actor_user_id,
    )
    corrected = await fixture.repository.resolve_source_and_append_revision(
        source_public_id="unused-source-corrected-source",
        revision_public_id="revision-corrected-source-2",
        group_lesson_id=group_lesson.id,
        kind=ContentKind.HINT,
        logical_filename="usl-00-p-sol.tex",
        payload=SourceRevisionPayload.from_bytes(
            b"second", encoding="utf-8", provenance={"logicalFilename": "correct"}
        ),
        actor_user_id=fixture.actor_user_id,
    )

    assert corrected.source.id == first.source.id
    assert corrected.revision.revision_number == 2
    assert corrected.revision.provenance["logicalFilename"] == "correct"


async def test_repeated_identical_upload_reuses_revision(content_fixture):
    fixture = content_fixture
    _, group_lesson = await _create_group_lesson(
        fixture,
        course_lesson_public_id="course-lesson-repeat-upload",
        course_id=fixture.course_id,
        lesson_number=60,
        group_id="content-a",
        group_lesson_public_id="group-lesson-repeat-upload",
    )
    payload = SourceRevisionPayload.from_bytes(
        b"same source",
        encoding="utf-8",
        provenance={"logicalFilename": "usl-60-n.tex"},
    )
    first = await fixture.repository.resolve_source_and_append_revision(
        source_public_id="source-repeat-upload",
        revision_public_id="revision-repeat-upload-1",
        group_lesson_id=group_lesson.id,
        kind=ContentKind.CONDITION,
        logical_filename="usl-60-n.tex",
        payload=payload,
        actor_user_id=fixture.actor_user_id,
        parser_version="compiler-v1",
    )
    repeated = await fixture.repository.resolve_source_and_append_revision(
        source_public_id="unused-source-repeat-upload",
        revision_public_id="unused-revision-repeat-upload",
        group_lesson_id=group_lesson.id,
        kind=ContentKind.CONDITION,
        logical_filename="usl-60-n.tex",
        payload=payload,
        actor_user_id=fixture.actor_user_id,
        parser_version="compiler-v1",
    )

    assert repeated.source.id == first.source.id
    assert repeated.revision.id == first.revision.id
    assert repeated.revision.revision_number == 1
    count = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT count(*) AS count FROM content_revisions WHERE source_id = ?",
            (first.source.id,),
        ).fetchone()["count"]
    )
    assert count == 1

    reopened = await fixture.repository.resolve_source_and_append_revision(
        source_public_id="unused-source-repeat-upload-2",
        revision_public_id="unused-revision-repeat-upload-2",
        group_lesson_id=group_lesson.id,
        kind=ContentKind.CONDITION,
        logical_filename="usl-60-n.tex",
        payload=payload,
        actor_user_id=fixture.actor_user_id,
        parser_version="compiler-v2",
    )
    assert reopened.revision.id == first.revision.id
    assert reopened.revision.status is RevisionStatus.UPLOADED
    assert reopened.revision.parser_version == "compiler-v2"
    assert reopened.revision.version == first.revision.version + 1


async def test_source_archive_and_publication_terminal_guards_block_sql_bypass(
    content_fixture,
):
    fixture = content_fixture
    _, group_lesson = await _create_group_lesson(
        fixture,
        course_lesson_public_id="course-lesson-sql-guards",
        course_id=fixture.course_id,
        lesson_number=62,
        group_id="content-a",
        group_lesson_public_id="group-lesson-sql-guards",
    )
    source, revision = await _create_source_revision(
        fixture, group_lesson_id=group_lesson.id, suffix="sql-guards"
    )
    publication = await fixture.repository.create_publication(
        public_id="publication-sql-guards",
        group_lesson_id=group_lesson.id,
        kind=ContentKind.CONDITION,
        revision_id=revision.id,
        state=PublicationState.PUBLISHED,
        actor_user_id=fixture.actor_user_id,
    )

    with pytest.raises(sqlite3.IntegrityError, match="identity/archive"):
        fixture.factory.run_write(
            lambda connection: connection.execute(
                "UPDATE content_sources SET logical_filename = 'renamed.tex' "
                "WHERE id = ?",
                (source.id,),
            )
        )
    fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE content_sources SET archived_at = ? WHERE id = ?",
            (format_utc_timestamp(NOW), source.id),
        )
    )
    with pytest.raises(sqlite3.IntegrityError, match="identity/archive"):
        fixture.factory.run_write(
            lambda connection: connection.execute(
                "UPDATE content_sources SET archived_at = NULL WHERE id = ?",
                (source.id,),
            )
        )
    with pytest.raises(sqlite3.IntegrityError, match="deletion is forbidden"):
        fixture.factory.run_write(
            lambda connection: connection.execute(
                "DELETE FROM content_sources WHERE id = ?", (source.id,)
            )
        )
    with pytest.raises(sqlite3.IntegrityError, match="terminal audit"):
        fixture.factory.run_write(
            lambda connection: connection.execute(
                "UPDATE lesson_publications SET version = version + 1 WHERE id = ?",
                (publication.id,),
            )
        )


async def test_compile_claim_is_recoverable_after_cancel_and_fixed_lease(
    content_fixture,
):
    fixture = content_fixture
    clock_value = [NOW]
    repository = PwaContentRepository(fixture.factory, clock=lambda: clock_value[0])
    _, group_lesson = await _create_group_lesson(
        fixture,
        course_lesson_public_id="course-lesson-compile-lease",
        course_id=fixture.course_id,
        lesson_number=59,
        group_id="content-a",
        group_lesson_public_id="group-lesson-compile-lease",
    )
    source = await repository.create_content_source(
        public_id="source-compile-lease",
        group_lesson_id=group_lesson.id,
        kind=ContentKind.CONDITION,
        logical_filename="lease.tex",
        source_encoding="utf-8",
        actor_user_id=fixture.actor_user_id,
    )
    uploaded = await repository.append_revision(
        public_id="revision-compile-lease",
        source_id=source.id,
        payload=SourceRevisionPayload.from_bytes(
            b"lease",
            encoding="utf-8",
            provenance={"logicalFilename": "lease.tex"},
        ),
        actor_user_id=fixture.actor_user_id,
        expected_previous_revision_number=0,
    )
    first = await repository.claim_revision_compilation(
        public_id=uploaded.public_id,
        expected_version=uploaded.version,
        claim_token="compile-lease-first-token",
        parser_version="lease-v1",
    )
    with pytest.raises(ContentConflict, match="lease is still active"):
        await repository.claim_revision_compilation(
            public_id=uploaded.public_id,
            expected_version=first.version,
            claim_token="compile-lease-blocked-token",
            parser_version="lease-v1",
        )

    abandoned = await repository.abandon_revision_compilation(
        public_id=uploaded.public_id,
        expected_version=first.version,
        claim_token="compile-lease-first-token",
    )
    reclaimed_after_cancel = await repository.claim_revision_compilation(
        public_id=uploaded.public_id,
        expected_version=abandoned.version,
        claim_token="compile-lease-second-token",
        parser_version="lease-v1",
    )
    clock_value[0] += timedelta(minutes=2, microseconds=1)

    async def reclaim(token: str):
        return await repository.claim_revision_compilation(
            public_id=uploaded.public_id,
            expected_version=reclaimed_after_cancel.version,
            claim_token=token,
            parser_version="lease-v1",
        )

    raced = await asyncio.gather(
        reclaim("compile-lease-racer-one"),
        reclaim("compile-lease-racer-two"),
        return_exceptions=True,
    )
    winner = next(result for result in raced if not isinstance(result, BaseException))
    assert winner.compile_attempt_count == 3
    assert sum(isinstance(result, ContentVersionConflict) for result in raced) == 1


async def test_cancelled_compile_request_expires_owned_claim_for_immediate_retry(
    content_fixture,
    monkeypatch,
):
    fixture = content_fixture
    _, group_lesson = await _create_group_lesson(
        fixture,
        course_lesson_public_id="course-lesson-compile-cancel",
        course_id=fixture.course_id,
        lesson_number=63,
        group_id="content-a",
        group_lesson_public_id="group-lesson-compile-cancel",
    )
    source = await fixture.repository.create_content_source(
        public_id="source-compile-cancel",
        group_lesson_id=group_lesson.id,
        kind=ContentKind.CONDITION,
        logical_filename="cancel.tex",
        source_encoding="utf-8",
        actor_user_id=fixture.actor_user_id,
    )
    uploaded = await fixture.repository.append_revision(
        public_id="revision-compile-cancel",
        source_id=source.id,
        payload=SourceRevisionPayload.from_bytes(
            b"cancel",
            encoding="utf-8",
            provenance={"logicalFilename": "cancel.tex"},
        ),
        actor_user_id=fixture.actor_user_id,
        expected_previous_revision_number=0,
    )
    compiler_started = threading.Event()
    release_compiler = threading.Event()

    def blocking_compiler(*_args, **_kwargs):
        compiler_started.set()
        release_compiler.wait(timeout=5)
        raise AssertionError("cancelled compiler result must be ignored")

    monkeypatch.setattr(content_routes_module, "compile_latex", blocking_compiler)
    monkeypatch.setattr(
        content_routes_module,
        "_staff_actor",
        lambda _request, _scope: (None, fixture.actor_user_id),
    )

    class CompileRequest:
        app = {
            content_routes_module.PWA_CONTENT_REPOSITORY: fixture.repository,
        }
        match_info = {"revision_id": uploaded.public_id}
        headers = CIMultiDict(
            {"If-Match": f'"{uploaded.public_id}:v{uploaded.version}"'}
        )

        def __getitem__(self, key):
            if key == "request_id":
                return "compile.cancel.test"
            raise KeyError(key)

    task = asyncio.create_task(
        content_routes_module.compile_content_revision(CompileRequest())
    )
    for _attempt in range(100):
        if compiler_started.is_set():
            break
        await asyncio.sleep(0.001)
    assert compiler_started.is_set()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    release_compiler.set()

    abandoned = await fixture.repository.get_revision(uploaded.public_id)
    assert abandoned.status is RevisionStatus.COMPILING
    assert abandoned.compile_lease_expires_at == NOW
    reclaimed = await fixture.repository.claim_revision_compilation(
        public_id=uploaded.public_id,
        expected_version=abandoned.version,
        claim_token="compile-cancel-retry-token",
        parser_version="cancel-retry-v1",
    )
    assert reclaimed.compile_attempt_count == 2


async def test_due_activation_is_single_winner_across_workers(content_fixture):
    fixture = content_fixture
    _, group_lesson = await _create_group_lesson(
        fixture,
        course_lesson_public_id="course-lesson-due-race",
        course_id=fixture.course_id,
        lesson_number=60,
        group_id="content-a",
        group_lesson_public_id="group-lesson-due-race",
    )
    _, revision = await _create_source_revision(
        fixture, group_lesson_id=group_lesson.id, suffix="due-race"
    )
    scheduled = await fixture.repository.create_publication(
        public_id="publication-due-race-scheduled",
        group_lesson_id=group_lesson.id,
        kind=ContentKind.CONDITION,
        revision_id=revision.id,
        state=PublicationState.SCHEDULED,
        scheduled_at=NOW,
        actor_user_id=fixture.actor_user_id,
    )
    other_worker = PwaContentRepository(
        PwaConnectionFactory(fixture.database_path), clock=lambda: NOW
    )
    results = await asyncio.gather(
        fixture.repository.activate_next_due_publication(
            published_public_id="publication-due-race-worker-one"
        ),
        other_worker.activate_next_due_publication(
            published_public_id="publication-due-race-worker-two"
        ),
    )

    assert sum(result is not None for result in results) == 1
    rows = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT state, terminal_by_user_id, terminal_at FROM lesson_publications "
            "WHERE id = ? OR activated_from_schedule_id = ? ORDER BY id",
            (scheduled.id, scheduled.id),
        ).fetchall()
    )
    assert [row["state"] for row in rows] == ["superseded", "published"]
    assert rows[0]["terminal_by_user_id"] == fixture.actor_user_id
    assert rows[0]["terminal_at"] == format_utc_timestamp(NOW)


async def test_due_activation_uses_injected_clock_cutoff(content_fixture):
    fixture = content_fixture
    clock_value = [NOW]
    repository = PwaContentRepository(fixture.factory, clock=lambda: clock_value[0])
    _, group_lesson = await _create_group_lesson(
        fixture,
        course_lesson_public_id="course-lesson-due-clock",
        course_id=fixture.course_id,
        lesson_number=64,
        group_id="content-a",
        group_lesson_public_id="group-lesson-due-clock",
    )
    _, revision = await _create_source_revision(
        fixture, group_lesson_id=group_lesson.id, suffix="due-clock"
    )
    await repository.create_publication(
        public_id="publication-due-clock-scheduled",
        group_lesson_id=group_lesson.id,
        kind=ContentKind.CONDITION,
        revision_id=revision.id,
        state=PublicationState.SCHEDULED,
        scheduled_at=NOW + timedelta(hours=1),
        actor_user_id=fixture.actor_user_id,
    )

    assert (
        await repository.activate_next_due_publication(
            published_public_id="publication-due-clock-too-early"
        )
        is None
    )
    clock_value[0] += timedelta(hours=1)
    activated = await repository.activate_next_due_publication(
        published_public_id="publication-due-clock-on-time"
    )
    assert activated is not None
    assert activated.publication.published_at == clock_value[0]


async def test_publication_replace_binds_and_cancels_exact_scheduled_slot(
    content_fixture,
):
    fixture = content_fixture
    _, group_lesson = await _create_group_lesson(
        fixture,
        course_lesson_public_id="course-lesson-schedule-bind",
        course_id=fixture.course_id,
        lesson_number=61,
        group_id="content-a",
        group_lesson_public_id="group-lesson-schedule-bind",
    )
    source, first = await _create_source_revision(
        fixture, group_lesson_id=group_lesson.id, suffix="schedule-bind-first"
    )
    second = await _append_ready_revision(
        fixture,
        source_id=source.id,
        suffix="schedule-bind-second",
        expected_previous_revision_number=1,
    )
    published = await fixture.repository.create_publication(
        public_id="publication-schedule-bind-published",
        group_lesson_id=group_lesson.id,
        kind=ContentKind.CONDITION,
        revision_id=first.id,
        state=PublicationState.PUBLISHED,
        actor_user_id=fixture.actor_user_id,
    )
    scheduled = await fixture.repository.create_publication(
        public_id="publication-schedule-bind-scheduled",
        group_lesson_id=group_lesson.id,
        kind=ContentKind.CONDITION,
        revision_id=second.id,
        state=PublicationState.SCHEDULED,
        scheduled_at=NOW + timedelta(days=1),
        actor_user_id=fixture.actor_user_id,
    )

    with pytest.raises(ContentVersionConflict, match="scheduled publication slot"):
        await fixture.repository.replace_publication(
            public_id="publication-schedule-bind-stale",
            group_lesson_id=group_lesson.id,
            kind=ContentKind.CONDITION,
            revision_id=second.id,
            state=PublicationState.PUBLISHED,
            expected_current_public_id=published.public_id,
            expected_current_version=published.version,
            actor_user_id=fixture.actor_user_id,
            cancel_scheduled=True,
            expected_scheduled_public_id=scheduled.public_id,
            expected_scheduled_version=scheduled.version + 1,
        )
    before = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT public_id, state FROM lesson_publications ORDER BY id"
        ).fetchall()
    )
    assert before == [
        {"public_id": published.public_id, "state": "published"},
        {"public_id": scheduled.public_id, "state": "scheduled"},
    ]

    replacement = await fixture.repository.replace_publication(
        public_id="publication-schedule-bind-replacement",
        group_lesson_id=group_lesson.id,
        kind=ContentKind.CONDITION,
        revision_id=second.id,
        state=PublicationState.PUBLISHED,
        expected_current_public_id=published.public_id,
        expected_current_version=published.version,
        actor_user_id=fixture.actor_user_id,
        cancel_scheduled=True,
        expected_scheduled_public_id=scheduled.public_id,
        expected_scheduled_version=scheduled.version,
    )
    after = fixture.factory.run_read(
        lambda connection: connection.execute(
            "SELECT public_id, state, terminal_by_user_id, terminal_at "
            "FROM lesson_publications ORDER BY id"
        ).fetchall()
    )
    assert [row["state"] for row in after] == [
        "superseded",
        "superseded",
        "published",
    ]
    assert all(row["terminal_by_user_id"] == fixture.actor_user_id for row in after[:2])
    assert all(row["terminal_at"] == format_utc_timestamp(NOW) for row in after[:2])
    assert replacement.state is PublicationState.PUBLISHED
