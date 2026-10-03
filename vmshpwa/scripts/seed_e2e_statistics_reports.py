"""Guarded 700 × 20 report fixture; e2e/statistics-reports.spec.ts."""

import json
import sqlite3

from db_methods.pwa import maintenance_database_lock
from vmshpwa.scripts.runtime_guard import require_pwa_profile_environment
from vmshpwa.scripts.seed_e2e_oral import _seed, _web_document, TIMESTAMP
from vmshpwa.scripts.seed_e2e_statistics import _require_e2e_target

TARGETS = (("chromium", 35101), ("webkit", 35102), ("firefox", 35103))


def document_factory(**kwargs):
    document = json.loads(_web_document(**kwargs))
    template = document["problems"][0]
    document["problems"] = [
        dict(template, ordinal=i, title=f"Задача {i}") for i in range(1, 21)
    ]
    return json.dumps(document, ensure_ascii=False)


def main():
    require_pwa_profile_environment()
    from helpers.config import config

    path = _require_e2e_target(config)
    with maintenance_database_lock(path), sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        if not _seed(db, TARGETS, document_factory=document_factory):
            return
        db.executemany(
            "INSERT INTO users(id,type,surname,name) VALUES(?,1,?,?)",
            [(800000 + i, f"Школьник {i:03}", "Тестовый") for i in range(700)],
        )
        for _, lesson in TARGETS:
            group = db.execute(
                "SELECT group_id FROM problems WHERE id=?", (lesson,)
            ).fetchone()[0]
            problem_ids = [lesson]
            for ordinal in range(2, 21):
                pid = lesson * 100 + ordinal
                problem_ids.append(pid)
                db.execute(
                    "INSERT INTO problems(id,group_id,lesson,prob,item,title,prob_text,prob_type,ans_type,ans_validation,validation_error,cor_ans,wrong_ans,congrat,synonyms) VALUES(?,?,?,?, '',?,'Fixture',2,0,'','','','','','')",
                    (pid, group, lesson, ordinal, f"Задача {ordinal}"),
                )
                db.execute(
                    "INSERT INTO content_problem_matches(content_revision_id,source_ordinal,source_item,problem_id,decision,resolved_by_user_id,resolved_at,diagnostics_json,created_at) VALUES(?,?,?,?,'manual_match',301,?,'[]',?)",
                    (lesson, ordinal, str(ordinal), pid, TIMESTAMP, TIMESTAMP),
                )
                db.execute(
                    "INSERT INTO problem_revisions(problem_id,content_revision_id,source_ordinal,source_item,display_number,title,normalized_title,problem_type,answer_type,answer_config_json,attempt_policy_json,config_version,created_at) VALUES(?,?,?,?,?,?,?,2,NULL,'{}','{}',1,?)",
                    (
                        pid,
                        lesson,
                        ordinal,
                        str(ordinal),
                        str(ordinal),
                        f"Задача {ordinal}",
                        f"задача {ordinal}",
                        TIMESTAMP,
                    ),
                )
            db.executemany(
                "INSERT INTO results(student_id,problem_id,group_id,lesson,teacher_id,ts,verdict,res_type) VALUES(?,?,?,?,201,?,?,?)",
                [
                    (
                        800000 + s,
                        pid,
                        group,
                        lesson,
                        TIMESTAMP,
                        16 if (s + i) % 5 == 0 else 17,
                        i % 4 + 1,
                    )
                    for s in range(700)
                    for i, pid in enumerate(problem_ids)
                ],
            )


if __name__ == "__main__":
    main()
