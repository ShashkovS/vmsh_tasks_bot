# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional, Generator

from helpers.consts import CHANGE, ONLINE_MODE, USER_TYPE
from models.pwa.auth import normalize_telegram_token
from helpers.config import logger
from models.group import Group
from helpers.trace import emit_trace

import db_methods as db


def _normilize_token(token: str) -> str:
    """Compatibility alias for the historical misspelled helper name."""

    return normalize_telegram_token(token)


@dataclass
class User:
    chat_id: int
    type: USER_TYPE
    name: str
    surname: str
    middlename: str
    token: str
    online: ONLINE_MODE
    grade: int
    birthday: Optional[date|str]
    group_id: Optional[str] = None
    allowed_groups: Optional[str] = None
    allowed_groups_set: set[str] = None
    _cached_group: Optional[Group] = None
    id: int = None
    # Opaque browser identity is assigned by the Phase-1 activation/backfill.
    # It stays optional so legacy Telegram rows remain readable before cutover.
    public_id: Optional[str] = None

    def __post_init__(self):
        if not self.online:
            self.online = ONLINE_MODE.ONLINE
        user_type = USER_TYPE(self.type) if self.type is not None else None
        if not self.group_id and user_type == USER_TYPE.STUDENT:
            default_group = db.group.get_default()
            if default_group:
                self.group_id = default_group['group_id']
        # Заливаем в базу, если значение не из базы
        if self.id is None:
            self.id = db.user.insert(self.__dict__)
        # Превращаем константы в enum'ы
        self.type = USER_TYPE(self.type)
        self.online = ONLINE_MODE(self.online) if self.online else None
        if self.allowed_groups:
            self.allowed_groups_set = {item for item in self.allowed_groups.split(';') if item}
        else:
            self.allowed_groups_set = set()

    def set_chat_id(self, chat_id: int):
        db.user.set_chat_id(self.id, chat_id)
        self.chat_id = chat_id

    def set_group_id(self, group_id: str):
        prev_group_id = self.group_id
        db.user.set_group_id(self.id, group_id)
        db.log.log_change(self.id, CHANGE.GROUP, group_id)
        self.group_id = group_id
        self._cached_group = None
        emit_trace(
            "user.group.changed",
            user_id=self.id,
            chat_id=self.chat_id,
            state_from=prev_group_id,
            state_to=group_id,
            group_id=group_id,
        )

    def set_allowed_groups(self, allowed_groups: str):
        db.user.set_allowed_groups(self.id, allowed_groups)
        self.allowed_groups = allowed_groups
        self.allowed_groups_set = {item for item in (allowed_groups or '').split(';') if item}

    def can_access_group(self, group_id: str) -> bool:
        if not group_id:
            return False
        allowed = self.allowed_groups_set
        if allowed:
            return group_id in allowed
        if self.type and self.type & USER_TYPE.TEACHER_OR_ADMIN:
            return True
        return self.group_id == group_id

    def accessible_group_ids(self):
        allowed = self.allowed_groups_set
        if allowed:
            return allowed
        if self.type and self.type & USER_TYPE.TEACHER_OR_ADMIN:
            return {row['group_id'] for row in db.group.get_active()}
        return {self.group_id} if self.group_id else set()

    @property
    def group(self) -> Optional[Group]:
        if self._cached_group:
            return self._cached_group
        if not self.group_id:
            return None
        self._cached_group = Group.get_by_id(self.group_id)
        return self._cached_group

    @property
    def group_code(self) -> str:
        group = self.group
        if group and group.short_code:
            return group.short_code
        return self.group_id or ''

    def set_user_type(self, user_type: USER_TYPE):
        db.user.set_type(self.id, user_type.value)
        self.type = user_type.value

    def set_online_mode(self, online: ONLINE_MODE):
        prev_online = self.online
        db.user.set_online_mode(self.id, online.value)
        db.log.log_change(self.id, CHANGE.ONLINE, online.value)
        self.online = online
        emit_trace(
            "user.mode.changed",
            user_id=self.id,
            chat_id=self.chat_id,
            state_from=(prev_online.value if prev_online is not None else None),
            state_to=online.value,
            group_id=self.group_id,
        )

    def __str__(self):
        return f'{self.name} {self.middlename} {self.surname}'

    @property
    def name_for_teacher(self):
        age = ''
        if self.birthday:
            try:
                age = f"возраст: {((datetime.now().date() - date.fromisoformat(self.birthday)).days / 365.25):0.1f}"
            except Exception:
                logger.exception(f'Дата рождения не парсится: {self.birthday}')
        if self.grade:
            grade = f'класс: {self.grade}'
        else:
            grade = ''
        group = self.group
        group_label = (group and group.public_name) or self.group_id or ''
        return f'{self.name} {self.surname} `{self.token}`\nгруппа: {group_label} {grade} {age}'

    @classmethod
    def all(cls) -> Generator[User, None, None]:
        for user in db.user.get_all_by_type():
            yield cls(**user)

    @classmethod
    def all_students(cls) -> Generator[User, None, None]:
        for user in db.user.get_all_by_type(USER_TYPE.STUDENT):
            yield cls(**user)

    @classmethod
    def all_teachers(cls) -> Generator[User, None, None]:
        for user in db.user.get_all_by_type(USER_TYPE.TEACHER):
            yield cls(**user)

    @classmethod
    def get_by_chat_id(cls, chat_id: int) -> Optional[User]:
        user = db.user.get_by_chat_id(chat_id)
        return user and cls(**user)  # None -> None

    @classmethod
    def get_by_token(cls, token: str) -> Optional[User]:
        if not token:
            return None
        user = db.user.get_by_token(_normilize_token(token))
        return user and cls(**user)  # None -> None

    @classmethod
    def get_by_id(cls, id: int) -> Optional[User]:
        user = db.user.get_by_id(id)
        return user and cls(**user)  # None -> None
