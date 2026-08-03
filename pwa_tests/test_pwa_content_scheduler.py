import asyncio
from collections import deque
from types import SimpleNamespace

import pytest
from aiohttp import web

from apps import pwa_app
from apps.pwa_api.content_routes import (
    PWA_CONTENT_INVALIDATOR,
    PWA_CONTENT_REPOSITORY,
)
from db_methods.pwa.content import GroupLessonContentScope
from helpers.config import config
from helpers.nats_brocker import InProcessBroker
from helpers.pwa.app_keys import RUNTIME_CONFIG
from helpers.pwa.auth_config import load_auth_runtime_config
from models.pwa.content import ContentKind


def _scope() -> GroupLessonContentScope:
    return GroupLessonContentScope(
        group_lesson_id=41,
        group_lesson_public_id="group-lesson-scheduler",
        course_id=7,
        course_public_id="course-scheduler",
        group_id="scheduler-group",
        group_public_id="group-scheduler",
        status="active",
        business_timezone="Europe/Moscow",
    )


def _publication_context(kind: ContentKind = ContentKind.CONDITION):
    return SimpleNamespace(
        scope=_scope(),
        publication=SimpleNamespace(kind=kind),
    )


class DueRepository:
    def __init__(self, *contexts):
        self.contexts = deque(contexts)
        self.public_ids: list[str] = []
        self.calls = 0

    async def activate_next_due_publication(self, *, published_public_id: str):
        self.calls += 1
        self.public_ids.append(published_public_id)
        if self.contexts:
            return self.contexts.popleft()
        return None


@pytest.mark.asyncio
async def test_content_invalidator_publishes_one_general_material_resource():
    class RecordingBroker:
        def __init__(self):
            self.messages = []

        async def publish(self, topic, payload):
            self.messages.append((topic, payload))

    app = web.Application()
    broker = RecordingBroker()
    app[pwa_app.PWA_BROKER] = broker

    await pwa_app.publish_content_invalidation(
        app,
        _scope(),
        ContentKind.SOLUTION,
        "content-published",
    )

    assert broker.messages == [
        (
            pwa_app.NATS_PWA_INVALIDATE,
            {
                "resources": ["group-lessons/group-lesson-scheduler/content/solution"],
                "reason": "content-published",
            },
        )
    ]


@pytest.mark.asyncio
async def test_content_invalidator_contains_broker_failure_after_commit(caplog):
    class FailingBroker:
        async def publish(self, _topic, _payload):
            raise RuntimeError("synthetic broker outage")

    app = web.Application()
    app[pwa_app.PWA_BROKER] = FailingBroker()

    await pwa_app.publish_content_invalidation(
        app,
        _scope(),
        ContentKind.HINT,
        "content-hidden",
    )

    assert "Content invalidation failed after commit" in caplog.text


@pytest.mark.asyncio
async def test_scheduler_drains_due_batch_with_unique_public_ids():
    repository = DueRepository(
        _publication_context(ContentKind.CONDITION),
        _publication_context(ContentKind.HINT),
    )
    invalidations = []

    async def invalidate(scope, kind, reason):
        invalidations.append((scope.group_lesson_public_id, kind, reason))

    app = web.Application()
    app[PWA_CONTENT_REPOSITORY] = repository
    app[PWA_CONTENT_INVALIDATOR] = invalidate

    activated = await pwa_app.activate_due_content_publications(app)

    assert activated == 2
    assert repository.calls == 3
    assert len(set(repository.public_ids)) == 3
    assert all(
        public_id.startswith("publication-scheduled-")
        for public_id in repository.public_ids
    )
    assert invalidations == [
        (
            "group-lesson-scheduler",
            ContentKind.CONDITION,
            "content-schedule-activated",
        ),
        (
            "group-lesson-scheduler",
            ContentKind.HINT,
            "content-schedule-activated",
        ),
    ]


