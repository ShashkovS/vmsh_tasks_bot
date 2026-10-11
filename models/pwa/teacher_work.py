"""Pure teacher-work calculations and roster parsing; docs/teacher-work.md."""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
import hashlib
import json
import re
import statistics
import unicodedata
from zoneinfo import ZoneInfo


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def normalize_name(value):
    return " ".join(
        unicodedata.normalize("NFKC", value).casefold().replace("ё", "е").split()
    )


def moment(value, zone, *, legacy_zoom=False):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    # Imported zoom_events are wall time MSK; current educational ledger is UTC.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(zone) if legacy_zoom else UTC)
    return parsed.astimezone(UTC)


def union_seconds(intervals):
    total = 0.0
    end = None
    for start, stop in sorted(intervals):
        if stop <= start:
            continue
        if end is None or start >= end:
            total += (stop - start).total_seconds()
        elif stop > end:
            total += (stop - end).total_seconds()
        end = max(end, stop) if end else stop
    return total


def split_days(start, stop, zone):
    tz = ZoneInfo(zone)
    while start < stop:
        local = start.astimezone(tz)
        midnight = datetime.combine(
            local.date() + timedelta(days=1), datetime.min.time(), tz
        )
        end = min(stop, midnight.astimezone(UTC))
        yield local.date().isoformat(), (start, end)
        start = end


def written_estimates(results, zone):
    """Each verdict has its own empirical distribution; no educational writes."""
    ordered = sorted(
        results, key=lambda r: (r["teacher_id"], moment(r["ts"], zone), r["id"])
    )
    samples = defaultdict(list)
    previous = {}
    observations = []
    for row in ordered:
        ts = moment(row["ts"], zone)
        last = previous.get(row["teacher_id"])
        delta = (ts - last).total_seconds() if last else None
        previous[row["teacher_id"]] = ts
        key = (row["problem_id"], row["verdict"])
        observations.append((row, delta, key))
        if delta is not None and 1 <= delta < 600:
            samples[key].append(delta)
    parameters = {}
    for key, values in samples.items():
        limit = statistics.mean(values) + 3 * statistics.pstdev(values)
        accepted = [v for v in values if 1 <= v <= min(300, limit)]
        parameters[key] = (
            min(300, max(60, limit)),
            statistics.median(accepted) if accepted else None,
        )
    estimates = []
    for row, delta, key in observations:
        limit, median = parameters.get(key, (60, None))
        direct = delta is not None and 1 <= delta <= limit
        seconds = delta if direct else (median + 4 if median is not None else 30)
        estimates.append(
            {
                **row,
                "seconds": seconds,
                "source": "series" if direct else "estimate",
                "gapSeconds": delta,
                "medianSeconds": median,
                "limitSeconds": limit,
            }
        )
    return estimates


def zoom_days(events, aliases, zone):
    """Pair participant streams, then union devices; partial means whole-day fallback."""
    streams = defaultdict(list)
    seen = set()
    for row in events:
        if row["event"] not in (
            "meeting.participant_joined",
            "meeting.participant_left",
        ):
            continue
        alias = aliases.get(normalize_name(row["zoom_user_name"] or ""))
        if not alias or alias["state"] != "mapped":
            continue
        teacher = alias["teacher_id"]
        ts = moment(row["event_ts"], zone, legacy_zoom=True)
        participant = str(row["zoom_user_id"] or "")
        dedup = (teacher, participant, ts, row["event"])
        if dedup in seen:
            continue
        seen.add(dedup)
        streams[(teacher, participant)].append((ts, row["event"], row["id"]))
    intervals = defaultdict(list)
    evidence = defaultdict(list)
    anomalies = defaultdict(list)
    for (teacher, participant), stream in streams.items():
        opened = None
        for ts, event, event_id in sorted(stream):
            day = ts.astimezone(ZoneInfo(zone)).date().isoformat()
            key = (teacher, day)
            evidence[key].append(event_id)
            if not participant:
                anomalies[key].append("missing_participant")
            if event.endswith("_joined"):
                if opened:
                    for affected, _ in split_days(
                        opened, ts + timedelta(microseconds=1), zone
                    ):
                        anomalies[(teacher, affected)].append("repeated_join")
                opened = ts
            elif opened is None:
                anomalies[key].append("missing_join")
            else:
                for affected, interval in split_days(opened, ts, zone):
                    intervals[(teacher, affected)].append(interval)
                    evidence[(teacher, affected)].append(event_id)
                if ts <= opened:
                    anomalies[key].append("nonpositive_interval")
                opened = None
        if opened:
            anomalies[
                (teacher, opened.astimezone(ZoneInfo(zone)).date().isoformat())
            ].append("missing_leave")
    keys = set(intervals) | set(evidence) | set(anomalies)
    return {
        key: {
            "hours": union_seconds(intervals[key]) / 3600,
            "anomalies": sorted(set(anomalies[key])),
            "eventIds": sorted(set(evidence[key])),
        }
        for key in keys
    }


