"""Copy this file beside legacy scripts as z_portal_print.py (Python 3.9+).

Normal use: a11 calls refresh_portal_conduit(...).
Diagnostic CLI: python z_portal_print.py events
                python z_portal_print.py download EVENT_ID LESSON_NUMBER
See legacy-api.md. No Telegram or Google dependencies.
"""

import argparse
import copy
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener


DEFAULT_SNAPSHOT = Path(__file__).resolve().with_name("portal-print.json")
DEFAULT_AFTER_LESSON_SNAPSHOT = Path(__file__).resolve().with_name(
    "portal-after-lesson.json"
)
API_BASE = "https://vmsh.shashkovs.ru/staff/api/legacy-print/v1"


class NoRedirect(HTTPRedirectHandler):
    # Do not forward the shared bearer credential to any redirect destination.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _get(path, token=None):
    token = token or os.environ.get("VMSH_PRINT_API_TOKEN", "")
    if not token:
        raise RuntimeError("Задайте VMSH_PRINT_API_TOKEN")
    request = Request(
        API_BASE + path,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/json",
        },
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=30) as response:
            return json.load(response), dict(response.headers.items())
    except HTTPError as error:
        try:
            payload = json.load(error)
            message = payload["error"]["message"]
        except Exception:
            message = "Сервер отклонил запрос"
        raise RuntimeError("API печати: HTTP %s — %s" % (error.code, message)) from None


def download_portal_conduit(event_id, lesson, filename=DEFAULT_SNAPSHOT, token=None):
    pupils, headers = _get(
        "/events/%s/pupils?lesson=%d" % (quote(event_id, safe=""), lesson), token
    )
    metadata = {key.lower(): value for key, value in headers.items()}
    if (
        not isinstance(pupils, list)
        or not pupils
        or metadata.get("x-print-event") != event_id
        or metadata.get("x-print-lesson") != str(lesson)
    ):
        raise RuntimeError("Некорректный ответ API печати")
    history, history_headers = _get(
        "/events/%s/previous-results?lesson=%d" % (quote(event_id, safe=""), lesson),
        token,
    )
    history_metadata = {key.lower(): value for key, value in history_headers.items()}
    if (
        not isinstance(history, dict)
        or history.get("lesson") != lesson - 1
        or not isinstance(history.get("problems"), list)
        or not isinstance(history.get("results"), list)
        or history_metadata.get("x-print-event") != event_id
        or history_metadata.get("x-print-lesson") != str(lesson)
        or history_metadata.get("x-print-previous-lesson") != str(lesson - 1)
        or history_metadata.get("x-print-plan") != metadata.get("x-print-plan")
        or history_metadata.get("x-print-plan-version")
        != metadata.get("x-print-plan-version")
    ):
        raise RuntimeError("Некорректный ответ API результатов печати")
    snapshot = {
        "eventId": event_id,
        "lesson": lesson,
        "etag": metadata["etag"],
        "historyEtag": history_metadata["etag"],
        "planId": metadata["x-print-plan"],
        "planVersion": metadata["x-print-plan-version"],
        "pupils": pupils,
        "previousLesson": history["lesson"],
        "problems": history["problems"],
        "results": history["results"],
    }
    destination = Path(filename)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # The file contains personal data, never the API credential.
        temporary.chmod(0o600)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return len(pupils)


def download_portal_lesson_results(
    event_id, lesson, filename=DEFAULT_AFTER_LESSON_SNAPSHOT, token=None
):
    """Download the current lesson matrix used by a22 and a23."""
    snapshot, headers = _get(
        "/events/%s/lesson-results?lesson=%d" % (quote(event_id, safe=""), lesson),
        token,
    )
    metadata = {key.lower(): value for key, value in headers.items()}
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("schemaVersion") != 1
        or snapshot.get("lesson") != lesson
        or not isinstance(snapshot.get("pupils"), list)
        or not isinstance(snapshot.get("problems"), list)
        or not isinstance(snapshot.get("results"), list)
        or not isinstance(snapshot.get("recentStudentIds"), list)
        or metadata.get("x-print-event") != event_id
        or metadata.get("x-print-lesson") != str(lesson)
    ):
        raise RuntimeError("Некорректный ответ API результатов занятия")
    snapshot = {
        **snapshot,
        "eventId": event_id,
        "etag": metadata["etag"],
        "planId": metadata["x-print-plan"],
        "planVersion": metadata["x-print-plan-version"],
    }
    destination = Path(filename)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.chmod(0o600)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return len(snapshot["pupils"])


