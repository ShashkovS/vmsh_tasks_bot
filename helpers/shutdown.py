# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from typing import Iterable, Tuple

PROJECT_MODULE_PREFIXES = (
    "apps.",
    "handlers.",
    "helpers.",
    "models.",
    "db_methods.",
    "main",
    "__main__",
)

IGNORED_MODULE_PREFIXES = (
    "aiogram.",
    "aiohttp.",
    "asyncio.",
    "yarl.",
    "multidict.",
)

IGNORED_NAME_PARTS = (
    "start_polling",
    "run_tg_bot_in_polling_mode",
    "Client._",
    "Subscription._",
)


def _task_identity(task: asyncio.Task) -> Tuple[str, str]:
    coro = task.get_coro()
    return (
        getattr(coro, "__qualname__", repr(coro)),
        getattr(coro, "__module__", ""),
    )


def _is_valuable_task(task: asyncio.Task) -> bool:
    name, module = _task_identity(task)
    if any(part in name for part in IGNORED_NAME_PARTS):
        return False
    if any(module.startswith(prefix) for prefix in IGNORED_MODULE_PREFIXES):
        return False
    return any(module.startswith(prefix) for prefix in PROJECT_MODULE_PREFIXES)


def partition_pending_tasks() -> Tuple[list[asyncio.Task], list[asyncio.Task]]:
    current = asyncio.current_task()
    valuable = []
    ignored = []
    for task in asyncio.all_tasks():
        if task is current or task.done():
            continue
        if _is_valuable_task(task):
            valuable.append(task)
        else:
            ignored.append(task)
    return valuable, ignored


async def wait_for_valuable_tasks(logger, timeout: float = 20.0) -> None:
    valuable, ignored = partition_pending_tasks()
    for task in ignored:
        task.cancel()
    if not valuable:
        return
    logger.warning(f'Waiting for {len(valuable)} task(s) to finish...')
    _, pending = await asyncio.wait(valuable, timeout=timeout)
    for task in pending:
        name, module = _task_identity(task)
        logger.warning(f'Pending task: {module}.{name}')
