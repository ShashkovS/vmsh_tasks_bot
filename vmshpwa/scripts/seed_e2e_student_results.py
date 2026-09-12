"""Hermetic archive acceptance fixture; docs/student-results.md. No external services."""

import hashlib
import json
import sqlite3
from pathlib import Path

from vmshpwa.scripts.runtime_guard import require_pwa_profile_environment
from vmshpwa.scripts.seed_e2e_review import _require_e2e_target
from vmshpwa.scripts.seed_e2e_oral import _web_document

STUDENT = 31301
STAMP = "2026-09-01T12:00:00Z"


def seed(config):
    path = _require_e2e_target(config)
    with sqlite3.connect(path) as c:
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        if c.execute("SELECT 1 FROM users WHERE id=?", (STUDENT,)).fetchone():
            return
        c.execute(
            "INSERT INTO users(id,type,surname,name,middlename,grade) VALUES(?,-1,'Архивов','Александр','Михайлович',7)",
            (STUDENT,),
        )
        # No account or enrollment. Modern history and old results still belong to this person.
        pr = c.execute(
            "SELECT id FROM problem_revisions WHERE problem_id=9701"
        ).fetchone()["id"]
        thread = c.execute(
            "INSERT INTO submission_threads(student_user_id,problem_id,condition_revision_id,status,latest_entry_at,created_at,updated_at) VALUES(?,9701,9701,'awaiting_review',?,?,?) RETURNING id",
            (STUDENT, STAMP, STAMP, STAMP),
        ).fetchone()["id"]
        entry = c.execute(
            "INSERT INTO submission_entries(thread_id,problem_revision_id,author_kind,author_user_id,channel,entry_kind,state,text,server_received_at) VALUES(?,?,'student',?,'pwa','submission','submitted','Рассмотрим треугольники ABC и ADC. У них общая сторона AC.',?) RETURNING id",
            (thread, pr, STUDENT, STAMP),
        ).fetchone()["id"]
        c.execute(
            "INSERT INTO submission_entries(thread_id,problem_revision_id,author_kind,author_user_id,channel,entry_kind,state,text,server_received_at) VALUES(?,?,'student',?,'pwa','submission','draft','НЕОТПРАВЛЕННЫЙ ЧЕРНОВИК',?)",
            (thread, pr, STUDENT, STAMP),
        )
        body = (
            Path(__file__).resolve().parents[2]
            / "pwa_tests/fixtures/student-results-photo.webp"
        ).read_bytes()
        key = "submission/student-results-photo.webp"
        file = Path(config.pwa_media_root) / key
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(body)
        asset = c.execute(
            "INSERT INTO media_assets(sha256,storage_namespace,object_key,media_type,byte_size,width,height,conversion_version,created_by_user_id,created_at) VALUES(?,'submission',?,'image/webp',?,640,360,'pwa-written-image-v1',?,?) RETURNING id",
            (hashlib.sha256(body).hexdigest(), key, len(body), STUDENT, STAMP),
        ).fetchone()["id"]
        attachment = c.execute(
            "INSERT INTO submission_attachments(entry_id,asset_id,ordinal,upload_status,created_at) VALUES(?,?,0,'stored',?) RETURNING id",
            (entry, asset, STAMP),
        ).fetchone()["id"]
        for n, verdict in enumerate((14, 17)):
            at = f"2026-09-01T12:0{n + 1}:00Z"
            comment = c.execute(
                "INSERT INTO submission_entries(thread_id,problem_revision_id,author_kind,author_user_id,channel,entry_kind,state,text,server_received_at,locked_at) VALUES(?,?,'teacher',201,'staff','teacher_comment','locked',?,?,?) RETURNING id",
                (
                    thread,
                    pr,
                    (
                        "Идея верная, обоснуйте равенство углов."
                        if n == 0
                        else "Исправление проверки: обоснование полное."
                    ),
                    at,
                    at,
                ),
            ).fetchone()["id"]
            result = c.execute(
                "INSERT INTO results(student_id,problem_id,group_id,lesson,teacher_id,ts,verdict,res_type) SELECT ?,id,group_id,lesson,201,?,?,2 FROM problems WHERE id=9701 RETURNING id",
                (STUDENT, at, verdict),
            ).fetchone()["id"]
            review = c.execute(
                "INSERT INTO submission_reviews(thread_id,queue_id,reviewer_user_id,evidence_through_entry_id,expected_thread_version,verdict,comment_entry_id,result_id,source,idempotency_key,payload_sha256,created_at) VALUES(?,9701,201,?,1,?,?,?,'staff',?,?,?) RETURNING id",
                (
                    thread,
                    entry,
                    verdict,
                    comment,
                    result,
                    f"archive-review-{n}",
                    "a" * 64,
                    at,
                ),
            ).fetchone()["id"]
            c.execute(
                "INSERT INTO submission_review_evidence_entries(review_id,entry_id,thread_id,problem_id,entry_version,server_received_at) VALUES(?,?,?,9701,1,?)",
                (review, entry, thread, STAMP),
            )
            c.execute(
                "INSERT INTO submission_review_evidence_attachments(review_id,attachment_id,entry_id,asset_id,ordinal) VALUES(?,?,?,?,0)",
                (review, attachment, entry, asset),
            )
            marks = json.dumps(
                [
                    dict(
                        markId="angle",
                        kind="rectangle",
                        data=dict(
                            x=0.42,
                            y=0.08,
                            width=0.13,
                            height=0.2,
                            strokeWidth=0.008,
                            color="red",
                        ),
                    )
                ]
            )
            c.execute(
                "INSERT INTO submission_review_annotations(review_id,attachment_id,schema_version,rotation,marks_json,payload_sha256,created_at) VALUES(?,?,1,0,?,?,?)",
                (
                    review,
                    attachment,
                    marks,
                    hashlib.sha256(marks.encode()).hexdigest(),
                    at,
                ),
            )
        c.execute(
            "UPDATE submission_threads SET status='accepted',latest_result_id=?,version=version+1 WHERE id=?",
            (result, thread),
        )
        # A mapped legacy row must not appear twice.
        did = c.execute(
            "INSERT INTO written_tasks_discussions(student_id,problem_id,ts,text) VALUES(?,9701,?,'Досылка из Telegram: добавил рисунок.') RETURNING id",
            (STUDENT, STAMP),
        ).fetchone()["id"]
        c.execute(
            "INSERT INTO submission_entries(thread_id,problem_revision_id,author_kind,author_user_id,channel,entry_kind,state,text,server_received_at,legacy_discussion_id) VALUES(?,?,'student',?,'telegram','text','submitted','Досылка из Telegram: добавил рисунок.',?,?)",
            (thread, pr, STUDENT, STAMP, did),
        )
        for n in range(55):
            c.execute(
                "INSERT INTO written_tasks_discussions(student_id,problem_id,teacher_id,ts,text,attach_path) VALUES(?,9701,?,?,?,?)",
                (
                    STUDENT,
                    201 if n % 2 else None,
                    f"2026-09-01T13:{n:02}:00Z",
                    f"Архивная досылка {n + 1}: уточнение решения.",
                    "solutions/missing-fixture.jpg" if n == 0 else None,
                ),
            )
        # Different level, same lesson, no modern publication, plus an oral-only task.
        for pid, group_id, problem_number in ((98101, "п", 2), (98102, "н", 3)):
            c.execute(
                "INSERT INTO problems(id,group_id,lesson,prob,item,title,prob_text,prob_type,ans_type,ans_validation,validation_error,cor_ans,wrong_ans,congrat,synonyms) VALUES(?,?,9701,?,'','Архивная задача','',3,0,'','','','','','')",
                (pid, group_id, problem_number),
            )
            c.execute(
                "INSERT INTO results(student_id,problem_id,group_id,lesson,teacher_id,ts,verdict,res_type) VALUES(?,?,?,9701,201,?,14,4)",
                (STUDENT, pid, group_id, STAMP),
            )
        c.execute(
            "INSERT INTO written_tasks_discussions(student_id,problem_id,ts,text) VALUES(?,98101,?,'Решение продвинутого уровня из Telegram.')",
            (STUDENT, STAMP),
        )
        # A second archived course exercises course-scoped lesson numbers.
        c.execute(
            "INSERT INTO courses(id,season_id,code,name,subject_code,status,sort_order,accent_key,created_at,updated_at) SELECT 31301,season_id,'archive-results','Архивный курс',subject_code,'archived',99,accent_key,created_at,updated_at FROM courses WHERE id=1"
        )
        c.execute(
            "INSERT INTO groups(id,group_id,short_code,public_name,sort_order,is_active,is_default,allow_self_switch,is_system,score_weight,course_id,status,created_at,updated_at) SELECT 31301,'archive-results','arch','Архивный уровень',99,0,0,0,0,1,31301,'archived',created_at,updated_at FROM groups WHERE id=1"
        )
        c.execute(
            "INSERT INTO problems(id,group_id,lesson,prob,item,title,prob_text,prob_type,ans_type,ans_validation,validation_error,cor_ans,wrong_ans,congrat,synonyms) SELECT 98103,'archive-results',7,1,item,title,prob_text,prob_type,ans_type,ans_validation,validation_error,cor_ans,wrong_ans,congrat,synonyms FROM problems WHERE id=98101"
        )
        c.execute(
            "INSERT INTO written_tasks_discussions(student_id,problem_id,ts,text) VALUES(?,98103,?,'Решение из другого курса.')",
            (STUDENT, STAMP),
        )
        # Test attempt with no result yet still belongs in the archive.
        c.execute(
            "INSERT INTO test_attempts(student_user_id,problem_id,problem_revision_id,answer_payload_json,normalized_answer_json,parse_status,counts_as_attempt,check_status,client_created_at,server_received_at,idempotency_key,payload_sha256,created_at) VALUES(?,9701,?,'{\"displayAnswer\":\"42\"}','{\"value\":42}','valid',1,'pending_configuration',?,?,'archive-test',?,?)",
            (STUDENT, pr, STAMP, STAMP, "a" * 64, STAMP),
        )
        document = _web_document(
            revision_id="cr-9701",
            source_sha256="a" * 64,
            title="Равнобедренный треугольник",
        )
        c.execute(
            "INSERT INTO content_derivatives(revision_id,kind,renderer_version,content_text,sha256,diagnostics_json,provenance_json,created_at) VALUES(9701,'web_ast','archive-e2e',?,?,'[]','{}',?)",
            (document, hashlib.sha256(document.encode()).hexdigest(), STAMP),
        )
    print("Seeded isolated student-results archive")


if __name__ == "__main__":
    if require_pwa_profile_environment() != "pwa-e2e":
        raise RuntimeError("Archive fixture requires pwa-e2e")
    from helpers.config import config

    seed(config)