def calculate_snapshot(facts):
    zone = facts["course"]["timezone"]
    cells = []

    def add(kind, teacher, slot, hours, source, evidence, anomalies=None):
        key = f"{kind}:{teacher}:{slot}"
        semantic_evidence = evidence
        if kind == "school":
            semantic_evidence = [
                {
                    k: v
                    for k, v in row.items()
                    if k not in ("version", "updated_at", "updated_by")
                }
                for row in evidence
            ]
        cells.append(
            {
                "key": key,
                "kind": kind,
                "teacherId": f"u-{teacher}",
                "slot": slot,
                "hours": hours,
                "source": source,
                "evidence": evidence,
                "anomalies": anomalies or [],
                "fingerprint": fingerprint(
                    [hours, source, semantic_evidence, anomalies or []]
                ),
            }
        )

    written = defaultdict(list)
    for row in written_estimates(
        [r for r in facts["results"] if r["res_type"] == 2], zone
    ):
        written[(row["teacher_id"], row["lesson"])].append(row)
    for (teacher, lesson), rows in written.items():
        add(
            "written",
            teacher,
            str(lesson),
            sum(r["seconds"] for r in rows) / 3600,
            "series" if all(r["source"] == "series" for r in rows) else "estimate",
            rows,
        )

    aliases = {r["normalized_name"]: r for r in facts["aliases"]}
    logged = zoom_days(facts["zoom"], aliases, zone)
    oral = defaultdict(list)
    for row in facts["results"]:
        if row["res_type"] == 3:
            day = moment(row["ts"], zone).astimezone(ZoneInfo(zone)).date().isoformat()
            oral[(row["teacher_id"], day)].append(row)
    for teacher, day in sorted(set(logged) | set(oral)):
        log = logged.get((teacher, day))
        rows = oral.get((teacher, day), [])
        anomalies = log["anomalies"] if log else ["no_log"]
        if log and not anomalies:
            hours, source = log["hours"], "log"
        elif rows:
            stamps = [moment(r["ts"], zone) for r in rows]
            hours = min(
                3.5,
                max(
                    (max(stamps) - min(stamps)).total_seconds() / 3600 + 0.3,
                    len(rows) / 14,
                ),
            )
            source = "estimate"
        else:
            hours, source = None, "unknown"
        add(
            "zoom",
            teacher,
            day,
            hours,
            source,
            {"log": log, "results": rows},
            anomalies,
        )

    school = defaultdict(list)
    for shift in facts["shifts"]:
        start, end = moment(shift["starts_at"], zone), moment(shift["ends_at"], zone)
        standard = (
            moment(shift["standard_ends_at"], zone)
            - moment(shift["standard_starts_at"], zone)
        ).total_seconds() / 3600
        day = start.astimezone(ZoneInfo(zone)).date().isoformat()
        school[(shift["teacher_id"], day)].append(
            {
                **shift,
                "creditedHours": max(
                    0,
                    shift["norm_hours"]
                    + (end - start).total_seconds() / 3600
                    - standard,
                ),
            }
        )
    for (teacher, day), rows in school.items():
        add(
            "school",
            teacher,
            day,
            sum(r["creditedHours"] for r in rows),
            "roster",
            rows,
        )
    return {
        "cells": cells,
        "course": facts["course"],
        "teachers": facts["teachers"],
        "lessons": facts["lessons"],
        "events": facts["events"],
        "windows": facts["windows"],
    }


