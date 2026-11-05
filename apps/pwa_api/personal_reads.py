"""Bounded personal snapshots; docs/performance/peak-read-admission-20261019.md."""

from copy import deepcopy

from aiohttp import web

from db_methods.pwa.course_achievements import list_student_course_achievements
from db_methods.pwa.course_analytics import latest_student_course_metrics
from db_methods.pwa.progress import (
    list_course_activity_rows,
    list_course_pending_review_rows,
    list_course_result_rows,
)
from helpers.pwa.app_keys import PWA_DATABASE
from helpers.pwa.read_cache import WorkerReadCache


class PersonalReadCache:
    """Access is checked by callers; keys bind student, course and lesson/group."""

    def __init__(self, *, available=lambda: True, clock=None):
        self.available = available
        self.cache = WorkerReadCache(
            ttl_seconds=5,
            max_entries=4096,
            max_bytes=32 * 1024**2,
            metric_name="personal",
            **({"clock": clock} if clock else {}),
        )

    def invalidate(self, resources=None):
        if resources is None or "courses" in resources:
            self.cache.invalidate()
            return
        owners = {
            parts[1]
            for r in resources
            if len(parts := r.split("/")) == 3
            and parts[0] == "students"
            and parts[2] == "work"
        }
        courses = {
            parts[1]
            for r in resources
            if len(parts := r.split("/")) >= 3 and parts[0] == "courses"
        }
        lessons = {
            parts[1]
            for r in resources
            if len(parts := r.split("/")) >= 3 and parts[0] == "group-lessons"
        }
        work = any(r.endswith("/work") for r in resources)
        broad = any(
            r
            in {"live-results", "home", "student-course-lessons", "course-enrollments"}
            for r in resources
        )
        if not (owners or courses or lessons or broad):
            return

        def affected(key):
            kind, student, course, scope = key
            if owners and student not in owners:
                return False
            if courses and course not in courses:
                return False
            if kind == "latest" and work:
                return False
            if kind == "work" and lessons:
                return scope in lessons
            return True

        self.cache.invalidate(affected)

    async def get(self, key, load):
        if not self.available():
            self.cache.invalidate()
            return deepcopy(await load())
        return deepcopy(await self.cache.get(key, load))


PWA_PERSONAL_READ_CACHE = web.AppKey("pwa_personal_read_cache", PersonalReadCache)


async def personal_read(request, key, load):
    cache = request.app.get(PWA_PERSONAL_READ_CACHE)
    return await load() if cache is None else await cache.get(key, load)


async def course_progress_rows(
    request, *, student_user_id, student_public_id, enrollment
):
    """Share Student/Family facts; neither authority nor formatted response is cached."""

    def read(connection):
        connection.execute("BEGIN")
        try:
            params = dict(
                student_user_id=student_user_id, course_id=enrollment.course_id
            )
            return (
                list_course_result_rows(connection, **params),
                list_course_pending_review_rows(connection, **params),
                latest_student_course_metrics(connection, **params),
                list_student_course_achievements(connection, **params),
                list_course_activity_rows(connection, **params),
            )
        finally:
            connection.execute("ROLLBACK")

    return await personal_read(
        request,
        ("progress", student_public_id, enrollment.course_public_id, ""),
        lambda: request.app[PWA_DATABASE].factory.run_read_async(read),
    )
