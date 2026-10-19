from copy import deepcopy

from helpers.pwa.i18n import current_locale
from helpers.pwa.written_notice_i18n import localize_thread_notices


def test_only_proven_system_notices_are_projected_without_changing_data():
    text = "Перенесено преподавателем в задачу 41н.6."
    payload = {
        "threadId": "thread-1",
        "entries": [
            {"authorKind": "system", "entryKind": "system_event", "text": text},
            {"authorKind": "student", "entryKind": "submission", "text": text},
            {
                "authorKind": "system",
                "entryKind": "system_event",
                "text": "Неизвестное событие",
            },
        ],
    }
    before = deepcopy(payload)
    token = current_locale.set("en")
    try:
        result = localize_thread_notices(payload)
    finally:
        current_locale.reset(token)
    assert result["entries"][0]["text"] == "Moved by a teacher to problem 41н.6."
    assert result["entries"][1:] == before["entries"][1:]
    assert payload == before
    assert result["threadId"] == before["threadId"]
