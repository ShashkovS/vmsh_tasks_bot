"""Lease-free CAS and existing evidence invariants; vmshpwa/docs/review-sheet.md."""

import pytest

from db_methods.pwa.reviews import (
    ReviewQueueForbidden,
    ReviewThreadChanged,
    ReviewQueueNotFound,
    ReviewIdempotencyConflict,
    ReviewCompletionInvalid,
    ReviewStaffScope,
)
from models.pwa import review_sheet
from pwa_tests.integration import test_review_queue_repository as fixtures
from pwa_tests.integration.test_review_entry_transfers import add_target

review_queue_fixture = fixtures.review_queue_fixture


def detail(f, scope=fixtures.ALL_GROUPS_SCOPE):
    return f.factory.run_read(lambda c: review_sheet.detail(c, scope, "st-1"))


def payload(f, key="sheet-first", **changes):
    return {
        "schemaVersion": 1,
        "snapshot": detail(f)["snapshot"],
        "idempotencyKey": key,
        "verdict": 17,
        "comment": "Принято в простыне",
        "confirmWithoutComment": False,
        "annotations": [],
        "internalReactionId": None,
        **changes,
    }


def complete(
    f,
    value,
    *,
    actor=fixtures.TEACHER_ONE_ID,
    annotations=(),
    scope=fixtures.ALL_GROUPS_SCOPE,
):
    return f.factory.run_write(
        lambda c: review_sheet.complete(
            c,
            scope=scope,
            actor=actor,
            case_id="st-1",
            payload=value,
            annotations=annotations,
            now=fixtures.NOW,
        )
    )


def test_directory_collection_and_reads_do_not_claim(review_queue_fixture):
    f = review_queue_fixture

    def read(c):
        directory = review_sheet.directory(c, fixtures.ALL_GROUPS_SCOPE)
        assert len(directory["lessons"]) == 2
        result = review_sheet.collection(c, fixtures.ALL_GROUPS_SCOPE, lesson_id="gl-1")
        assert result["total"] == 1 and result["canOpenLesson"]
        assert result["tasks"][0]["cases"][0]["caseId"] == "st-1"
        assert (
            review_sheet.collection(
                c, fixtures.ALL_GROUPS_SCOPE, lesson_id=None, problem_id="p-1"
            )["lessonId"]
            == "gl-1"
        )
        assert {
            row["claim_token"]
            for row in c.execute("SELECT claim_token FROM written_tasks_queue")
        } == {None}

    f.factory.run_read(read)
    d = detail(f)
    assert d["pending"] and len(d["workspace"]["branches"]) == 2
    assert "claimToken" not in d["workspace"]
    assert [
        e["entryId"]
        for b in d["workspace"]["evidenceBranches"]
        for e in b["thread"]["entries"]
    ] == ["se-2", "se-3"]


@pytest.mark.asyncio
async def test_other_claim_and_heartbeat_do_not_change_snapshot(review_queue_fixture):
    f = review_queue_fixture
    before = detail(f)["snapshot"]
    lease = await f.repository.claim(
        queue_public_id=f.queue_public_ids[0],
        teacher_user_id=fixtures.TEACHER_TWO_ID,
        scope=fixtures.ALL_GROUPS_SCOPE,
    )
    await f.repository.heartbeat(
        queue_public_id=f.queue_public_ids[0],
        claim_token=lease.claim_token,
        teacher_user_id=fixtures.TEACHER_TWO_ID,
        scope=fixtures.ALL_GROUPS_SCOPE,
    )
    assert detail(f)["snapshot"] == before
    receipt = complete(f, payload(f))
    assert receipt.verdict == 17
    assert detail(f)["pending"] is False


