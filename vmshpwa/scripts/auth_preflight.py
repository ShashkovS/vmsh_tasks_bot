"""Produce a privacy-safe aggregate auth preflight from ``db/vmsh.db``.

Only aggregate counts leave this module. Source rows, generated login candidates,
tokens and identifiers are never written to a report. Exact bytes are read and
hashed through a nofollow descriptor, then queried through an in-memory SQLite
``deserialize`` snapshot with ``query_only`` enabled. Journal sidecars are
refused so an incomplete or live snapshot is never silently analyzed. See
AUTH-01 in ``vmshpwa/dev/development-plan/05-phase-1-auth.md``.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import unicodedata
from collections import Counter
from contextlib import closing
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from models.pwa.auth import (
    STUDENT_USERNAME_ALGORITHM_VERSION,
    build_student_username,
    legacy_telegram_token_risk_shapes,
)
from vmshpwa.scripts.report_io import AtomicReportWriteError, atomic_write_text
from vmshpwa.scripts.safe_source import (
    SafeSourceError,
    fingerprint,
    read_and_fingerprint,
    secure_open,
    verify_path_matches,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE = REPOSITORY_ROOT / "db/vmsh.db"
JSON_REPORT = REPOSITORY_ROOT / "pwa_tests/reports/auth-preflight.json"
MARKDOWN_REPORT = REPOSITORY_ROOT / "pwa_tests/reports/auth-preflight.md"
SCHEMA_VERSION = 2
STUDENT_TYPE = 1

_TYPE_LABELS = {
    -4: "unknown",
    -2: "deactivated_student",
    -1: "deleted",
    1: "student",
    2: "teacher",
    128: "admin",
}


class AuthPreflightError(RuntimeError):
    """Raised for unsafe sources, incomplete schema or stale reports."""


def _sqlite_sidecars(path: Path) -> tuple[Path, ...]:
    return tuple(
        path.with_name(path.name + suffix) for suffix in ("-wal", "-shm", "-journal")
    )


def _require_quiescent_snapshot(path: Path) -> None:
    if any(sidecar.exists() for sidecar in _sqlite_sidecars(path)):
        raise AuthPreflightError(
            "Auth preflight requires a quiescent SQLite snapshot without "
            "WAL/journal sidecars"
        )


def _deserialize_snapshot(connection: Any, content: bytes) -> None:
    deserialize = getattr(connection, "deserialize", None)
    if not callable(deserialize):
        raise AuthPreflightError(
            "SQLite connection deserialize support is required for auth preflight"
        )
    try:
        deserialize(content)
    except sqlite3.Error as error:
        raise AuthPreflightError(
            "SQLite source bytes could not be deserialized safely"
        ) from error


def _open_read_only_snapshot(content: bytes) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", autocommit=True)
    try:
        _deserialize_snapshot(connection, content)
    except Exception:
        connection.close()
        raise
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    if connection.execute("PRAGMA query_only").fetchone()[0] != 1:
        connection.close()
        raise AuthPreflightError(
            "SQLite query_only could not be enabled for deserialized snapshot"
        )
    connection.execute("BEGIN")
    return connection


def _normalized(value: Any) -> str:
    text = "" if value is None else str(value)
    return " ".join(unicodedata.normalize("NFKC", text).strip().casefold().split())


def _birthday(value: Any) -> tuple[str, date | None]:
    if value is None:
        return "null", None
    text = str(value).strip()
    if not text:
        return "blank", None
    try:
        parsed = date.fromisoformat(text)
    except (TypeError, ValueError):  # fmt: skip
        return "invalidIsoDate", None
    if parsed > date.today():
        return "futureDate", parsed
    return "validIsoDate", parsed


def _length_bucket(token: str) -> str:
    length = len(token)
    if length == 0:
        return "0"
    if length <= 5:
        return "1-5"
    if length <= 7:
        return "6-7"
    if length <= 11:
        return "8-11"
    if length <= 15:
        return "12-15"
    if length <= 31:
        return "16-31"
    return "32+"


def _collision_counts(keys: Iterable[str]) -> dict[str, int]:
    counts = Counter(key for key in keys if key)
    collisions = [count for count in counts.values() if count > 1]
    return {
        "collisionGroups": len(collisions),
        "affectedRows": sum(collisions),
    }


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_schema WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def analyze_database(database_path: Path) -> dict[str, Any]:
    """Analyze a SQLite snapshot and return aggregate, non-identifying metrics."""

    supplied_path = Path(database_path)
    if supplied_path.is_symlink():
        raise AuthPreflightError(f"Expected a regular SQLite source: {supplied_path}")
    path = supplied_path.resolve()
    try:
        _require_quiescent_snapshot(path)
        with secure_open(path) as source_descriptor:
            before, source_bytes = read_and_fingerprint(source_descriptor)
            verify_path_matches(path, before)
            with closing(_open_read_only_snapshot(source_bytes)) as connection:
                # Queries run against an in-memory database deserialized from the
                # exact bytes read and hashed through source_descriptor. SQLite does
                # not reopen the source path.
                verify_path_matches(path, before)
                if not _table_exists(connection, "users"):
                    raise AuthPreflightError("SQLite source has no users table")
                rows = connection.execute(
                    "SELECT type, surname, birthday, token, chat_id FROM users"
                ).fetchall()
                student_rows = [row for row in rows if row["type"] == STUDENT_TYPE]

                birthday_counts: Counter[str] = Counter()
                surname_counts: Counter[str] = Counter()
                length_counts: Counter[str] = Counter()
                shape_counts: Counter[str] = Counter()
                canonical_login_keys: list[str] = []
                assessments: list[tuple[bool, str | None]] = []

                for row in student_rows:
                    birthday_status, parsed_birthday = _birthday(row["birthday"])
                    birthday_counts[birthday_status] += 1
                    surname = _normalized(row["surname"])
                    surname_status = "present" if surname else "emptyAfterTrim"
                    surname_counts[surname_status] += 1

                    raw_token = (
                        "" if row["token"] is None else str(row["token"]).strip()
                    )
                    token_status = "null" if row["token"] is None else "present"
                    if row["token"] is not None and not raw_token:
                        token_status = "blankAfterTrim"
                    length_counts[_length_bucket(raw_token)] += 1
                    shapes = (
                        legacy_telegram_token_risk_shapes(raw_token, row["chat_id"])
                        if raw_token
                        else set()
                    )
                    shape_counts.update(shapes)
                    if shapes:
                        shape_counts["anyGuessableShape"] += 1

                    canonical_login = None
                    if (
                        surname
                        and parsed_birthday is not None
                        and birthday_status == "validIsoDate"
                    ):
                        try:
                            canonical_login = build_student_username(
                                str(row["surname"]), parsed_birthday
                            )
                        except ValueError:
                            surname_counts["emptyLoginStem"] += 1

                    birthday_blocked = birthday_status != "validIsoDate"
                    token_blocked = token_status != "present" or bool(shapes)
                    blocked_by_fields = (
                        birthday_blocked
                        or not surname
                        or canonical_login is None
                        or token_blocked
                    )
                    if canonical_login is not None:
                        canonical_login_keys.append(canonical_login)
                    assessments.append((blocked_by_fields, canonical_login))

                canonical_login_counts = Counter(canonical_login_keys)
                colliding_canonical_logins = {
                    key for key, count in canonical_login_counts.items() if count > 1
                }
                field_blocked_rows = sum(blocked for blocked, _key in assessments)
                canonical_collision_rows = sum(
                    key in colliding_canonical_logins
                    for _blocked, key in assessments
                    if key
                )
                activation_blocked_rows = sum(
                    blocked or key in colliding_canonical_logins
                    for blocked, key in assessments
                )

                legacy_login_report: dict[str, Any]
                if _table_exists(connection, "kv_logins"):
                    legacy_logins = connection.execute(
                        """
                        SELECT k.kv_login
                        FROM kv_logins k
                        JOIN users u ON u.id = k.user_id
                        WHERE u.type = ?
                        """,
                        (STUDENT_TYPE,),
                    ).fetchall()
                    normalized_logins = [
                        _normalized(row["kv_login"]) for row in legacy_logins
                    ]
                    legacy_login_report = {
                        "tablePresent": True,
                        "studentRows": len(legacy_logins),
                        "nullOrBlank": sum(not login for login in normalized_logins),
                        **_collision_counts(normalized_logins),
                    }
                else:
                    legacy_login_report = {
                        "tablePresent": False,
                        "studentRows": 0,
                        "nullOrBlank": 0,
                        "collisionGroups": 0,
                        "affectedRows": 0,
                    }

            after = fingerprint(source_descriptor)
            verify_path_matches(path, after)
            _require_quiescent_snapshot(path)
            if before != after:
                raise AuthPreflightError(
                    "SQLite source changed while auth preflight was reading it"
                )
    except SafeSourceError as error:
        raise AuthPreflightError(str(error)) from error

    rows_by_type = Counter(row["type"] for row in rows)
    other_type_rows = sum(
        count
        for user_type, count in rows_by_type.items()
        if user_type not in _TYPE_LABELS
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "source": path.relative_to(REPOSITORY_ROOT).as_posix()
        if path.is_relative_to(REPOSITORY_ROOT)
        else "external-test-fixture",
        "sourceAccess": (
            "secure pre-open fd with strongest available nofollow flag; exact bytes "
            "read+SHA-256 on that fd; in-memory sqlite deserialize; PRAGMA "
            "query_only=ON; explicit read transaction; source path/fingerprint "
            "rechecked; WAL/journal sidecars refused"
        ),
        "sourceUnchanged": True,
        "cohort": {
            "definition": "users.type = 1",
            "studentRows": len(student_rows),
            "excludedNonStudentRows": len(rows) - len(student_rows),
            "rowsByKnownType": [
                {
                    "type": user_type,
                    "label": label,
                    "count": rows_by_type[user_type],
                }
                for user_type, label in sorted(_TYPE_LABELS.items())
                if rows_by_type[user_type]
            ],
            "otherTypeRows": other_type_rows,
            "explicitTestFlagAvailable": False,
            "explicitTestRows": None,
            "classificationNote": (
                "The legacy schema has no explicit test-account flag; no rows were "
                "classified from names, tokens, groups or identifiers."
            ),
        },
        "students": {
            "birthday": {
                key: birthday_counts[key]
                for key in (
                    "null",
                    "blank",
                    "validIsoDate",
                    "invalidIsoDate",
                    "futureDate",
                )
            },
            "surname": {
                key: surname_counts[key]
                for key in ("present", "emptyAfterTrim", "emptyLoginStem")
            },
            "tokenLengthBuckets": {
                key: length_counts[key]
                for key in ("0", "1-5", "6-7", "8-11", "12-15", "16-31", "32+")
            },
            "guessableTokenShapes": {
                key: shape_counts[key]
                for key in (
                    "shorterThan8",
                    "digitsOnly",
                    "singleRepeatedCharacter",
                    "commonPlaceholder",
                    "sameAsChatId",
                    "anyGuessableShape",
                )
            },
            "activation": {
                "blockedByFieldOrTokenCondition": field_blocked_rows,
                "eligibleByFieldAndTokenConditions": len(student_rows)
                - field_blocked_rows,
                "canonicalLoginCollisionRows": canonical_collision_rows,
                "blockedBeforeExplicitOverrides": activation_blocked_rows,
                "eligibleBeforeExplicitOverrides": len(student_rows)
                - activation_blocked_rows,
                "explicitOverridesApplied": 0,
                "canonicalEligibilityMeasured": True,
                "finalEligibilityKnown": False,
                "finalEligibilityUnknownReason": (
                    "Launch cohort exclusions and explicit collision overrides have "
                    "not been supplied."
                ),
            },
        },
        "loginCollisions": {
            "canonicalGeneratorAvailable": True,
            "studentUsernameAlgorithmVersion": STUDENT_USERNAME_ALGORITHM_VERSION,
            "canonicalStudentUsername": {
                **_collision_counts(canonical_login_keys),
                "interpretation": (
                    "Exact v1 transliterated-surname-DD candidates before any "
                    "explicit stored admin overrides; candidate values are not retained."
                ),
            },
            "legacyKvLogin": legacy_login_report,
        },
    }


def render_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def render_markdown(report: dict[str, Any]) -> str:
    cohort = report["cohort"]
    students = report["students"]
    birthday = students["birthday"]
    surname = students["surname"]
    activation = students["activation"]
    canonical_collisions = report["loginCollisions"]["canonicalStudentUsername"]
    legacy_collisions = report["loginCollisions"]["legacyKvLogin"]
    bucket_lines = "\n".join(
        f"- `{name}`: {count}" for name, count in students["tokenLengthBuckets"].items()
    )
    shape_lines = "\n".join(
        f"- `{name}`: {count}"
        for name, count in students["guessableTokenShapes"].items()
    )
    return f"""# Auth preflight

