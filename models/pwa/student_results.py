"""Archive composition; authoritative contract: vmshpwa/docs/student-results.md."""

import json

from db_methods.pwa.content import _overlay_problem_titles
from pathlib import Path
from urllib.parse import urlencode

from db_methods.pwa import student_results as db
from helpers.consts import VERDICT_DECODER


class ArchiveNotFound(Exception):
    pass


def require(value):
    if value is None:
        raise ArchiveNotFound()
    return value


def identity(s):
    return dict(
        studentId=s["public_id"],
        name=" ".join(filter(None, [s["surname"], s["name"]])),
        middleName=s["middlename"],
        grade=s["grade"],
        groups=s.get("groups") or "",
    )


def directory(c):
    return dict(students=[identity(s) for s in db.directory(c)])


def symbol(value):
    return VERDICT_DECODER.get(value, str(value)) if value is not None else ""


def current(r):
    return (
        None
        if r is None
        else dict(
            verdict=r["verdict"],
            symbol=symbol(r["verdict"]),
            author=r["author"] or None,
            at=r["ts"],
        )
    )


def group_rows(problems, results):
    groups = {}
    for p in problems:
        g = groups.setdefault(
            p["group_public_id"],
            dict(
                groupId=p["group_public_id"],
                name=p["group_name"],
                code=p["group_code"],
                problems=[],
            ),
        )
        g["problems"].append(
            dict(
                problemId=p["public_id"],
                label=f"{p['lesson']}{p['group_code']}.{p['prob']}{p['item'] or ''}",
                title=p["title"] or "",
                current=current(results.get(p["id"])),
                hasSubmissions=bool(p["submitted"]),
            )
        )
    return list(groups.values())


def overview(c, student_public_id, course_public_id=None):
    s = require(db.student(c, student_public_id))
    courses = db.courses(c, s["id"])
    course = (
        next((v for v in courses if v["public_id"] == course_public_id), None)
        if course_public_id
        else next(iter(courses), None)
    )
    if course_public_id and course is None:
        raise ArchiveNotFound()
    result = dict(
        student=identity(s),
        courses=[dict(courseId=v["public_id"], name=v["name"]) for v in courses],
        courseId=course["public_id"] if course else None,
        lessons=[],
        summaries=[],
    )
    if course is None:
        return result
    problems = db.problems(c, s["id"], course["id"])
    results = {r["problem_id"]: r for r in db.current_results(c, s["id"])}
    active = {(p["lesson"], p["group_public_id"]) for p in problems if p["active"]}
    result["lessons"] = [
        dict(
            number=lesson_row["number"],
            title=lesson_row["title"] or "",
            hasActivity=any(a[0] == lesson_row["number"] for a in active),
        )
        for lesson_row in db.lessons(c, course["id"])
    ]
    for number in sorted({v[0] for v in active}, reverse=True):
        result["summaries"].append(
            dict(
                number=number,
                groups=group_rows(
                    [
                        p
                        for p in problems
                        if p["lesson"] == number
                        and (number, p["group_public_id"]) in active
                    ],
                    results,
                ),
            )
        )
    return result


def document(c, problem_id, revision_id=None):
    m = db.material(c, problem_id, revision_id)
    if m is None:
        return None
    try:
        doc = json.loads(m["content_text"])
    except ValueError, TypeError:
        return None
    if not isinstance(doc, dict) or not isinstance(doc.get("problems"), list):
        return None
    _overlay_problem_titles(c, doc, m["content_revision_id"])
    doc["introduction"] = []
    doc["problems"] = [
        p
        for p in doc["problems"]
        if isinstance(p, dict) and p.get("ordinal") == m["source_ordinal"]
    ]
    return doc if doc["problems"] else None


def legacy_path(root, stored):
    """Resolve legacy paths under solutions without exposing identity-bearing names."""
    if not stored:
        return None
    root = Path(root).resolve()
    raw = Path(stored)
    # Old deployments stored an absolute repository prefix; only the solutions suffix migrates.
    if raw.is_absolute() and not raw.is_relative_to(root):
        if "solutions" not in raw.parts:
            return None
        raw = Path(*raw.parts[raw.parts.index("solutions") + 1 :])
    elif not raw.is_absolute() and raw.parts and raw.parts[0] == "solutions":
        raw = Path(*raw.parts[1:])
    target = (root / raw).resolve()
    return target if target.is_relative_to(root) and target.is_file() else None