MONTHS = {
    "январ": 1,
    "феврал": 2,
    "март": 3,
    "апрел": 4,
    "ма": 5,
    "июн": 6,
    "июл": 7,
    "август": 8,
    "сентябр": 9,
    "окт": 10,
    "ноябр": 11,
    "декабр": 12,
}


def name_candidates(value, teachers):
    name = re.sub(
        r"\b(?:принима\w*|провер\w*|модератор)\b", "", normalize_name(value)
    ).strip()
    ranked = []
    for teacher in teachers:
        variants = [
            teacher["surname"],
            f"{teacher['surname']} {teacher['name']}",
            f"{teacher['name']} {teacher['surname']}",
            f"{teacher['surname']} {teacher['name'][:1]}.",
        ]
        score = max(
            SequenceMatcher(None, name, normalize_name(v)).ratio() for v in variants
        )
        if score >= 0.45:
            ranked.append(
                {
                    "teacherId": teacher["public_id"],
                    "label": f"{teacher['surname']} {teacher['name']}",
                    "score": round(score, 3),
                }
            )
    return sorted(ranked, key=lambda r: (-r["score"], r["teacherId"]))[:5]


def parse_roster(text, events, teachers, zone):
    rows, notes = [], []
    date_match = re.search(r"\b(\d{1,2})\s+([а-яё]+)(?:\s+(20\d{2}))?", text, re.I)
    event_candidates = []
    if date_match:
        day, month_name, year = date_match.groups()
        month = next(
            (
                m
                for prefix, m in MONTHS.items()
                if month_name.casefold().startswith(prefix)
            ),
            None,
        )
        event_candidates = [
            e["public_id"]
            for e in events
            if moment(e["starts_at"], zone).astimezone(ZoneInfo(zone)).day == int(day)
            and moment(e["starts_at"], zone).astimezone(ZoneInfo(zone)).month == month
            and (not year or moment(e["starts_at"], zone).year == int(year))
        ]
    for line_number, line in enumerate(text.splitlines()):
        # A bare date heading is metadata, not a two-digit classroom.
        if re.match(
            r"^\s*\d{1,2}\s+(?:январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|окт|ноябр|декабр)",
            line,
            re.I,
        ):
            notes.append(line.strip())
            continue
        room = re.match(r"^\s*(\d{2,4})\s*(?::|[-—–]{1,2})?\s+(.+?)\s*$", line)
        if not room or re.search(r"резерв", line, re.I):
            if line.strip():
                notes.append(line.strip())
            continue
        # Commas inside parentheses belong to time/group notes.
        chunks = re.split(r",\s*(?![^()]*\))", room[2].rstrip("."))
        for index, chunk in enumerate(chunks):
            name = re.sub(r"\([^)]*\)", "", chunk).strip(" .")
            if not name:
                continue
            start = re.search(r"\bс\s*(\d{1,2}:\d{2})", chunk, re.I)
            end = re.search(r"\bдо\s*(\d{1,2}:\d{2})", chunk, re.I)
            rows.append(
                {
                    "rowId": f"{line_number}-{index}",
                    "name": name,
                    "room": room[1],
                    "startsTime": start[1] if start else None,
                    "endsTime": end[1] if end else None,
                    "teacherId": None,
                    "source": line.strip(),
                    "candidates": name_candidates(name, teachers),
                }
            )
    return {
        "rows": rows,
        "notes": notes,
        "eventCandidates": event_candidates,
        "preliminary": bool(
            re.search(r"предварител|пока не очень понятно", text, re.I)
        ),
        "sourceSha256": fingerprint(text),
    }
