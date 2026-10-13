"""Worker read projections; governing decision: worker-read-cache.md."""

from __future__ import annotations

from copy import deepcopy

from helpers.pwa.read_cache import WorkerReadCache


class CachedContentRepository:
    """Keep shared lessons in RAM, always overlay fresh personal work from SQL."""

    def __init__(self, repository, *, available=lambda: True):
        self.repository = repository
        self.available = available
        self.cache = WorkerReadCache()

    def __getattr__(self, name):
        return getattr(self.repository, name)

    def invalidate(self, resources=None):
        if resources is None or any(
            item == "courses"
            or item.startswith("courses/")
            or item.startswith("problems/")
            and not item.endswith(("/test-attempts", "/thread"))
            for item in resources
        ):
            self.cache.invalidate()
            return
        lessons = {
            item.split("/")[1]
            for item in resources
            if item.startswith("group-lessons/")
            and len(item.split("/")) >= 3
            and item.split("/")[2]
            in {"content", "blocks", "problem-release", "oral-window"}
        }
        if lessons or "student-course-lessons" in resources:
            self.cache.invalidate(
                lambda key: (
                    key[0] == "lessons"
                    or key[0] in {"lesson", "problems"}
                    and key[-1] in lessons
                    or key[0] in {"scope", "content"}
                    and key[1] in lessons
                )
            )

    async def _get(self, key, load):
        if not self.available():
            self.cache.invalidate()
            return await load()
        # Routes may decorate nested ASTs; never expose the retained dictionary.
        return deepcopy(await self.cache.get(key, load))

    async def get_group_lesson_scope(self, public_id):
        return await self._get(
            ("scope", public_id),
            lambda: self.repository.get_group_lesson_scope(public_id),
        )

    async def list_student_lessons(
        self, *, course_public_id, group_public_id, before_lesson_number=None, limit=50
    ):
        return await self._get(
            ("lessons", course_public_id, group_public_id, before_lesson_number, limit),
            lambda: self.repository.list_student_lessons(
                course_public_id=course_public_id,
                group_public_id=group_public_id,
                before_lesson_number=before_lesson_number,
                limit=limit,
            ),
        )

    async def get_student_lesson(
        self, *, course_public_id, group_public_id, group_lesson_public_id
    ):
        return await self._get(
            ("lesson", course_public_id, group_public_id, group_lesson_public_id),
            lambda: self.repository.get_student_lesson(
                course_public_id=course_public_id,
                group_public_id=group_public_id,
                group_lesson_public_id=group_lesson_public_id,
            ),
        )

    async def get_published_content(
        self, *, group_lesson_public_id, kind, released_only=False
    ):
        return await self._get(
            ("content", group_lesson_public_id, kind, released_only),
            lambda: self.repository.get_published_content(
                group_lesson_public_id=group_lesson_public_id,
                kind=kind,
                released_only=released_only,
            ),
        )

    async def list_student_problems(
        self,
        *,
        student_user_id,
        course_public_id,
        group_public_id,
        group_lesson_public_id,
    ):
        scope = dict(
            course_public_id=course_public_id,
            group_public_id=group_public_id,
            group_lesson_public_id=group_lesson_public_id,
        )
        lesson = await self._get(
            ("problems", course_public_id, group_public_id, group_lesson_public_id),
            lambda: self.repository.list_lesson_problems(**scope),
        )
        return await self.repository.get_student_problem_work(
            student_user_id=student_user_id, lesson=lesson
        )


class InvalidatingBroker:
    """Fence local caches before best-effort NATS publication can fail."""

    def __init__(self, broker, invalidate):
        self.broker = broker
        self.invalidate = invalidate

    def __getattr__(self, name):
        return getattr(self.broker, name)

    async def publish(self, topic, payload):
        self.invalidate(topic, payload)
        await self.broker.publish(topic, payload)
