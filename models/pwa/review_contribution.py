"""Personal totals and gentle milestones; vmshpwa/docs/review-contribution.md."""

from collections import Counter
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

LESSON_MILESTONES = (1, 10, 25, 50, 100, 200, 500, 1000)
LIFETIME_MILESTONES = (1, 10, 50, 100, 250, 500, 1000, 2500, 5000, 10000)
DAY_MILESTONES = (2, 3, 5, 7, 14, 30)
WEEK_MILESTONES = (2, 4, 8, 12, 26, 52)
TIMEZONE = "Europe/Moscow"


def milestone(value, thresholds, step):
    reached = [n for n in thresholds if n <= value]
    if value >= thresholds[-1]:
        reached.extend(range(thresholds[-1] + step, value + 1, step))
    upcoming = next((n for n in thresholds if n > value), None)
    if upcoming is None:
        upcoming = thresholds[-1] + ((value - thresholds[-1]) // step + 1) * step
    return {"value": value, "reached": reached, "next": upcoming}


def totals(rows):
    def count(items):
        return {"total": len(items), "plus": sum(row["val"] >= 0.8 for row in items)}

    return {
        **count(rows),
        "byKind": {
            kind: count([row for row in rows if row["kind"] == kind])
            for kind in ("written", "school", "zoom")
        },
    }


def streak(counts, today, step, thresholds, milestone_step):
    previous = None
    run = best = 0
    end = None
    for day in sorted(day for day, n in counts.items() if n >= 3 and day <= today):
        run = run + 1 if previous is not None and day - previous == step else 1
        best = max(best, run)
        previous = end = day
    current = run if end in (today, today - step) else 0
    return {
        "current": current,
        "best": best,
        "periodCount": counts[today],
        "minimum": 3,
        "milestone": milestone(best, thresholds, milestone_step),
    }


def calculate_contribution(rows, lessons, *, course=None, lesson=None, now=None):
    now = now or datetime.now(UTC)
    today = now.astimezone(ZoneInfo(TIMEZONE)).date()
    courses = {}
    for item in lessons:
        courses.setdefault(
            item["course_id"],
            {
                "id": item["course_id"],
                "name": item["course_name"],
                "lessons": [],
            },
        )["lessons"].append(item["lesson"])
    for item in courses.values():
        item["lessons"] = sorted(set(item["lessons"]), reverse=True)
    if course is not None and course not in courses:
        raise PermissionError("course_not_available")
    selected_course = course or (next(iter(courses)) if len(courses) == 1 else None)
    selected_lessons = courses[selected_course]["lessons"] if selected_course else []
    if lesson is not None and lesson not in selected_lessons:
        raise PermissionError("lesson_not_available")
    selected_lesson = (
        lesson if lesson is not None else next(iter(selected_lessons), None)
    )
    period_rows = [
        r
        for r in rows
        if r["course_id"] == selected_course and r["lesson"] == selected_lesson
    ]
    days, weeks = Counter(), Counter()
    for row in rows:
        stamp = datetime.fromisoformat(str(row["ts"]).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=UTC)
        day = stamp.astimezone(ZoneInfo(TIMEZONE)).date()
        days[day] += 1
        weeks[day - timedelta(days=day.weekday())] += 1
    return {
        "schemaVersion": 1,
        "timezone": TIMEZONE,
        "allTime": totals(rows),
        "lesson": None
        if selected_course is None
        else {
            "courseId": selected_course,
            "number": selected_lesson,
            "counts": totals(period_rows),
            "milestone": milestone(len(period_rows), LESSON_MILESTONES, 1000),
        },
        "milestone": milestone(len(rows), LIFETIME_MILESTONES, 5000),
        "daily": streak(days, today, timedelta(days=1), DAY_MILESTONES, 30),
        "weekly": streak(
            weeks,
            today - timedelta(days=today.weekday()),
            timedelta(days=7),
            WEEK_MILESTONES,
            26,
        ),
        "courses": list(courses.values()),
    }
