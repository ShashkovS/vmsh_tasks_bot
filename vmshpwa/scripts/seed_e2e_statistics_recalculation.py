"""Published lesson observations for statistics UI acceptance, E2E only."""

import sqlite3

from vmshpwa.scripts.seed_e2e_statistics import _require_e2e_target
from vmshpwa.scripts.runtime_guard import require_pwa_profile_environment


def main():
    require_pwa_profile_environment()
    from helpers.config import config

    path = _require_e2e_target(config)
    with sqlite3.connect(path) as connection:
        for lesson in (931, 932, 933):
            for student, verdict in ((101, 17), (102, 16)):
                problem = connection.execute(
                    "SELECT id,group_id FROM problems WHERE lesson=? ORDER BY prob,item LIMIT 1",
                    (lesson,),
                ).fetchone()
                assert problem is not None
                if not connection.execute(
                    "SELECT 1 FROM results WHERE student_id=? AND problem_id=?",
                    (student, problem[0]),
                ).fetchone():
                    connection.execute(
                        "INSERT INTO results(student_id,problem_id,group_id,lesson,teacher_id,ts,verdict,res_type) VALUES(?,?,?,?,201,'2026-09-13T12:00:00Z',?,2)",
                        (student, problem[0], problem[1], lesson, verdict),
                    )


if __name__ == "__main__":
    main()
