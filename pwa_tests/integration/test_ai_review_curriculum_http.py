"""Prior lessons in one scoped MCP batch; ai-review-assistant.md."""

import hashlib
import json

import pytest

from pwa_tests.integration import test_review_queue_http_api as fixtures
from pwa_tests.integration.test_ai_review_http import token, call, install_image, counts
from pwa_tests.integration.test_ai_review_exports_http import export

review_http = fixtures.review_http


def add_lesson(c, number, *, group_id="review-http-a", status="active"):
    anchor = c.execute("SELECT * FROM group_lessons WHERE public_id='gl-1'").fetchone()
    course_lesson = c.execute(
        "SELECT id FROM course_lessons WHERE course_id=? AND lesson_number=?",
        (anchor["course_id"], number),
    ).fetchone()
    if course_lesson is None:
        course_lesson = c.execute(
            """INSERT INTO course_lessons(course_id,lesson_number,title,created_at,updated_at)
            VALUES(?, ?, ?, ?, ?) RETURNING id""",
            (
                anchor["course_id"],
                number,
                f"Тема {number}",
                fixtures._timestamp(),
                fixtures._timestamp(),
            ),
        ).fetchone()
    return c.execute(
        """INSERT INTO group_lessons(course_lesson_id,course_id,group_id,
        cycle_anchor_date,business_timezone,status,created_at,updated_at)
        VALUES(?,?,?,'2026-09-01','Europe/Moscow',?,?,?) RETURNING id,public_id""",
        (
            course_lesson["id"],
            anchor["course_id"],
            group_id,
            status,
            fixtures._timestamp(),
            fixtures._timestamp(),
        ),
    ).fetchone()


def add_material(
    c,
    lesson,
    kind,
    *,
    filename=None,
    parsed=True,
    published=False,
    source_id=None,
    revision=1,
):
    if source_id is None:
        source_id = c.execute(
            """INSERT INTO content_sources(group_lesson_id,kind,logical_filename,source_encoding,created_at)
            VALUES(?,?,?,'utf-8',?) RETURNING id""",
            (lesson["id"], kind, filename or f"{kind}.tex", fixtures._timestamp()),
        ).fetchone()["id"]
    latex = f"{kind} lesson={lesson['id']} revision={revision}"
    row = c.execute(
        """INSERT INTO content_revisions(source_id,revision_number,source_sha256,
        latex_text,parser_version,status,canonical_json,diagnostics_json,provenance_json,created_at)
        VALUES(?,?,?,?, 'curriculum-test','ready','{}','[]','{}',?) RETURNING id,public_id""",
        (
            source_id,
            revision,
            hashlib.sha256(latex.encode()).hexdigest(),
            latex,
            fixtures._timestamp(),
        ),
    ).fetchone()
    if parsed:
        document = json.dumps(
            {
                "introduction": "Сначала мы изучали инварианты.",
                "problems": [
                    {
                        "ordinal": n,
                        "blocks": [{"type": "paragraph", "text": f"{latex} task {n}"}],
                    }
                    for n in range(1, 62)
                ],
            }
        )
        c.execute(
            """INSERT INTO content_derivatives(revision_id,kind,renderer_version,content_text,
            sha256,provenance_json,created_at) VALUES(?,'web_ast','curriculum-test',?,?,'{}',?)""",
            (
                row["id"],
                document,
                hashlib.sha256(document.encode()).hexdigest(),
                fixtures._timestamp(),
            ),
        )
    if published:
        c.execute(
            """INSERT INTO lesson_publications(group_lesson_id,kind,revision_id,state,
            published_at,created_by_user_id,published_by_user_id,created_at,updated_at)
            VALUES(?,?,?,'published',?,?,?,?,?)""",
            (
                lesson["id"],
                kind,
                row["id"],
                fixtures._timestamp(),
                fixtures.FULL_TEACHER_ID,
                fixtures.FULL_TEACHER_ID,
                fixtures._timestamp(),
                fixtures._timestamp(),
            ),
        )
    return {**row, "source_id": source_id}


