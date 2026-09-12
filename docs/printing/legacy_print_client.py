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
    snapshot = {
        "eventId": event_id,
        "lesson": lesson,
        "etag": metadata["etag"],
        "planId": metadata["x-print-plan"],
        "planVersion": metadata["x-print-plan-version"],
        "pupils": pupils,
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
