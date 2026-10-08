"""Admin archive acceptance: vmshpwa/docs/student-results.md."""

from pwa_tests.integration import test_review_entry_transfers as transfer_support
from pwa_tests.integration import test_review_queue_repository as review_support
import pytest

from pwa_tests.integration import test_content_http_api as support
from pwa_tests.integration import test_live_marking as live
from apps.pwa_api.student_results_routes import LEGACY_SOLUTIONS_ROOT

content_http = support.content_http


async def get(f, path, role="admin"):
    r = await f.client.get(
        "/staff/api/v1/student-results/" + path,
        headers=support._headers(),
        cookies=support._cookie(f, role),
    )
    return r, await r.json()


async def test_archive_permissions_overview_oral_and_undo(content_http):
    f = content_http
    pid, spec = await live.setup(f)
    _, mark, _ = await live.operation(f, spec, pid, 0)
    for role in ("teacher", "student"):
        r, _ = await get(f, "directory", role)
        assert r.status == (401 if role == "student" else 403)
        r, _ = await get(
            f, "u-903101/probleMs/none/history".replace("probleMs", "problems"), role
        )
        assert r.status == (401 if role == "student" else 403)
    r, directory = await get(f, "directory")
    assert r.status == 200, directory
    assert any(s["studentId"] == "u-903101" for s in directory["students"])
    r, overview = await get(f, "u-903101/overview")
    assert r.status == 200, overview
    assert (
        overview["summaries"][0]["groups"][0]["problems"][0]["current"]["symbol"] == "+"
    )
    course = overview["courseId"]
    number = overview["summaries"][0]["number"]
    r, lesson = await get(f, f"u-903101/lessons/{course}/{number}")
    assert r.status == 200, lesson
    assert lesson["groups"] == []  # Oral marks do not produce empty submission cards.
    r, history = await get(f, f"u-903101/problems/{pid}/history")
    assert r.status == 200, history
    assert history["events"][0]["symbol"] == "+"
    await live.call(
        f,
        "post",
        "operations",
        dict(
            kind="undo",
            operationId="archive-undo",
            context=spec,
            targetOperationId=mark["operationId"],
        ),
    )
    r, history = await get(f, f"u-903101/problems/{pid}/history")
    assert r.status == 200, history
    assert history["events"][-1]["kind"] == "undo"


async def test_archive_legacy_paging_missing_and_safe_files(content_http, tmp_path):
    f = content_http
    pid, _ = await live.setup(f)
    root = tmp_path / "solutions"
    root.mkdir()
    (root / "old-secret-token.txt").write_text("Архивное решение", encoding="utf-8")
    # Inject only the hermetic directory, never read the developer archive.
    f.client.server.app[LEGACY_SOLUTIONS_ROOT] = root

    def seed(c):
        problem = c.execute(
            "SELECT id FROM problems WHERE public_id=?", (pid,)
        ).fetchone()["id"]
        for n in range(55):
            c.execute(
                "INSERT INTO written_tasks_discussions(student_id,problem_id,ts,text,attach_path) VALUES(?,?,?,?,?)",
                (
                    support.STUDENT_USER_ID,
                    problem,
                    f"2026-09-01 12:{n:02}:00",
                    f"Досылка {n}",
                    "solutions/old-secret-token.txt"
                    if n == 0
                    else ("../../outside.jpg" if n == 1 else None),
                ),
            )
        c.execute("UPDATE users SET type=-1 WHERE id=?", (support.STUDENT_USER_ID,))
        c.execute(
            "UPDATE course_enrollments SET status='archived' WHERE student_user_id=?",
            (support.STUDENT_USER_ID,),
        )

    f.factory.run_write(seed)
    r, data = await get(f, "directory")
    assert r.status == 200
    assert any(s["studentId"] == "u-903101" for s in data["students"])
    r, overview = await get(f, "u-903101/overview")
    assert r.status == 200, overview
    r, lesson = await get(f, f"u-903101/lessons/{overview['courseId']}/41")
    assert r.status == 200, lesson
    h = lesson["groups"][0]["problems"][0]["history"]
    assert h["total"] == 55 and len(h["events"]) == 50
    assert "Архивное решение" in h["events"][0]["text"]
    assert not h["events"][1]["attachments"][0]["available"]
    assert "old-secret-token" not in str(lesson) and "../../outside" not in str(lesson)
    r, tail = await get(f, f"u-903101/problems/{pid}/history?cursor={h['nextCursor']}")
    assert r.status == 200 and len(tail["events"]) == 5 and tail["nextCursor"] is None
    assert not set(e["id"] for e in h["events"]) & set(e["id"] for e in tail["events"])
    media = h["events"][1]["attachments"][0]["url"].split("/student-results/")[1]
    r, _ = await get(f, media)
    assert r.status == 404
    r, _ = await get(f, media, "teacher")
    assert r.status == 403