def seed_curriculum(c):
    lessons = {}
    for number in (5, 8, 13, 21, 34, 42):
        lesson = add_lesson(c, number, status="archived" if number == 5 else "active")
        lessons[number] = lesson
        for kind in ("condition", "hint", "solution"):
            add_material(c, lesson, kind, published=kind == "condition")
    add_lesson(c, 40, status="draft")
    add_material(
        c, add_lesson(c, 39, group_id="review-http-b"), "condition", published=True
    )
    return lessons


async def test_previous_three_five_and_short_history_are_complete_same_level_batches(
    review_http,
):
    f = review_http
    f.factory.run_write(seed_curriculum)
    secret = (await token(f))["secret"]
    before = counts(f)
    for count, numbers in [
        (3, [13, 21, 34]),
        (5, [5, 8, 13, 21, 34]),
        (20, [5, 8, 13, 21, 34]),
    ]:
        data = await export(
            f,
            secret,
            "get_previous_lesson_materials",
            {"lessonId": "gl-1", "count": count},
        )
        assert data["availablePreviousCount"] == 5
        assert data["returnedCount"] == len(numbers)
        assert [lesson["number"] for lesson in data["lessons"]] == numbers
        assert all(
            lesson["groupId"] == data["groupId"]
            and lesson["courseId"] == data["courseId"]
            for lesson in data["lessons"]
        )
        for lesson in data["lessons"]:
            assert lesson["missingMaterials"] == []
            assert {material["kind"] for material in lesson["materials"]} == {
                "condition",
                "hint",
                "solution",
            }
            for material in lesson["materials"]:
                assert len(material["document"]["problems"]) == 61
                assert material["document"]["introduction"]
                assert material["publicationState"] == (
                    "published" if material["kind"] == "condition" else "unpublished"
                )
    default = await export(
        f, secret, "get_previous_lesson_materials", {"lessonId": "gl-1"}
    )
    assert default["returnedCount"] == 3
    first = default["lessons"][0]["lessonId"]
    early = await export(
        f, secret, "get_previous_lesson_materials", {"lessonId": first, "count": 5}
    )
    assert [lesson["number"] for lesson in early["lessons"]] == [5, 8]
    earliest = early["lessons"][0]["lessonId"]
    empty = await export(
        f, secret, "get_previous_lesson_materials", {"lessonId": earliest}
    )
    assert empty["lessons"] == [] and empty["returnedCount"] == 0
    assert counts(f) == before
    assert not f.telegram_calls


async def test_published_revision_wins_drafts_and_unparsed_sources_are_explicit(
    review_http,
):
    f = review_http

    def seed(c):
        lesson = add_lesson(c, 40)
        published = add_material(c, lesson, "condition", published=True)
        add_material(
            c, lesson, "condition", source_id=published["source_id"], revision=2
        )
        hint = add_material(c, lesson, "hint", parsed=False)
        latest_hint = add_material(
            c, lesson, "hint", source_id=hint["source_id"], revision=2, parsed=False
        )
        add_material(c, lesson, "teacher_note")
        return lesson, published, latest_hint

    lesson, published, hint = f.factory.run_write(seed)
    secret = (await token(f))["secret"]
    data = await export(
        f, secret, "get_previous_lesson_materials", {"lessonId": "gl-1"}
    )
    assert data["returnedCount"] == 1
    value = data["lessons"][0]
    assert value["missingMaterials"] == ["solution"]
    assert value["lessonId"] == lesson["public_id"]
    assert len(value["materials"]) == 2
    condition = next(m for m in value["materials"] if m["filename"] == "condition.tex")
    assert condition["revisionId"] == published["public_id"]
    latest = next(m for m in value["materials"] if m["kind"] == "hint")
    assert (
        latest["availability"] == "source_only"
        and latest["latex"]
        and latest["document"] is None
    )
    assert (
        latest["revisionId"] == hint["public_id"]
        and latest["publicationState"] == "unpublished"
    )


