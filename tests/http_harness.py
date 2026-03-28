from __future__ import annotations

from typing import Any

from yarl import URL


class FakeRequest:
    def __init__(
        self,
        *,
        method: str = "GET",
        path: str = "/",
        headers: dict[str, str] | None = None,
        json_data: Any = None,
        json_exc: Exception | None = None,
        post_data: dict[str, Any] | None = None,
        cookies: dict[str, str] | None = None,
    ):
        self.method = method
        self.path = path
        self.headers = headers or {}
        self._json_data = json_data
        self._json_exc = json_exc
        self._post_data = post_data or {}
        self.cookies = cookies or {}
        self.url = URL(f"http://testserver{path}")

    async def json(self):
        if self._json_exc is not None:
            raise self._json_exc
        return self._json_data

    async def post(self):
        return self._post_data
