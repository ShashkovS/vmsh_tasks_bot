"""HTTP contracts and authorisation for series routing and history."""

import pytest
from pwa_tests.integration import test_review_queue_http_api as fixtures
from pwa_tests.integration.test_review_entry_transfers import add_target
from models.pwa import review_transfers

review_http = fixtures.review_http


@pytest.mark.asyncio
async def test_transfer_http_full_entry_and_authenticated_projections(
    review_http, monkeypatch
):
    f = review_http

    class Clock:
        @staticmethod
        def now(tz):
            return fixtures.NOW

    monkeypatch.setattr(review_transfers, "datetime", Clock)
    target = f.factory.run_write(add_target)
    queue = f.queue_public_ids[0]
    cookie = fixtures._cookie(f, "full")
    headers = fixtures._headers(unsafe=True)
    claim = await f.client.post(
        f"/staff/api/v1/review/items/{queue}/claim",
        json={"schemaVersion": 1},
        cookies=cookie,
        headers=headers,
    )
    assert claim.status == 200, await claim.text()
    lease = (await claim.json())["lease"]
    preview = await f.client.post(
        f"/staff/api/v1/review/items/{queue}/transfer-preview",
        json={"schemaVersion": 1, "entryId": "se-1", "claimToken": lease["claimToken"]},
        cookies=cookie,
        headers=headers,
    )
    assert preview.status == 200, await preview.text()
    p = await preview.json()
    payload = {
        "schemaVersion": 1,
        "entryId": "se-1",
        "claimToken": lease["claimToken"],
        "targetProblemId": target,
        "sourceVersion": p["sourceVersion"],
        "entryVersion": p["entryVersion"],
        "targetVersion": 0,
        "targetThreadId": None,
        "mode": "clone",
        "idempotencyKey": "http-clone",
    }
    response = await f.client.post(
        f"/staff/api/v1/review/items/{queue}/transfer",
        json=payload,
        cookies=cookie,
        headers=headers,
    )
    assert response.status == 200, await response.text()
    first = await response.json()
    response = await f.client.post(
        f"/staff/api/v1/review/items/{queue}/transfer",
        json=payload,
        cookies=cookie,
        headers=headers,
    )
    assert response.status == 200 and await response.json() == first
    denied = await f.client.post(
        f"/staff/api/v1/review/items/{queue}/transfer",
        json=payload,
        cookies=fixtures._cookie(f, "partial"),
        headers=headers,
    )
    assert denied.status == 403, await denied.text()
    history = await f.client.get(
        "/staff/api/v1/review/series/p-1/history",
        cookies=cookie,
        headers=fixtures._headers(),
    )
    assert history.status == 200 and (await history.json())["items"] == []
    condition = await f.client.get(
        "/staff/api/v1/review/series/p-1/condition?entry=se-1",
        cookies=cookie,
        headers=fixtures._headers(),
    )
    assert condition.status == 200, await condition.text()
    missing = await f.client.get(
        "/staff/api/v1/review/series/p-1/current?review=r-999",
        cookies=cookie,
        headers=fixtures._headers(),
    )
    assert missing.status == 404
