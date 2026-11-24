"""Key identical uploads by compiler generation while retaining terminal history.

See vmshpwa/docs/content-recovery-20261004.md and upload-generation regressions.
"""

import re

from yoyo import step

__depends__ = {"0112.scheduled_publication_lifecycle"}
# Own the atomic parent-table rebuild, as in migration 0112.
__transactional__ = False

OLD_CHECK = "unique (source_id, source_sha256)"
NEW_CHECK = "unique (source_id, source_sha256, parser_version)"


def _identifier(name):
    return '"' + name.replace('"', '""') + '"'


def _rebuild(connection, old_check, new_check):
    if connection.in_transaction:
        raise RuntimeError("Revision migration requires its own transaction")
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
            "WHERE sql IS NOT NULL AND (tbl_name='content_revisions' "
            "OR lower(sql) LIKE '%content_revisions%') ORDER BY type, name"
        ).fetchall()
        table_sql = next(
            sql
            for kind, name, _table, sql in objects
            if kind == "table" and name == "content_revisions"
        )
        if table_sql.count(old_check) != 1:
            raise RuntimeError("Unexpected revision upload uniqueness constraint")
        columns = [
            row[1]
            for row in connection.execute("PRAGMA table_xinfo(content_revisions)")
            if row[6] == 0
        ]
        dependents = [row for row in objects if row[0] in {"index", "trigger", "view"}]
        # External publication/material triggers also reference this table. Restore their
        # exact definitions after the temporary absence of the old table.
        for kind, name, _table, _sql in dependents:
            connection.execute(f"DROP {kind} {_identifier(name)}")
        new_sql, replacements = re.subn(
            r'\ACREATE TABLE\s+(?:"content_revisions"|content_revisions)(?=\s*\()',
            "CREATE TABLE content_revisions_0113",
            table_sql,
        )
        if replacements != 1:
            raise RuntimeError("Unexpected revision table declaration")
        new_sql = new_sql.replace(old_check, new_check)
        connection.execute(new_sql)
        names = ", ".join(map(_identifier, columns))
        connection.execute(
            f"INSERT INTO content_revisions_0113 ({names}) "
            f"SELECT {names} FROM content_revisions"
        )
        connection.execute("DROP TABLE content_revisions")
        connection.execute(
            "ALTER TABLE content_revisions_0113 RENAME TO content_revisions"
        )
        for _kind, _name, _table, sql in dependents:
            connection.execute(sql)
        if (
            sorted(connection.execute("PRAGMA foreign_key_check").fetchall())
            != foreign_key_errors
        ):
            raise RuntimeError("Revision migration failed foreign key validation")
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.execute(f"PRAGMA foreign_keys={int(foreign_keys)}")


def apply(connection):
    _rebuild(connection, OLD_CHECK, NEW_CHECK)


def rollback(connection):
    if connection.execute(
        "SELECT 1 FROM content_revisions GROUP BY source_id, source_sha256 "
        "HAVING count(*) > 1 LIMIT 1"
    ).fetchone() is not None:
        raise RuntimeError("Retain migration 0113: compiler generation history exists")
    _rebuild(connection, NEW_CHECK, OLD_CHECK)


steps = [step(apply, rollback)]
