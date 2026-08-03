from __future__ import annotations

import pytest

from models.pwa.account_batches import (
    InvalidAccountBatchRow,
    choose_available_login,
    normalize_family_batch_row,
    normalize_student_batch_row,
)


def test_student_batch_normalizes_required_and_optional_fields() -> None:
    row = normalize_student_batch_row(
        {
            "surname": "  Ёлкин ",
            "name": " Лев ",
            "login": " Lev-17 ",
            "password": " Telegram-Token ",
        }
    )

    assert row == {
        "surname": "Ёлкин",
        "name": "Лев",
        "patronymic": "",
        "birth_date": None,
        "grade": None,
        "login": "Lev-17",
        "login_normalized": "lev-17",
        "password": "telegram-token",
    }


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("birthDate", "31.02.2013", "invalid_birth_date"),
        ("grade", 12, "invalid_grade"),
        ("password", "", "invalid_password"),
    ],
)
def test_student_batch_rejects_invalid_fields(
    field: str, value: object, code: str
) -> None:
    source: dict[str, object] = {
        "surname": "Иванов",
        "name": "Иван",
        "login": "ivanov",
        "password": "token",
    }
    source[field] = value

    with pytest.raises(InvalidAccountBatchRow, match=code):
        normalize_student_batch_row(source)


def test_family_batch_splits_comma_separated_emails_and_normalizes_children() -> None:
    row = normalize_family_batch_row(
        {
            "name": " Анна Иванова ",
            "login": " Parent-Ivanov ",
            "password": "qwerty-family",
            "emails": " parent@example.org, second@example.org, ",
            "childLogins": [" IVANOV-1 ", "ivanov-2"],
        }
    )

    assert row["emails"] == ("parent@example.org", "second@example.org")
    assert row["child_logins"] == ("ivanov-1", "ivanov-2")
    assert row["login_normalized"] == "parent-ivanov"


def test_family_batch_rejects_duplicate_email_and_child() -> None:
    source = {
        "name": "Анна",
        "login": "parent",
        "password": "qwerty-family",
        "emails": "A@example.org, a@example.org",
        "childLogins": ["child"],
    }
    with pytest.raises(InvalidAccountBatchRow, match="invalid_emails"):
        normalize_family_batch_row(source)

    source["emails"] = "a@example.org"
    source["childLogins"] = ["child", "CHILD"]
    with pytest.raises(InvalidAccountBatchRow, match="invalid_child_logins"):
        normalize_family_batch_row(source)


def test_login_collision_gets_reviewable_two_digit_suffix() -> None:
    used = {"ivanov"}

    login, normalized, adjusted = choose_available_login(
        "ivanov", "ivanov", used, [17, 42]
    )

    assert (login, normalized, adjusted) == ("ivanov-17", "ivanov-17", True)
    assert "ivanov-17" in used
