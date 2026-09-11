"""Read-only archive queries; vmshpwa/docs/student-results.md."""

from db_methods.pwa.live_marking import rows, one

# Deleted entries count only when their prior submission is evidenced in the ledger.
SENT = """(e.state IN ('submitted','locked') OR e.legacy_discussion_id IS NOT NULL OR EXISTS (
 SELECT 1 FROM submission_entry_replacements rep WHERE rep.replaced_entry_id=e.id)
 OR EXISTS(SELECT 1 FROM submission_review_evidence_entries ev WHERE ev.entry_id=e.id)
 OR EXISTS(SELECT 1 FROM submission_entry_transfers x WHERE x.source_entry_id=e.id))"""
ACTIVITY = f"""
 SELECT problem_id FROM results WHERE student_id=:student
 UNION SELECT t.problem_id FROM submission_threads t JOIN submission_entries e ON e.thread_id=t.id
 WHERE t.student_user_id=:student AND e.author_kind='student' AND {SENT}
 UNION SELECT source_problem_id FROM submission_material_reassignments WHERE student_user_id=:student
 UNION SELECT target_problem_id FROM submission_material_reassignments WHERE student_user_id=:student
 UNION SELECT problem_id FROM test_attempts WHERE student_user_id=:student
 UNION SELECT problem_id FROM written_tasks_discussions WHERE student_id=:student AND problem_id>0
"""
SUBMITTED = f"""
 SELECT t.problem_id FROM submission_threads t JOIN submission_entries e ON e.thread_id=t.id
 WHERE t.student_user_id=:student AND e.author_kind='student' AND {SENT}
 UNION SELECT source_problem_id FROM submission_material_reassignments WHERE student_user_id=:student
 UNION SELECT target_problem_id FROM submission_material_reassignments WHERE student_user_id=:student
 UNION SELECT problem_id FROM test_attempts WHERE student_user_id=:student
 UNION SELECT problem_id FROM written_tasks_discussions WHERE student_id=:student AND teacher_id IS NULL AND problem_id>0
 UNION SELECT problem_id FROM results WHERE student_id=:student AND res_type=1 AND answer IS NOT NULL
"""


def directory(c):
    return rows(
        c,
        """SELECT u.id,coalesce(u.public_id,'u-'||u.id) public_id,
      u.name,u.surname,u.middlename,u.grade,
      (SELECT group_concat(DISTINCT g.public_name) FROM course_enrollments e
        JOIN groups g ON g.group_id=e.active_group_id AND g.course_id=e.course_id
        WHERE e.student_user_id=u.id) groups
      FROM users u WHERE u.type IN (1,-2) OR EXISTS(SELECT 1 FROM submission_threads t WHERE t.student_user_id=u.id) OR EXISTS(SELECT 1 FROM test_attempts a WHERE a.student_user_id=u.id) OR EXISTS(SELECT 1 FROM results r WHERE r.student_id=u.id)
        OR EXISTS(SELECT 1 FROM written_tasks_discussions d WHERE d.student_id=u.id AND d.problem_id>0) OR EXISTS(
        SELECT 1 FROM course_enrollments ce WHERE ce.student_user_id=u.id)
      ORDER BY u.surname COLLATE NOCASE,u.name COLLATE NOCASE,u.id""",
    )


def student(c, public_id):
    return one(
        c,
        """SELECT id,coalesce(public_id,'u-'||id) public_id,name,surname,middlename,grade
      FROM users WHERE coalesce(public_id,'u-'||id)=? AND (type IN (1,-2)
        OR EXISTS(SELECT 1 FROM submission_threads t WHERE t.student_user_id=users.id)
        OR EXISTS(SELECT 1 FROM test_attempts a WHERE a.student_user_id=users.id)
        OR EXISTS(SELECT 1 FROM results r WHERE r.student_id=users.id)
        OR EXISTS(SELECT 1 FROM written_tasks_discussions d WHERE d.student_id=users.id AND d.problem_id>0)
        OR EXISTS(SELECT 1 FROM course_enrollments e WHERE e.student_user_id=users.id))""",
        (public_id,),
    )


