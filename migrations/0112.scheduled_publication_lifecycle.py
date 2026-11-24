"""Preserve schedule provenance when publications become terminal.

See vmshpwa/docs/content-recovery-20261004.md and test_runtime_schema.py.
"""

import re

from yoyo import step

__depends__ = {"0111.current_schema"}
# PRAGMA foreign_keys must change outside a transaction. The single callback
# owns the atomic rebuild; yoyo still owns the migration lock/bookkeeping.
__transactional__ = False

OLD_CHECK = "check (activated_from_schedule_id is null or state = 'published')"
NEW_CHECK = (
    "check (activated_from_schedule_id is null or "
    "(state in ('published', 'superseded', 'hidden') and published_at is not null))"
)


def _identifier(name):
    return '"' + name.replace('"', '""') + '"'


def _rebuild(connection, old_check, new_check):
    if connection.in_transaction:
        raise RuntimeError("Publication migration requires its own transaction")
    foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
    connection.execute("PRAGMA foreign_keys=OFF")
    try:
        connection.execute("BEGIN IMMEDIATE")
        # Production retains known legacy FK defects outside this component.
        # Require the exact same violations, so unrelated history is preserved
        # and this rebuild cannot introduce a new broken reference.
        foreign_key_errors = sorted(
            connection.execute("PRAGMA foreign_key_check").fetchall()
        )
        objects = connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_schema "
            "WHERE sql IS NOT NULL AND (tbl_name='lesson_publications' "
            "OR lower(sql) LIKE '%lesson_publications%') ORDER BY type, name"
        ).fetchall()
        table_sql = next(
            sql
            for kind, name, _table, sql in objects
            if kind == "table" and name == "lesson_publications"
        )
        if table_sql.count(old_check) != 1:
            raise RuntimeError("Unexpected publication lifecycle CHECK")
        columns = [
            row[1]
            for row in connection.execute("PRAGMA table_xinfo(lesson_publications)")
            if row[6] == 0
        ]
        dependents = [row for row in objects if row[0] in {"index", "trigger", "view"}]
        # External reveal triggers also reference this table. Restore their
        # exact definitions after the temporary absence of the old table.
        for kind, name, _table, _sql in dependents:
            connection.execute(f"DROP {kind} {_identifier(name)}")
        new_sql, replacements = re.subn(
            r'\ACREATE TABLE\s+(?:"lesson_publications"|lesson_publications)(?=\s*\()',
            "CREATE TABLE lesson_publications_0112",
            table_sql,
        )
        if replacements != 1:
            raise RuntimeError("Unexpected publication table declaration")
        new_sql = new_sql.replace(old_check, new_check)
        connection.execute(new_sql)
        names = ", ".join(map(_identifier, columns))
        connection.execute(
            f"INSERT INTO lesson_publications_0112 ({names}) "
            f"SELECT {names} FROM lesson_publications"
        )
        connection.execute("DROP TABLE lesson_publications")
        connection.execute(
            "ALTER TABLE lesson_publications_0112 RENAME TO lesson_publications"
        )
        for _kind, _name, _table, sql in dependents:
            connection.execute(sql)
        if (
            sorted(connection.execute("PRAGMA foreign_key_check").fetchall())
            != foreign_key_errors
        ):
            raise RuntimeError("Publication migration failed foreign key validation")
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.execute(f"PRAGMA foreign_keys={int(foreign_keys)}")


def apply(connection):
    _rebuild(connection, OLD_CHECK, NEW_CHECK)


def rollback(connection):
    # Never erase valid terminal history to satisfy the former broken CHECK.
    if (
        connection.execute(
            "SELECT 1 FROM lesson_publications WHERE activated_from_schedule_id IS NOT NULL "
            "AND state <> 'published' LIMIT 1"
        ).fetchone()
        is not None
    ):
        raise RuntimeError(
            "Retain migration 0112: terminal schedule publications exist"
        )
    _rebuild(connection, NEW_CHECK, OLD_CHECK)


steps = [step(apply, rollback)]
