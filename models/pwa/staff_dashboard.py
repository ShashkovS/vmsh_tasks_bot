"""Pure projection for the Staff weekly operational dashboard.

The dashboard follows ``vmshpwa/docs/weekly-lifecycle.md``.  It deliberately
contains only aggregate operational facts: no Student row or private message
is returned to the browser.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class InvalidStaffDashboardData(ValueError):
    """Stored lesson data cannot form a safe dashboard projection."""


@dataclass(frozen=True, slots=True)
class StaffDashboardScope:
    global_access: bool = False
    course_public_ids: frozenset[str] = frozenset()
    group_public_ids: frozenset[str] = frozenset()

    def allows(self, row: Mapping[str, object]) -> bool:
        if self.global_access:
            return True
        return (
            row.get("course_public_id") in self.course_public_ids
            or row.get("group_public_id") in self.group_public_ids
        )


def _timestamp(value: object, *, field: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidStaffDashboardData(f"{field} is not a timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise InvalidStaffDashboardData(f"{field} is invalid") from error
    if parsed.tzinfo is None:
        raise InvalidStaffDashboardData(f"{field} has no timezone")
    return parsed.astimezone(UTC)


def _anchor_date(row: Mapping[str, object]) -> date:
    value = row.get("cycle_anchor_date")
    if not isinstance(value, str):
        raise InvalidStaffDashboardData("cycle anchor date is missing")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise InvalidStaffDashboardData("cycle anchor date is invalid") from error


def _local_today(row: Mapping[str, object], *, now: datetime) -> date:
    timezone = row.get("business_timezone")
    if not isinstance(timezone, str):
        raise InvalidStaffDashboardData("business timezone is missing")
    try:
        return now.astimezone(ZoneInfo(timezone)).date()
    except ZoneInfoNotFoundError as error:
        raise InvalidStaffDashboardData("business timezone is invalid") from error


def _select_current_lessons(
    rows: Iterable[Mapping[str, object]],
    *,
    scope: StaffDashboardScope,
    now: datetime,
) -> list[Mapping[str, object]]:
    by_group: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        if scope.allows(row):
            by_group[
                (str(row["course_public_id"]), str(row["group_public_id"]))
            ].append(row)

    selected: list[Mapping[str, object]] = []
    for candidates in by_group.values():
        today = _local_today(candidates[0], now=now)
        past = [row for row in candidates if _anchor_date(row) <= today]
        if past:
            selected.append(max(past, key=_anchor_date))
        else:
            selected.append(min(candidates, key=_anchor_date))
    return sorted(
        selected,
        key=lambda row: (
            int(row["course_sort_order"]),
            str(row["course_code"]),
            int(row["group_sort_order"]),
            str(row["group_code"]),
        ),
    )


def _select_lessons(
    rows: Iterable[Mapping[str, object]],
    *,
    scope: StaffDashboardScope,
    now: datetime,
    selection: Literal["current", "all"],
) -> list[Mapping[str, object]]:
    if selection == "current":
        return _select_current_lessons(rows, scope=scope, now=now)
    return sorted(
        (row for row in rows if scope.allows(row)),
        key=lambda row: (
            int(row["course_sort_order"]),
            str(row["course_code"]),
            -int(row["lesson_number"]),
            int(row["group_sort_order"]),
            str(row["group_code"]),
        ),
    )


def _publication_state(
    rows: Iterable[Mapping[str, object]], *, kind: str
) -> dict[str, object]:
    candidates = [row for row in rows if row.get("kind") == kind]
    published = next(
        (row for row in candidates if row.get("state") == "published"), None
    )
    if published is not None:
        return {"state": "published", "scheduledAt": None}
    scheduled = next(
        (row for row in candidates if row.get("state") == "scheduled"), None
    )
    if scheduled is not None:
        scheduled_at = _timestamp(scheduled.get("scheduled_at"), field="scheduled_at")
        return {
            "state": "scheduled",
            "scheduledAt": scheduled_at.isoformat().replace("+00:00", "Z"),
        }
    return {"state": "none", "scheduledAt": None}


def _phase(
    row: Mapping[str, object],
    *,
    condition_state: str,
    hint_state: str,
    solution_state: str,
    now: datetime,
) -> str:
    opens_at = _timestamp(row.get("opens_at"), field="opens_at")
    closes_at = _timestamp(
        row.get("submission_closes_at"), field="submission_closes_at"
    )
    if condition_state == "none" or closes_at is None:
        return "draft"
    if opens_at is not None and now < opens_at:
        return "scheduled"
    if solution_state == "published":
        return "solutions_published"
    if now >= closes_at:
        return "submissions_closed"
    if hint_state == "published":
        return "hints_published"
    return "active"


def build_staff_dashboard_lessons(
    lesson_rows: Iterable[Mapping[str, object]],
    publication_rows: Iterable[Mapping[str, object]],
    oral_window_rows: Iterable[Mapping[str, object]],
    *,
    scope: StaffDashboardScope,
    now: datetime,
    selection: Literal["current", "all"] = "current",
) -> list[dict[str, object]]:
    """Select visible lessons and derive their public state."""

    if now.tzinfo is None:
        raise ValueError("dashboard clock must be timezone-aware")
    now = now.astimezone(UTC)
    publications: dict[int, list[Mapping[str, object]]] = defaultdict(list)
    for row in publication_rows:
        publications[int(row["group_lesson_id"])].append(row)
    oral_windows: dict[int, list[Mapping[str, object]]] = defaultdict(list)
    for row in oral_window_rows:
        oral_windows[int(row["group_lesson_id"])].append(row)

    result: list[dict[str, object]] = []
    for row in _select_lessons(
        lesson_rows,
        scope=scope,
        now=now,
        selection=selection,
    ):
        group_lesson_id = int(row["group_lesson_id"])
        condition = _publication_state(publications[group_lesson_id], kind="condition")
        hint = _publication_state(publications[group_lesson_id], kind="hint")
        solution = _publication_state(publications[group_lesson_id], kind="solution")
        opened_oral = 0
        upcoming_oral = 0
        for oral in oral_windows[group_lesson_id]:
            opens_at = _timestamp(oral.get("opens_at"), field="oral opens_at")
            closes_at = _timestamp(oral.get("closes_at"), field="oral closes_at")
            if opens_at is None or closes_at is None:
                raise InvalidStaffDashboardData("oral window is incomplete")
            if opens_at <= now < closes_at:
                opened_oral += 1
            elif now < opens_at:
                upcoming_oral += 1
        result.append(
            {
                "groupLessonId": row["group_lesson_public_id"],
                "lessonNumber": int(row["lesson_number"]),
                "cycleAnchorDate": row["cycle_anchor_date"],
                "course": {
                    "courseId": row["course_public_id"],
                    "code": row["course_code"],
                    "name": row["course_name"],
                },
                "group": {
                    "groupId": row["group_public_id"],
                    "code": row["group_code"],
                    "name": row["group_name"],
                    "colorKey": row["color_key"],
                },
                "phase": _phase(
                    row,
                    condition_state=str(condition["state"]),
                    hint_state=str(hint["state"]),
                    solution_state=str(solution["state"]),
                    now=now,
                ),
                "publications": {
                    "condition": condition,
                    "hint": hint,
                    "solution": solution,
                },
                "oral": {
                    "openWindows": opened_oral,
                    "upcomingWindows": upcoming_oral,
                },
            }
        )
    return result


__all__ = [
    "InvalidStaffDashboardData",
    "StaffDashboardScope",
    "build_staff_dashboard_lessons",
]