def media(
    student,
    attachment_id,
    available=True,
    annotation=None,
    legacy=False,
    media_kind="image",
):
    kind = "legacy-attachments" if legacy else "attachments"
    return dict(
        id=attachment_id,
        url=f"/staff/api/v1/student-results/{student}/{kind}/{attachment_id}",
        available=available,
        kind=media_kind,
        annotation=annotation,
    )


def event_payload(c, index, s, p, root):
    kind = index["kind"]
    r = db.event_record(c, kind, index["id"])
    event = dict(
        id=f"{kind}:{index['id']}",
        kind=kind,
        at=index["ts"],
        author=None,
        authorKind="system",
        source="archive",
        text=None,
        verdict=None,
        symbol="",
        revisionId=None,
        attachments=[],
        reviewId=None,
        internal=False,
        action=None,
        transfer=None,
        checkStatus=None,
    )
    author = " ".join(filter(None, [r.get("surname"), r.get("name")]))
    event["author"] = author or None
    if kind == "entry":
        event.update(
            text=r["text"],
            source=r["channel"],
            revisionId=r["revision_id"],
            author=author or None,
            authorKind=r["author_kind"],
        )
        event["attachments"] = [
            media(
                s["public_id"],
                a["public_id"],
                a["upload_status"] in ("stored", "locked"),
            )
            for a in db.attachments(c, r["id"])
        ]
    elif kind == "test":
        answer = json.loads(r["answer_payload_json"])
        event.update(
            source="pwa",
            text=answer if isinstance(answer, str) else answer.get("displayAnswer", ""),
            verdict=r["verdict"],
            revisionId=r["revision_id"],
            author=identity(s)["name"],
            authorKind="student",
        )
        event["checkStatus"] = r["check_status"]
    elif kind == "review":
        event.update(
            source=r["source"],
            text=r["text"],
            verdict=r["verdict"],
            reviewId=r["public_id"],
            authorKind="ai" if r["source"] == "ai" else "teacher",
        )
        event["attachments"] = [
            media(
                s["public_id"],
                a["attachment_id"],
                annotation=dict(
                    attachmentId=a["attachment_id"],
                    schemaVersion=a["schema_version"],
                    rotation=a["rotation"],
                    marks=json.loads(a["marks_json"]),
                ),
            )
            for a in db.annotations(c, r["id"])
        ]
    elif kind == "discussion":
        event.update(
            source="telegram",
            text=r["text"],
            author=author or identity(s)["name"],
            authorKind="teacher" if r["teacher_id"] is not None else "student",
        )
        if r["attach_path"]:
            target = legacy_path(root, r["attach_path"])
            if target and target.suffix.lower() == ".txt":
                try:
                    archived_text = target.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    archived_text = None
                    event["attachments"] = [
                        media(
                            s["public_id"],
                            str(r["id"]),
                            False,
                            legacy=True,
                            media_kind="file",
                        )
                    ]
                event["text"] = "\n".join(
                    filter(
                        None,
                        [
                            event["text"],
                            archived_text,
                        ],
                    )
                )
            else:
                event["attachments"] = [
                    media(
                        s["public_id"],
                        str(r["id"]),
                        bool(target),
                        legacy=True,
                        media_kind="image"
                        if Path(r["attach_path"]).suffix.lower()
                        in (".jpg", ".jpeg", ".png", ".webp", ".gif")
                        else "file",
                    )
                ]
    elif kind == "result":
        event.update(
            text=r["answer"],
            verdict=r["verdict"],
            source={3: "zoom", 4: "school"}.get(r["res_type"], "archive"),
        )
    elif kind in ("reaction", "student_reaction", "legacy_reaction"):
        event.update(
            text=r.get("reaction"),
            source="staff" if kind == "reaction" else "archive",
            internal=kind == "reaction"
            or (kind == "legacy_reaction" and r["reaction_type_id"] in (100, 300)),
        )
        event["action"] = r.get("event_kind")
        if r.get("event_kind") == "deleted":
            event["text"] = None
    elif kind == "transfer":
        event.update(
            source="staff",
            transfer=dict(
                mode=r["mode"],
                source=f"{r['source_number']}{r['source_item'] or ''}",
                target=f"{r['target_number']}{r['target_item'] or ''}",
            ),
        )
    elif kind == "reassignment":
        event.update(
            source="staff",
            text=r["reason"],
            transfer=dict(
                mode="move", source=r["source_label"], target=r["target_label"]
            ),
        )
        materials = db.reassigned_materials(c, r["id"])
        event["text"] = (
            "\n".join(
                filter(
                    None,
                    [
                        r["reason"],
                        *[
                            m["text"]
                            for m in materials
                            if m["item_kind"] == "entry_text"
                        ],
                    ],
                )
            )
            or None
        )
        event["attachments"] = [
            media(
                s["public_id"],
                m["attachment_id"],
                m["upload_status"] in ("stored", "locked"),
            )
            for m in materials
            if m["attachment_id"]
        ]
    elif kind == "replacement":
        event.update(source="pwa", author=identity(s)["name"])
    elif kind == "undo":
        before = json.loads(r["before_json"])
        event.update(source="staff", verdict=before.get("verdict"))
    event["symbol"] = symbol(event["verdict"])
    return event


