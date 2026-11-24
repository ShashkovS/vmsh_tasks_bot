"""Adapters for the same authorized operations used by the Staff interface."""

import json

from multidict import CIMultiDict, MultiDict

from apps.pwa_api import admin_course_routes as courses
from apps.pwa_api import content_routes as content
from apps.pwa_api import lesson_block_routes as blocks
from apps.pwa_api import problem_release_routes as release
from apps.pwa_api import submission_routes as submissions
from apps.pwa_api.middleware import PWA_AUTHENTICATED_SESSION


class StaffCommand(dict):
    """Bounded JSON command context; only the server selects the handler and actor."""

    content_type = "application/json"

    def __init__(
        self,
        request,
        session,
        *,
        method="GET",
        path=None,
        query=None,
        body=None,
        etag=None,
    ):
        super().__init__(request_id=request["request_id"])
        self[PWA_AUTHENTICATED_SESSION] = session
        self.app = request.app
        self.method = method
        self.match_info = path or {}
        self.query = MultiDict(query or {})
        self.headers = CIMultiDict({"If-Match": etag} if etag else {})
        self._data = (
            json.dumps(body, ensure_ascii=False).encode() if body is not None else b""
        )
        self.content_length = len(self._data)

    async def read(self):
        return self._data

    async def json(self):
        return json.loads(self._data)


def unpack(response):
    result = json.loads(response.body)
    if "ETag" in response.headers:
        result["etag"] = response.headers["ETag"]
    return result


# Names, identifiers and argument descriptions also drive the MCP reference.
OPERATIONS = {
    "create_lesson": (
        courses.create_group_lesson,
        "POST",
        "",
        "idempotencyKey (reuse on retry), schemaVersion=1, courseId, groupId, lessonNumber, title, cycleAnchorDate, businessTimezone, opensLocalTime, submissionClosesLocalTime, hintScheduledLocalTime, solutionScheduledLocalTime",
    ),
    "lesson_window": (
        content.get_lesson_window,
        "GET",
        "group_lesson_id",
        "Read lesson dates, timezone and ETag.",
    ),
    "create_lesson_window": (
        content.create_lesson_window,
        "POST",
        "group_lesson_id",
        "opensLocalTime, hintScheduledLocalTime, solutionScheduledLocalTime, businessTimezone, submissionClosesLocalTime, confirmSubmissionCutoff",
    ),
    "set_lesson_dates": (
        content.update_lesson_window_schedule,
        "PATCH",
        "group_lesson_id",
        "opensLocalTime, hintScheduledLocalTime, solutionScheduledLocalTime, businessTimezone",
    ),
    "set_submission_cutoff": (
        content.update_submission_cutoff,
        "PATCH",
        "group_lesson_id",
        "submissionClosesLocalTime, businessTimezone, confirmChange=true. Use the current time to close, a future deadline to reopen.",
    ),
    "material_history": (
        content.staff_content_history,
        "GET",
        "?groupLesson",
        "Read revisions, scheduled and active publications for one group lesson.",
    ),
    "material_diagnostics": (
        content.content_diagnostics,
        "GET",
        "revision_id",
        "Read source diagnostics including line and column.",
    ),
    "material_assets": (
        content.list_content_revision_assets,
        "GET",
        "revision_id",
        "Read references and missing assets.",
    ),
    "compile_material": (
        content.compile_content_revision,
        "POST",
        "revision_id",
        "Compile the revision after supplying assets. Supply its ETag.",
    ),
    "problem_matches": (
        content.get_problem_matches,
        "GET",
        "revision_id",
        "Read proposed mappings to catalog problems.",
    ),
    "save_problem_matches": (
        content.put_problem_matches,
        "PUT",
        "revision_id",
        "matches: rows with sourceOrdinal, sourceItem, decision, problemId",
    ),
    "metadata_grid": (
        content.get_metadata_grid,
        "GET",
        "group_lesson_id ?revisionId",
        "Read editable rows and their review ETag.",
    ),
    "generate_metadata": (
        content.generate_metadata_grid,
        "POST",
        "group_lesson_id",
        "revisionId, confirmedOverwrite; optional problemTypes. Generate a draft with the configured course model.",
    ),
    "save_metadata_grid": (
        content.put_metadata_grid,
        "PUT",
        "group_lesson_id",
        "revisionId, rows. Use the ETag and the complete editable grid.",
    ),
    "material_figures": (
        content.content_figure_layout,
        "GET",
        "revision_id",
        "List occurrences, layout version and allowed positions.",
    ),
    "set_figure_layout": (
        content.content_figure_layout,
        "PUT",
        "revision_id",
        "version, entries. Apply the selected occurrence positions.",
    ),
    "set_figure_scale": (
        content.put_content_figure_scale,
        "PUT",
        "revision_id",
        "assetId, scale",
    ),
    "publish_material": (
        content.publish_content_revision,
        "POST",
        "",
        "groupLessonId, kind, revisionId, mode, scheduledLocalTime, businessTimezone, expectedCurrentPublicationId, expectedCurrentVersion, expectedScheduledPublicationId, expectedScheduledVersion",
    ),
    "cancel_publication": (
        content.cancel_scheduled_publication,
        "POST",
        "publication_id",
        "Cancel a scheduled publication using its ETag.",
    ),
    "hide_material": (
        content.hide_published_content,
        "POST",
        "publication_id",
        "Hide the selected publication using its ETag.",
    ),
    "lesson_blocks": (
        blocks.get_staff_lesson_blocks,
        "GET",
        "group_lesson_id",
        "Read before/after markdown, versions and publications.",
    ),
    "save_lesson_block": (
        blocks.save_lesson_block_draft,
        "PUT",
        "group_lesson_id position",
        "markdown, document. Save a draft at before or after.",
    ),
    "publish_lesson_block": (
        blocks.publish_lesson_block,
        "POST",
        "group_lesson_id position",
        "revisionId, mode, scheduledAt",
    ),
    "hide_lesson_block": (
        blocks.hide_lesson_block,
        "DELETE",
        "group_lesson_id position",
        "Hide the current publication using its ETag.",
    ),
    "cancel_lesson_block": (
        blocks.cancel_lesson_block_publication,
        "DELETE",
        "group_lesson_id position",
        "Cancel pending block publication.",
    ),
    "problem_availability": (
        release.get_problem_release,
        "GET",
        "group_lesson_id ?revisionId",
        "Read open/closed state by problem ordinal.",
    ),
    "set_problem_availability": (
        release.change_problem_release,
        "PUT",
        "group_lesson_id",
        "conditionRevisionId, changes: [{sourceOrdinal,isOpen}]",
    ),
    "preview_recheck": (
        submissions.get_test_attempt_recheck_preview,
        "GET",
        "problem_public_id",
        "Read exact impact and problemRevision before retesting.",
    ),
    "recheck_problem": (
        submissions.recheck_test_attempts,
        "POST",
        "problem_public_id",
        "schemaVersion=1, problemRevision from preview_recheck",
    ),
}