def resolve_portal_print_event(lesson, token=None):
    """Find the one confirmed event made entirely from this lesson number."""
    payload, _ = _get("/events", token)
    events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list):
        raise RuntimeError("Некорректный список событий API печати")
    matches = [
        event
        for event in events
        if isinstance(event, dict)
        and isinstance(event.get("event_id"), str)
        and event["event_id"]
        and event.get("plan_id")
        and event.get("status") != "cancelled"
        and event.get("lesson_numbers") == [lesson]
    ]
    if len(matches) != 1:
        details = ", ".join(
            "%s (%s, %s)"
            % (
                event.get("event_id", "без ID"),
                event.get("starts_at", "без даты"),
                event.get("status", "без статуса"),
            )
            for event in matches
        )
        if not details:
            details = "нет"
        raise RuntimeError(
            "Не удалось однозначно выбрать подтверждённое очное событие для "
            "занятия %s. Подходящие события: %s. Укажите event_id явно."
            % (lesson, details)
        )
    return matches[0]["event_id"]


def refresh_portal_conduit(
    lesson, filename=DEFAULT_SNAPSHOT, token=None, event_id=None
):
    """Download one fresh snapshot and return its Excel-compatible rows."""
    event_id = event_id or resolve_portal_print_event(lesson, token)
    download_portal_conduit(event_id, lesson, filename, token)
    return load_portal_conduit(lesson, filename)


def refresh_portal_lesson_results(
    lesson,
    filename=DEFAULT_AFTER_LESSON_SNAPSHOT,
    token=None,
    event_id=None,
):
    """Refresh the post-lesson snapshot once before generating artifacts."""
    event_id = event_id or resolve_portal_print_event(lesson, token)
    download_portal_lesson_results(event_id, lesson, filename, token)
    return load_portal_lesson_results(lesson, filename)