def history(c, student_public_id, problem_public_id, root, cursor=None):
    s = require(db.student(c, student_public_id))
    p = require(db.problem(c, problem_public_id))
    events = db.event_index(c, s["id"], p["id"])
    start = 0
    if cursor:
        found = next(
            (i for i, e in enumerate(events) if f"{e['kind']}:{e['id']}" == cursor),
            None,
        )
        if found is None:
            raise ArchiveNotFound()
        start = found + 1
    batch = events[start : start + 50]
    return dict(
        events=[event_payload(c, e, s, p, root) for e in batch],
        nextCursor=f"{batch[-1]['kind']}:{batch[-1]['id']}"
        if batch and start + 50 < len(events)
        else None,
        total=len(events),
    )


def lesson(c, student_public_id, course_public_id, number, root):
    s = require(db.student(c, student_public_id))
    course = require(
        next(
            (v for v in db.courses(c, s["id"]) if v["public_id"] == course_public_id),
            None,
        )
    )
    require(
        next(
            (
                lesson_row
                for lesson_row in db.lessons(c, course["id"])
                if lesson_row["number"] == number
            ),
            None,
        )
    )
    problems = db.problems(c, s["id"], course["id"], number)
    results = {r["problem_id"]: r for r in db.current_results(c, s["id"])}
    active_groups = {p["group_public_id"] for p in problems if p["active"]}
    tables = group_rows(
        [
            p
            for p in problems
            if not active_groups or p["group_public_id"] in active_groups
        ],
        results,
    )
    groups = group_rows([p for p in problems if p["submitted"]], results)
    ids = {p["public_id"]: p["id"] for p in problems}
    legacy_conditions = {p["public_id"]: p["prob_text"] for p in problems}
    for g in groups:
        for p in g["problems"]:
            p["document"] = document(c, ids[p["problemId"]])
            p["legacyCondition"] = (
                (legacy_conditions[p["problemId"]] or None)
                if p["document"] is None
                else None
            )
            p["history"] = history(c, student_public_id, p["problemId"], root)
            link = db.review_link(c, s["id"], ids[p["problemId"]])
            queue = db.queue_link(c, s["id"], ids[p["problemId"]])
            p["reviewUrl"] = (
                "/staff/review/" + queue["public_id"]
                if queue
                else None
                if link is None
                else "/staff/review/history?"
                + urlencode(dict(review=link["public_id"]))
            )
    return dict(
        number=number,
        groups=groups,
        tables=tables,
        notes=lesson_notes(c, s["id"], course["id"], number),
    )


def lesson_notes(c, student_id, course_id, number):
    operations = db.note_operations(c, student_id, course_id, number)
    covered = {
        json.loads(o["before_json"])["visit"]["conversation_id"] for o in operations
    }
    result = [
        dict(n, action="current")
        for n in db.notes(c, student_id, course_id, number)
        if n["id"] not in covered
    ]
    labels = db.reaction_labels(c)
    for operation in operations:
        author = " ".join(filter(None, [operation["surname"], operation["name"]]))
        for at, state, action in [
            (operation["created_at"], operation["after_json"], "changed"),
            (operation["undone_at"], operation["before_json"], "undo"),
        ]:
            if at is None:
                continue
            reactions = json.loads(state).get("reactions", [])
            result.append(
                dict(
                    id=operation["id"] + action,
                    ts=at,
                    reaction_at=at,
                    author=author,
                    reaction=" · ".join(labels.get(r, str(r)) for r in reactions)
                    or None,
                    action=action,
                )
            )
    return sorted(result, key=lambda n: n["reaction_at"] or n["ts"])
