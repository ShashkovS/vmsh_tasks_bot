"""Audience scoping for Staff enrollment changes."""

from __future__ import annotations

import pytest
from aiohttp import web

from apps import pwa_app


@pytest.mark.asyncio
async def test_enrollment_change_invalidates_only_owners_and_staff_directory() -> None:
    class RecordingBroker:
        def __init__(self) -> None:
            self.messages: list[tuple[str, dict[str, object]]] = []

        async def publish(self, topic: str, payload: dict[str, object]) -> None:
            self.messages.append((topic, payload))

    app = web.Application()
    broker = RecordingBroker()
    app[pwa_app.PWA_BROKER] = broker

    await pwa_app.publish_enrollment_invalidation(
        app,
        student_account_public_ids=("student-account",),
        family_account_public_ids=("family-account",),
        reason="staff-enrollment-updated",
    )

    assert broker.messages == [
        (
            "pwa_invalidate",
            {
                "resources": ["courses", "home", "classroom-assignments"],
                "reason": "staff-enrollment-updated",
                "audience": "student",
                "accountId": "student-account",
            },
        ),
        (
            "pwa_invalidate",
            {
                "resources": ["courses", "home", "classroom-assignments"],
                "reason": "staff-enrollment-updated",
                "audience": "family",
                "accountId": "family-account",
            },
        ),
        (
            "pwa_invalidate",
            {
                "resources": ["admin-student-enrollments"],
                "reason": "staff-enrollment-updated",
                "audience": "staff",
            },
        ),
    ]