def test_save_replay_and_cross_teacher_recheck_preserve_history(review_queue_fixture):
    f = review_queue_fixture
    first = payload(f, internalReactionId=100)
    receipt = complete(f, first)
    replay = complete(f, first)
    assert replay.replayed and replay.review_public_id == receipt.review_public_id
    assert replay.internal_reaction.reaction_id == 100
    with pytest.raises(ReviewIdempotencyConflict):
        complete(f, {**first, "comment": "Другой payload"})
    second = complete(
        f, payload(f, "sheet-second", verdict=14), actor=fixtures.TEACHER_TWO_ID
    )
    assert second.review_public_id != receipt.review_public_id
    assert detail(f)["currentReview"]["verdict"] == 14

    def read(c):
        assert (
            c.execute("SELECT count(*) AS n FROM submission_reviews").fetchone()["n"]
            == 2
        )
        assert (
            c.execute("SELECT count(*) AS n FROM results WHERE res_type=2").fetchone()[
                "n"
            ]
            == 2
        )
        pending = review_sheet.collection(
            c, fixtures.ALL_GROUPS_SCOPE, lesson_id="gl-1"
        )
        all_works = review_sheet.collection(
            c, fixtures.ALL_GROUPS_SCOPE, lesson_id="gl-1", mode="all"
        )
        assert pending["total"] == 0 and all_works["total"] == 1
        evidence = c.execute(
            "SELECT review_id,group_concat(entry_id) AS ids FROM submission_review_evidence_entries GROUP BY review_id"
        ).fetchall()
        assert evidence[0]["ids"] == evidence[1]["ids"]

    f.factory.run_read(read)


@pytest.mark.asyncio
async def test_single_review_race_then_explicit_resend(review_queue_fixture):
    f = review_queue_fixture
    stale = payload(f)
    lease = await f.repository.claim(
        queue_public_id=f.queue_public_ids[0],
        teacher_user_id=fixtures.TEACHER_ONE_ID,
        scope=fixtures.ALL_GROUPS_SCOPE,
    )
    original = await f.repository.complete(fixtures._complete_command(lease))
    with pytest.raises(ReviewThreadChanged):
        complete(f, stale, actor=fixtures.TEACHER_TWO_ID)
    assert detail(f)["currentReview"]["reviewId"] == original.review_public_id
    accepted = complete(
        f,
        {
            **stale,
            "snapshot": detail(f)["snapshot"],
            "idempotencyKey": "confirmed-new-result",
        },
        actor=fixtures.TEACHER_TWO_ID,
    )
    assert detail(f)["currentReview"]["reviewId"] == accepted.review_public_id


def test_two_sheet_snapshots_cannot_silently_overwrite(review_queue_fixture):
    f = review_queue_fixture
    one, two = payload(f, "one"), payload(f, "two", verdict=14)
    complete(f, one)
    with pytest.raises(ReviewThreadChanged):
        complete(f, two, actor=fixtures.TEACHER_TWO_ID)
    assert detail(f)["currentReview"]["verdict"] == 17


def test_scope_includes_all_synonym_branches_on_read_write_and_replay(
    review_queue_fixture,
):
    f = review_queue_fixture
    limited = ReviewStaffScope(group_public_ids=frozenset({"g-5"}))
    value = payload(f)
    with pytest.raises(ReviewQueueForbidden):
        detail(f, limited)
    with pytest.raises(ReviewQueueForbidden):
        complete(f, value, scope=limited)
    complete(f, value)
    with pytest.raises(ReviewQueueForbidden):
        complete(f, value, scope=limited)
    result = f.factory.run_read(
        lambda c: review_sheet.collection(c, limited, lesson_id="gl-1", mode="all")
    )
    assert result["total"] == 0


def test_annotations_are_bound_to_evidence_and_failure_rolls_back(review_queue_fixture):
    f = review_queue_fixture
    invalid = fixtures._annotation_manifest(attachment_public_id="sa-999")
    value = payload(f)
    with pytest.raises(ReviewCompletionInvalid):
        complete(f, value, annotations=(invalid,))
    assert detail(f)["pending"]
    valid = fixtures._annotation_manifest()
    receipt = complete(f, value, annotations=(valid,))
    assert receipt.annotations[0].attachment_public_id == "sa-1"
    assert len(detail(f)["annotations"]) == 1


def test_new_material_changes_snapshot_and_has_priority(review_queue_fixture):
    f = review_queue_fixture
    stale = payload(f)

    def add(c):
        c.execute("""INSERT INTO submission_entries
        (thread_id,problem_revision_id,author_kind,author_user_id,channel,entry_kind,state,text,server_received_at)
        SELECT thread_id,problem_revision_id,author_kind,author_user_id,channel,entry_kind,state,'Дополнение',server_received_at
        FROM submission_entries WHERE public_id='se-2'""")
        c.execute(
            "UPDATE submission_threads SET version=version+1 WHERE public_id='st-1'"
        )

    f.factory.run_write(add)
    with pytest.raises(ReviewThreadChanged):
        complete(f, stale)
    receipt = complete(f, payload(f, "new-material"))
    assert len(receipt.evidence_entry_public_ids) == 3


