# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Optional
import secrets

import db_methods as db
from .user import User

class Webtoken:
    @staticmethod
    def gen_new_webtoken(tok_len=16, chars='23456789abcdefghijkmnpqrstuvwxyz') -> str:
        return ''.join(secrets.choice(chars) for _ in range(tok_len))

    @staticmethod
    def user_by_webtoken(webtoken: str) -> Optional[User]:
        if not webtoken:
            return None
        user_id = db.web_token.get_user_id(webtoken)
        return user_id and User.get_by_id(user_id)  # None -> None

    @staticmethod
    def webtoken_by_user(user: User) -> str:
        if not user:
            return None
        webtoken = db.web_token.get_by_user_id(user.id)
        if webtoken is None:
            webtoken = Webtoken.gen_new_webtoken()
            db.web_token.insert(user.id, webtoken)
        return webtoken
