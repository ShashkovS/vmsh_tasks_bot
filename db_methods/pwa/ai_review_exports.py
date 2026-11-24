"""Read-only calibration/batch data; vmshpwa/docs/ai-review-assistant.md."""

from db_methods.pwa.student_results import SENT


def students(connection, problem_id):
    return connection.execute(
        """SELECT u.id,coalesce(u.public_id,'u-'||u.id) AS public_id,u.name,u.surname,u.middlename,u.grade
        FROM users u WHERE u.id IN (
          SELECT student_user_id FROM submission_threads WHERE problem_id=:problem
          UNION SELECT student_id FROM written_tasks_discussions WHERE problem_id=:problem
          UNION SELECT student_id FROM results WHERE problem_id=:problem
          UNION SELECT student_user_id FROM test_attempts WHERE problem_id=:problem
        ) ORDER BY u.id""",
        {"problem": problem_id},
    ).fetchall()


def submission_states(connection, student_id, problem_id):
    return connection.execute(
        f"""SELECT e.id,e.public_id,e.state,e.problem_revision_id,
        EXISTS(SELECT 1 FROM submission_review_evidence_entries x WHERE x.entry_id=e.id) AS reviewed,
        EXISTS(SELECT 1 FROM submission_entry_replacements x WHERE x.replaced_entry_id=e.id)
          OR EXISTS(SELECT 1 FROM submission_entry_transfers x WHERE x.source_entry_id=e.id AND x.mode='move')
          AS superseded
        FROM submission_entries e JOIN submission_threads t ON t.id=e.thread_id
        WHERE t.student_user_id=? AND t.problem_id=? AND e.author_kind='student'
        AND e.entry_kind IN ('text','submission') AND {SENT} ORDER BY e.id""",
        (student_id, problem_id),
    ).fetchall()


def reviews(connection, entry_id):
    return connection.execute(
        """SELECT r.id,r.public_id FROM submission_review_evidence_entries x
        JOIN submission_reviews r ON r.id=x.review_id WHERE x.entry_id=? ORDER BY r.id""",
        (entry_id,),
    ).fetchall()


def revision_ids(connection, student_id, problem_id):
    return {
        row["problem_revision_id"]
        for row in connection.execute(
            f"""SELECT e.problem_revision_id FROM submission_entries e
            JOIN submission_threads t ON t.id=e.thread_id
            WHERE t.student_user_id=:student AND t.problem_id=:problem
            AND e.author_kind='student' AND {SENT}
            UNION SELECT problem_revision_id FROM test_attempts
            WHERE student_user_id=:student AND problem_id=:problem""",
            {"student": student_id, "problem": problem_id},
        ).fetchall()
    }


def modern_case(connection, student_id, problem_id):
    return connection.execute(
        "SELECT public_id FROM submission_threads WHERE student_user_id=? AND problem_id=? ORDER BY id LIMIT 1",
        (student_id, problem_id),
    ).fetchone()