def load_portal_conduit(lesson, filename=DEFAULT_SNAPSHOT):
    """Same mutable row shape as parse_xls_conduit; all scripts use one snapshot."""
    try:
        snapshot = json.loads(Path(filename).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RuntimeError(
            "Снимок portal-print.json не найден; сначала запустите a11"
        ) from None
    if snapshot["lesson"] != lesson:
        raise RuntimeError("Снимок распределения относится к другому занятию")
    return copy.deepcopy(snapshot["pupils"])


def load_portal_lesson_results(
    lesson, filename=DEFAULT_AFTER_LESSON_SNAPSHOT
):
    try:
        snapshot = json.loads(Path(filename).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RuntimeError(
            "Снимок portal-after-lesson.json не найден; сначала обновите его через API"
        ) from None
    if snapshot.get("schemaVersion") != 1 or snapshot.get("lesson") != lesson:
        raise RuntimeError("Снимок результатов относится к другому занятию")
    return snapshot


def get_portal_mail_pupils(lesson, filename=DEFAULT_AFTER_LESSON_SNAPSHOT):
    """Return the dict shape formerly produced from the legacy users table."""
    snapshot = load_portal_lesson_results(lesson, filename)
    pupils = {}
    for source in snapshot["pupils"]:
        pupil = {
            "id": int(source["id"]),
            "token": source["login"],
            "surname": source["surname"],
            "name": source["name"],
            "group_id": source["level"],
        }
        pupil["key"] = "%s\t%s\t%s\t%s" % (
            pupil["token"],
            pupil["surname"],
            pupil["name"],
            pupil["group_id"],
        )
        pupils[pupil["id"]] = pupil
    return pupils


def get_portal_mail_problems(
    lesson, level, filename=DEFAULT_AFTER_LESSON_SNAPSHOT
):
    """Return current lesson columns for one human level code."""
    snapshot = load_portal_lesson_results(lesson, filename)
    problems = {}
    for source in snapshot["problems"]:
        if source.get("level") != level:
            continue
        problem = copy.deepcopy(source)
        problem["key"] = "%s%s.%s%s" % (
            problem["lesson"],
            level,
            problem["prob"],
            problem["item"],
        )
        problem["formatted"] = "%02d%s.%02d%s" % (
            int(problem["lesson"]),
            level,
            int(problem["prob"]),
            problem["item"],
        )
        problems[int(problem["id"])] = problem
    return problems


def get_portal_mail_results(
    lesson, level, filename=DEFAULT_AFTER_LESSON_SNAPSHOT
):
    """Return attempted verdicts; missing matrix cells stay absent."""
    snapshot = load_portal_lesson_results(lesson, filename)
    problem_ids = {
        int(problem["id"])
        for problem in snapshot["problems"]
        if problem.get("level") == level
    }
    return {
        (int(row["student_id"]), int(row["problem_id"])): float(
            row["max_verdict"]
        )
        for row in snapshot["results"]
        if int(row["problem_id"]) in problem_ids
        and row.get("max_verdict") is not None
    }


def get_portal_recent_student_ids(
    lesson, filename=DEFAULT_AFTER_LESSON_SNAPSHOT
):
    snapshot = load_portal_lesson_results(lesson, filename)
    return {int(student_id) for student_id in snapshot["recentStudentIds"]}


def get_portal_problem_statistics(
    lesson, filename=DEFAULT_AFTER_LESSON_SNAPSHOT
):
    """Aggregate the scored participant matrix for the legacy site markers."""
    snapshot = load_portal_lesson_results(lesson, filename)
    problems = {int(problem["id"]): problem for problem in snapshot["problems"]}
    totals = {}
    for row in snapshot["results"]:
        problem_id = int(row["problem_id"])
        solved, count = totals.get(problem_id, (0.0, 0))
        totals[problem_id] = (solved + float(row["score"]), count + 1)
    statistics = {}
    for problem_id, (solved, count) in totals.items():
        problem = problems[problem_id]
        key = "%s%s.%s%s" % (
            problem["lesson"],
            problem["level"],
            problem["prob"],
            problem["item"],
        )
        statistics[key] = (int(solved + 0.5), count)
    return statistics


def _load_portal_history(lesson, filename=DEFAULT_SNAPSHOT):
    try:
        snapshot = json.loads(Path(filename).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RuntimeError(
            "Снимок portal-print.json не найден; сначала запустите a11"
        ) from None
    if snapshot.get("previousLesson") != lesson:
        raise RuntimeError("Снимок результатов относится к другому занятию")
    if not isinstance(snapshot.get("problems"), list) or not isinstance(
        snapshot.get("results"), list
    ):
        raise RuntimeError("В снимке нет задач и результатов; сначала запустите a11")
    return snapshot


def get_portal_pupils_for_results(logins, lesson, filename=DEFAULT_SNAPSHOT):
    """Replacement for a13 get_pupils: identity/group come from the same plan."""
    by_login = {row["IDd"]: row for row in load_portal_conduit(lesson, filename)}
    selected = [by_login[login] for login in logins]
    selected.sort(key=lambda row: (row["ФИО"].casefold().replace("ё", "е"), row["ID"]))
    return [
        {
            "id": row["UserID"],
            "token": row["IDd"],
            "surname": row["Фамилия"],
            "name": row["Имя"],
            "group_id": row["GroupID"],
            "grade": row["Клс"],
        }
        for row in selected
    ]


def get_portal_problems(lesson, group_id, filename=DEFAULT_SNAPSHOT):
    """Replacement for the a13 problem query."""
    snapshot = _load_portal_history(lesson, filename)
    return copy.deepcopy(
        [row for row in snapshot["problems"] if row.get("group_id") == group_id]
    )


def get_portal_results(pupil_ids, lesson, group_id, filename=DEFAULT_SNAPSHOT):
    """Return raw verdict weights keyed exactly as the a13 conduit expects."""
    snapshot = _load_portal_history(lesson, filename)
    selected_pupils = {int(pupil_id) for pupil_id in pupil_ids}
    selected_problems = {
        int(problem["id"])
        for problem in snapshot["problems"]
        if problem.get("group_id") == group_id
    }
    return {
        (int(row["student_id"]), int(row["syn_problem_id"])): float(row["max_verdict"])
        for row in snapshot["results"]
        if int(row["student_id"]) in selected_pupils
        and int(row["syn_problem_id"]) in selected_problems
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("events")
    download = commands.add_parser("download")
    download.add_argument("event_id")
    download.add_argument("lesson", type=int)
    download.add_argument("--output", type=Path, default=DEFAULT_SNAPSHOT)
    args = parser.parse_args()
    if args.command == "events":
        payload, _ = _get("/events")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        count = download_portal_conduit(args.event_id, args.lesson, args.output)
        print(
            "Сохранён снимок: %s, занятие %s, %s учеников"
            % (args.output, args.lesson, count)
        )


if __name__ == "__main__":
    main()