async def test_archive_modern_review_annotations_dedup_and_drafts(content_http):
    f = content_http
    # Exercise the same real upload/submit/claim/complete flow as the Family contract.
    await support.test_family_written_thread_is_read_only_child_scoped_and_hides_staff_reaction(
        f
    )
    pid = f.factory.run_read(
        lambda c: c.execute(
            "SELECT p.public_id FROM submission_threads t JOIN problems p ON p.id=t.problem_id LIMIT 1"
        ).fetchone()["public_id"]
    )
    r, h = await get(f, f"u-903101/problems/{pid}/history")
    assert r.status == 200, h
    kinds = [e["kind"] for e in h["events"]]
    assert kinds.count("review") == 1 and "result" not in kinds
    assert kinds.count("entry") == 1  # Review comment is incorporated into its review.
    review = next(e for e in h["events"] if e["kind"] == "review")
    assert (
        review["verdict"] == 15
        and review["attachments"][0]["annotation"]["rotation"] == 90
    )
    assert any(e["internal"] for e in h["events"])
    image = review["attachments"][0]["url"]
    response = await f.client.get(
        image, headers=support._headers(), cookies=support._cookie(f, "admin")
    )
    assert response.status == 200
    forbidden = await f.client.get(
        image, headers=support._headers(), cookies=support._cookie(f, "teacher")
    )
    assert forbidden.status == 403
    e = next(e for e in h["events"] if e["kind"] == "entry")
    r, doc = await get(f, f"u-903101/problems/{pid}/condition/{e['revisionId']}")
    assert r.status == 200 and doc["document"]

    def legacy(c):
        t = c.execute("SELECT id,problem_id FROM submission_threads LIMIT 1").fetchone()
        did = c.execute(
            "INSERT INTO written_tasks_discussions(student_id,problem_id,ts,text) VALUES(?,?,?,'Mapped Telegram text') RETURNING id",
            (support.STUDENT_USER_ID, t["problem_id"], "2026-09-01"),
        ).fetchone()["id"]
        c.execute(
            "INSERT INTO submission_entries(thread_id,problem_revision_id,author_kind,author_user_id,channel,entry_kind,state,text,server_received_at,legacy_discussion_id) VALUES(?,(SELECT id FROM problem_revisions LIMIT 1),'student',?,'telegram','text','submitted','Mapped Telegram text','2026-09-01',?)",
            (t["id"], support.STUDENT_USER_ID, did),
        )
        c.execute(
            "INSERT INTO submission_entries(thread_id,problem_revision_id,author_kind,author_user_id,channel,entry_kind,state,text,server_received_at) VALUES(?,(SELECT id FROM problem_revisions LIMIT 1),'student',?,'pwa','text','draft','SECRET DRAFT','2026-09-01')",
            (t["id"], support.STUDENT_USER_ID),
        )

    f.factory.run_write(legacy)
    r, h = await get(f, f"u-903101/problems/{pid}/history")
    assert r.status == 200, h
    assert sum(e["text"] == "Mapped Telegram text" for e in h["events"]) == 1
    assert "SECRET DRAFT" not in str(h)


