"""Server-side PWA i18n: request language, error translation and catalog tooling.

See helpers/pwa/i18n.py, vmshpwa/scripts/backend_i18n.py and vmshpwa/docs/i18n.md.
"""

from __future__ import annotations

import pytest
from aiohttp import web

from apps import pwa_app
from apps.pwa_api.errors import PwaApiError
from helpers.pwa import i18n
from helpers.pwa.i18n import (
    DEFAULT_LOCALE,
    LOCALE_COOKIE_NAME,
    N_,
    current_locale,
    locale_from_cookies,
    translate,
)
from vmshpwa.scripts import backend_i18n


FAKE_ENGLISH = {
    "Задача {number} уже проверена": "Problem {number} has already been reviewed",
    "Внутренняя ошибка сервера": "Internal server error",
}


@pytest.fixture()
def english_catalog(monkeypatch):
    def fake_catalog(locale: str):
        return FAKE_ENGLISH if locale == "en" else {}

    monkeypatch.setattr(i18n, "_catalog", fake_catalog)


def test_real_catalog_translates_shared_server_error():
    assert translate("en", "Внутренняя ошибка сервера") == "Internal server error"
    assert translate("ru", "Внутренняя ошибка сервера") == "Внутренняя ошибка сервера"


def test_missing_translation_and_unknown_locale_fall_back_to_russian():
    assert (
        translate("en", "Такой строки нет в каталоге") == "Такой строки нет в каталоге"
    )
    assert translate("de", "Внутренняя ошибка сервера") == "Внутренняя ошибка сервера"


def test_params_are_substituted_after_translation(english_catalog):
    del english_catalog
    message = N_("Задача {number} уже проверена")
    assert translate("ru", message, {"number": 7}) == "Задача 7 уже проверена"
    assert (
        translate("en", message, {"number": 7}) == "Problem 7 has already been reviewed"
    )


def test_message_without_params_keeps_literal_braces():
    assert translate("en", "Формат {x}") == "Формат {x}"


@pytest.mark.parametrize(
    ("cookies", "expected"),
    [
        ({LOCALE_COOKIE_NAME: "en"}, "en"),
        ({LOCALE_COOKIE_NAME: "ru"}, "ru"),
        ({LOCALE_COOKIE_NAME: "EN"}, DEFAULT_LOCALE),
        ({LOCALE_COOKIE_NAME: "de"}, DEFAULT_LOCALE),
        ({}, DEFAULT_LOCALE),
    ],
)
def test_request_locale_comes_from_the_device_cookie(cookies, expected):
    assert locale_from_cookies(cookies) == expected


@pytest.fixture()
async def probe_client(aiohttp_client, english_catalog):
    del english_catalog

    async def reviewed(_request):
        raise PwaApiError(
            status=409,
            code="already_reviewed",
            message=N_("Задача {number} уже проверена"),
            params={"number": 3},
        )

    async def crash(_request):
        raise RuntimeError("boom")

    async def locale_echo(_request):
        return web.json_response({"locale": current_locale.get()})

    app = web.Application(middlewares=[pwa_app.pwa_error_middleware])
    app.router.add_get("/student/api/v1/i18n-probe", reviewed)
    app.router.add_get("/student/api/v1/i18n-crash", crash)
    app.router.add_get("/student/api/v1/i18n-locale", locale_echo)
    return await aiohttp_client(app)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cookie", "expected"),
    [
        (None, "Задача 3 уже проверена"),
        ("ru", "Задача 3 уже проверена"),
        ("en", "Problem 3 has already been reviewed"),
    ],
)
async def test_error_middleware_translates_api_errors(probe_client, cookie, expected):
    headers = {"Cookie": f"{LOCALE_COOKIE_NAME}={cookie}"} if cookie else {}
    response = await probe_client.get("/student/api/v1/i18n-probe", headers=headers)

    assert response.status == 409
    error = (await response.json())["error"]
    assert error["code"] == "already_reviewed"
    assert error["message"] == expected


@pytest.mark.asyncio
async def test_unhandled_error_message_uses_request_language(probe_client):
    response = await probe_client.get(
        "/student/api/v1/i18n-crash", headers={"Cookie": f"{LOCALE_COOKIE_NAME}=en"}
    )

    assert response.status == 500
    assert (await response.json())["error"]["message"] == "Internal server error"


