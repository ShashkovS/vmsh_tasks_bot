"""Whole-entry routing against migrated SQLite; serial-review-feed.md."""

import pytest

from pwa_tests.integration.test_review_queue_repository import (
    ALL_GROUPS_SCOPE,
    TEACHER_ONE_ID,
    NOW,
)
from models.pwa.review_transfers import preview
from db_methods.pwa.reviews import ReviewLeaseConflict, ReviewQueueForbidden
from pwa_tests.integration import test_review_queue_repository as queue_tests

review_queue_fixture = queue_tests.review_queue_fixture


def execute(connection, **kwargs):
    from models.pwa.review_transfers import execute as transfer

    return transfer(connection, notices=("to {target}", "from {source}"), **kwargs)


def add_target(connection):
    source = connection.execute("SELECT * FROM problems ORDER BY id LIMIT 1").fetchone()
    problem = connection.execute(
        """INSERT INTO problems
      (group_id,lesson,prob,item,title,prob_text,prob_type,ans_type,ans_validation,
       validation_error,cor_ans,wrong_ans,congrat,synonyms)
      VALUES(?,?,3,'','Целевая','',2,0,'','','','','','') RETURNING id,public_id""",
        (source["group_id"], source["lesson"]),
    ).fetchone()
    connection.execute(
        """INSERT INTO content_problem_matches
      (content_revision_id,source_ordinal,source_item,problem_id,decision,resolved_by_user_id,resolved_at,diagnostics_json,created_at)
      SELECT content_revision_id,3,'3',?,'manual_match',resolved_by_user_id,resolved_at,'[]',created_at
      FROM content_problem_matches ORDER BY id LIMIT 1""",
        (problem["id"],),
    )
    connection.execute(
        """INSERT INTO problem_revisions
      (problem_id,content_revision_id,source_ordinal,source_item,display_number,title,
       normalized_title,problem_type,answer_type,answer_config_json,attempt_policy_json,
       config_version,created_at)
      SELECT ?,content_revision_id,3,'3','41а.3','Целевая','целевая',2,0,'{}','{}',1,created_at
      FROM problem_revisions ORDER BY id LIMIT 1""",
        (problem["id"],),
    )
    return problem["public_id"]


