"""Shared MCP/HTTP inputs; no runtime config imports. See ai-review-assistant.md."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

PublicId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._:-]{0,127}$")]
Snapshot = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
Cursor = Annotated[str, StringConstraints(min_length=1, max_length=128)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CatalogQuery(Input):
    courseId: PublicId | None = None
    groupId: PublicId | None = None
    lessonId: PublicId | None = None
    cursor: Cursor | None = None


class PendingQuery(CatalogQuery):
    problemId: PublicId | None = None
    suggestions: Literal["any", "with", "without"] = "any"


class ProblemQuery(Input):
    problemId: PublicId


class CommentsQuery(Input):
    lessonId: PublicId | None = None
    problemId: PublicId | None = None
    cursor: Cursor | None = None


class SubmissionsQuery(ProblemQuery):
    status: Literal["pending", "reviewed", "all"] = "all"
    pageSize: Annotated[int, Field(ge=1, le=20)] = 10
    cursor: Cursor | None = None


class PreviousLessonsQuery(Input):
    lessonId: PublicId
    count: Annotated[int, Field(ge=1, le=20)] = 3


class LessonImageQuery(Input):
    lessonId: PublicId
    snapshot: Snapshot
    imageId: Annotated[str, StringConstraints(min_length=1, max_length=256)]


class ContextQuery(Input):
    caseId: PublicId


class SnapshotQuery(ContextQuery):
    snapshot: Snapshot


class DialogueQuery(SnapshotQuery):
    cursor: Cursor | None = None


class ImageQuery(SnapshotQuery):
    imageId: Annotated[str, StringConstraints(min_length=1, max_length=256)]


class SuggestionsQuery(ContextQuery):
    cursor: Cursor | None = None


class SubmitQuery(SnapshotQuery):
    idempotencyKey: Cursor
    comment: Annotated[str, StringConstraints(max_length=100_000)] | None = None
    verdict: Annotated[int, Field(ge=11, le=17)] | None = None
    analysis: Annotated[str, StringConstraints(max_length=100_000)] | None = None
    source: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    model: Annotated[str, StringConstraints(max_length=200)] | None = None


TOOLS = {
    "list_courses": CatalogQuery,
    "list_groups": CatalogQuery,
    "list_lessons": CatalogQuery,
    "list_problems": CatalogQuery,
    "get_problem": ProblemQuery,
    "list_pending_reviews": PendingQuery,
    "list_review_comments": CommentsQuery,
    "get_problem_submissions": SubmissionsQuery,
    "get_previous_lesson_materials": PreviousLessonsQuery,
    "get_lesson_material_image": LessonImageQuery,
    "get_review_context": ContextQuery,
    "get_review_dialogue": DialogueQuery,
    "get_review_image": ImageQuery,
    "list_ai_suggestions": SuggestionsQuery,
    "submit_ai_suggestion": SubmitQuery,
}
