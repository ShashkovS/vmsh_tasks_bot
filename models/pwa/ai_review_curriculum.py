"""Prior-level teaching context; vmshpwa/docs/ai-review-assistant.md.

Read whole documents, including unmatched tasks and introductory text. The
anchor fixes the level and teaching order without guessing the current week.
"""

import json

from db_methods.pwa import ai_review as assistant_db, ai_review_curriculum as db
from db_methods.pwa.reviews import ReviewQueueForbidden, ReviewQueueNotFound
from models.pwa import ai_review as ai


def authorized_lesson(connection, scope, lesson_id):
    lesson = db.lesson(connection, lesson_id)
    if lesson is None:
        raise ReviewQueueNotFound("lesson not found")
    if not scope.allows(lesson):
        raise ReviewQueueForbidden("lesson outside scope")
    return lesson


def lesson_materials(connection, scope, lesson_id):
    lesson = authorized_lesson(connection, scope, lesson_id)
    sources = {}
    for row in db.material_revisions(connection, lesson["id"]):
        prior = sources.get(row["source_id"])
        # Prefer the current student publication over a newer private draft.
        if prior is None or row["published_at"] is not None:
            sources[row["source_id"]] = row
    materials = []
    for row in sources.values():
        materials.append(
            {
                "sourceId": row["source_public_id"],
                "kind": row["kind"],
                "filename": row["logical_filename"],
                "revisionId": row["revision_id"],
                "revisionNumber": row["revision_number"],
                "version": row["version"],
                "status": row["status"],
                "publishedAt": row["published_at"],
                "publicationState": "published"
                if row["published_at"] is not None
                else "unpublished",
                "document": json.loads(row["document"]) if row["document"] else None,
                "latex": row["latex_text"] if not row["document"] else None,
                "availability": "web_ast" if row["document"] else "source_only",
                "problems": [
                    {
                        "problemId": p["problem_id"],
                        "ordinal": p["source_ordinal"],
                        "item": p["source_item"],
                        "title": p["title"],
                        "answerType": p["answer_type"],
                        "answer": json.loads(p["answer_config_json"])
                        if p["answer_config_json"]
                        else None,
                        "answerConfigVersion": p["config_version"],
                    }
                    for p in db.problem_bindings(connection, row["id"])
                ],
                "images": [
                    {
                        "imageId": "content:" + image["public_id"],
                        "name": image["logical_name"],
                        "mimeType": image["media_type"],
                        "sha256": image["sha256"],
                    }
                    for image in assistant_db.material_images(
                        connection, row["revision_id"]
                    )
                ],
            }
        )
    result = {
        "lessonId": lesson["lesson_id"],
        "number": lesson["number"],
        "title": lesson["title"],
        "groupId": lesson["group_public_id"],
        "groupName": lesson["group_name"],
        "courseId": lesson["course_public_id"],
        "status": lesson["status"],
        "materials": materials,
        "missingMaterials": [
            kind
            for kind in ("condition", "hint", "solution")
            if not any(m["kind"] == kind for m in materials)
        ],
    }
    result["snapshot"] = ai.digest(result)
    return result


def previous_materials(connection, scope, query):
    anchor = authorized_lesson(connection, scope, query["lessonId"])
    previous = db.previous_lessons(connection, anchor)
    selected = previous[: query["count"]]
    result = {
        "anchorLessonId": anchor["lesson_id"],
        "anchorNumber": anchor["number"],
        "groupId": anchor["group_public_id"],
        "courseId": anchor["course_public_id"],
        "requestedCount": query["count"],
        "returnedCount": len(selected),
        "availablePreviousCount": len(previous),
        "lessons": [
            lesson_materials(connection, scope, row["lesson_id"])
            for row in reversed(selected)
        ],
    }
    result["snapshot"] = ai.digest(result)
    return result


def material_image(connection, scope, query):
    value = lesson_materials(connection, scope, query["lessonId"])
    ai.require_snapshot(value, query["snapshot"])
    for material in value["materials"]:
        if any(image["imageId"] == query["imageId"] for image in material["images"]):
            return {
                "storage": next(
                    image
                    for image in assistant_db.material_images(
                        connection, material["revisionId"]
                    )
                    if "content:" + image["public_id"] == query["imageId"]
                )
            }
    raise ai.AssistantError("image_not_found", 404)