async def prepare(f):
    target = f.factory.run_write(add_target)
    lease = await f.repository.claim(
        queue_public_id=f.queue_public_ids[0],
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    args = dict(
        queue_id=f.queue_public_ids[0],
        actor=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
        now=NOW,
    )
    p = f.factory.run_read(
        lambda c: preview(c, entry_id="se-2", claim_token=lease.claim_token, **args)
    )
    return args, dict(
        schemaVersion=1,
        entryId="se-2",
        claimToken=lease.claim_token,
        targetProblemId=target,
        sourceVersion=p["sourceVersion"],
        entryVersion=p["entryVersion"],
        targetVersion=0,
        mode="clone",
        targetThreadId=None,
        idempotencyKey="prepared",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change", ["level", "lesson", "test", "lease", "entry-version", "scope", "owner"]
)
async def test_changed_scope_target_or_lease_cannot_commit(
    review_queue_fixture, change
):
    f = review_queue_fixture
    args, payload = await prepare(f)
    if change in ("level", "lesson", "test"):
        sql = {
            "level": "UPDATE problems SET group_id='review-b' WHERE public_id=?",
            "lesson": "UPDATE problems SET lesson=42 WHERE public_id=?",
            "test": "UPDATE problems SET prob_type=1 WHERE public_id=?",
        }[change]
        f.factory.run_write(lambda c: c.execute(sql, (payload["targetProblemId"],)))
    elif change == "lease":
        payload["claimToken"] = "not-my-lease"
    elif change == "entry-version":
        payload["entryVersion"] += 1
    elif change == "scope":
        args["scope"] = queue_tests.ReviewStaffScope()
    else:
        args["actor"] = queue_tests.TEACHER_TWO_ID
    with pytest.raises((ReviewQueueForbidden, ReviewLeaseConflict)):
        f.factory.run_write(lambda c: execute(c, payload=payload, **args))
    assert (
        f.factory.run_read(
            lambda c: c.execute(
                "SELECT count(*) AS n FROM submission_entry_transfers"
            ).fetchone()["n"]
        )
        == 0
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("closed", [False, True])
async def test_existing_target_verdict_and_evidence_survive_new_submission(
    review_queue_fixture,
    closed,
):
    f = review_queue_fixture
    args, payload = await prepare(f)
    first = f.factory.run_write(lambda c: execute(c, payload=payload, **args))
    queue = f.factory.run_read(
        lambda c: c.execute(
            "SELECT q.public_id FROM written_tasks_queue q JOIN problems p ON p.id=q.problem_id WHERE p.public_id=?",
            (payload["targetProblemId"],),
        ).fetchone()["public_id"]
    )
    lease = await f.repository.claim(
        queue_public_id=queue, teacher_user_id=TEACHER_ONE_ID, scope=ALL_GROUPS_SCOPE
    )
    completion = await f.repository.complete(queue_tests._complete_command(lease))
    if closed:
        f.factory.run_write(
            lambda c: c.execute(
                "UPDATE submission_threads SET status='closed',version=version+1 WHERE public_id=?",
                (completion.target_thread_public_id,),
            )
        )
    old = f.factory.run_read(
        lambda c: c.execute(
            "SELECT latest_result_id FROM submission_threads WHERE public_id=?",
            (completion.target_thread_public_id,),
        ).fetchone()["latest_result_id"]
    )
    old_entry = f.factory.run_read(
        lambda c: c.execute(
            "SELECT * FROM submission_entries WHERE public_id=?",
            (first["targetEntryId"],),
        ).fetchone()
    )
    p = f.factory.run_read(
        lambda c: preview(c, entry_id="se-2", claim_token=payload["claimToken"], **args)
    )
    payload.update(
        mode="move",
        idempotencyKey="move-after-verdict",
        sourceVersion=p["sourceVersion"],
        targetVersion=p["targets"][0]["threadVersion"],
        targetThreadId=p["targets"][0]["threadId"],
    )
    second = f.factory.run_write(lambda c: execute(c, payload=payload, **args))

    def check(c):
        target = c.execute(
            "SELECT * FROM submission_threads WHERE public_id=?",
            (completion.target_thread_public_id,),
        ).fetchone()
        assert (
            target["latest_result_id"] == old and target["status"] == "awaiting_review"
        )
        assert (
            c.execute(
                "SELECT * FROM submission_entries WHERE public_id=?",
                (first["targetEntryId"],),
            ).fetchone()
            == old_entry
        )
        assert (
            c.execute(
                "SELECT state FROM submission_entries WHERE public_id=?",
                (second["targetEntryId"],),
            ).fetchone()["state"]
            == "submitted"
        )
        assert (
            c.execute("SELECT count(*) AS n FROM submission_reviews").fetchone()["n"]
            == 1
        )

    f.factory.run_read(check)


@pytest.mark.asyncio
async def test_failure_rolls_back_material_queue_and_audit(
    review_queue_fixture, monkeypatch
):
    from db_methods.pwa import review_transfers as storage

    f = review_queue_fixture
    args, payload = await prepare(f)
    payload["mode"] = "move"
    original = storage.commit

    def fail(*a, **kw):
        original(*a, **kw)
        raise RuntimeError("synthetic post-insert failure")

    monkeypatch.setattr(storage, "commit", fail)
    with pytest.raises(RuntimeError, match="synthetic"):
        f.factory.run_write(lambda c: execute(c, payload=payload, **args))

    def check(c):
        assert (
            c.execute(
                "SELECT state FROM submission_entries WHERE public_id='se-2'"
            ).fetchone()["state"]
            == "submitted"
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM submission_entry_transfers"
            ).fetchone()["n"]
            == 0
        )
        assert (
            c.execute("SELECT count(*) AS n FROM written_tasks_queue").fetchone()["n"]
            == 2
        )

    f.factory.run_read(check)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["move", "clone"])