def test_legacy_path_confines_absolute_relative_and_symlink(tmp_path):
    from models.pwa.student_results import legacy_path

    root = tmp_path / "solutions"
    root.mkdir()
    (root / "photo.jpg").write_bytes(b"image")
    (tmp_path / "secret.jpg").write_bytes(b"secret")
    (root / "symlink.jpg").symlink_to(tmp_path / "secret.jpg")
    assert (
        legacy_path(root, "/old/deployment/solutions/photo.jpg") == root / "photo.jpg"
    )
    for path in (
        "../secret.jpg",
        "solutions/../secret.jpg",
        "symlink.jpg",
        str(tmp_path / "secret.jpg"),
    ):
        assert legacy_path(root, path) is None


async def test_archive_partial_transfer_keeps_materials_at_both_origins(content_http):
    f = content_http
    await (
        support.test_staff_written_material_reassignment_previews_commits_and_projects(
            f
        )
    )
    target = f.factory.run_read(
        lambda c: c.execute(
            "SELECT p.public_id FROM submission_material_reassignments x JOIN problems p ON p.id=x.target_problem_id LIMIT 1"
        ).fetchone()["public_id"]
    )
    r, h = await get(f, f"u-903101/problems/{target}/history")
    assert r.status == 200, h
    moved = next(e for e in h["events"] if e["kind"] == "reassignment")
    assert moved["text"] and moved["attachments"]
    assert moved["transfer"]["source"] != moved["transfer"]["target"]
    r, overview = await get(f, "u-903101/overview")
    assert r.status == 200
    assert any(
        p["problemId"] == target and p["hasSubmissions"]
        for lesson in overview["summaries"]
        for g in lesson["groups"]
        for p in g["problems"]
    )


async def test_archive_no_account_multiple_courses_and_empty_lessons(content_http):
    f = content_http
    pid, _ = await live.setup(f)

    def seed(c):
        c.execute(
            "INSERT INTO users(id,type,name,surname,grade) VALUES(987651,-1,'Архивный','БезАккаунта',8)"
        )
        c.execute(
            "INSERT INTO courses(id,season_id,code,name,subject_code,status,sort_order,accent_key,created_at,updated_at) SELECT 987651,season_id,'archive','Архивный курс',subject_code,'archived',99,accent_key,created_at,updated_at FROM courses WHERE id=1"
        )
        c.execute(
            "INSERT INTO groups(id,group_id,short_code,public_name,sort_order,is_active,is_default,allow_self_switch,is_system,score_weight,course_id,status,created_at,updated_at) SELECT 987651,'archive','arch','Архивный уровень',99,0,0,0,0,1,987651,'archived',created_at,updated_at FROM groups WHERE id=1"
        )
        c.execute(
            "INSERT INTO problems(id,group_id,lesson,prob,item,title,prob_text,prob_type,ans_type,ans_validation,validation_error,cor_ans,wrong_ans,congrat,synonyms) SELECT 987651,'archive',5,prob,item,title,prob_text,prob_type,ans_type,ans_validation,validation_error,cor_ans,wrong_ans,congrat,synonyms FROM problems WHERE public_id=?",
            (pid,),
        )
        for problem in (pid, "p-987651"):
            c.execute(
                "INSERT INTO results(student_id,problem_id,group_id,lesson,teacher_id,ts,verdict,res_type) SELECT 987651,id,group_id,lesson,?,'2020-01-01',14,2 FROM problems WHERE public_id=?",
                (support.ADMIN_USER_ID, problem),
            )
        c.execute(
            "INSERT INTO course_lessons(course_id,lesson_number,title,created_by_user_id,updated_by_user_id,created_at,updated_at) VALUES(987651,6,'Пустое занятие',?,?,'2020-01-01','2020-01-01')",
            (support.ADMIN_USER_ID, support.ADMIN_USER_ID),
        )

    f.factory.run_write(seed)
    r, directory = await get(f, "directory")
    assert r.status == 200
    assert any(s["studentId"] == "u-987651" for s in directory["students"])
    r, overview = await get(f, "u-987651/overview")
    assert r.status == 200 and len(overview["courses"]) == 2
    r, overview = await get(f, "u-987651/overview?course=c-987651")
    assert r.status == 200, overview
    assert [lesson["number"] for lesson in overview["lessons"]] == [6, 5]
    assert [lesson["number"] for lesson in overview["summaries"]] == [5]
    assert (
        overview["summaries"][0]["groups"][0]["problems"][0]["current"]["verdict"] == 14
    )
    r, empty = await get(f, "u-987651/lessons/c-987651/6")
    assert r.status == 200 and empty["groups"] == []
    r, missing = await get(f, "u-987651/lessons/c-987651/7")
    assert r.status == 404


