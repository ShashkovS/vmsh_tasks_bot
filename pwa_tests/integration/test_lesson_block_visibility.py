"""Reader discovery for a lesson whose tasks are still unpublished."""

from __future__ import annotations

from pwa_tests.integration import test_content_repository as content_support

from db_methods.pwa.lesson_blocks import list_published_lesson_blocks
from models.pwa.lesson_blocks import LessonBlockService


content_fixture = content_support.content_fixture

DOCUMENT = {
    "schemaVersion": 1,
    "blocks": [
        {
            "type": "paragraph",
            "children": [{"type": "text", "text": "Материал до задач"}],
        }
    ],
    "media": [],
}


async def test_published_block_makes_active_conditionless_lesson_readable(content_fixture):
    _course_lesson, group_lesson = await content_support._create_group_lesson(
        content_fixture,
        course_lesson_public_id="lesson-block-visibility-course-lesson",
        course_id=content_fixture.course_id,
        lesson_number=77,
        group_id="content-a",
        group_lesson_public_id="lesson-block-visibility-group-lesson",
    )
    content_fixture.factory.run_write(
        lambda connection: connection.execute(
            "UPDATE group_lessons SET status = 'active' WHERE id = ?", (group_lesson.id,)
        )
    )
    service = LessonBlockService(
        content_fixture.factory,
        clock=lambda: content_support.NOW,
    )
    block, revision = await service.save_draft(
        group_lesson_id=group_lesson.id,
        position="before",
        expected_version=None,
        markdown="Материал до задач",
        document=DOCUMENT,
        actor_user_id=content_fixture.actor_user_id,
    )
    await service.publish_revision(
        group_lesson_id=group_lesson.id,
        position="before",
        expected_version=block.version,
        revision_public_id=revision.public_id,
        mode="now",
        scheduled_at=None,
        actor_user_id=content_fixture.actor_user_id,
    )

    scope = await content_fixture.repository.get_group_lesson_scope(group_lesson.public_id)
    lessons = await content_fixture.repository.list_student_lessons(
        course_public_id=scope.course_public_id,
        group_public_id=scope.group_public_id,
    )
    assert [(lesson.group_lesson_public_id, lesson.problem_count) for lesson in lessons] == [
        (group_lesson.public_id, 0)
    ]
    assert lessons[0].condition is None
    assert lessons[0].hint is None
    assert lessons[0].solution is None
    assert [(item.position, item.document) for item in lessons[0].blocks] == [
        ("before", DOCUMENT)
    ]

    published = await service.get_staff_blocks(group_lesson.id)
    await service.hide_block(
        group_lesson_id=group_lesson.id,
        position="before",
        expected_version=published[0].version,
        actor_user_id=content_fixture.actor_user_id,
    )
    assert await content_fixture.repository.list_student_lessons(
        course_public_id=scope.course_public_id,
        group_public_id=scope.group_public_id,
    ) == ()
    assert content_fixture.factory.run_read(
        lambda connection: list_published_lesson_blocks(
            connection, group_lesson_id=group_lesson.id
        )
    ) == ()