@pytest.mark.asyncio
async def test_request_language_is_scoped_to_the_request(probe_client):
    english = await probe_client.get(
        "/student/api/v1/i18n-locale", headers={"Cookie": f"{LOCALE_COOKIE_NAME}=en"}
    )
    default = await probe_client.get("/student/api/v1/i18n-locale")

    assert (await english.json())["locale"] == "en"
    assert (await default.json())["locale"] == DEFAULT_LOCALE
    assert current_locale.get() == DEFAULT_LOCALE


def _write(root, relative: str, source: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_extraction_finds_marked_and_error_messages_but_not_dynamic_ones(tmp_path):
    _write(
        tmp_path,
        "apps/pwa_api/sample_routes.py",
        """
from apps.pwa_api.errors import PwaApiError
from helpers.pwa.i18n import N_, _

LABEL = N_("Метка по умолчанию")

def handler(name):
    title = _("Заголовок")
    raise PwaApiError(status=400, code="bad", message="Проверьте поля формы")

def dynamic(name):
    raise PwaApiError(status=400, code="bad", message=f"Сейчас проверяет {name}")

def english():
    raise PwaApiError(status=400, code="bad", message="Invalid JSON")
""",
    )
    extraction = backend_i18n.extract(
        [tmp_path / "apps/pwa_api/sample_routes.py"], root=tmp_path
    )

    assert extraction.messages == {
        "Метка по умолчанию": {"apps/pwa_api/sample_routes.py"},
        "Заголовок": {"apps/pwa_api/sample_routes.py"},
        "Проверьте поля формы": {"apps/pwa_api/sample_routes.py"},
    }
    assert [(item.origin, item.kind) for item in extraction.dynamic] == [
        ("apps/pwa_api/sample_routes.py", "f-string")
    ]


def test_catalog_round_trip_keeps_translations_quotes_and_newlines(tmp_path):
    messages = {
        'Файл «{name}» не "найден"': {"apps/pwa_api/a.py"},
        "Первая строка\nВторая строка": {"apps/pwa_api/a.py", "models/pwa/b.py"},
        "Без перевода": {"helpers/pwa/c.py"},
    }
    translations = {
        'Файл «{name}» не "найден"': 'File "{name}" was not found',
        "Первая строка\nВторая строка": "First line\nSecond line",
    }
    catalog_path = tmp_path / "en.po"
    catalog_path.write_text(
        backend_i18n.render_catalog(messages, translations), encoding="utf-8"
    )

    assert backend_i18n.read_translations(catalog_path) == {
        **translations,
        "Без перевода": "",
    }
    assert backend_i18n.render_catalog(
        messages, backend_i18n.read_translations(catalog_path)
    ) == catalog_path.read_text(encoding="utf-8")


def test_check_reports_stale_catalog_untranslated_scope_and_dynamic_messages():
    extraction = backend_i18n.Extraction(
        messages={
            "Переведено": {"apps/pwa_api/done.py"},
            "Не переведено": {"apps/pwa_api/done.py"},
            "Чужая область": {"apps/pwa_api/later.py"},
        },
        dynamic=[
            backend_i18n.DynamicMessage("apps/pwa_api/done.py", 12, "f-string"),
            backend_i18n.DynamicMessage("apps/pwa_api/later.py", 3, "concatenation"),
        ],
    )
    translations = {"Переведено": "Translated"}
    in_sync = backend_i18n.render_catalog(extraction.messages, translations)

    problems = backend_i18n.check(
        extraction,
        catalog_text=in_sync,
        translations=translations,
        scopes=["apps/pwa_api/done.py"],
    )
    assert len(problems) == 2
    assert "apps/pwa_api/done.py: 'Не переведено'" in problems[0]
    assert "Чужая область" not in problems[0]
    assert problems[1] == (
        "apps/pwa_api/done.py:12 builds a message with f-string; pass params instead"
    )

    stale = backend_i18n.check(
        extraction, catalog_text="", translations=translations, scopes=[]
    )
    assert stale == [
        "helpers/pwa/locales/en.po is out of sync with the code; run `make pwa-i18n-extract`."
    ]


def test_repository_backend_catalog_is_in_sync_and_scopes_are_translated():
    extraction = backend_i18n.extract(backend_i18n.python_sources())
    problems = backend_i18n.check(
        extraction,
        catalog_text=backend_i18n.CATALOG_PATH.read_text(encoding="utf-8"),
        translations=backend_i18n.read_translations(),
        scopes=backend_i18n.load_scopes(),
    )
    assert problems == []
