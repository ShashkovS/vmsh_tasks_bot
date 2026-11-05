"""Read-only Phase-6 inventory for legacy written reactions.

Historical ``reactions`` rows point to a result, not to a concrete review
round.  The owner decision in
``vmshpwa/dev/development-plan/20-implementation-questions.md`` forbids
guessing that missing relationship.  This command therefore reports exact
aggregate/malformed/duplicate counts and never mutates the database.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import quote

from vmshpwa.scripts.report_io import atomic_write_text


REPORT_SCHEMA_VERSION = 1
WRITTEN_REACTION_TYPES = (0, 100)


def _scalar(connection: sqlite3.Connection, query: str, parameters=()) -> int:
    return int(connection.execute(query, parameters).fetchone()[0])


def _has_table(connection: sqlite3.Connection, name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (name,),
        ).fetchone()
        is not None
    )


def build_report(connection: sqlite3.Connection) -> dict[str, object]:
    """Return privacy-safe counts; never select names, contacts or tokens."""

    by_type = {
        str(row["reaction_type_id"]): int(row["row_count"])
        for row in connection.execute(
            "SELECT reaction_type_id, count(*) AS row_count FROM reactions "
            "GROUP BY reaction_type_id ORDER BY reaction_type_id"
        )
    }
    written_filter = "reaction_type_id IN (0, 100)"
    written_rows = _scalar(
        connection, f"SELECT count(*) FROM reactions WHERE {written_filter}"
    )
    duplicate_groups = _scalar(
        connection,
        "SELECT count(*) FROM ("
        "SELECT reaction_type_id, result_id FROM reactions "
        "WHERE reaction_type_id IN (0, 100) AND result_id IS NOT NULL "
        "GROUP BY reaction_type_id, result_id HAVING count(*) > 1)",
    )
    duplicate_rows = _scalar(
        connection,
        "SELECT coalesce(sum(row_count), 0) FROM ("
        "SELECT count(*) AS row_count FROM reactions "
        "WHERE reaction_type_id IN (0, 100) AND result_id IS NOT NULL "
        "GROUP BY reaction_type_id, result_id HAVING count(*) > 1)",
    )
    missing_result_id = _scalar(
        connection,
        "SELECT count(*) FROM reactions WHERE reaction_type_id IN (0, 100) "
        "AND result_id IS NULL",
    )
    missing_result_row = _scalar(
        connection,
        "SELECT count(*) FROM reactions AS reaction "
        "LEFT JOIN results AS result ON result.id = reaction.result_id "
        "WHERE reaction.reaction_type_id IN (0, 100) AND result.id IS NULL",
    )
    invalid_enum = _scalar(
        connection,
        "SELECT count(*) FROM reactions AS reaction "
        "LEFT JOIN reaction_enum AS enum "
        "ON enum.reaction_id = reaction.reaction_id "
        "AND enum.reaction_type_id = reaction.reaction_type_id "
        "WHERE reaction.reaction_type_id IN (0, 100) "
        "AND enum.reaction_id IS NULL",
    )
    missing_actor = _scalar(
        connection,
        "SELECT count(*) FROM reactions AS reaction "
        "JOIN results AS result ON result.id = reaction.result_id "
        "LEFT JOIN users AS actor ON actor.id = CASE reaction.reaction_type_id "
        "WHEN 0 THEN result.student_id WHEN 100 THEN result.teacher_id END "
        "WHERE reaction.reaction_type_id IN (0, 100) AND actor.id IS NULL",
    )

    review_table_available = _has_table(connection, "submission_reviews")
    mapping = {
        "reviewTableAvailable": review_table_available,
        "mappedRows": 0,
        "unmappedRows": written_rows,
        "ambiguousRows": 0,
        "eligibleRows": 0,
        "occupiedTargetRows": 0,
        "actorMismatchRows": 0,
    }
    if review_table_available:
        mapped = _scalar(
            connection,
            "SELECT count(*) FROM reactions AS reaction WHERE "
            "reaction.reaction_type_id IN (0, 100) AND "
            "(SELECT count(*) FROM submission_reviews AS review "
            "WHERE review.result_id = reaction.result_id) = 1",
        )
        ambiguous = _scalar(
            connection,
            "SELECT count(*) FROM reactions AS reaction WHERE "
            "reaction.reaction_type_id IN (0, 100) AND "
            "(SELECT count(*) FROM submission_reviews AS review "
            "WHERE review.result_id = reaction.result_id) > 1",
        )
        mapping.update(
            {
                "mappedRows": mapped,
                "unmappedRows": written_rows - mapped - ambiguous,
                "ambiguousRows": ambiguous,
            }
        )
        state_tables_available = _has_table(
            connection, "submission_review_internal_reactions"
        ) and _has_table(connection, "submission_review_student_reactions")
        if state_tables_available:
            actor_match = (
                "((reaction.reaction_type_id = 100 "
                "AND review.reviewer_user_id = result.teacher_id) OR "
                "(reaction.reaction_type_id = 0 "
                "AND thread.student_user_id = result.student_id))"
            )
            mapped_join = (
                " FROM reactions AS reaction "
                "JOIN results AS result ON result.id = reaction.result_id "
                "JOIN submission_reviews AS review ON review.result_id = result.id "
                "JOIN submission_threads AS thread ON thread.id = review.thread_id "
                "LEFT JOIN reaction_enum AS enum ON enum.reaction_id = reaction.reaction_id "
                "AND enum.reaction_type_id = reaction.reaction_type_id "
                "LEFT JOIN submission_review_internal_reactions AS teacher_state "
                "ON teacher_state.review_id = review.id AND reaction.reaction_type_id = 100 "
                "LEFT JOIN submission_review_student_reactions AS student_state "
                "ON student_state.review_id = review.id AND reaction.reaction_type_id = 0 "
                "WHERE reaction.reaction_type_id IN (0, 100) "
                "AND (SELECT count(*) FROM submission_reviews AS candidate "
                "WHERE candidate.result_id = result.id) = 1 "
            )
            occupied = _scalar(
                connection,
                "SELECT count(*)"
                + mapped_join
                + "AND (teacher_state.review_id IS NOT NULL "
                "OR student_state.review_id IS NOT NULL)",
            )
            actor_mismatch = _scalar(
                connection,
                "SELECT count(*)" + mapped_join + f"AND NOT {actor_match}",
            )
            eligible = _scalar(
                connection,
                "SELECT count(*)"
                + mapped_join
                + f"AND {actor_match} AND enum.reaction_id IS NOT NULL "
                "AND teacher_state.review_id IS NULL "
                "AND student_state.review_id IS NULL",
            )
            mapping.update(
                {
                    "eligibleRows": eligible,
                    "occupiedTargetRows": occupied,
                    "actorMismatchRows": actor_mismatch,
                }
            )

    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "scope": "aggregate-only",
        "legacy": {
            "rowsByReactionType": by_type,
            "writtenRows": written_rows,
            "writtenDistinctResultIds": _scalar(
                connection,
                "SELECT count(DISTINCT result_id) FROM reactions "
                "WHERE reaction_type_id IN (0, 100) AND result_id IS NOT NULL",
            ),
            "duplicateWrittenTargets": duplicate_groups,
            "rowsInDuplicateWrittenTargets": duplicate_rows,
            "missingResultIdRows": missing_result_id,
            "missingResultRows": missing_result_row,
            "invalidReactionEnumRows": invalid_enum,
            "missingActorRows": missing_actor,
        },
        "reviewMapping": mapping,
        "decision": {
            "historicalReviewRelationshipMayBeGuessed": False,
            "databaseWasModified": False,
            "automaticBackfillPerformed": False,
        },
        "privacy": {
            "containsNames": False,
            "containsContacts": False,
            "containsTokens": False,
            "containsLegacyRowIds": False,
        },
    }


def build_owner_details(connection: sqlite3.Connection) -> dict[str, object]:
    """Return IDs only for local manual diagnosis of malformed/duplicate rows."""

    duplicates = [
        {
            "reactionTypeId": int(row["reaction_type_id"]),
            "resultId": int(row["result_id"]),
            "reactionRowIds": [
                int(value) for value in str(row["reaction_row_ids"]).split(",") if value
            ],
        }
        for row in connection.execute(
            "SELECT reaction_type_id, result_id, group_concat(id) AS reaction_row_ids "
            "FROM reactions WHERE reaction_type_id IN (0, 100) "
            "AND result_id IS NOT NULL GROUP BY reaction_type_id, result_id "
            "HAVING count(*) > 1 ORDER BY reaction_type_id, result_id"
        )
    ]
    malformed = [
        int(row["id"])
        for row in connection.execute(
            "SELECT reaction.id FROM reactions AS reaction "
            "LEFT JOIN results AS result ON result.id = reaction.result_id "
            "LEFT JOIN reaction_enum AS enum "
            "ON enum.reaction_id = reaction.reaction_id "
            "AND enum.reaction_type_id = reaction.reaction_type_id "
            "WHERE reaction.reaction_type_id IN (0, 100) "
            "AND (result.id IS NULL OR enum.reaction_id IS NULL) "
            "ORDER BY reaction.id"
        )
    ]
    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "ownerOnly": True,
        "duplicateWrittenTargets": duplicates,
        "malformedWrittenReactionRowIds": malformed,
        "containsNamesContactsOrTokens": False,
    }


def _open_read_only(path: Path) -> sqlite3.Connection:
    database = Path(path).resolve(strict=True)
    connection = sqlite3.connect(
        f"file:{quote(str(database))}?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--aggregate-output", type=Path)
    parser.add_argument("--owner-details-output", type=Path)
    arguments = parser.parse_args(argv)

    with _open_read_only(arguments.database) as connection:
        aggregate = (
            json.dumps(
                build_report(connection), ensure_ascii=False, indent=2, sort_keys=True
            )
            + "\n"
        )
        if arguments.aggregate_output is None:
            print(aggregate, end="")
        else:
            atomic_write_text(arguments.aggregate_output, aggregate)
        if arguments.owner_details_output is not None:
            details = (
                json.dumps(
                    build_owner_details(connection),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            atomic_write_text(arguments.owner_details_output, details, mode=0o600)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
