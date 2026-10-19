"""Conversation reads; see vmshpwa/docs/review-history.md and student_results.py."""

from db_methods.pwa.review_history import history_rows, scope_clause
from db_methods.pwa.student_results import rows, one


def context(c, scope, actor, is_admin, review_id):
    reviews = history_rows(c, scope, actor, is_admin, review=review_id)
    if not reviews:
        return None
    review = reviews[0]
    problems = rows(
        c,
        """SELECT DISTINCT p.id,p.public_id,p.prob,p.item,p.title,p.lesson,
        g.short_code,c.public_id course_public_id,g.public_id group_public_id
        FROM problem_catalog p JOIN groups g ON g.group_id=p.group_id
        JOIN courses c ON c.id=g.course_id
        WHERE p.public_id=? OR p.id IN (
          SELECT problem_id FROM submission_review_evidence_entries WHERE review_id=?)
        ORDER BY p.id""",
        (review["problem_id"], review["id"]),
    )
    return review, problems


def review_in_scope(c, scope, review_id):
    clause, values = scope_clause(scope, None, True)
    return (
        one(
            c,
            "SELECT r.id FROM submission_reviews r JOIN submission_threads t ON t.id=r.thread_id "
            "JOIN problem_catalog p ON p.id=t.problem_id JOIN groups g ON g.group_id=p.group_id "
            "JOIN courses c ON c.id=g.course_id WHERE r.id=? AND " + clause,
            (review_id, *values),
        )
        is not None
    )


def reassignment_scopes(c, reassignment_id):
    return rows(
        c,
        """SELECT c.public_id course_public_id,g.public_id group_public_id
        FROM problem_catalog p JOIN groups g ON g.group_id=p.group_id
        JOIN courses c ON c.id=g.course_id
        JOIN submission_material_reassignments x
          ON p.id=x.source_problem_id OR p.id=x.target_problem_id WHERE x.id=?""",
        (reassignment_id,),
    )