@pytest.mark.parametrize("photo_only", [False, True])
async def test_whole_entry_is_atomic_and_replay_safe(
    review_queue_fixture, mode, photo_only
):
    f = review_queue_fixture
    if photo_only:
        f.factory.run_write(
            lambda c: c.execute(
                "UPDATE submission_entries SET text=NULL,version=version+1 WHERE public_id='se-2'"
            )
        )
    target = f.factory.run_write(add_target)
    lease = await f.repository.claim(
        queue_public_id=f.queue_public_ids[0],
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    args = dict(
        queue_id=f.queue_public_ids[0],
        actor=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
        now=NOW,
    )
    p = f.factory.run_read(
        lambda c: preview(c, entry_id="se-2", claim_token=lease.claim_token, **args)
    )
    assert [t["problemId"] for t in p["targets"]] == [target]
    payload = dict(
        schemaVersion=1,
        entryId="se-2",
        claimToken=lease.claim_token,
        targetProblemId=target,
        sourceVersion=p["sourceVersion"],
        entryVersion=p["entryVersion"],
        targetVersion=0,
        mode=mode,
        targetThreadId=None,
        idempotencyKey="transfer-test",
    )
    response = f.factory.run_write(lambda c: execute(c, payload=payload, **args))
    assert (
        f.factory.run_write(lambda c: execute(c, payload=payload, **args)) == response
    )

    def check(c):
        original = c.execute(
            "SELECT * FROM submission_entries WHERE public_id='se-2'"
        ).fetchone()
        new = c.execute(
            "SELECT * FROM submission_entries WHERE public_id=?",
            (response["targetEntryId"],),
        ).fetchone()
        assert original["state"] == ("deleted" if mode == "move" else "submitted")
        assert new["state"] == "submitted" and new["text"] == original["text"]
        assert (
            c.execute(
                "SELECT asset_id FROM submission_attachments WHERE entry_id=?",
                (new["id"],),
            ).fetchone()["asset_id"]
            == c.execute(
                "SELECT asset_id FROM submission_attachments WHERE entry_id=?",
                (original["id"],),
            ).fetchone()["asset_id"]
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM submission_entry_transfers"
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute(
                "SELECT state FROM submission_entries WHERE public_id='se-3'"
            ).fetchone()["state"]
            == "submitted"
        )
        from db_methods.pwa.lesson_statistics import course_facts

        course = c.execute("SELECT id FROM courses ORDER BY id LIMIT 1").fetchone()[
            "id"
        ]
        pending = {row["problem_id"] for row in course_facts(c, course)[2]}
        assert 3 in pending
        assert (1 in pending) == (mode == "clone")

    f.factory.run_read(check)
    from db_methods.pwa.written_submissions import PwaWrittenSubmissionRepository

    media = await PwaWrittenSubmissionRepository(f.factory).get_staff_attachment_media(
        entry_public_id="se-2", attachment_public_id="sa-1"
    )
    assert media.media.object_key == "submission/review-asset-test-1.webp"


@pytest.mark.asyncio
async def test_preview_conflict_and_invalid_target_leave_source_untouched(
    review_queue_fixture,
):
    f = review_queue_fixture
    target = f.factory.run_write(add_target)
    lease = await f.repository.claim(
        queue_public_id=f.queue_public_ids[0],
        teacher_user_id=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    args = dict(
        queue_id=f.queue_public_ids[0],
        actor=TEACHER_ONE_ID,
        scope=ALL_GROUPS_SCOPE,
        now=NOW,
    )
    p = f.factory.run_read(
        lambda c: preview(c, entry_id="se-2", claim_token=lease.claim_token, **args)
    )
    payload = dict(
        schemaVersion=1,
        entryId="se-2",
        claimToken=lease.claim_token,
        targetProblemId=target,
        sourceVersion=p["sourceVersion"] + 1,
        entryVersion=p["entryVersion"],
        targetVersion=0,
        mode="move",
        targetThreadId=None,
        idempotencyKey="conflict",
    )
    with pytest.raises(ReviewLeaseConflict):
        f.factory.run_write(lambda c: execute(c, payload=payload, **args))
    payload["targetProblemId"] = "p-2"
    with pytest.raises(ReviewQueueForbidden):
        f.factory.run_write(lambda c: execute(c, payload=payload, **args))
    assert (
        f.factory.run_read(
            lambda c: c.execute(
                "SELECT count(*) AS n FROM submission_entry_transfers"
            ).fetchone()["n"]
        )
        == 0
    )


@pytest.mark.asyncio
async def test_move_keeps_other_pending_entry_and_releases_surviving_case(
    review_queue_fixture,
):
    f = review_queue_fixture
    args, payload = await prepare(f)

    def add(c):
        entry = c.execute("""INSERT INTO submission_entries(thread_id,problem_revision_id,author_kind,author_user_id,channel,entry_kind,state,text,server_received_at)
          SELECT thread_id,problem_revision_id,author_kind,author_user_id,channel,entry_kind,state,'Другая посылка',server_received_at
          FROM submission_entries WHERE public_id='se-2' RETURNING id""").fetchone()[
            "id"
        ]
        c.execute(
            "UPDATE submission_threads SET version=version+1 WHERE public_id='st-1'"
        )
        return entry

    remaining = f.factory.run_write(add)
    payload.update(mode="move", sourceVersion=payload["sourceVersion"] + 1)
    f.factory.run_write(lambda c: execute(c, payload=payload, **args))

    def read(c):
        assert (
            c.execute(
                "SELECT state FROM submission_entries WHERE id=?", (remaining,)
            ).fetchone()["state"]
            == "submitted"
        )
        queue = c.execute(
            "SELECT * FROM written_tasks_queue WHERE public_id=?", (args["queue_id"],)
        ).fetchone()
        assert queue["cur_status"] == 0 and queue["claim_token"] is None
        assert (
            c.execute(
                "SELECT status FROM submission_threads WHERE public_id='st-1'"
            ).fetchone()["status"]
            == "awaiting_review"
        )

    f.factory.run_read(read)


@pytest.mark.asyncio
async def test_target_lease_blocks_clone_and_teacher_test_identity_stays_excluded(
    review_queue_fixture,
):
    from db_methods.pwa.lesson_statistics import course_facts

    f = review_queue_fixture
    args, payload = await prepare(f)
    f.factory.run_write(
        lambda c: c.execute(
            "UPDATE users SET type=512 WHERE id=?", (queue_tests.STUDENT_ID,)
        )
    )
    f.factory.run_write(lambda c: execute(c, payload=payload, **args))

    def state(c):
        assert course_facts(c, 1)[2] == []
        return c.execute(
            "SELECT public_id FROM written_tasks_queue WHERE problem_id=3"
        ).fetchone()["public_id"]

    queue = f.factory.run_read(state)
    p = f.factory.run_read(
        lambda c: preview(c, entry_id="se-2", claim_token=payload["claimToken"], **args)
    )
    payload.update(
        idempotencyKey="another-clone",
        sourceVersion=p["sourceVersion"],
        targetVersion=p["targets"][0]["threadVersion"],
        targetThreadId=p["targets"][0]["threadId"],
    )
    await f.repository.claim(
        queue_public_id=queue,
        teacher_user_id=queue_tests.TEACHER_TWO_ID,
        scope=ALL_GROUPS_SCOPE,
    )
    with pytest.raises(ReviewLeaseConflict):
        f.factory.run_write(lambda c: execute(c, payload=payload, **args))