async def test_curriculum_images_are_bound_to_lesson_scope_and_snapshot(review_http):
    f = review_http
    image = await install_image(f)

    def seed(c):
        lesson = add_lesson(c, 40)
        material = add_material(c, lesson, "condition", published=True)
        c.execute(
            """INSERT INTO content_revision_assets(revision_id,asset_id,logical_name,role,ordinal,created_at)
            SELECT ?,id,'figure.webp','figure',0,? FROM media_assets ORDER BY id LIMIT 1""",
            (material["id"], fixtures._timestamp()),
        )
        return lesson, material

    lesson, material = f.factory.run_write(seed)
    secret = (await token(f))["secret"]
    batch = await export(
        f, secret, "get_previous_lesson_materials", {"lessonId": "gl-1"}
    )
    value = batch["lessons"][0]
    query = {
        "lessonId": lesson["public_id"],
        "snapshot": value["snapshot"],
        "imageId": value["materials"][0]["images"][0]["imageId"],
    }
    result = await call(f, secret, "get_lesson_material_image", query)
    assert result.status == 200 and await result.read() == image
    assert (
        await call(
            f,
            secret,
            "get_lesson_material_image",
            {**query, "imageId": "content:ma-999"},
        )
    ).status == 404
    f.factory.run_write(
        lambda c: c.execute(
            "UPDATE content_derivatives SET invalidated_at=? WHERE revision_id=?",
            (fixtures._timestamp(), material["id"]),
        )
    )
    assert (await call(f, secret, "get_lesson_material_image", query)).status == 409
    partial = (await token(f, "partial"))["secret"]
    assert (
        await call(f, partial, "get_previous_lesson_materials", {"lessonId": "gl-2"})
    ).status == 403
    f.factory.run_write(lambda c: c.execute("DELETE FROM staff_scopes"))
    assert (await call(f, secret, "get_lesson_material_image", query)).status == 403


@pytest.mark.parametrize("count", [0, 21, -1, True, "5", 1.5])
async def test_curriculum_count_is_strict_and_bounded(review_http, count):
    f = review_http
    secret = (await token(f))["secret"]
    response = await call(
        f, secret, "get_previous_lesson_materials", {"lessonId": "gl-1", "count": count}
    )
    assert response.status == 422


async def test_missing_materials_empty_lesson_and_unknown_anchor_are_explicit(
    review_http,
):
    f = review_http
    f.factory.run_write(lambda c: add_lesson(c, 40))
    secret = (await token(f))["secret"]
    data = await export(
        f, secret, "get_previous_lesson_materials", {"lessonId": "gl-1"}
    )
    lesson = data["lessons"][0]
    assert data["returnedCount"] == 1 and lesson["materials"] == []
    assert lesson["missingMaterials"] == ["condition", "hint", "solution"]
    assert (
        await call(
            f, secret, "get_previous_lesson_materials", {"lessonId": "gl-999999"}
        )
    ).status == 404
    assert (await call(f, secret, "get_previous_lesson_materials", {})).status == 422


async def test_archived_published_source_is_preserved_next_to_active_private_replacement(
    review_http,
):
    f = review_http

    def seed(c):
        lesson = add_lesson(c, 40)
        old = add_material(c, lesson, "condition", published=True)
        c.execute(
            "UPDATE content_sources SET archived_at=? WHERE id=?",
            (fixtures._timestamp(), old["source_id"]),
        )
        new = add_material(c, lesson, "condition", filename="replacement.tex")
        return old, new

    old, new = f.factory.run_write(seed)
    secret = (await token(f))["secret"]
    data = await export(
        f, secret, "get_previous_lesson_materials", {"lessonId": "gl-1"}
    )
    materials = data["lessons"][0]["materials"]
    assert len(materials) == 2
    assert {m["revisionId"]: m["publicationState"] for m in materials} == {
        old["public_id"]: "published",
        new["public_id"]: "unpublished",
    }
