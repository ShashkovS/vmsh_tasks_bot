"""Compact scoped statistics snapshots; scoped-reads-20261013.md."""

from copy import deepcopy

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from db_methods.pwa.course_analytics import (
    find_latest_completed_course_run,
    list_course_run_metrics,
)
from db_methods.pwa.iterative_analytics import read_state
from db_methods.pwa.lesson_statistics import course_facts, published_problems
from db_methods.pwa.statistics_reports import report_facts
from helpers.prometheus_metrics import PROJECTION_DURATION
from helpers.pwa.read_cache import WorkerReadCache
from models.pwa.lesson_statistics import summarize_lessons
from models.pwa.staff_statistics import summarize_staff_course_metrics
from models.pwa.statistics_reports import build_reports


class StatisticsReadCache:
    def __init__(self, *, clock=None, available=lambda: True):
        self.available = available
        options = {} if clock is None else {"clock": clock}
        self.cache = WorkerReadCache(
            ttl_seconds=60,
            max_entries=128,
            max_bytes=64 * 1024**2,
            metric_name="statistics",
            **options,
        )

    def invalidate(self, resources=None):
        if resources is None or any(
            item in {"courses", "course-enrollments"} for item in resources
        ):
            self.cache.invalidate()
            return
        courses = {
            item.split("/")[1]
            for item in resources
            if item.startswith("courses/") and len(item.split("/")) >= 3
        }
        if courses:
            self.cache.invalidate(lambda key: key[1] in courses)

    async def get(self, key, load, *, force_refresh=False):
        async def fresh():
            started = self.cache.clock()
            value = await load()
            if self.cache.clock() - started >= 60:
                raise PwaApiError(
                    status=503,
                    code="statistics_unavailable",
                    message="Статистика временно недоступна",
                )
            return value

        if not self.available():
            self.cache.invalidate()
            return deepcopy(await fresh())
        value = await self.cache.get(
            key, fresh, force_refresh=force_refresh, retry_invalidated=False
        )
        return deepcopy(value)


PWA_STATISTICS_CACHE = web.AppKey("pwa_statistics_cache", StatisticsReadCache)


def main_snapshot(connection, course_id, allowed_groups):
    """One read snapshot, then pure aggregation on the existing analytics thread."""
    connection.execute("BEGIN")
    try:
        run = find_latest_completed_course_run(connection, course_id=course_id)
        metrics = (
            []
            if run is None
            else list_course_run_metrics(
                connection, run_id=run["id"], allowed_group_public_ids=allowed_groups
            )
        )
        facts = course_facts(
            connection, course_id, allowed_group_public_ids=allowed_groups
        )
        difficulty, _ = read_state(connection, course_id)
    finally:
        connection.execute("ROLLBACK")
    with PROJECTION_DURATION.labels("statistics_calculation").time():
        basic = summarize_lessons(*facts, allowed_groups)
        by_public = {p["public_id"]: p for p in facts[0]}
        for lesson in basic:
            for group in lesson["groups"]:
                for problem in group["problems"]:
                    values = difficulty.get(
                        by_public[problem["problemId"]]["logical_problem_key"]
                    )
                    problem["difficultyWeak"] = values[0] if values else None
                    problem["difficultyStrong"] = values[1] if values else None
        students = {
            r["student_public_id"]: dict(
                studentId=r["student_public_id"],
                name=r["student_name"],
                id=r["student_user_id"],
            )
            for r in facts[1]
        }
        personal = {}
        for row in metrics:
            personal.setdefault(row["student_user_id"], []).append(
                {
                    "lessonNumber": row["lesson_number"],
                    "groupCode": row["group_code"],
                    "simple": row["simple_strength"],
                    "complex": row["complex_strength"],
                    "difficulty": row["max_complex_strength"],
                    "simpleSmooth": row["simple_smooth"],
                    "complexSmooth": row["complex_smooth"],
                    "solved": row["solved_items"],
                    "total": row["total_items"],
                }
            )
        return dict(
            run=run,
            lessons=summarize_staff_course_metrics(
                metrics, allowed_group_public_ids=allowed_groups
            ),
            basic=basic,
            students=students,
            personal=personal,
        )


def report_snapshot(connection, course_id, allowed_groups, number, *, matrix):
    connection.execute("BEGIN")
    try:
        published = published_problems(
            connection, course_id, allowed_group_public_ids=allowed_groups
        )
        numbers = sorted({p["lesson_number"] for p in published})
        selected = number if number is not None else max(numbers, default=None)
        problems = [
            p for p in published if not matrix or p["lesson_number"] == selected
        ]
        facts = report_facts(connection, course_id, problems=problems)
    finally:
        connection.execute("ROLLBACK")
    with PROJECTION_DURATION.labels("statistics_calculation").time():
        report = build_reports(facts, allowed_groups, selected, include_table=matrix)
        report["lessonNumbers"] = numbers
        report["lessonNumber"] = selected
        return report
