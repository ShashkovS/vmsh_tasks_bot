"""Isolated live-marking browser personas/events; vmshpwa/docs/live-marking.md."""

import sqlite3

from vmshpwa.scripts.runtime_guard import require_pwa_profile_environment
from vmshpwa.scripts.seed_e2e_oral import _require_e2e_target, _seed, TIMESTAMP
from db_methods.pwa.classroom_assignments import insert_plan, confirm_plan

TARGETS = (("live-chromium", 931), ("live-webkit", 932), ("live-firefox", 933))


def seed(config):
    path = _require_e2e_target(config)
    with sqlite3.connect(path) as c:
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        _seed(c, TARGETS)
        for project, lesson_id in TARGETS:
            fixture_id = 19000 + lesson_id
            if c.execute("SELECT 1 FROM users WHERE id=?", (fixture_id,)).fetchone():
                continue
            c.execute(
                """INSERT INTO users(id,type,name,surname)
                SELECT ?,type,'Преподаватель',? FROM users WHERE id=201""",
                (fixture_id, project),
            )
            c.execute(
                """INSERT INTO auth_accounts(id,audience,username,username_normalized,provisioning_source,
                display_name,credential_kind,credential_hash,linked_user_id,status,created_at,updated_at)
                SELECT ?,'staff',?,?,'synthetic_live_marking',?,'password',credential_hash,?,'active',?,?
                FROM auth_accounts WHERE linked_user_id=201 AND audience='staff' """,
                (
                    fixture_id,
                    project,
                    project,
                    project,
                    fixture_id,
                    TIMESTAMP,
                    TIMESTAMP,
                ),
            )
            group = c.execute("SELECT group_id FROM groups WHERE id=1").fetchone()[
                "group_id"
            ]
            c.execute(
                """INSERT INTO staff_scopes(staff_user_id,course_id,group_id,role,valid_from,created_at,updated_at)
                VALUES(?,1,?,'teacher',?,?,?)""",
                (fixture_id, group, TIMESTAMP, TIMESTAMP, TIMESTAMP),
            )
            season = c.execute("SELECT season_id FROM courses WHERE id=1").fetchone()[
                "season_id"
            ]
            c.execute(
                """INSERT INTO in_person_events(id,season_id,name,starts_at,ends_at,status,created_by_user_id,updated_by_user_id,created_at,updated_at)
                VALUES(?,?,?,'2026-09-09T09:00:00Z','2026-09-09T12:00:00Z','scheduled',301,301,?,?)""",
                (fixture_id, season, f"Очное {project}", TIMESTAMP, TIMESTAMP),
            )
            c.execute(
                "INSERT INTO in_person_event_group_lessons(in_person_event_id,group_lesson_id,added_by_user_id,created_at) VALUES(?,?,301,?)",
                (fixture_id, lesson_id, TIMESTAMP),
            )
            c.execute(
                """INSERT INTO classrooms(id,name,normalized_name,created_by_user_id,updated_by_user_id,created_at,updated_at)
                VALUES(?,?,?,301,301,?,?)""",
                (fixture_id, f"101 {project}", f"101 {project}", TIMESTAMP, TIMESTAMP),
            )
            layout = c.execute(
                """INSERT INTO classroom_layout_versions(in_person_event_id,state,created_by_user_id,created_at,updated_at)
                VALUES(?,'draft',301,?,?) RETURNING id""",
                (fixture_id, TIMESTAMP, TIMESTAMP),
            ).fetchone()["id"]
            c.execute(
                "INSERT INTO classroom_layout_rooms(layout_version_id,classroom_id,group_lesson_id,created_at,updated_at) VALUES(?,?,?,?,?)",
                (layout, fixture_id, lesson_id, TIMESTAMP, TIMESTAMP),
            )
            c.execute(
                "UPDATE classroom_layout_versions SET state='confirmed',confirmed_by_user_id=301,confirmed_at=? WHERE id=?",
                (TIMESTAMP, layout),
            )
            plan_id, _ = insert_plan(
                c,
                event_id=fixture_id,
                layout_id=layout,
                base_plan_id=None,
                actor_user_id=301,
                now=TIMESTAMP,
            )
            confirm_plan(
                c, plan_id=plan_id, expected_version=1, actor_user_id=301, now=TIMESTAMP
            )
    print("Seeded isolated live-marking lessons, teachers and classrooms")


if __name__ == "__main__":
    if require_pwa_profile_environment() != "pwa-e2e":
        raise RuntimeError("Live marking seed requires pwa-e2e")
    from helpers.config import config

    seed(config)
