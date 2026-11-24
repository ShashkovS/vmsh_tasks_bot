"""An additional accessible course for docs/question-attention.md's E2E gate."""

from __future__ import annotations

import os
import sqlite3

from db_methods.pwa import PwaConnectionFactory, maintenance_database_lock
from vmshpwa.scripts.runtime_guard import require_pwa_profile_environment
from vmshpwa.scripts.seed_e2e_statistics import _require_e2e_target

TIMESTAMP = "2026-01-01T00:00:00Z"


def _seed(connection: sqlite3.Connection) -> int:
    if connection.execute(
        "SELECT id FROM courses WHERE code='support-navigation'"
    ).fetchone():
        return 0
    course = connection.execute(
        "INSERT INTO courses(season_id,code,name,subject_code,status,sort_order,"
        "accent_key,created_at,updated_at) SELECT season_id,'support-navigation',"
        "'Другой курс E2E','math','active',100,'math',?,? FROM courses WHERE id=1 "
        "RETURNING id",
        (TIMESTAMP, TIMESTAMP),
    ).fetchone()
    if course is None:
        raise RuntimeError("Support navigation seed requires the baseline course")
    connection.execute(
        "INSERT INTO groups(group_id,short_code,public_name,sort_order,is_active,"
        "is_default,allow_self_switch,is_system,score_weight,course_id,status,"
        "created_at,updated_at) VALUES('support-navigation','other','Другая группа',"
        "1,1,0,1,0,1.0,?,'active',?,?)",
        (course["id"], TIMESTAMP, TIMESTAMP),
    )
    enrollment = connection.execute(
        "INSERT INTO course_enrollments(student_user_id,course_id,active_group_id,"
        "attendance_mode,status,created_at,updated_at) VALUES(101,?,"
        "'support-navigation','online','active',?,?) RETURNING id",
        (course["id"], TIMESTAMP, TIMESTAMP),
    ).fetchone()
    connection.execute(
        "INSERT INTO course_group_access(enrollment_id,course_id,group_id,valid_from,"
        "created_at,updated_at) VALUES(?,?,'support-navigation',?,?,?)",
        (enrollment["id"], course["id"], TIMESTAMP, TIMESTAMP, TIMESTAMP),
    )
    return 1


def main() -> None:
    if os.environ.get("PROD", "").strip().casefold() == "true":
        raise RuntimeError("Support navigation seed is forbidden when PROD=true")
    if require_pwa_profile_environment() != "pwa-e2e":
        raise RuntimeError("Support navigation seed requires pwa-e2e")
    from helpers.config import config

    database_path = _require_e2e_target(config)
    with maintenance_database_lock(database_path):
        inserted = PwaConnectionFactory(database_path).run_write(_seed)
    print(f"Seeded support navigation course: inserted={inserted}")


if __name__ == "__main__":
    main()
