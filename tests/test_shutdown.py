from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from helpers import shutdown


class FakeTask:
    def __init__(self, name: str, module: str, *, done: bool = False):
        self._coro = SimpleNamespace(__qualname__=name, __module__=module)
        self._done = done
        self.cancelled = False

    def get_coro(self):
        return self._coro

    def done(self):
        return self._done

    def cancel(self):
        self.cancelled = True


def test_is_valuable_task_filters_project_and_ignored_tasks():
    valuable = FakeTask("prc_teacher_select_action", "handlers.teacher_handlers")
    ignored_by_module = FakeTask("something", "asyncio.tasks")
    ignored_by_name = FakeTask("start_polling", "handlers.teacher_handlers")

    assert shutdown._is_valuable_task(valuable) is True
    assert shutdown._is_valuable_task(ignored_by_module) is False
    assert shutdown._is_valuable_task(ignored_by_name) is False


@pytest.mark.asyncio
async def test_wait_for_valuable_tasks_cancels_ignored_and_logs_pending(monkeypatch):
    valuable = FakeTask("project_task", "handlers.student_handlers")
    ignored = FakeTask("network_task", "aiohttp.client")
    logger = SimpleNamespace(messages=[])
    logger.warning = logger.messages.append

    async def fake_wait(tasks, timeout):
        assert tasks == [valuable]
        assert timeout == 1.5
        return set(), {valuable}

    monkeypatch.setattr(shutdown, "partition_pending_tasks", lambda: ([valuable], [ignored]))
    monkeypatch.setattr(asyncio, "wait", fake_wait)

    await shutdown.wait_for_valuable_tasks(logger, timeout=1.5)

    assert ignored.cancelled is True
    assert any("Waiting for 1 task" in message for message in logger.messages)
    assert any("Pending task" in message for message in logger.messages)
