"""Business limit refusals must not trigger transport retries, including old replays."""

import pytest

from apps.pwa_api.errors import PwaApiError
from apps.pwa_api.submission_routes import _translate_submission_errors
from db_methods.pwa.submissions import TestSubmissionRejected as Rejected


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["test_attempt_hour_limit", "test_attempt_day_limit"])
async def test_old_limit_replay_is_not_transport_throttling(code):
    @_translate_submission_errors
    async def handler(request):
        raise Rejected(code=code, message="Лимит", http_status=429)

    with pytest.raises(PwaApiError) as caught:
        await handler(None)
    assert caught.value.status == 422
    assert caught.value.code == code