Источник: `{report["source"]}`; режим: `{report["sourceAccess"]}`.
Источник после чтения не изменился: **да**.

Отчёт содержит только агрегаты. Реальные фамилии, login candidates, tokens,
chat IDs и user IDs не сохранялись.

## Cohort

- Student (`users.type = 1`): {cohort["studentRows"]}
- Исключены как non-Student по явному `type`: {cohort["excludedNonStudentRows"]}
- Строки с неизвестным `users.type`, агрегировано без raw value: {cohort["otherTypeRows"]}
- Явного test-account flag нет; число доказуемо тестовых строк: **неизвестно**.

Строки не классифицировались по имени, token, group или identifier.

## Поля Student

- birthday valid ISO date: {birthday["validIsoDate"]}
- birthday NULL/blank: {birthday["null"] + birthday["blank"]}
- birthday invalid/future: {birthday["invalidIsoDate"] + birthday["futureDate"]}
- surname empty after trim: {surname["emptyAfterTrim"]}
- surname present, but canonical login stem empty: {surname["emptyLoginStem"]}
- проходят field/token checks: {activation["eligibleByFieldAndTokenConditions"]}
- имеют field/token blocker: {activation["blockedByFieldOrTokenCondition"]}
- входят в collision канонического login v{report["loginCollisions"]["studentUsernameAlgorithmVersion"]}: {activation["canonicalLoginCollisionRows"]}
- можно активировать до явных admin overrides: {activation["eligibleBeforeExplicitOverrides"]}

