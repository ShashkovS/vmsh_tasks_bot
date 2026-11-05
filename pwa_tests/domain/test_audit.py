from __future__ import annotations

import pytest

from models.pwa.audit import InvalidAuditEvent, audit_event_payload


def _row(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "public_id": "audit.event-1",
        "occurred_at": "2026-08-02T10:30:00Z",
        "audience": "staff",
        "action": "account.status_changed",
        "object_type": "account",
        "object_id": "account.student-1",
        "request_id": "request-1",
        "before_json": '{"status":"active"}',
        "after_json": '{"status":"blocked","version":2}',
        "actor_user_public_id": "user.admin-1",
        "actor_account_public_id": "account.admin-1",
        "actor_name": "Анна",
        "actor_surname": "Петрова",
    }
    row.update(changes)
    return row


def test_audit_event_projects_flat_changes_and_actor() -> None:
    payload = audit_event_payload(_row())

    assert payload["actor"] == {
        "userId": "user.admin-1",
        "accountId": "account.admin-1",
        "displayName": "Петрова Анна",
    }
    assert payload["before"] == {"status": "active"}
    assert payload["after"] == {"status": "blocked", "version": 2}


@pytest.mark.parametrize(
    "stored",
    [
        "not-json",
        "[]",
        '{"credentialHash":"never"}',
        '{"passwordChanged":true}',
        '{"status":{"old":"active"}}',
        '{"bad_key":"active"}',
    ],
)
def test_audit_event_rejects_unsafe_or_malformed_changes(stored: str) -> None:
    with pytest.raises(InvalidAuditEvent):
        audit_event_payload(_row(after_json=stored))


def test_audit_event_labels_missing_actor_as_system() -> None:
    payload = audit_event_payload(
        _row(
            actor_user_public_id=None,
            actor_account_public_id=None,
            actor_name=None,
            actor_surname=None,
        )
    )

    assert payload["actor"] == {
        "userId": None,
        "accountId": None,
        "displayName": "Система",
    }
