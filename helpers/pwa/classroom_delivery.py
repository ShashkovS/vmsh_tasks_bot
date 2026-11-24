"""Telegram text for the narrow classroom-assignment delivery."""

from __future__ import annotations


def classroom_assignment_message(recipient: dict[str, object]) -> str:
    return (
        f"{recipient['event_name']}\n"
        f"{recipient['course_name']} · {recipient['group_name']}\n\n"
        f"Ваша аудитория: {recipient['classroom_name']}.\n\n"
        "Если вы не планируете прийти очно, пожалуйста, заранее измените режим "
        "занятия в личном кабинете."
    )


__all__ = ["classroom_assignment_message"]