Это точный dry-run канонического генератора для выбранного `users.type = 1`
cohort до явных admin overrides. Явного признака test-account в legacy-схеме нет;
поэтому test/unknown exclusions всё равно должны быть утверждены перед apply.

### Длины token

{bucket_lines}

### Консервативные guessable-shape сигналы

{shape_lines}

Категории могут пересекаться; `anyGuessableShape` считает уникальные Student rows.

## Login collisions

- Canonical Student username algorithm version:
  {report["loginCollisions"]["studentUsernameAlgorithmVersion"]}.
- Точный dry-run `transliterated-surname-DD`: groups
  {canonical_collisions["collisionGroups"]}, affected rows
  {canonical_collisions["affectedRows"]}. Сами login candidates не сохранялись.
- Legacy `kv_logins`: rows {legacy_collisions["studentRows"]}, blank
  {legacy_collisions["nullOrBlank"]}, normalized collision groups
  {legacy_collisions["collisionGroups"]}, affected rows
  {legacy_collisions["affectedRows"]}.

До активации Phase 1 нужно явно разрешить каждую collision сохранённым уникальным
override и утвердить launch cohort. Автоматические row-ID suffixes запрещены.
"""


def _atomic_write(path: Path, content: str) -> None:
    try:
        atomic_write_text(path, content)
    except AtomicReportWriteError as error:
        raise AuthPreflightError(str(error)) from error


def write_reports(database_path: Path = DEFAULT_DATABASE) -> None:
    report = analyze_database(database_path)
    _atomic_write(JSON_REPORT, render_json(report))
    _atomic_write(MARKDOWN_REPORT, render_markdown(report))


def validate_reports(database_path: Path = DEFAULT_DATABASE) -> None:
    report = analyze_database(database_path)
    expected = {
        JSON_REPORT: render_json(report),
        MARKDOWN_REPORT: render_markdown(report),
    }
    for path, content in expected.items():
        try:
            committed = path.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise AuthPreflightError(
                f"Missing auth preflight report: {path}; run "
                "`make pwa-auth-preflight-update`"
            ) from error
        if committed != content:
            raise AuthPreflightError(
                "Auth preflight is stale; inspect the aggregate diff and run "
                "`make pwa-auth-preflight-update` (or "
                "`python -m vmshpwa.scripts.auth_preflight write`)"
            )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "write"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.command == "write":
            write_reports()
            print("Wrote aggregate auth preflight reports")
        else:
            validate_reports()
            print("Verified aggregate auth preflight reports")
    except (AuthPreflightError, sqlite3.Error) as error:
        print(f"auth preflight error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
