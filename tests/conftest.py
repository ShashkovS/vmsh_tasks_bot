# -*- coding: utf-8 -*-
import asyncio
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import db_methods as db
from handlers import admin_handlers, common_handlers, main_handlers, student_handlers, teacher_handlers, student_keyboards
from helpers.features import FEATURES

from tests.live_seed import LiveScenarioBuilder, load_live_seed
from tests.telegram_harness import RecordingBot, TaskTracker


async def _fast_sleep(_seconds=0):
    return None


async def _noop(*args, **kwargs):
    return None


def _get_worker_id():
    return os.environ.get('PYTEST_XDIST_WORKER', 'gw0')


@pytest.fixture()
def live_seed_db(tmp_path):
    db.sql.disconnect()
    db_file = tmp_path / f"live_seed_{_get_worker_id()}.db"
    db.sql.setup(str(db_file))
    seed = load_live_seed()
    yield LiveScenarioBuilder(seed=seed)
    db.sql.disconnect()


@pytest.fixture()
def scenario_env(monkeypatch, live_seed_db):
    original_create_task = asyncio.create_task
    original_sleep = asyncio.sleep
    tracker = TaskTracker(create_task=original_create_task, sleep=original_sleep)
    bot = RecordingBot()

    for module in (main_handlers, student_handlers, teacher_handlers, admin_handlers, common_handlers):
        monkeypatch.setattr(module, "bot", bot)

    monkeypatch.setattr(asyncio, "create_task", tracker.create_task)
    monkeypatch.setattr(asyncio, "sleep", _fast_sleep)

    monkeypatch.setattr(student_handlers, "sleep_and_send_problems_keyboard", _noop)
    monkeypatch.setattr(student_handlers, "refresh_last_student_keyboard", _noop)
    monkeypatch.setattr(teacher_handlers, "sleep_and_send_problems_keyboard", _noop)
    monkeypatch.setattr(teacher_handlers, "prc_teacher_select_action", _noop)

    monkeypatch.setattr(student_handlers, "SAVE_SOL_MODE", FEATURES.SAVE_SOL_IN_TG_ONLY)
    monkeypatch.setattr(student_handlers, "RESULT_MODE", FEATURES.RESULT_IMMEDIATELY)
    monkeypatch.setattr(student_handlers, "RATE_LIMIT_MODE", FEATURES.RATE_LIMIT_NONE)
    monkeypatch.setattr(teacher_handlers, "RESULT_MODE", FEATURES.RESULT_IMMEDIATELY)
    monkeypatch.setattr(student_keyboards, "RESULT_MODE", FEATURES.RESULT_IMMEDIATELY)
    monkeypatch.setattr(student_keyboards, "GAME_MODE", FEATURES.GAME_HIDDEN)
    monkeypatch.setattr(student_keyboards, "PREV_PROBLEMS_MODE", FEATURES.PREV_PROBLEMS_HIDDEN)

    return {"data": live_seed_db, "bot": bot, "tasks": tracker}
