"""Mechanical reads needed by the optional Telegram review adapter."""

from __future__ import annotations

import sqlite3


def read_review_telegram_delivery(
    connection: sqlite3.Connection,
    review_public_id: str,
) -> dict[str, object] | None:
    review = connection.execute(
        "SELECT student.chat_id, review.verdict "
        "FROM submission_reviews AS review "
        "JOIN submission_threads AS thread ON thread.id = review.thread_id "
        "JOIN users AS student ON student.id = thread.student_user_id "
        "WHERE review.public_id = ?",
        (review_public_id,),
    ).fetchone()
    if review is None:
        return None

    problems = connection.execute(
        "SELECT DISTINCT problem.id, problem.lesson, problem.prob, problem.item, "
        "problem.title, group_row.short_code "
        "FROM submission_review_evidence_entries AS evidence "
        "JOIN submission_reviews AS review ON review.id = evidence.review_id "
        "JOIN problems AS problem ON problem.id = evidence.problem_id "
        "LEFT JOIN groups AS group_row ON group_row.group_id = problem.group_id "
        "WHERE review.public_id = ? "
        "ORDER BY problem.lesson, group_row.sort_order, problem.prob, problem.item, "
        "problem.id",
        (review_public_id,),
    ).fetchall()
    annotations = connection.execute(
        "SELECT attachment.public_id AS attachment_public_id, asset.object_key, "
        "annotation.rotation, annotation.marks_json "
        "FROM submission_review_annotations AS annotation "
        "JOIN submission_reviews AS review ON review.id = annotation.review_id "
        "JOIN submission_attachments AS attachment "
        "ON attachment.id = annotation.attachment_id "
        "JOIN media_assets AS asset ON asset.id = attachment.asset_id "
        "WHERE review.public_id = ? "
        "ORDER BY attachment.ordinal, attachment.id",
        (review_public_id,),
    ).fetchall()
    return {
        "chat_id": review["chat_id"],
        "verdict": int(review["verdict"]),
        "problems": [dict(row) for row in problems],
        "annotations": [dict(row) for row in annotations],
    }


__all__ = ["read_review_telegram_delivery"]