def courses(c, student_id):
    return rows(
        c,
        f"""WITH activity AS ({ACTIVITY})
      SELECT DISTINCT c.id,c.public_id,c.name,c.sort_order FROM courses c
      WHERE EXISTS(SELECT 1 FROM course_enrollments e WHERE e.course_id=c.id AND e.student_user_id=:student)
        OR EXISTS(SELECT 1 FROM activity a JOIN problems p ON p.id=a.problem_id
          JOIN groups g ON g.group_id=p.group_id WHERE g.course_id=c.id)
      ORDER BY c.sort_order,c.id""",
        {"student": student_id},
    )


def lessons(c, course_id):
    return rows(
        c,
        """SELECT lesson_number number,max(title) title FROM (
      SELECT lesson_number,title FROM course_lessons WHERE course_id=?
      UNION ALL SELECT p.lesson,NULL FROM problems p JOIN groups g ON g.group_id=p.group_id WHERE g.course_id=?
      ) GROUP BY lesson_number ORDER BY lesson_number DESC""",
        (course_id, course_id),
    )


def problems(c, student_id, course_id, number=None):
    return rows(
        c,
        f"""WITH activity AS ({ACTIVITY}), submitted AS ({SUBMITTED})
      SELECT p.id,p.public_id,p.prob,p.item,p.title,p.prob_text,p.lesson,g.public_id group_public_id,
        g.public_name group_name,g.short_code group_code,g.sort_order,
        EXISTS(SELECT 1 FROM activity a WHERE a.problem_id=p.id) active,
        EXISTS(SELECT 1 FROM submitted a WHERE a.problem_id=p.id) submitted
      FROM problems p JOIN groups g ON g.group_id=p.group_id
      WHERE g.course_id=:course AND p.id>0 AND p.public_id IS NOT NULL
        AND (:number IS NULL OR p.lesson=:number)
      ORDER BY p.lesson DESC,g.sort_order,g.group_id,p.prob,p.item,p.id""",
        {"student": student_id, "course": course_id, "number": number},
    )


def current_results(c, student_id):
    return rows(
        c,
        """SELECT * FROM (SELECT r.*,v.val,
      trim(coalesce(u.surname,'')||' '||coalesce(u.name,'')) author,
      row_number() OVER(PARTITION BY r.problem_id ORDER BY v.val DESC,r.ts DESC,r.id DESC) priority
      FROM effective_results r JOIN verdicts v ON v.id=r.verdict LEFT JOIN users u ON u.id=r.teacher_id
      WHERE r.student_id=?) WHERE priority=1""",
        (student_id,),
    )


def problem(c, public_id):
    return one(
        c,
        "SELECT id,public_id,prob,item,title,lesson FROM problems WHERE public_id=? AND id>0",
        (public_id,),
    )


def material(c, problem_id, revision_id=None):
    return one(
        c,
        """SELECT cr.id content_revision_id,cr.public_id revision_id,pr.source_ordinal,d.content_text
      FROM problem_revisions pr JOIN content_revisions cr ON cr.id=pr.content_revision_id
      JOIN content_sources cs ON cs.id=cr.source_id AND cs.kind='condition'
      JOIN content_derivatives d ON d.revision_id=cr.id AND d.kind='web_ast' AND d.invalidated_at IS NULL
      WHERE pr.problem_id=? AND (? IS NULL OR cr.public_id=?)
      ORDER BY EXISTS(SELECT 1 FROM lesson_publications lp WHERE lp.revision_id=cr.id AND lp.state='published') DESC,
        pr.id DESC,d.id DESC LIMIT 1""",
        (problem_id, revision_id, revision_id),
    )


