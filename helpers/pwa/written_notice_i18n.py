"""P8 read projection for system notices written by review_transfers.commit.

Only system-authored system_event entries match these exact application-owned
templates. Authored messages and stored bytes are never rewritten.
See vmshpwa/dev/development-plan/24-i18n-execution-plan.md, P8.2.
"""

import re

from helpers.pwa.i18n import N_, _

_TEMPLATES = (
    N_("Перенесено преподавателем в задачу {problem}."),
    N_("Перенесено преподавателем из задачи {problem}."),
    N_("Скопировано преподавателем в задачу {problem}."),
    N_("Скопировано преподавателем из задачи {problem}."),
)
_PATTERNS = tuple(
    (re.compile(re.escape(template).replace(r"\{problem\}", "(.+)")), template)
    for template in _TEMPLATES
)


def localize_thread_notices(payload: dict) -> dict:
    """Return a shallow projection, preserving unknown messages and all data."""
    entries = []
    for entry in payload["entries"]:
        text = entry.get("text")
        if (
            entry.get("authorKind") == "system"
            and entry.get("entryKind") == "system_event"
            and isinstance(text, str)
        ):
            for pattern, template in _PATTERNS:
                match = pattern.fullmatch(text)
                if match:
                    entry = {**entry, "text": _(template, problem=match[1])}
                    break
        entries.append(entry)
    return {**payload, "entries": entries}
