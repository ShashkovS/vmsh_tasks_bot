"""Domain policy for correcting an immutable completed written review."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from db_methods.pwa.connection import PwaConnectionFactory
from db_methods.pwa.review_corrections import (
    copy_evidence,
    copy_annotations,
    store_annotations,
    active_review_owner,
    read_verdict_mode,
    evidence_scopes,
    find_replay,
    find_source_review,
    insert_comment,
    insert_event,
    insert_result,
    insert_review,
    invalidate_current_written_results,
    latest_review_public_id,
    recipient_account_public_ids,
    update_thread_result,
)
from db_methods.pwa.reviews import ReviewStaffScope, ReviewAnnotationManifest
from helpers.consts import USER_TYPE, VERDICT, VERDICTS_SOLVED
from models.pwa.course_runtime_settings import DEFAULT_COURSE_RUNTIME_SETTINGS


class ReviewCorrectionNotFound(RuntimeError):
    pass


class ReviewCorrectionForbidden(RuntimeError):
    pass


class ReviewCorrectionStale(RuntimeError):
    pass


class ReviewCorrectionConflict(RuntimeError):
    pass


class ReviewCorrectionInvalid(RuntimeError):
    pass


class ReviewCorrectionLeased(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ReviewCorrectionCommand:
    source_review_public_id: str
    reviewer_user_id: int
    reviewer_type: int
    scope: ReviewStaffScope
    idempotency_key: str
    verdict: int
    comment: str | None
    confirm_without_comment: bool
    annotations: tuple[ReviewAnnotationManifest, ...] | None = None
    expected_latest_review_id: str | None = None
    expected_thread_version: int | None = None
    confirm_replace_newer: bool = False


@dataclass(frozen=True, slots=True)
class ReviewCorrectionReceipt:
    review_public_id: str
    source_review_public_id: str
    thread_public_id: str
    problem_public_id: str
    verdict: int
    status: str
    owner_account_public_ids: tuple[str, ...]
    family_account_public_ids: tuple[str, ...]
    completed_at: datetime
    replayed: bool = False


def _payload(command: ReviewCorrectionCommand) -> dict[str, object]:
    payload = {
        "sourceReviewId": command.source_review_public_id,
        "verdict": command.verdict,
        "comment": command.comment,
        "confirmWithoutComment": command.confirm_without_comment,
    }
    # Preserve legacy idempotency hashes; see vmshpwa/docs/review-history.md.
    if command.expected_latest_review_id is not None:
        payload.update(
            {
                "expectedLatestReviewId": command.expected_latest_review_id,
                "expectedThreadVersion": command.expected_thread_version,
                "confirmReplaceNewer": command.confirm_replace_newer,
                "annotations": None
                if command.annotations is None
                else [annotation.payload() for annotation in command.annotations],
            }
        )
    return payload


def _payload_hash(command: ReviewCorrectionCommand) -> str:
    encoded = json.dumps(
        _payload(command), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


async def correct_written_review(
    factory: PwaConnectionFactory,
    command: ReviewCorrectionCommand,
    *,
    now: datetime | None = None,
) -> ReviewCorrectionReceipt:
    """Append a correction while keeping the original review/evidence intact."""

    if command.verdict not in range(11, 18):
        raise ReviewCorrectionInvalid("written verdict is outside the supported scale")
    comment = command.comment.strip() if command.comment else None
    if command.verdict < 16 and not comment and not command.confirm_without_comment:
        raise ReviewCorrectionInvalid(
            "lower verdict requires a comment or confirmation"
        )
    completed_at = (now or datetime.now(UTC)).astimezone(UTC)
    if (command.expected_latest_review_id is None) != (
        command.expected_thread_version is None
    ):
        raise ReviewCorrectionInvalid("both optimistic expectations are required")
    if command.annotations is not None and command.expected_latest_review_id is None:
        raise ReviewCorrectionInvalid(
            "annotation changes require optimistic expectations"
        )
    payload_sha256 = _payload_hash(command)

    def operation(connection):
        source = find_source_review(connection, command.source_review_public_id)
        if source is None:
            raise ReviewCorrectionNotFound("source review was not found")
        if not command.scope.allows(source) or not all(
            command.scope.allows(evidence)
            for evidence in evidence_scopes(connection, source["id"])
        ):
            raise ReviewCorrectionForbidden("review is outside current Staff scope")
        is_admin = bool(command.reviewer_type & int(USER_TYPE.ADMIN))
        if not is_admin and int(source["reviewer_user_id"]) != command.reviewer_user_id:
            raise ReviewCorrectionForbidden("teacher may correct only their own review")
        replay = find_replay(
            connection, command.reviewer_user_id, command.idempotency_key
        )
        if replay is not None:
            if replay["payload_sha256"] != payload_sha256:
                raise ReviewCorrectionConflict("idempotency key was reused")
            source = find_source_review(connection, command.source_review_public_id)
            if source is None:
                raise ReviewCorrectionNotFound("source review no longer exists")
            owners, family = recipient_account_public_ids(
                connection, int(source["student_user_id"])
            )
            return ReviewCorrectionReceipt(
                review_public_id=str(replay["public_id"]),
                source_review_public_id=command.source_review_public_id,
                thread_public_id=str(replay["thread_public_id"]),
                problem_public_id=str(replay["problem_public_id"]),
                verdict=int(replay["verdict"]),
                status=(
                    "accepted"
                    if VERDICT(int(replay["verdict"])) in VERDICTS_SOLVED
                    else "needs_work"
                ),
                owner_account_public_ids=owners,
                family_account_public_ids=family,
                completed_at=datetime.fromisoformat(
                    str(replay["created_at"]).replace("Z", "+00:00")
                ),
                replayed=True,
            )

        latest_id = latest_review_public_id(connection, int(source["thread_id"]))
        if command.expected_latest_review_id is not None:
            mode = (
                read_verdict_mode(connection, source["course_public_id"])
                or DEFAULT_COURSE_RUNTIME_SETTINGS["verdictMode"]
            )
            allowed = {
                "verdict_plus_minus": {11, 17},
                "verdict_plus_minus_half": {11, 14, 17},
                "verdict_plus_steps": set(range(11, 18)),
            }[mode]
            if command.verdict not in allowed:
                raise ReviewCorrectionInvalid("verdict is outside current course scale")
        if command.expected_latest_review_id is not None and (
            latest_id != command.expected_latest_review_id
            or int(source["thread_version"]) != command.expected_thread_version
        ):
            raise ReviewCorrectionStale("review or thread changed after opening")
        if latest_id != str(source["public_id"]) and not (
            command.expected_latest_review_id is not None
            and command.confirm_replace_newer
        ):
            raise ReviewCorrectionStale("a newer review already exists")
        owner = active_review_owner(connection, source, completed_at)
        if owner is not None and int(owner["teacher_id"]) != command.reviewer_user_id:
            raise ReviewCorrectionLeased(str(owner["display_name"]))

        stored_updated_at = datetime.fromisoformat(
            str(source["thread_updated_at"]).replace("Z", "+00:00")
        )
        effective_completed_at = max(
            completed_at, stored_updated_at + timedelta(microseconds=1)
        )
        effective_completed_at_text = effective_completed_at.isoformat(
            timespec="microseconds"
        ).replace("+00:00", "Z")

        # Legacy result readers choose the best positive row. An explicit
        # correction therefore retires every earlier positive written result
        # before appending the replacement; immutable review history still
        # preserves the exact former verdict shown to the Student.
        invalidate_current_written_results(
            connection,
            student_user_id=int(source["student_user_id"]),
            problem_id=int(source["problem_id"]),
        )
        result_id = insert_result(
            connection,
            student_user_id=int(source["student_user_id"]),
            problem_id=int(source["problem_id"]),
            group_id=str(source["group_id"]),
            lesson=int(source["lesson"]),
            reviewer_user_id=command.reviewer_user_id,
            verdict=command.verdict,
            created_at=effective_completed_at_text,
        )
        author_kind = "admin" if is_admin else "teacher"
        comment_entry_id = (
            None
            if comment is None
            else insert_comment(
                connection,
                thread_id=int(source["thread_id"]),
                author_kind=author_kind,
                author_user_id=command.reviewer_user_id,
                text=comment,
                created_at=effective_completed_at_text,
            )
        )
        review_id, review_public_id = insert_review(
            connection,
            source=source,
            reviewer_user_id=command.reviewer_user_id,
            verdict=command.verdict,
            comment_entry_id=comment_entry_id,
            result_id=result_id,
            idempotency_key=command.idempotency_key,
            payload_sha256=payload_sha256,
            created_at=effective_completed_at_text,
        )
        copy_evidence(
            connection, source_review_id=int(source["id"]), review_id=review_id
        )
        if command.annotations is None:
            copy_annotations(
                connection, int(source["id"]), review_id, effective_completed_at_text
            )
        else:
            try:
                store_annotations(
                    connection,
                    review_id,
                    command.annotations,
                    effective_completed_at_text,
                )
            except ValueError as error:
                raise ReviewCorrectionInvalid(str(error)) from error
        status = (
            "accepted" if VERDICT(command.verdict) in VERDICTS_SOLVED else "needs_work"
        )
        update_thread_result(
            connection,
            thread_id=int(source["thread_id"]),
            result_id=result_id,
            current_status=str(source["thread_status"]),
            status=status,
            comment_created=comment_entry_id is not None,
            created_at=effective_completed_at_text,
        )
        insert_event(
            connection,
            review_id=review_id,
            payload_json=json.dumps(
                {
                    "reviewPublicId": review_public_id,
                    "correctsReviewPublicId": command.source_review_public_id,
                    "supersedesReviewPublicId": latest_id,
                    "studentUserId": source["student_user_id"],
                    "targetProblemId": source["problem_id"],
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            created_at=effective_completed_at_text,
        )
        owners, family = recipient_account_public_ids(
            connection, int(source["student_user_id"])
        )
        return ReviewCorrectionReceipt(
            review_public_id=review_public_id,
            source_review_public_id=command.source_review_public_id,
            thread_public_id=str(source["thread_public_id"]),
            problem_public_id=str(source["problem_public_id"]),
            verdict=command.verdict,
            status=status,
            owner_account_public_ids=owners,
            family_account_public_ids=family,
            completed_at=effective_completed_at,
        )

    return await factory.run_write_async(operation)