# Page the event index before fetching text or media; never cut a task's history silently.
def event_index(c, student_id, problem_id):
    return rows(
        c,
        f"""WITH s AS (SELECT :student sid,:problem pid), events AS (
      SELECT 'entry' kind,cast(e.id AS TEXT) id,e.server_received_at ts FROM submission_entries e
        JOIN submission_threads t ON t.id=e.thread_id,s WHERE t.student_user_id=s.sid AND t.problem_id=s.pid AND {SENT}
        AND NOT EXISTS(SELECT 1 FROM submission_reviews r WHERE r.comment_entry_id=e.id)
      UNION ALL SELECT 'test',cast(a.id AS TEXT),a.server_received_at FROM test_attempts a,s
        WHERE a.student_user_id=s.sid AND a.problem_id=s.pid
      UNION ALL SELECT 'review',cast(r.id AS TEXT),r.created_at FROM submission_reviews r
        JOIN submission_threads t ON t.id=r.thread_id,s WHERE t.student_user_id=s.sid AND (t.problem_id=s.pid OR EXISTS(SELECT 1 FROM submission_review_evidence_entries ev WHERE ev.review_id=r.id AND ev.problem_id=s.pid))
      UNION ALL SELECT 'discussion',cast(d.id AS TEXT),d.ts FROM written_tasks_discussions d,s
        WHERE d.student_id=s.sid AND d.problem_id=s.pid
        AND NOT EXISTS(SELECT 1 FROM submission_entries e WHERE e.legacy_discussion_id=d.id)
      UNION ALL SELECT 'result',cast(r.id AS TEXT),r.ts FROM results r,s
        WHERE r.student_id=s.sid AND r.problem_id=s.pid
        AND NOT EXISTS(SELECT 1 FROM test_attempts a WHERE a.result_id=r.id)
        AND NOT EXISTS(SELECT 1 FROM submission_reviews v WHERE v.result_id=r.id)
      UNION ALL SELECT 'reaction',cast(e.id AS TEXT),e.created_at FROM submission_review_internal_reaction_events e
        JOIN submission_reviews r ON r.id=e.review_id JOIN submission_threads t ON t.id=r.thread_id,s
        WHERE t.student_user_id=s.sid AND t.problem_id=s.pid
      UNION ALL SELECT 'student_reaction',cast(e.id AS TEXT),e.created_at FROM submission_review_student_reaction_events e
        JOIN submission_reviews r ON r.id=e.review_id JOIN submission_threads t ON t.id=r.thread_id,s
        WHERE t.student_user_id=s.sid AND t.problem_id=s.pid
      UNION ALL SELECT 'legacy_reaction',cast(e.id AS TEXT),e.ts FROM reactions e
        JOIN results r ON r.id=e.result_id,s WHERE r.student_id=s.sid AND r.problem_id=s.pid
      UNION ALL SELECT 'transfer',cast(x.id AS TEXT),x.created_at FROM submission_entry_transfers x
        JOIN submission_entries e ON e.id=x.source_entry_id OR e.id=x.target_entry_id
        JOIN submission_threads t ON t.id=e.thread_id,s WHERE t.student_user_id=s.sid AND t.problem_id=s.pid
      UNION ALL SELECT 'reassignment',cast(x.id AS TEXT),x.created_at FROM submission_material_reassignments x,s
        WHERE x.student_user_id=s.sid AND (x.source_problem_id=s.pid OR x.target_problem_id=s.pid)
      UNION ALL SELECT 'replacement',cast(x.id AS TEXT),x.replaced_at FROM submission_entry_replacements x
        JOIN submission_threads t ON t.id=x.thread_id,s WHERE t.student_user_id=s.sid AND t.problem_id=s.pid
      UNION ALL SELECT 'undo',o.id,o.undone_at FROM live_mark_operations o,s
        WHERE o.kind='mark' AND o.undone_at IS NOT NULL
          AND json_extract(o.after_json,'$.studentId')=(SELECT coalesce(public_id,'u-'||id) FROM users WHERE id=s.sid)
          AND json_extract(o.after_json,'$.problemId')=(SELECT public_id FROM problems WHERE id=s.pid)
      ) SELECT DISTINCT kind,id,ts FROM events ORDER BY julianday(ts),ts,kind,id""",
        {"student": student_id, "problem": problem_id},
    )