review_queue_fixture = review_support.review_queue_fixture


@pytest.mark.parametrize("mode", ["move", "clone"])
async def test_archive_whole_transfers_keep_origin(
    review_queue_fixture, tmp_path, mode
):
    from models.pwa import student_results as archive

    f = review_queue_fixture
    args, payload = await transfer_support.prepare(f)
    payload["mode"] = mode
    f.factory.run_write(lambda c: transfer_support.execute(c, payload=payload, **args))

    def read(c):
        student = c.execute(
            "SELECT u.public_id FROM submission_threads t JOIN users u ON u.id=t.student_user_id WHERE t.problem_id=1"
        ).fetchone()["public_id"]
        return [
            archive.history(c, student, p, tmp_path)
            for p in ("p-1", payload["targetProblemId"])
        ]

    for h in f.factory.run_read(read):
        transfers = [e for e in h["events"] if e["kind"] == "transfer"]
        assert transfers and transfers[0]["transfer"]["mode"] == mode
        assert any(e["kind"] == "entry" for e in h["events"])


async def test_archive_keeps_previous_corrected_reviews(review_queue_fixture, tmp_path):
    from models.pwa import student_results as archive

    f = review_queue_fixture
    await review_support.test_review_correction_appends_history_and_replaces_legacy_result(
        f
    )

    def read(c):
        student = c.execute(
            "SELECT u.public_id FROM submission_threads t JOIN users u ON u.id=t.student_user_id WHERE t.problem_id=1"
        ).fetchone()["public_id"]
        return archive.history(c, student, "p-1", tmp_path)

    h = f.factory.run_read(read)
    reviews = [e for e in h["events"] if e["kind"] == "review"]
    assert len(reviews) >= 2 and len({e["verdict"] for e in reviews}) >= 2
    assert not any(e["kind"] == "result" for e in h["events"])


async def test_archive_zoom_note_changes_and_undo(content_http):
    f = content_http
    _, spec = await live.setup(f)
    _, visit = await live.call(f, "post", "visits", spec)
    _, changed = await live.call(
        f,
        "post",
        "operations",
        dict(
            kind="reaction",
            operationId="archive-note",
            context=spec,
            studentId="u-903101",
            expectedVersion=visit["version"],
            reactions=[304],
        ),
    )
    response, _ = await live.call(
        f,
        "post",
        "operations",
        dict(
            kind="undo",
            operationId="archive-note-undo",
            context=spec,
            targetOperationId=changed["operationId"],
        ),
    )
    assert response.status == 200
    _, overview = await get(f, "u-903101/overview")
    response, lesson = await get(f, f"u-903101/lessons/{overview['courseId']}/41")
    assert response.status == 200, lesson
    assert [n["action"] for n in lesson["notes"]] == ["changed", "undo"]
    assert "ИИ" in lesson["notes"][0]["reaction"]
    assert lesson["notes"][1]["reaction"] is None
