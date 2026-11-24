"""Calendar projection and compatible three-header TSV; docs/teacher-work.md."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from models.pwa.teacher_work import moment, normalize_name

META = [
    "id",
    "surname",
    "name",
    "middlename",
    "",
    "РазОчн",
    "РазZoom",
    "РазПисм",
    "РазСум",
    "ЧасОчн",
    "ЧасZoom",
    "ЧасПисьм",
    "ЧасСум",
]
DAY_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MONTH_NAMES = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]


def build_report(snapshot, overrides, *, first=None, last=None, query="", today=None):
    zone = snapshot["course"]["timezone"]
    today = today or datetime.now(ZoneInfo(zone)).date().isoformat()
    all_lessons = [r for r in snapshot["lessons"] if r["anchor"] <= today]
    lessons = [
        r
        for r in all_lessons
        if (first is None or r["number"] >= first)
        and (last is None or r["number"] <= last)
    ]

    def lesson_for(day):
        candidates = [r for r in all_lessons if r["anchor"] <= day]
        return (
            max(candidates, key=lambda r: (r["anchor"], r["number"]))["number"]
            if candidates
            else None
        )

    weekdays = {0, 1, 2}
    for window in snapshot["windows"]:
        day = moment(window["opens_at"], zone).astimezone(ZoneInfo(zone)).date()
        if lesson_for(day.isoformat()) in {r["number"] for r in lessons}:
            weekdays.add(day.weekday())
    for cell in snapshot["cells"]:
        if cell["kind"] == "zoom" and lesson_for(cell["slot"]) in {
            r["number"] for r in lessons
        }:
            weekdays.add(datetime.fromisoformat(cell["slot"]).weekday())
    # Preserve actual dates during gaps in the lesson calendar as extra offsets.
    zoom_offsets = set()
    for cell in snapshot["cells"]:
        if cell["kind"] == "zoom":
            number = lesson_for(cell["slot"])
            anchor = next((r["anchor"] for r in lessons if r["number"] == number), None)
            if anchor:
                zoom_offsets.add(
                    (
                        datetime.fromisoformat(cell["slot"]).date()
                        - datetime.fromisoformat(anchor).date()
                    ).days
                )
    columns = []
    for lesson in lessons:
        anchor = datetime.fromisoformat(lesson["anchor"]).date()
        school_days = [
            moment(e["starts_at"], zone).astimezone(ZoneInfo(zone)).date()
            for e in snapshot["events"]
            if lesson_for(
                moment(e["starts_at"], zone)
                .astimezone(ZoneInfo(zone))
                .date()
                .isoformat()
            )
            == lesson["number"]
        ]
        school_days.extend(
            datetime.fromisoformat(c["slot"]).date()
            for c in snapshot["cells"]
            if c["kind"] == "school" and lesson_for(c["slot"]) == lesson["number"]
        )
        school_dates = sorted(set(school_days)) or [anchor]
        offsets = sorted(
            zoom_offsets | {(wd - anchor.weekday()) % 7 for wd in weekdays}
        )
        for kind, day, label in (
            [("school", day, "Шк") for day in school_dates]
            + [
                (
                    "zoom",
                    anchor + timedelta(days=offset),
                    DAY_NAMES[(anchor.weekday() + offset) % 7],
                )
                for offset in offsets
            ]
            + [("written", anchor + timedelta(days=6), "✏")]
        ):
            columns.append(
                {
                    "key": f"{lesson['number']}:{kind}:{day.isoformat()}",
                    "lesson": lesson["number"],
                    "kind": kind,
                    "date": day.isoformat(),
                    "label": label,
                }
            )
    report_rows = []
    for teacher in snapshot["teachers"]:
        if normalize_name(query) not in normalize_name(
            " ".join(
                str(teacher.get(k) or "")
                for k in ["id", "surname", "name", "middlename"]
            )
        ):
            continue
        cells = []
        counts = {"school": set(), "zoom": set(), "written": set()}
        totals = {"school": 0.0, "zoom": 0.0, "written": 0.0}
        unknown = set()
        for column in columns:
            matched = [
                cell
                for cell in snapshot["cells"]
                if cell["teacherId"] == teacher["public_id"]
                and cell["kind"] == column["kind"]
                and (
                    int(cell["slot"]) == column["lesson"]
                    if column["kind"] == "written"
                    else lesson_for(cell["slot"]) == column["lesson"]
                    and cell["slot"] == column["date"]
                )
            ]
            values, stale, sources = [], False, set()
            for cell in matched:
                override = overrides.get(cell["key"])
                if override and override["hours"] is None:
                    override = None
                value = override["hours"] if override else cell["hours"]
                values.append(value)
                stale |= bool(
                    override and override["source_fingerprint"] != cell["fingerprint"]
                )
                sources.add("manual" if override else cell["source"])
                if value is None:
                    unknown.add(column["kind"])
                    counts[column["kind"]].add(cell["slot"])
                else:
                    totals[column["kind"]] += value
                    if value > 0:
                        counts[column["kind"]].add(cell["slot"])
            cells.append(
                {
                    "columnKey": column["key"],
                    "keys": [c["key"] for c in matched],
                    "hours": None if None in values else sum(values),
                    "sources": sorted(sources),
                    "stale": stale,
                    "anomalies": sorted({a for c in matched for a in c["anomalies"]}),
                }
            )
        if not any(c["keys"] for c in cells):
            continue
        report_rows.append(
            {
                "teacherId": teacher["public_id"],
                "id": teacher["id"],
                "surname": teacher["surname"],
                "name": teacher["name"],
                "middlename": teacher["middlename"] or "",
                "counts": {k: len(v) for k, v in counts.items()},
                "totals": {k: None if k in unknown else v for k, v in totals.items()},
                "totalHours": None if unknown else sum(totals.values()),
                "cells": cells,
            }
        )
    report_rows.sort(
        key=lambda r: (-(r["totalHours"] or 0), r["surname"], r["name"], r["id"])
    )
    return {"columns": columns, "rows": report_rows, "lessons": all_lessons}


def export_tsv(report):
    def clean(value):
        # Keep TSV rectangular and spreadsheet formula text inert.
        text = str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")
        return "'" + text if text.startswith(("=", "+", "-", "@")) else text

    def hours(value, places=1):
        return "" if value is None else f"{value:.{places}f}"

    top = ["1", "2", "3", "4", "6", "8", "9", "10", "11", "12", "13", "14", "15"] + [
        c["label"] for c in report["columns"]
    ]
    second = [""] * 13 + [str(c["lesson"]) for c in report["columns"]]
    third = META + [
        f"{int(c['date'][8:10])}-{MONTH_NAMES[int(c['date'][5:7]) - 1]}"
        for c in report["columns"]
    ]
    lines = [top, second, third]
    for row in report["rows"]:
        counts, totals = row["counts"], row["totals"]
        lines.append(
            [
                row["id"],
                row["surname"],
                row["name"],
                row["middlename"],
                "|",
                counts["school"],
                counts["zoom"],
                counts["written"],
                sum(counts.values()),
                hours(totals["school"]),
                hours(totals["zoom"]),
                hours(totals["written"]),
                hours(row["totalHours"], 2),
            ]
            + [hours(c["hours"]) for c in row["cells"]]
        )
    return "\n".join("\t".join(clean(v) for v in line) for line in lines) + "\n"