def attachments(c, entry_id):
    return rows(
        c,
        """SELECT a.public_id,a.id,a.upload_status,a.ordinal FROM submission_attachments a
      WHERE a.entry_id=? ORDER BY a.ordinal,a.id""",
        (entry_id,),
    )


def attachment(c, student_id, public_id):
    return one(
        c,
        f"""SELECT m.object_key,m.media_type,m.byte_size,m.sha256
      FROM submission_attachments a JOIN media_assets m ON m.id=a.asset_id
      JOIN submission_entries e ON e.id=a.entry_id JOIN submission_threads t ON t.id=e.thread_id
      WHERE t.student_user_id=? AND a.public_id=? AND {SENT} AND a.upload_status IN ('stored','locked')""",
        (student_id, public_id),
    )


def annotations(c, review_id):
    return rows(
        c,
        """SELECT a.public_id attachment_id,n.schema_version,n.rotation,n.marks_json
      FROM submission_review_annotations n JOIN submission_attachments a ON a.id=n.attachment_id
      WHERE n.review_id=?""",
        (review_id,),
    )


def notes(c, student_id, course_id, number):
    return rows(
        c,
        """SELECT z.id,z.ts,trim(coalesce(u.surname,'')||' '||coalesce(u.name,'')) author,
      re.reaction, r.ts reaction_at FROM zoom_conversation z JOIN groups g ON g.group_id=z.group_id
      LEFT JOIN users u ON u.id=z.teacher_id LEFT JOIN reactions r ON r.zoom_conversation_id=z.id
      LEFT JOIN reaction_enum re ON re.reaction_id=r.reaction_id
      WHERE z.student_id=? AND g.course_id=? AND z.lesson=? ORDER BY z.ts,r.id""",
        (student_id, course_id, number),
    )


def event_record(c, kind, event_id):
    queries = {
        "entry": """SELECT e.*,cr.public_id revision_id,u.name,u.surname FROM submission_entries e
          LEFT JOIN users u ON u.id=e.author_user_id LEFT JOIN problem_revisions pr ON pr.id=e.problem_revision_id
          LEFT JOIN content_revisions cr ON cr.id=pr.content_revision_id WHERE e.id=?""",
        "test": """SELECT a.*,cr.public_id revision_id FROM test_attempts a
          JOIN problem_revisions pr ON pr.id=a.problem_revision_id JOIN content_revisions cr ON cr.id=pr.content_revision_id WHERE a.id=?""",
        "review": """SELECT r.*,e.text,u.name,u.surname FROM submission_reviews r
          LEFT JOIN submission_entries e ON e.id=r.comment_entry_id LEFT JOIN users u ON u.id=r.reviewer_user_id WHERE r.id=?""",
        "discussion": """SELECT d.*,u.name,u.surname FROM written_tasks_discussions d LEFT JOIN users u ON u.id=d.teacher_id WHERE d.id=?""",
        "result": """SELECT r.*,u.name,u.surname FROM results r LEFT JOIN users u ON u.id=r.teacher_id WHERE r.id=?""",
        "reaction": """SELECT r.*,e.reaction,u.name,u.surname FROM submission_review_internal_reaction_events r
          LEFT JOIN reaction_enum e ON e.reaction_id=r.reaction_id LEFT JOIN users u ON u.id=r.actor_user_id WHERE r.id=?""",
        "student_reaction": """SELECT r.*,e.reaction,u.name,u.surname FROM submission_review_student_reaction_events r
          LEFT JOIN reaction_enum e ON e.reaction_id=r.reaction_id LEFT JOIN users u ON u.id=r.actor_user_id WHERE r.id=?""",
        "legacy_reaction": """SELECT r.*,e.reaction FROM reactions r JOIN reaction_enum e ON e.reaction_id=r.reaction_id WHERE r.id=?""",
        "transfer": """SELECT x.*,u.name,u.surname,p1.public_id source_problem,p2.public_id target_problem,
          p1.prob source_number,p1.item source_item,p2.prob target_number,p2.item target_item
          FROM submission_entry_transfers x LEFT JOIN users u ON u.id=x.actor_user_id
          JOIN submission_entries e1 ON e1.id=x.source_entry_id JOIN submission_threads t1 ON t1.id=e1.thread_id JOIN problems p1 ON p1.id=t1.problem_id
          JOIN submission_entries e2 ON e2.id=x.target_entry_id JOIN submission_threads t2 ON t2.id=e2.thread_id JOIN problems p2 ON p2.id=t2.problem_id WHERE x.id=?""",
        "reassignment": """SELECT x.*,u.name,u.surname,
          printf('%d%s.%d%s',p1.lesson,g1.short_code,p1.prob,coalesce(p1.item,'')) source_label,
          printf('%d%s.%d%s',p2.lesson,g2.short_code,p2.prob,coalesce(p2.item,'')) target_label
          FROM submission_material_reassignments x
          JOIN problems p1 ON p1.id=x.source_problem_id JOIN groups g1 ON g1.group_id=p1.group_id
          JOIN problems p2 ON p2.id=x.target_problem_id JOIN groups g2 ON g2.group_id=p2.group_id
          LEFT JOIN users u ON u.id=x.performed_by_user_id WHERE x.id=?""",
        "replacement": "SELECT * FROM submission_entry_replacements WHERE id=?",
        "undo": """SELECT o.*,u.name,u.surname FROM live_mark_operations o LEFT JOIN users u ON u.id=o.teacher_id WHERE o.id=?""",
    }
    return one(c, queries[kind], (event_id,))


