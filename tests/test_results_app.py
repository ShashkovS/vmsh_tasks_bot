from __future__ import annotations

from apps import results_app
from models import Webtoken

from .http_harness import FakeRequest


def test_results_routes_require_login_page_when_cookie_missing(live_seed_db, monkeypatch):
    monkeypatch.setattr(results_app.trash_print_stats, "get_html", lambda: "stats-html")
    monkeypatch.setattr(results_app.trash_print_results, "get_html", lambda: "results-html")

    stat_response = __import__("asyncio").run(results_app.print_stat(FakeRequest(path="/stat")))
    res_response = __import__("asyncio").run(results_app.show_res(FakeRequest(path="/res")))

    assert stat_response.status == 200
    assert stat_response.text == results_app.templates["login_res"]
    assert res_response.status == 200
    assert res_response.text == results_app.templates["login_res"]


def test_results_routes_allow_teacher_and_reject_student(live_seed_db, monkeypatch):
    monkeypatch.setattr(results_app.trash_print_stats, "get_html", lambda: "stats-html")
    monkeypatch.setattr(results_app.trash_print_results, "get_html", lambda: "results-html")
    teacher = live_seed_db.get_teacher()
    student = live_seed_db.get_user("qwerty1")
    teacher_token = Webtoken.webtoken_by_user(teacher)
    student_token = Webtoken.webtoken_by_user(student)

    teacher_stat = __import__("asyncio").run(
        results_app.print_stat(FakeRequest(path="/stat", cookies={results_app.COOKIE_NAME: teacher_token}))
    )
    teacher_res = __import__("asyncio").run(
        results_app.show_res(FakeRequest(path="/res", cookies={results_app.COOKIE_NAME: teacher_token}))
    )
    assert teacher_stat.status == 200
    assert teacher_stat.text == "stats-html"
    assert teacher_res.status == 200
    assert teacher_res.text == "results-html"

    student_stat = __import__("asyncio").run(
        results_app.print_stat(FakeRequest(path="/stat", cookies={results_app.COOKIE_NAME: student_token}))
    )
    student_res = __import__("asyncio").run(
        results_app.show_res(FakeRequest(path="/res", cookies={results_app.COOKIE_NAME: student_token}))
    )
    assert student_stat.status == 401
    assert student_res.status == 401


def test_results_login_sets_cookie_for_valid_token(live_seed_db, monkeypatch):
    monkeypatch.setattr(results_app, "use_cookie", results_app.DEBUG_COOKIE)
    teacher = live_seed_db.get_teacher()

    response = __import__("asyncio").run(
        results_app.login_res(FakeRequest(method="POST", path="/stat", post_data={"password": teacher.token}))
    )

    assert response.status == 302
    assert results_app.COOKIE_NAME in response.cookies
    cookie_value = response.cookies[results_app.COOKIE_NAME].value
    assert Webtoken.user_by_webtoken(cookie_value).id == teacher.id



def test_results_login_returns_login_page_for_invalid_token(live_seed_db):
    response = __import__("asyncio").run(
        results_app.login_res(FakeRequest(method="POST", path="/res", post_data={"password": "missing-token"}))
    )

    assert response.status == 200
    assert response.text == results_app.templates["login_res"]