def _add_students(c, count):
    for index in range(count):
        student = -960_000 - index
        c.execute(
            "INSERT INTO users(id,type,name,surname) VALUES(?,1,'Ученик',?)",
            (student, str(index)),
        )
        thread = c.execute(
            """INSERT INTO submission_threads
        (student_user_id,problem_id,condition_revision_id,status,latest_entry_at,created_at,updated_at)
        SELECT ?,problem_id,condition_revision_id,'awaiting_review',latest_entry_at,created_at,updated_at
        FROM submission_threads WHERE public_id='st-1' RETURNING id""",
            (student,),
        ).fetchone()["id"]
        c.execute(
            """INSERT INTO submission_entries
        (thread_id,problem_revision_id,author_kind,author_user_id,channel,entry_kind,state,text,server_received_at)
        SELECT ?,problem_revision_id,author_kind,?,channel,entry_kind,state,'Решение',server_received_at
        FROM submission_entries WHERE public_id='se-2'""",
            (thread, student),
        )
        c.execute(
            """INSERT INTO written_tasks_queue(ts,student_id,problem_id,cur_status,updated_at)
        SELECT ts,?,problem_id,0,updated_at FROM written_tasks_queue ORDER BY id LIMIT 1""",
            (student,),
        )


@pytest.mark.parametrize("total", [299, 300, 301])
def test_lesson_limit_counts_cases_and_problem_remains_open(
    review_queue_fixture, total
):
    f = review_queue_fixture
    f.factory.run_write(lambda c: _add_students(c, total - 1))
    result = f.factory.run_read(
        lambda c: review_sheet.collection(
            c, fixtures.ALL_GROUPS_SCOPE, lesson_id="gl-1"
        )
    )
    assert result["total"] == total and result["canOpenLesson"] == (total <= 300)
    if total > 300:
        assert all(not task["cases"] and not task["parts"] for task in result["tasks"])
    selected = f.factory.run_read(
        lambda c: review_sheet.collection(
            c, fixtures.ALL_GROUPS_SCOPE, lesson_id="gl-1", problem_id="p-1"
        )
    )
    assert len(selected["tasks"][0]["cases"]) == total


def test_full_conversation_is_separate_from_gradeable_evidence(
    review_queue_fixture, tmp_path
):
    f = review_queue_fixture

    def read(c):
        result = review_sheet.conversation(
            c, fixtures.ALL_GROUPS_SCOPE, "st-1", tmp_path
        )
        assert any(
            event["text"] == "Поясните первый переход." for event in result["events"]
        )
        assert all(not event["internal"] for event in result["events"])
        assert result["nextCursor"] is None

    f.factory.run_read(read)


def test_old_only_cases_are_excluded_and_multipart_selector_is_whole_number(
    review_queue_fixture,
):
    f = review_queue_fixture
    target = f.factory.run_write(add_target)

    def arrange(c):
        c.execute("UPDATE problems SET prob=1,item='Б' WHERE public_id=?", (target,))
        c.execute(
            """INSERT INTO written_tasks_discussions(student_id,problem_id,ts,text)
        SELECT ?,id,?,'Старая посылка Telegram' FROM problems WHERE public_id=?""",
            (fixtures.STUDENT_ID, fixtures._timestamp(fixtures.NOW), target),
        )
        c.execute(
            """INSERT INTO written_tasks_queue(ts,student_id,problem_id,cur_status,updated_at)
        SELECT ?,?,id,0,? FROM problems WHERE public_id=?""",
            (
                fixtures._timestamp(fixtures.NOW),
                fixtures.STUDENT_ID,
                fixtures._timestamp(fixtures.NOW),
                target,
            ),
        )

    f.factory.run_write(arrange)
    result = f.factory.run_read(
        lambda c: review_sheet.collection(
            c, fixtures.ALL_GROUPS_SCOPE, lesson_id="gl-1", problem_id=target
        )
    )
    assert len(result["tasks"]) == 1 and len(result["tasks"][0]["parts"]) == 2
    assert result["tasks"][0]["count"] == 1
    assert (
        f.factory.run_read(
            lambda c: review_sheet.collection(
                c, fixtures.ALL_GROUPS_SCOPE, lesson_id="gl-1", mode="all"
            )
        )["total"]
        == 1
    )