def review_link(c, student_id, problem_id):
    return one(
        c,
        """SELECT r.public_id FROM submission_reviews r JOIN submission_threads t ON t.id=r.thread_id
      WHERE t.student_user_id=? AND t.problem_id=? ORDER BY r.created_at DESC,r.id DESC LIMIT 1""",
        (student_id, problem_id),
    )


def legacy_attachment(c, student_id, discussion_id):
    return one(
        c,
        "SELECT attach_path FROM written_tasks_discussions WHERE id=? AND student_id=? AND problem_id>0",
        (discussion_id, student_id),
    )


def reassigned_materials(c, reassignment_id):
    return rows(
        c,
        """SELECT i.item_kind,e.text,a.public_id attachment_id,a.upload_status
      FROM submission_material_reassignment_items i JOIN submission_entries e ON e.id=i.source_entry_id
      LEFT JOIN submission_attachments a ON a.id=i.attachment_id
      WHERE i.reassignment_id=? ORDER BY i.ordinal""",
        (reassignment_id,),
    )


def queue_link(c, student_id, problem_id):
    return one(
        c,
        """SELECT q.public_id FROM written_tasks_queue q
      WHERE q.student_id=? AND q.problem_id=? AND EXISTS(
        SELECT 1 FROM submission_threads t WHERE t.student_user_id=q.student_id AND t.problem_id=q.problem_id)
      ORDER BY q.id DESC LIMIT 1""",
        (student_id, problem_id),
    )


def note_operations(c, student_id, course_id, number):
    return rows(
        c,
        """SELECT o.*,u.surname,u.name FROM live_mark_operations o
      JOIN zoom_conversation z ON z.id=json_extract(o.before_json,'$.visit.conversation_id')
      JOIN groups g ON g.group_id=z.group_id LEFT JOIN users u ON u.id=o.teacher_id
      WHERE o.kind='reaction' AND z.student_id=? AND g.course_id=? AND z.lesson=?
      ORDER BY o.created_at,o.id""",
        (student_id, course_id, number),
    )


def reaction_labels(c):
    return {
        r["reaction_id"]: r["reaction"]
        for r in rows(c, "SELECT reaction_id,reaction FROM reaction_enum")
    }
