"""Read projections for the serial feed; vmshpwa/docs/serial-review-feed.md."""

import json

from db_methods.pwa.review_history import scope_clause, history_detail


SIGNATURE = """(SELECT group_concat(entry_public_id, ',') FROM
 (SELECT e.public_id AS entry_public_id FROM submission_review_evidence_entries x
  JOIN submission_entries e ON e.id=x.entry_id WHERE x.review_id=r.id ORDER BY e.public_id))"""


def history(connection, scope, actor, problem, before=None):
    clause, values = scope_clause(scope, actor, False)
    rows = connection.execute(
        """WITH eligible AS (
      SELECT r.id,r.public_id,r.created_at,"""
        + SIGNATURE
        + """ AS material_key
      FROM submission_reviews r JOIN submission_threads t ON t.id=r.thread_id
      JOIN problems p ON p.id=t.problem_id JOIN groups g ON g.group_id=p.group_id
      JOIN courses c ON c.id=g.course_id WHERE """
        + clause
        + """
      AND EXISTS(SELECT 1 FROM submission_review_evidence_entries x
        JOIN problems ep ON ep.id=x.problem_id WHERE x.review_id=r.id AND ep.public_id=?)
    ), roots AS (SELECT min(id) AS id,max(id) AS latest_id,material_key FROM eligible GROUP BY material_key)
    SELECT e.*, (SELECT public_id FROM eligible WHERE id=root.latest_id) AS own_review_id
    FROM eligible e JOIN roots root ON root.id=e.id
    WHERE e.material_key IS NOT NULL AND (? IS NULL OR (e.created_at,e.id)<
      (SELECT created_at,id FROM submission_reviews WHERE public_id=?))
    ORDER BY e.created_at DESC,e.id DESC LIMIT 21""",
        (*values, problem, before, before),
    ).fetchall()
    return {
        "schemaVersion": 1,
        "items": [
            {"reviewId": r["own_review_id"], "materialKey": r["material_key"]}
            for r in rows[:20]
        ],
        "nextCursor": rows[19]["public_id"] if len(rows) > 20 else None,
    }


def current_detail(connection, scope, actor, review):
    # Establish ownership and current scope before following a different author's
    # correction. Only the exact same immutable evidence may be followed.
    original = history_detail(connection, scope, actor, False, review)
    if original is None:
        return None
    latest = connection.execute(
        """WITH evidence AS (
      SELECT r.public_id,r.created_at,r.id,"""
        + SIGNATURE
        + """ AS material_key
      FROM submission_reviews r WHERE r.thread_id=(SELECT thread_id FROM submission_reviews WHERE public_id=?))
      SELECT public_id FROM evidence WHERE material_key=
      (SELECT material_key FROM evidence WHERE public_id=?)
      ORDER BY created_at DESC,id DESC LIMIT 1""",
        (review, review),
    ).fetchone()
    return (
        history_detail(connection, scope, actor, True, latest["public_id"])
        if latest
        else original
    )


def condition(connection, scope, problem, entry=None):
    row = connection.execute(
        """SELECT p.id,p.lesson,p.prob,p.item,p.title,g.short_code,
      g.public_id AS group_public_id,c.public_id AS course_public_id
      FROM problems p JOIN groups g ON g.group_id=p.group_id JOIN courses c ON c.id=g.course_id
      WHERE p.public_id=?""",
        (problem,),
    ).fetchone()
    if row is None or not scope.allows(row):
        return None
    material = connection.execute(
        """SELECT d.content_text,pr.source_ordinal
      FROM problem_revisions pr JOIN content_revisions cr ON cr.id=pr.content_revision_id
      JOIN content_sources cs ON cs.id=cr.source_id AND cs.kind='condition'
      JOIN content_derivatives d ON d.revision_id=cr.id AND d.kind='web_ast' AND d.invalidated_at IS NULL
      WHERE pr.problem_id=? AND (? IS NULL OR pr.id=(SELECT e.problem_revision_id
        FROM submission_entries e JOIN submission_threads t ON t.id=e.thread_id
        WHERE e.public_id=? AND t.problem_id=?))
      ORDER BY pr.id DESC,d.id DESC LIMIT 1""",
        (row["id"], entry, entry, row["id"]),
    ).fetchone()
    document = None
    if material:
        document = json.loads(material["content_text"])
        document["problems"] = [
            p
            for p in document["problems"]
            if p["ordinal"] == material["source_ordinal"]
        ]
    return {
        "schemaVersion": 1,
        "label": f"{row['lesson']}{row['short_code']}.{row['prob']}{row['item'] or ''} · {row['title'] or ''}",
        "document": document,
    }
