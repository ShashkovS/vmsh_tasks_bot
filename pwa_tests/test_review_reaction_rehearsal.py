"""Read-only legacy reaction inventory and duplicate-report tests."""

from __future__ import annotations

import json
import sqlite3

from vmshpwa.scripts.review_reaction_rehearsal import (
    build_owner_details,
    build_report,
    main,
)


def _legacy_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE users (id INTEGER PRIMARY KEY);
        CREATE TABLE results (
            id INTEGER PRIMARY KEY,
            student_id INTEGER,
            teacher_id INTEGER
        );
        CREATE TABLE reaction_enum (
            reaction_id INTEGER,
            reaction_type_id INTEGER,
            PRIMARY KEY (reaction_id, reaction_type_id)
        );
        CREATE TABLE reactions (
            id INTEGER PRIMARY KEY,
            result_id INTEGER,
            zoom_conversation_id INTEGER,
            reaction_id INTEGER,
            reaction_type_id INTEGER
        );
        INSERT INTO users VALUES (1), (10);
        INSERT INTO results VALUES (101, 1, 10), (102, 1, 10);
        INSERT INTO reaction_enum VALUES (0, 0), (2, 0), (100, 100);
        INSERT INTO reactions VALUES
            (1, 101, NULL, 0, 0),
            (2, 101, NULL, 2, 0),
            (3, 102, NULL, 100, 100),
            (4, NULL, NULL, 0, 0),
            (5, 999, NULL, 100, 100),
            (6, 102, NULL, 999, 100),
            (7, NULL, 501, 200, 200);
        """
    )
    return connection


def _add_review_tables(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE submission_threads (
            id INTEGER PRIMARY KEY,
            student_user_id INTEGER NOT NULL
        );
        CREATE TABLE submission_reviews (
            id INTEGER PRIMARY KEY,
            result_id INTEGER,
            thread_id INTEGER NOT NULL,
            reviewer_user_id INTEGER NOT NULL
        );
        CREATE TABLE submission_review_internal_reactions (
            review_id INTEGER PRIMARY KEY
        );
        CREATE TABLE submission_review_student_reactions (
            review_id INTEGER PRIMARY KEY
        );
        INSERT INTO submission_threads VALUES (201, 1), (202, 1);
        INSERT INTO submission_reviews VALUES (301, 101, 201, 10);
        INSERT INTO submission_reviews VALUES (302, 102, 202, 999);
        INSERT INTO submission_review_internal_reactions VALUES (302);
        """
    )


def test_report_is_aggregate_only_when_no_review_target_exists() -> None:
    connection = _legacy_connection()

    report = build_report(connection)

    assert report["legacy"] == {
        "rowsByReactionType": {"0": 3, "100": 3, "200": 1},
        "writtenRows": 6,
        "writtenDistinctResultIds": 3,
        "duplicateWrittenTargets": 2,
        "rowsInDuplicateWrittenTargets": 4,
        "missingResultIdRows": 1,
        "missingResultRows": 2,
        "invalidReactionEnumRows": 1,
        "missingActorRows": 0,
    }
    assert report["reviewMapping"] == {
        "reviewTableAvailable": False,
        "mappedRows": 0,
        "unmappedRows": 6,
        "ambiguousRows": 0,
        "eligibleRows": 0,
        "occupiedTargetRows": 0,
        "actorMismatchRows": 0,
    }
    assert report["decision"]["databaseWasModified"] is False


def test_report_separates_eligible_occupied_and_actor_mismatch_rows() -> None:
    connection = _legacy_connection()
    _add_review_tables(connection)

    report = build_report(connection)

    assert report["reviewMapping"] == {
        "reviewTableAvailable": True,
        "mappedRows": 4,
        "unmappedRows": 2,
        "ambiguousRows": 0,
        "eligibleRows": 2,
        "occupiedTargetRows": 2,
        "actorMismatchRows": 2,
    }


def test_owner_details_contain_only_ids_for_duplicates_and_malformed_rows() -> None:
    connection = _legacy_connection()

    details = build_owner_details(connection)

    assert details["duplicateWrittenTargets"] == [
        {"reactionTypeId": 0, "resultId": 101, "reactionRowIds": [1, 2]},
        {"reactionTypeId": 100, "resultId": 102, "reactionRowIds": [3, 6]},
    ]
    assert details["malformedWrittenReactionRowIds"] == [4, 5, 6]
    assert all(
        not isinstance(value, str)
        for item in details["duplicateWrittenTargets"]
        for value in item.values()
    )


def test_cli_keeps_source_unchanged_and_owner_report_private(tmp_path) -> None:
    database = tmp_path / "legacy.sqlite3"
    source = _legacy_connection()
    target = sqlite3.connect(database)
    source.backup(target)
    target.close()
    source.close()
    before = database.read_bytes()
    aggregate = tmp_path / "aggregate.json"
    owner = tmp_path / "owner.json"

    assert (
        main(
            [
                "--database",
                str(database),
                "--aggregate-output",
                str(aggregate),
                "--owner-details-output",
                str(owner),
            ]
        )
        == 0
    )

    assert database.read_bytes() == before
    assert aggregate.stat().st_mode & 0o777 == 0o644
    assert owner.stat().st_mode & 0o777 == 0o600
    assert json.loads(aggregate.read_text())["scope"] == "aggregate-only"
