# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional, Generator

from helpers.consts import *
from helpers.config import logger
import db_methods as db


def _normilize_token(token: str, *, RU_TO_EN=str.maketrans('УКЕНХВАРОСМТукехарос', 'YKEHXBAPOCMTykexapoc')) -> str:
    return token.strip().translate(RU_TO_EN).lower()


@dataclass
class User:
    chat_id: int
    type: USER_TYPE
    level: LEVEL
    name: str
    surname: str
    middlename: str
    token: str
    online: ONLINE_MODE
    grade: int
    birthday: date
    id: int = None

    def __post_init__(self):
        # Заполняем дефолтные значения
        if not self.level:
            self.level = LEVEL.NOVICE
        if not self.online:
            self.online = ONLINE_MODE.ONLINE
        # Заливаем в базу, если значение не из базы
        if self.id is None:
            self.id = db.user.insert(self.__dict__)
        # Превращаем константы в enum'ы
        self.type = USER_TYPE(self.type)
        self.level = LEVEL(self.level) if self.level else None
        self.online = ONLINE_MODE(self.online) if self.online else None

    def set_chat_id(self, chat_id: int):
        db.user.set_chat_id(self.id, chat_id)
        self.chat_id = chat_id

    def set_level(self, level: LEVEL):
        db.user.set_level(self.id, level.value)
        db.log.log_change(self.id, CHANGE.LEVEL, level.value)
        self.level = level

    def set_user_type(self, user_type: USER_TYPE):
        db.user.set_type(self.id, user_type.value)
        self.type = user_type.value

    def set_online_mode(self, online: ONLINE_MODE):
        db.user.set_online_mode(self.id, online.value)
        db.log.log_change(self.id, CHANGE.ONLINE, online.value)
        self.online = online

    def __str__(self):
        return f'{self.name} {self.middlename} {self.surname}'

    def name_for_teacher(self):
        age = ''
        if self.birthday:
            try:
                age = f"возраст: {((datetime.now().date() - date.fromisoformat(self.birthday)).days / 365.25):0.1f}"
            except Exception as e:
                logger.exception(f'Дата рождения не парсится: {self.birthday}')
        if self.grade:
            grade = f'класс: {self.grade}'
        else:
            grade = ''
        return f'{self.name} {self.surname} `{self.token}`\nуровень: {self.level} {grade} {age}'

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
