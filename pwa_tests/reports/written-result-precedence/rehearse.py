"""Rehearse 0110 on a new copy; never migrate the supplied snapshot.

See vmshpwa/docs/written-result-precedence.md. Reports contain counts/digests,
and only the three incident records expressly named by the owner.
"""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

import yoyo

from db_methods.pwa.migrations import MIGRATIONS_ROOT
from db_methods.pwa.performance_guard import check_database_performance


MIGRATION = "0110.pwa_written_result_precedence"


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def fingerprints(c):
    tables = [
        r[0]
        for r in c.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%yoyo%' "
            "AND name NOT IN ('live_mark_cells','live_mark_clock') ORDER BY name"
        )
    ]
    report = {}
    for table in tables:
        fields = ",".join(
            quote(r[1]) for r in c.execute(f"PRAGMA table_info({quote(table)})")
        )
        digest = hashlib.sha256()
        count = 0
        for row in c.execute(f"SELECT {fields} FROM {quote(table)} ORDER BY {fields}"):
            digest.update(repr(tuple(row)).encode())
            digest.update(b"\n")
            count += 1
        report[table] = dict(count=count, sha256=digest.hexdigest())
    return report


def current(c):
    return {
        (r[0], r[1]): (r[2], r[3], r[4])
        for r in c.execute(
            """SELECT student_id,problem_id,id,verdict,val FROM (
        SELECT r.*,v.val,row_number() OVER(PARTITION BY student_id,problem_id
        ORDER BY v.val DESC,r.id DESC) priority
        FROM effective_results r JOIN verdicts v ON v.id=r.verdict) WHERE priority=1"""
        )
    }


def incident_cases(c):
    cases = []
    for name, surname, prob, item in [
        ("Юстина", "Баймиева", 10, "б"),
        ("Назар", "Демьяненков", 10, "а"),
        ("Назар", "Демьяненков", 11, "а"),
    ]:
        matches = c.execute(
            """SELECT u.id,p.id FROM users u CROSS JOIN problems p JOIN groups g
            ON g.group_id=p.group_id WHERE u.name=? AND u.surname=?
            AND p.lesson=2 AND p.prob=? AND p.item=? AND g.short_code='п'""",
            (name, surname, prob, item),
        ).fetchall()
        assert len(matches) == 1, (name, surname, prob, item, len(matches))
        uid, pid = matches[0]
        history = c.execute(
            "SELECT id,verdict,res_type,ts FROM results WHERE student_id=? AND problem_id=? ORDER BY id",
            (uid, pid),
        ).fetchall()
        written = [r for r in history if r[2] == 2][-1]
        old_manual = [r for r in history if r[2] in (3, 4) and r[0] < written[0]][-1]
        new_manual = [r for r in history if r[2] in (3, 4) and r[0] > written[0]][-1]
        assert old_manual[1] == -1 and written[1] == 17 and new_manual[1] == 18
        cases.append(
            dict(
                student=f"{surname} {name}",
                problem=f"2п.{prob}{item}",
                state="already-repaired-through-zoom",
                oldManualId=old_manual[0],
                writtenId=written[0],
                laterManualId=new_manual[0],
                laterManualAt=new_manual[3],
            )
        )
    return cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--copy", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--skip-incidents", action="store_true", help="For the independent TLF database"
    )
    args = parser.parse_args()
    source, target = args.snapshot.resolve(strict=True), args.copy.resolve()
    if target.exists() or target == source:
        raise ValueError("Rehearsal requires a new, separate copy")
    target.parent.mkdir(parents=True, exist_ok=True)
    source_hash = hashlib.file_digest(source.open("rb"), "sha256").hexdigest()
    with (
        sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as c,
        sqlite3.connect(target) as t,
    ):
        c.backup(t)
    with sqlite3.connect(target) as c:
        before = fingerprints(c)
        keys_before = c.execute("PRAGMA foreign_key_check").fetchall()
        pointers = c.execute(
            "SELECT student_id,problem_id,result_id FROM live_mark_cells WHERE result_id IS NOT NULL ORDER BY 1,2"
        ).fetchall()
        statuses_before = current(c)
        cases = [] if args.skip_incidents else incident_cases(c)
    migration = yoyo.read_migrations(str(MIGRATIONS_ROOT)).filter(
        lambda m: m.id == MIGRATION
    )

    def migrate(up):
        with yoyo.get_backend(f"sqlite:///{target}") as backend:
            with backend.lock():
                if up:
                    backend.apply_migrations(backend.to_apply(migration))
                else:
                    backend.rollback_migrations(backend.to_rollback(migration))
        with sqlite3.connect(target) as c:
            assert c.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
            assert c.execute("PRAGMA foreign_key_check").fetchall() == keys_before
            assert fingerprints(c) == before
            assert (
                c.execute(
                    "SELECT student_id,problem_id,result_id FROM live_mark_cells WHERE result_id IS NOT NULL ORDER BY 1,2"
                ).fetchall()
                == pointers
            )
        return check_database_performance(target)

    up = migrate(True)
    with sqlite3.connect(target) as c:
        statuses_after = current(c)
    down = migrate(False)
    with sqlite3.connect(target) as c:
        assert current(c) == statuses_before
    again = migrate(True)
    with sqlite3.connect(target) as c:
        assert current(c) == statuses_after
    assert hashlib.file_digest(source.open("rb"), "sha256").hexdigest() == source_hash
    changed = [
        key
        for key in statuses_before.keys() | statuses_after.keys()
        if statuses_before.get(key) != statuses_after.get(key)
    ]
    repaired = [
        key
        for key in changed
        if statuses_before.get(key, (0, 0, 0))[2] < 0.8
        and statuses_after.get(key, (0, 0, 0))[2] >= 0.8
    ]
    args.report.write_text(
        json.dumps(
            dict(
                migration=MIGRATION,
                sourceSha256=source_hash,
                sourceUnchanged=True,
                upDownUp=True,
                integrity="ok",
                existingForeignKeyViolations=len(keys_before),
                newForeignKeyViolations=0,
                unchangedProductTables=len(before),
                resultsCount=before["results"]["count"],
                retainedManualPointers=len(pointers),
                changedCurrentResults=len(changed),
                repairedAcceptedResults=len(repaired),
                incidents=cases,
                performance=dict(up=up, down=down, again=again),
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            dict(
                unchangedTables=len(before),
                changed=len(changed),
                repaired=len(repaired),
            )
        )
    )


if __name__ == "__main__":
    main()
