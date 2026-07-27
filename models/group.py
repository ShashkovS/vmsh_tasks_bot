# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import db_methods as db


@dataclass
class Group:
    group_id: str
    short_code: str
    broadcast_code: str
    tg_command: str
    public_name: str
    conditions_url: str
    tasks_header_template: str
    switch_message: str
    sort_order: int
    is_active: int
    is_default: int
    allow_self_switch: int
    is_system: int
    score_weight: float
    # Transitional Phase-1 fields are optional until the controlled Phase-11
    # backfill assigns every legacy group to a course. Keeping them on the
    # legacy dataclass lets its SELECT * readers survive the additive migration
    # without making Telegram depend on the new course model.
    public_id: Optional[str] = None
    course_id: Optional[int] = None
    status: Optional[str] = None
    color_key: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    version: int = 1

    def save(self) -> str:
        return db.group.insert(self.__dict__)

    @classmethod
    def get_by_id(cls, group_id: str) -> Optional["Group"]:
        row = db.group.get_by_id(group_id)
        return row and cls(**row)

    @classmethod
    def get_active(cls, include_system: bool = False) -> List["Group"]:
        rows = db.group.get_active(include_system=include_system)
        return [cls(**row) for row in rows]

    @classmethod
    def get_by_short_code(cls, short_code: str) -> List["Group"]:
        rows = db.group.get_by_short_code(short_code)
        return [cls(**row) for row in rows]

    @classmethod
    def get_by_broadcast_code(cls, broadcast_code: str) -> Optional["Group"]:
        row = db.group.get_by_broadcast_code(broadcast_code)
        return row and cls(**row)

    @classmethod
    def get_by_command(cls, tg_command: str) -> Optional["Group"]:
        row = db.group.get_by_command(tg_command)
        return row and cls(**row)

    @classmethod
    def get_default(cls) -> Optional["Group"]:
        row = db.group.get_default()
        return row and cls(**row)