def test_unknown_case_is_not_readable(review_queue_fixture):
    with pytest.raises(ReviewQueueNotFound):
        review_queue_fixture.factory.run_read(
            lambda c: review_sheet.detail(c, fixtures.ALL_GROUPS_SCOPE, "st-999")
        )


@pytest.mark.parametrize("mode", ["pending", "all"])
@pytest.mark.parametrize("limited", [False, True])
def test_pending_prefilter_matches_full_context_without_losing_aliases(
    review_queue_fixture, monkeypatch, mode, limited
):
    from db_methods.pwa import review_sheet as sheet_db
    f = review_queue_fixture
    scope = ReviewStaffScope(group_public_ids=frozenset({"g-5"})) if limited else fixtures.ALL_GROUPS_SCOPE
    def arrange(c):
        # Selected branch closed; the pending queue exists only on its synonym.
        c.execute("DELETE FROM written_tasks_queue WHERE problem_id=(SELECT problem_id FROM submission_threads WHERE public_id='st-1')")
        c.execute("UPDATE submission_threads SET status='closed',version=version+1 WHERE public_id='st-1'")
        _add_students(c, 10)
        c.execute("DELETE FROM written_tasks_queue WHERE student_id<=-960000")
        c.execute("UPDATE submission_threads SET status='closed',version=version+1 WHERE student_user_id<=-960000")
    f.factory.run_write(arrange)
    def read(c):
        return review_sheet.collection(c, scope, lesson_id="gl-1", mode=mode)
    actual = f.factory.run_read(read)
    original = sheet_db.lesson_threads
    original_context = review_sheet.context
    monkeypatch.setattr(sheet_db, "lesson_threads", lambda c, selected, **_: original(c, selected))
    monkeypatch.setattr(review_sheet, "context", lambda c, s, case, **_: original_context(c, s, case))
    assert f.factory.run_read(read) == actual
    if not limited:
        assert actual["total"] == 1


def test_completed_history_does_not_expand_pending_collection_reads(review_queue_fixture):
    f = review_queue_fixture
    def arrange(c):
        _add_students(c, 100)
        c.execute("DELETE FROM written_tasks_queue WHERE student_id<=-960000")
        c.execute("UPDATE submission_threads SET status='closed',version=version+1 WHERE student_user_id<=-960000")
    f.factory.run_write(arrange)
    statements = []
    def read(c):
        c.set_trace_callback(statements.append)
        return review_sheet.collection(c, fixtures.ALL_GROUPS_SCOPE, lesson_id="gl-1")
    assert f.factory.run_read(read)["total"] == 1
    assert len(statements) < 60


def test_condition_reuse_keeps_access_checks_and_independent_trees(review_queue_fixture, monkeypatch):
    from db_methods.pwa import review_series
    f = review_queue_fixture
    import json
    f.factory.run_write(lambda c: c.execute(
        """INSERT INTO content_derivatives
        (revision_id,kind,renderer_version,content_text,sha256,provenance_json,created_at)
        VALUES(1,'web_ast','memo-test',?,?,'{}',?)""",
        (json.dumps({"materialKind": "condition", "problems": [
            {"ordinal": 1, "blocks": [{"text": "Condition"}]}]}),
         "a" * 64, fixtures._timestamp(fixtures.NOW)),
    ))
    original = review_series._overlay_problem_titles
    overlays = []
    def overlay(c, document, revision):
        overlays.append(revision)
        return original(c, document, revision)
    monkeypatch.setattr(review_series, "_overlay_problem_titles", overlay)
    def read(c):
        documents = {}
        first = review_series.condition(c, fixtures.ALL_GROUPS_SCOPE, "p-1", documents=documents)
        second = review_series.condition(c, fixtures.ALL_GROUPS_SCOPE, "p-1", documents=documents)
        assert first == second and first["document"] is not None
        assert len(overlays) == 1
        first["document"]["problems"].clear()
        assert second["document"]["problems"]
        assert review_series.condition(c, ReviewStaffScope(), "p-1", documents=documents) is None
    f.factory.run_read(read)
