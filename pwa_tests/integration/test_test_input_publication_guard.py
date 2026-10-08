"""TLF 4 October regression: a reviewed choice problem still needs visible options."""

import json
from dataclasses import replace

import pytest

from models.pwa.content import (
    ContentInvariantError,
    ProblemMatchDecision,
    ProblemMatchDraft,
    ProblemMetadataDraft,
)
from pwa_tests.integration.test_content_repository import (
    _create_group_lesson,
    _create_source_revision,
    content_fixture,
)


async def test_invalid_choice_cannot_be_saved_or_marked_publishable_but_can_be_repaired(
    content_fixture,
):
    fixture = content_fixture
    _, lesson = await _create_group_lesson(
        fixture, course_lesson_public_id="input-lesson", course_id=fixture.course_id,
        lesson_number=42, group_id="content-a", group_lesson_public_id="input-group-lesson",
    )
    _, revision = await _create_source_revision(
        fixture, group_lesson_id=lesson.id, suffix="test-input",
        canonical_document={"problems": [{"ordinal": 1, "source_item": None,
                                          "source_title": "Choice"}]},
    )
    await fixture.repository.resolve_problem_matches(
        revision_public_id=revision.public_id, expected_review_version=1,
        drafts=(ProblemMatchDraft(source_ordinal=1, source_item="1",
                                 decision=ProblemMatchDecision.INSERT_NEW, problem_id=None),),
        actor_user_id=fixture.actor_user_id,
    )
    grid = await fixture.repository.get_problem_metadata_grid(revision_public_id=revision.public_id)
    row = grid.rows[0]
    invalid = ProblemMetadataDraft(
        problem_id=row.problem.problem_id, source_ordinal=1, source_item="1",
        display_number="1", title="Choice", problem_type=1, answer_type=98,
        answer_validation=None, validation_error=None, correct_answer="7",
        correct_answer_checker=None, wrong_answer=None, congratulation=None,
    )
    with pytest.raises(ContentInvariantError, match="no visible options"):
        await fixture.repository.save_problem_metadata_grid(
            revision_public_id=revision.public_id, expected_review_version=grid.review_version,
            drafts=(invalid,), actor_user_id=fixture.actor_user_id,
        )
    assert await fixture.repository.get_problem_metadata_grid(revision_public_id=revision.public_id) == grid
    saved = await fixture.repository.save_problem_metadata_grid(
        revision_public_id=revision.public_id, expected_review_version=grid.review_version,
        drafts=(replace(invalid, answer_validation=" 7 ; 8 ; "),),
        actor_user_id=fixture.actor_user_id,
    )
    assert (await fixture.repository.get_revision_publication_readiness(revision_id=revision.id)).is_ready
    fixture.factory.run_write(lambda connection: connection.execute(
        "UPDATE problem_revisions SET answer_config_json=? WHERE content_revision_id=?",
        (json.dumps(invalid.answer_config), revision.id),
    ))
    readiness = await fixture.repository.get_revision_publication_readiness(revision_id=revision.id)
    assert not readiness.is_ready
    assert readiness.invalid_test_input_count == 1
    # Reading a historical bad draft remains possible; changing to STRING is explicit.
    damaged = await fixture.repository.get_problem_metadata_grid(revision_public_id=revision.public_id)
    assert damaged.rows[0].problem.answer_validation is None
    repaired = await fixture.repository.save_problem_metadata_grid(
        revision_public_id=revision.public_id, expected_review_version=damaged.review_version,
        drafts=(replace(invalid, answer_type=99),), actor_user_id=fixture.actor_user_id,
    )
    assert repaired.review_version > saved.review_version
    assert (await fixture.repository.get_revision_publication_readiness(revision_id=revision.id)).is_ready
    # Legacy content without an enabled answer input remains publishable;
    # submissions._SUBMISSION_CONTEXT_SELECT also excludes NULL answer types.
    fixture.factory.run_write(lambda connection: connection.execute(
        "UPDATE problem_revisions SET answer_type=NULL WHERE content_revision_id=?",
        (revision.id,),
    ))
    assert (await fixture.repository.get_revision_publication_readiness(revision_id=revision.id)).is_ready
