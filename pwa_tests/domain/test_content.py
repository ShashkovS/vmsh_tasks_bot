"""Pure invariants for the Phase-2 content model."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, time, timedelta

import pytest

from models.pwa.content import (
    ContentInvariantError,
    LessonWindowDraft,
    ProblemMatchDecision,
    ProblemMatchDraft,
    ProblemMetadataDraft,
    ProblemRevisionDraft,
    ProblemTitleCandidateInput,
    PublicationState,
    RevisionStatus,
    ScheduleField,
    ScheduleRuleValue,
    SourceRevisionPayload,
    find_problem_synonym_candidates,
    normalize_problem_title,
    materialize_lesson_window,
    resolve_local_wall_time,
    require_publication_transition,
    require_revision_transition,
)


NOW = datetime(2026, 9, 20, 13, tzinfo=UTC)


def test_local_wall_time_uses_named_business_timezone_not_machine_timezone():
    assert resolve_local_wall_time(
        "2026-09-20T16:30", timezone="Europe/Moscow"
    ) == datetime(2026, 9, 20, 13, 30, tzinfo=UTC)


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("2026-03-29T03:30", "does not exist"),
        ("2026-10-25T03:30", "ambiguous"),
    ],
)
def test_local_wall_time_rejects_dst_gap_and_fold(value: str, message: str):
    with pytest.raises(ContentInvariantError, match=message):
        resolve_local_wall_time(value, timezone="Europe/Helsinki")


@pytest.mark.parametrize(
    "value",
    ["2026-09-20 16:30", "2026-09-20T16:30:00", "2026-09-20T16:30Z"],
)
def test_local_wall_time_requires_exact_minute_wire_shape(value: str):
    with pytest.raises(ContentInvariantError, match="invalid"):
        resolve_local_wall_time(value, timezone="Europe/Moscow")


def test_source_payload_hashes_exact_uploaded_bytes_and_keeps_provenance():
    source = r"\section*{Задачи}".encode("cp1251")

    payload = SourceRevisionPayload.from_bytes(
        source,
        encoding="windows-1251",
        provenance={"upload": "staff", "logicalFilename": "n41.tex"},
    )

    assert payload.latex_text == r"\section*{Задачи}"
    assert payload.source_encoding == "cp1251"
    assert payload.source_sha256 == hashlib.sha256(source).hexdigest()
    assert payload.provenance["sourceByteLength"] == len(source)
    assert payload.provenance["sourceEncoding"] == "cp1251"
    assert '"logicalFilename":"n41.tex"' in payload.provenance_json()


@pytest.mark.parametrize("encoding", ["latin-1", "utf-16", ""])
def test_source_payload_rejects_unapproved_or_ambiguous_encoding(encoding):
    with pytest.raises(ContentInvariantError, match="UTF-8 or CP1251"):
        SourceRevisionPayload.from_bytes(
            b"source", encoding=encoding, provenance={"upload": "staff"}
        )


def test_source_payload_rejects_provenance_that_contradicts_bytes():
    with pytest.raises(ContentInvariantError, match="sourceByteLength"):
        SourceRevisionPayload.from_bytes(
            b"source",
            encoding="utf-8",
            provenance={"sourceByteLength": 100},
        )


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "UTF8"])
def test_source_payload_strips_utf8_bom_but_hashes_exact_bytes(encoding):
    source = b"\xef\xbb\xbf\\section*{A}"

    payload = SourceRevisionPayload.from_bytes(
        source, encoding=encoding, provenance={"upload": "test"}
    )

    assert payload.latex_text == r"\section*{A}"
    assert payload.source_encoding == "utf-8"
    assert payload.source_sha256 == hashlib.sha256(source).hexdigest()
    assert payload.source_byte_length == len(source)


def test_problem_title_normalization_is_unicode_and_whitespace_stable():
    assert normalize_problem_title("  МЕТРИК\u3000и  число ") == "метрик и число"
    assert normalize_problem_title("ＤＰ２") == "dp2"


def test_synonym_discovery_is_course_lesson_scoped_cross_group_and_read_only():
    inputs = (
        ProblemTitleCandidateInput(1, 10, 100, "Метрик и число"),
        ProblemTitleCandidateInput(1, 20, 200, "  МЕТРИК  И ЧИСЛО "),
        # Same group: never a candidate pair with problem 100.
        ProblemTitleCandidateInput(1, 10, 101, "Метрик и число"),
        # Same title but another course lesson: never crosses the boundary.
        ProblemTitleCandidateInput(2, 30, 300, "Метрик и число"),
        ProblemTitleCandidateInput(2, 40, 400, "Другая задача"),
    )

    candidates = find_problem_synonym_candidates(inputs)

    assert {(item.first_problem_id, item.second_problem_id) for item in candidates} == {
        (100, 200),
        (101, 200),
    }
    assert all(item.course_lesson_id == 1 for item in candidates)
    assert inputs[0].title == "Метрик и число"


def test_candidate_discovery_property_never_pairs_same_group_or_lesson():
    """Small exhaustive property check without a runtime fuzz dependency."""

    for lesson_count in range(1, 5):
        inputs = tuple(
            ProblemTitleCandidateInput(
                course_lesson_id=lesson,
                group_lesson_id=lesson * 100 + group,
                problem_id=lesson * 1_000 + group,
                title="Общее имя" if group % 2 else "Другое имя",
            )
            for lesson in range(1, lesson_count + 1)
            for group in range(1, 7)
        )
        for candidate in find_problem_synonym_candidates(inputs):
            assert candidate.first_group_lesson_id != candidate.second_group_lesson_id
            first_lesson = candidate.first_problem_id // 1_000
            second_lesson = candidate.second_problem_id // 1_000
            assert first_lesson == second_lesson == candidate.course_lesson_id


def test_lesson_window_keeps_solution_schedule_independent_from_cutoff():
    before_cutoff = LessonWindowDraft(
        opens_at=NOW,
        submission_closes_at=NOW + timedelta(days=5),
        hint_scheduled_at=NOW + timedelta(days=2),
        solution_scheduled_at=NOW + timedelta(days=4),
        timezone="Europe/Moscow",
    )
    after_cutoff = LessonWindowDraft(
        opens_at=NOW,
        submission_closes_at=NOW + timedelta(days=5),
        hint_scheduled_at=None,
        solution_scheduled_at=NOW + timedelta(days=6),
        timezone="Europe/Moscow",
    )

    assert before_cutoff.submission_closes_at != before_cutoff.solution_scheduled_at
    assert after_cutoff.solution_scheduled_at > after_cutoff.submission_closes_at


def test_lesson_window_rejects_naive_or_reversed_business_time():
    with pytest.raises(ContentInvariantError, match="timezone-aware"):
        LessonWindowDraft(
            opens_at=None,
            submission_closes_at=datetime(2026, 9, 20, 13),
            hint_scheduled_at=None,
            solution_scheduled_at=None,
            timezone="Europe/Moscow",
        )
    with pytest.raises(ContentInvariantError, match="earlier"):
        LessonWindowDraft(
            opens_at=NOW + timedelta(days=1),
            submission_closes_at=NOW,
            hint_scheduled_at=None,
            solution_scheduled_at=None,
            timezone="Europe/Moscow",
        )


def test_lesson_window_and_schedule_reject_unknown_timezone_or_invalid_time():
    with pytest.raises(ContentInvariantError, match="timezone is unknown"):
        LessonWindowDraft(
            opens_at=NOW,
            submission_closes_at=NOW + timedelta(days=1),
            hint_scheduled_at=None,
            solution_scheduled_at=None,
            timezone="Mars/Olympus",
        )
    with pytest.raises(ContentInvariantError, match="local time is invalid"):
        ScheduleRuleValue.from_text(
            day_offset=0, local_time="24:00", timezone="Europe/Moscow"
        )
    with pytest.raises(ContentInvariantError, match="timezone is unknown"):
        ScheduleRuleValue.from_text(
            day_offset=0, local_time="16:00", timezone="Mars/Olympus"
        )


@pytest.mark.parametrize(
    ("cycle_anchor_date", "message"),
    [
        (date(2026, 3, 29), "does not exist"),
        (date(2026, 10, 25), "ambiguous"),
    ],
)
def test_schedule_rule_rejects_dst_gap_and_fold(cycle_anchor_date, message):
    rule = ScheduleRuleValue.from_text(
        day_offset=0, local_time="02:30", timezone="Europe/Berlin"
    )

    with pytest.raises(ContentInvariantError, match=message):
        rule.resolve(cycle_anchor_date)


def test_materialized_schedule_keeps_solution_independent_from_cutoff():
    window = materialize_lesson_window(
        cycle_anchor_date=date(2026, 9, 14),
        business_timezone="Europe/Moscow",
        rules={
            ScheduleField.OPENS_AT: ScheduleRuleValue(0, time(16), "Europe/Moscow"),
            ScheduleField.SUBMISSION_CLOSES_AT: ScheduleRuleValue(
                5, time(20, 50), "Europe/Moscow"
            ),
            ScheduleField.HINT_SCHEDULED_AT: None,
            ScheduleField.SOLUTION_SCHEDULED_AT: ScheduleRuleValue(
                6, time(9), "Europe/Moscow"
            ),
        },
    )

    assert window.submission_closes_at == datetime(2026, 9, 19, 17, 50, tzinfo=UTC)
    assert window.solution_scheduled_at == datetime(2026, 9, 20, 6, tzinfo=UTC)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (RevisionStatus.UPLOADED, RevisionStatus.COMPILING),
        (RevisionStatus.COMPILING, RevisionStatus.READY),
        (RevisionStatus.READY, RevisionStatus.SUPERSEDED),
        (RevisionStatus.UPLOADED, RevisionStatus.INVALID),
    ],
)
def test_supported_revision_transitions(current, target):
    require_revision_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (RevisionStatus.UPLOADED, RevisionStatus.READY),
        (RevisionStatus.READY, RevisionStatus.COMPILING),
        (RevisionStatus.INVALID, RevisionStatus.UPLOADED),
    ],
)
def test_backward_or_skipped_revision_transitions_fail(current, target):
    with pytest.raises(ContentInvariantError, match="cannot transition"):
        require_revision_transition(current, target)


def test_problem_revision_allows_empty_type_specific_configs():
    draft = ProblemRevisionDraft(
        problem_id=1,
        source_ordinal=0,
        source_item="a",
        display_number="1",
        title="Задача",
        problem_type=2,
        answer_type=None,
        answer_config={},
        attempt_policy={},
    )

    assert draft.answer_config_json() == "{}"
    assert draft.attempt_policy_json() == "{}"


@pytest.mark.parametrize(
    "answer_type",
    [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 98, 99],
)
def test_metadata_review_accepts_every_historical_answer_type(answer_type: int):
    draft = ProblemMetadataDraft(
        problem_id=1,
        source_ordinal=1,
        source_item=" 1 ",
        display_number=" 1 ",
        title=" Тестовая задача ",
        problem_type=1,
        answer_type=answer_type,
        answer_validation=None,
        validation_error="Введите ответ",
        correct_answer=None,
        correct_answer_checker=None,
        wrong_answer="Нет",
        congratulation="Да",
    )

    assert draft.source_item == "1"
    assert draft.title == "Тестовая задача"
    assert draft.answer_config["answerType"] == answer_type


def test_metadata_review_rejects_hidden_test_config_for_written_problem():
    with pytest.raises(ContentInvariantError, match="must not keep"):
        ProblemMetadataDraft(
            problem_id=1,
            source_ordinal=1,
            source_item="1",
            display_number="1",
            title="Письменная задача",
            problem_type=2,
            answer_type=None,
            answer_validation=None,
            validation_error=None,
            correct_answer="stale",
            correct_answer_checker=None,
            wrong_answer=None,
            congratulation=None,
        )


def test_problem_match_decision_controls_problem_identity():
    assert ProblemMatchDraft(
        source_ordinal=1,
        source_item="1",
        decision=ProblemMatchDecision.INSERT_NEW,
        problem_id=None,
    ).problem_id is None
    with pytest.raises(ContentInvariantError, match="must not have"):
        ProblemMatchDraft(
            source_ordinal=1,
            source_item="1",
            decision=ProblemMatchDecision.OMIT,
            problem_id=1,
        )


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (PublicationState.SCHEDULED, PublicationState.PUBLISHED),
        (PublicationState.SCHEDULED, PublicationState.HIDDEN),
        (PublicationState.PUBLISHED, PublicationState.SUPERSEDED),
    ],
)
def test_supported_publication_transitions(current, target):
    require_publication_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (PublicationState.PUBLISHED, PublicationState.SCHEDULED),
        (PublicationState.HIDDEN, PublicationState.PUBLISHED),
        (PublicationState.SUPERSEDED, PublicationState.HIDDEN),
    ],
)
def test_terminal_or_backward_publication_transitions_fail(current, target):
    with pytest.raises(ContentInvariantError, match="cannot transition"):
        require_publication_transition(current, target)