@pytest.mark.asyncio
async def test_scheduler_is_periodic_and_stops_cleanly(monkeypatch):
    repository = DueRepository()
    second_poll = asyncio.Event()
    news_windows: list[tuple[str, str]] = []

    original_activate = repository.activate_next_due_publication

    async def activate_next_due_publication(*, published_public_id):
        result = await original_activate(published_public_id=published_public_id)
        if repository.calls >= 2:
            second_poll.set()
        return result

    repository.activate_next_due_publication = activate_next_due_publication

    async def invalidate(_scope, _kind, _reason):
        raise AssertionError("there are no due rows")

    async def invalidate_due_news(_app, *, after, through):
        news_windows.append((after, through))
        return False

    monkeypatch.setattr(pwa_app, "CONTENT_SCHEDULER_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(pwa_app, "invalidate_due_local_news", invalidate_due_news)
    app = web.Application()
    app[PWA_CONTENT_REPOSITORY] = repository
    app[PWA_CONTENT_INVALIDATOR] = invalidate

    await pwa_app.on_content_scheduler_startup(app)
    task = app[pwa_app.PWA_CONTENT_SCHEDULER_TASK]
    await asyncio.wait_for(second_poll.wait(), timeout=1)
    await pwa_app.on_content_scheduler_shutdown(app)

    assert task.done()
    assert task.cancelled() is False
    assert len(news_windows) >= 2
    assert news_windows[0][1] == news_windows[1][0]


@pytest.mark.asyncio
async def test_news_scan_retries_the_same_window_after_broker_failure(monkeypatch):
    windows: list[tuple[str, str]] = []
    retried = asyncio.Event()

    async def invalidate_due_news(_app, *, after, through):
        windows.append((after, through))
        if len(windows) == 1:
            raise RuntimeError("synthetic broker failure")
        retried.set()
        return False

    monkeypatch.setattr(pwa_app, "CONTENT_SCHEDULER_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(pwa_app, "invalidate_due_local_news", invalidate_due_news)
    app = web.Application()
    app[PWA_CONTENT_REPOSITORY] = DueRepository()
    app[PWA_CONTENT_INVALIDATOR] = None

    await pwa_app.on_content_scheduler_startup(app)
    await asyncio.wait_for(retried.wait(), timeout=1)
    await pwa_app.on_content_scheduler_shutdown(app)

    assert windows[0][0] == windows[1][0]


@pytest.mark.asyncio
async def test_shutdown_waits_for_scheduler_commit_and_invalidation_before_broker():
    events = []
    activation_started = asyncio.Event()
    release_activation = asyncio.Event()

    class BlockingRepository:
        def __init__(self):
            self.returned = False

        async def activate_next_due_publication(self, *, published_public_id):
            del published_public_id
            if self.returned:
                return None
            activation_started.set()
            await release_activation.wait()
            self.returned = True
            events.append("commit")
            return _publication_context()

    class Registry:
        async def shutdown(self):
            events.append("websockets")

    class Broker:
        async def disconnect(self):
            events.append("broker")

    async def invalidate(_scope, _kind, _reason):
        events.append("invalidation")

    app = web.Application()
    app[PWA_CONTENT_REPOSITORY] = BlockingRepository()
    app[PWA_CONTENT_INVALIDATOR] = invalidate
    app[pwa_app.PWA_WEBSOCKET_REGISTRY] = Registry()
    app[pwa_app.PWA_BROKER] = Broker()

    await pwa_app.on_content_scheduler_startup(app)
    await asyncio.wait_for(activation_started.wait(), timeout=1)
    shutdown = asyncio.create_task(pwa_app.on_shutdown(app))
    await asyncio.sleep(0)
    assert events == []

    release_activation.set()
    await asyncio.wait_for(shutdown, timeout=1)

    assert events == ["commit", "invalidation", "websockets", "broker"]


def test_configure_injects_content_invalidator_and_registers_scheduler():
    auth_config = load_auth_runtime_config(config)
    auth_service = SimpleNamespace(runtime_config=auth_config)
    app = web.Application()
    app[RUNTIME_CONFIG] = config

    pwa_app.configure(
        app,
        broker=InProcessBroker("content_scheduler_configure_test"),
        auth_runtime_config=auth_config,
        auth_service=auth_service,
        content_repository=DueRepository(),
    )

    assert PWA_CONTENT_INVALIDATOR in app
    assert pwa_app.on_content_scheduler_startup in app.on_startup
