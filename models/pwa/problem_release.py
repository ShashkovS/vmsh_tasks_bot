"""Whole-task release policy; see vmshpwa/docs/problem-release.md."""

from __future__ import annotations

from datetime import UTC, datetime

from db_methods.pwa import problem_release as storage
from models.pwa.content import format_utc_timestamp


class ProblemReleaseNotFound(ValueError):
    pass


class ProblemReleaseConflict(ValueError):
    pass


def task_states(rows, *, new_tasks_open: bool) -> dict[int, bool]:
    groups: dict[int, list] = {}
    for row in rows:
        groups.setdefault(int(row["source_ordinal"]), []).append(row)
    states = {}
    for ordinal, members in groups.items():
        known = [
            bool(member["is_open"])
            for member in members
            if member["is_open"] is not None
        ]
        states[ordinal] = all(known) if known else new_tasks_open
    return states


def reconcile_problem_release(
    connection,
    *,
    group_lesson_id: int,
    revision_id: int,
    actor_user_id: int,
    timestamp: str,
) -> None:
    """Called inside the publication transaction, before replacing its old slot."""
    rows = storage.revision_rows(connection, group_lesson_id, revision_id)
    states = task_states(
        rows, new_tasks_open=not storage.has_closed_tasks(connection, group_lesson_id)
    )
    after = {int(row["problem_id"]): states[int(row["source_ordinal"])] for row in rows}
    before = {
        int(row["problem_id"]): bool(row["is_open"])
        for row in rows
        if row["is_open"] is not None
    }
    storage.save_states(connection, group_lesson_id, after)
    if before != after:
        storage.record_change(
            connection,
            group_lesson_id=group_lesson_id,
            revision_id=revision_id,
            before=before,
            after=after,
            actor_user_id=actor_user_id,
            request_id="publication",
            timestamp=timestamp,
        )


def release_snapshot(connection, *, group_lesson_id: int, revision_id: int) -> dict:
    rows = storage.revision_rows(connection, group_lesson_id, revision_id)
    states = task_states(
        rows, new_tasks_open=not storage.has_closed_tasks(connection, group_lesson_id)
    )
    current = storage.current_condition(connection, group_lesson_id)
    return {
        "version": storage.version(connection, group_lesson_id),
        "editable": current is None or int(current["revision_id"]) == revision_id,
        "problems": [
            {"sourceOrdinal": ordinal, "isOpen": is_open}
            for ordinal, is_open in states.items()
        ],
    }


def filter_released_document(
    connection, *, group_lesson_id: int, revision_id: int, document: dict
) -> dict:
    current = storage.current_condition(connection, group_lesson_id)
    if current is None:
        return {**document, "problems": []}
    condition_rows = storage.revision_rows(
        connection, group_lesson_id, int(current["revision_id"])
    )
    states = task_states(condition_rows, new_tasks_open=True)
    if all(states.values()):
        return document
    visible_ids = {
        int(row["problem_id"])
        for row in condition_rows
        if states[int(row["source_ordinal"])]
    }
    # Material ordinals may differ. Match hints/solutions by stable problem ID.
    material_rows = storage.material_rows(connection, revision_id)
    material_groups: dict[int, set[int]] = {}
    for row in material_rows:
        material_groups.setdefault(int(row["source_ordinal"]), set()).add(
            int(row["problem_id"])
        )
    ordinals = {
        ordinal
        for ordinal, ids in material_groups.items()
        if ids and ids <= visible_ids
    }
    return {
        **document,
        "problems": [
            problem
            for problem in document["problems"]
            if problem["ordinal"] in ordinals
        ],
    }


class ProblemReleaseService:
    def __init__(self, factory):
        self._factory = factory

    @staticmethod
    def _revision(connection, group_lesson_id: int, revision_public_id: str) -> int:
        row = storage.ready_condition(connection, group_lesson_id, revision_public_id)
        if row is None:
            raise ProblemReleaseNotFound("ready condition revision not found")
        return int(row["id"])

    async def get(self, group_lesson_id: int, revision_public_id: str) -> dict:
        def read(connection):
            revision_id = self._revision(
                connection, group_lesson_id, revision_public_id
            )
            return release_snapshot(
                connection, group_lesson_id=group_lesson_id, revision_id=revision_id
            )

        return await self._factory.run_read_async(read)

    async def change(
        self,
        *,
        group_lesson_id: int,
        revision_public_id: str,
        expected_version: int,
        changes: dict[int, bool],
        actor_user_id: int,
        request_id: str,
    ) -> dict:
        def write(connection):
            revision_id = self._revision(
                connection, group_lesson_id, revision_public_id
            )
            snapshot = release_snapshot(
                connection, group_lesson_id=group_lesson_id, revision_id=revision_id
            )
            if not snapshot["editable"] or snapshot["version"] != expected_version:
                raise ProblemReleaseConflict(
                    "release state or published condition changed"
                )
            states = {
                item["sourceOrdinal"]: item["isOpen"] for item in snapshot["problems"]
            }
            if not changes or not changes.keys() <= states.keys():
                raise ProblemReleaseNotFound("task is not in the checked condition")
            rows = storage.revision_rows(connection, group_lesson_id, revision_id)
            before = {
                int(row["problem_id"]): states[int(row["source_ordinal"])]
                for row in rows
            }
            states.update(changes)
            after = {
                int(row["problem_id"]): states[int(row["source_ordinal"])]
                for row in rows
            }
            # Materialize all rows, including unchanged On tasks, for revision inheritance.
            storage.save_states(connection, group_lesson_id, after)
            if before != after:
                storage.record_change(
                    connection,
                    group_lesson_id=group_lesson_id,
                    revision_id=revision_id,
                    before=before,
                    after=after,
                    actor_user_id=actor_user_id,
                    request_id=request_id,
                    timestamp=format_utc_timestamp(datetime.now(UTC)),
                )
            return release_snapshot(
                connection, group_lesson_id=group_lesson_id, revision_id=revision_id
            )

        return await self._factory.run_write_async(write)
