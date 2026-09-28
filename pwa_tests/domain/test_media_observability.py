import asyncio

import pytest

from helpers.pwa.media_observability import MEDIA_STAGE_DURATION, media_stage
from helpers.pwa.request_trace import RequestTrace, current_trace


@pytest.mark.parametrize('outcome,error', [('ok', None), ('error', ValueError('private')), ('cancelled', asyncio.CancelledError())])
def test_media_stage_records_outcomes_and_preserves_exception(outcome, error):
    metric = MEDIA_STAGE_DURATION.labels('storage.get', outcome)
    before = metric._sum.get()
    trace = RequestTrace()
    token = current_trace.set(trace)
    try:
        if error is None:
            with media_stage('storage.get'):
                pass
        else:
            with pytest.raises(type(error)) as caught:
                with media_stage('storage.get'):
                    raise error
            assert caught.value is error
        assert trace.stages['storage.get'][0] == 1
        assert metric._sum.get() >= before
        assert 'private' not in str(trace.stages)
    finally:
        current_trace.reset(token)


def test_stage_names_are_bounded():
    with pytest.raises(ValueError, match='Unknown'):
        with media_stage('https://private-photo'):
            pass
