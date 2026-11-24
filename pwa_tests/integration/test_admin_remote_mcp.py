"""A real MCP client authenticates with a Staff grant. See docs/admin-mcp/oauth.md."""

import json
import subprocess
from contextlib import asynccontextmanager
from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from admin_mcp import oauth
from pwa_tests.integration import test_content_http_api as content_fixtures
from pwa_tests.integration import test_review_queue_http_api as fixtures

review_http = fixtures.review_http


@pytest.fixture(scope="module")
def render_bundle(tmp_path_factory):
    # Use the production entry point even in a fresh checkout and isolate xdist workers.
    from admin_mcp.render import BUNDLE

    destination = tmp_path_factory.mktemp("admin-render")
    subprocess.run(
        [
            "node",
            "node_modules/vite/bin/vite.js",
            "build",
            "--config",
            "admin-render/vite.config.ts",
            "--outDir",
            str(destination),
        ],
        cwd=BUNDLE.parents[2],
        check=True,
    )
    return destination / "render.cjs"


async def issue(f):
    verifier = "a" * 45
    query = {
        "client_id": oauth.client(),
        "redirect_uri": oauth.callback(),
        "resource": fixtures.ORIGIN + oauth.PATH,
        "response_type": "code",
        "scope": oauth.SCOPE,
        "state": "test",
        "code_challenge_method": "S256",
        "code_challenge": oauth.challenge(verifier),
    }
    response = await f.client.post(
        oauth.ISSUER_PATH + "/authorize",
        params=query,
        data={"decision": "allow"},
        headers=fixtures._headers(unsafe=True),
        cookies=fixtures._cookie(f, "admin"),
        allow_redirects=False,
    )
    assert response.status == 302, await response.text()
    code = parse_qs(urlsplit(response.headers["Location"]).query)["code"][0]
    data = {
        "client_id": oauth.client(),
        "resource": query["resource"],
        "redirect_uri": query["redirect_uri"],
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": verifier,
    }
    for payload, status in [
        ({**data, "code_verifier": "b" * 45}, 400),
        (data, 200),
        (data, 400),
    ]:
        response = await f.client.post(
            oauth.ISSUER_PATH + "/token", data=payload, headers=fixtures._headers()
        )
        assert response.status == status, await response.text()
        if status == 200:
            tokens = await response.json()
    return tokens


@asynccontextmanager
async def connect(f, secret):
    async with httpx2.AsyncClient(
        headers={"Host": fixtures.HOST, "Authorization": "Bearer " + secret}
    ) as http:
        async with streamable_http_client(
            str(f.client.make_url(oauth.PATH)), http_client=http
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session


async def test_oauth_tools_and_revocation(review_http):
    f = review_http
    resp = await f.client.get(oauth.PATH, headers=fixtures._headers())
    assert resp.status == 401
    assert oauth.METADATA in resp.headers["WWW-Authenticate"]
    discovery = await f.client.get(oauth.METADATA, headers=fixtures._headers())
    assert (await discovery.json())["resource"] == fixtures.ORIGIN + oauth.PATH
    issuer = await f.client.get(
        "/.well-known/oauth-authorization-server" + oauth.ISSUER_PATH,
        headers=fixtures._headers(),
    )
    assert (await issuer.json())["code_challenge_methods_supported"] == ["S256"]
    tokens = await issue(f)
    async with connect(f, tokens["access_token"]) as client:
        result = await client.call_tool("get_my_access", {})
        assert not result.is_error, result
        assert json.loads(result.content[0].text)["portal"] == fixtures.ORIGIN
        result = await client.call_tool("list_lessons", {})
        assert not result.is_error, result
    response = await f.client.post(
        oauth.ISSUER_PATH + "/revoke",
        headers=fixtures._headers(),
        data={"client_id": oauth.client(), "token": tokens["refresh_token"]},
    )
    assert response.status == 200
    response = await f.client.get(
        oauth.PATH,
        headers={
            **fixtures._headers(),
            "Authorization": "Bearer " + tokens["access_token"],
        },
    )
    assert response.status == 401


content_http = content_fixtures.content_http


async def test_admin_material_lifecycle(content_http, monkeypatch, render_bundle):
    monkeypatch.setattr("admin_mcp.render.BUNDLE", render_bundle)
    from datetime import UTC, datetime, timedelta

    from admin_mcp import server
    from admin_mcp.schedule import activate

    f = content_http
    tokens = await issue(f)
    async with connect(f, tokens["access_token"]) as client:

        async def call(name, **args):
            result = await client.call_tool(name, args)
            assert not result.is_error, (name, result)
            return json.loads(result.content[0].text)

        async def op(name, ids, body=None, etag=None):
            return await call(name, identifiers=ids, body=body, etag=etag)

        resources = await client.list_resources()
        assert len(resources.resources) == len(server.TOPICS)
        assert (
            "Администрирование"
            in (await client.read_resource(resources.resources[0].uri)).contents[0].text
        )
        assert (
            "group_lesson_id"
            in (await call("get_admin_guide", topic="tools/set_intake"))["markdown"]
        )
        for topic in server.TOPICS:
            assert (await call("get_admin_guide", topic=topic))["markdown"]
        group = f.factory.run_read(
            lambda c: c.execute(
                "SELECT g.public_id gid,c.public_id cid FROM groups g JOIN courses c ON c.id=g.course_id WHERE group_id='content-a'"
            ).fetchone()
        )
        create = {
            "schemaVersion": 1,
            "idempotencyKey": "test-create",
            "courseId": group["cid"],
            "groupId": group["gid"],
            "lessonNumber": 58,
            "cycleAnchorDate": "2026-11-20",
            "businessTimezone": "Europe/Moscow",
            "title": "Листок",
            "opensLocalTime": "2026-11-20T00:00",
            "submissionClosesLocalTime": "2026-12-01T00:00",
            "hintScheduledLocalTime": None,
            "solutionScheduledLocalTime": None,
        }
        first = await op("create_lesson", {}, create)
        assert first == await op("create_lesson", {}, create)
        lesson = first["groupLesson"]["groupLessonId"]
        ids = {"group_lesson_id": lesson}
        uploaded = await call(
            "upload_material",
            **ids,
            kind="condition",
            filename="sheet.tex",
            source=r"\задача[title=Куб] Найдите $2+2$. \includegraphics{figure.svg} \кзадача",
        )
        rev = uploaded["revisionId"]
        rid = {"revision_id": rev}
        files = {"svg": content_fixtures.SAFE_SVG, "pdf": b"%PDF-1.4\n%%EOF"}

        async def file_reader(file, maximum):
            return files[file["file_id"]]

        def native(key):
            return {
                "file_id": key,
                "download_url": "https://test.oaiusercontent.com/upload",
            }

        monkeypatch.setattr(server, "download", file_reader)
        attached = await call(
            "upload_figure",
            **rid,
            logical_name="figure.svg",
            kind="svg",
            etag=uploaded["etag"],
            file=native("svg"),
        )
        job_args = dict(
            operation="compile_material",
            identifiers=rid,
            body={},
            etag=attached["etag"],
            request_key="compile",
        )
        job = await call("start_operation", **job_args)
        assert job == await call("start_operation", **job_args)
        import asyncio

        for _ in range(50):
            finished = await call("get_operation", operation_id=job["operationId"])
            if finished["state"] != "running":
                break
            await asyncio.sleep(0.03)
        assert finished["state"] == "completed", finished
        layout = await op("material_figures", rid)
        await op(
            "set_figure_layout",
            rid,
            {
                "version": layout["version"],
                "entries": [
                    {
                        "occurrenceId": layout["figures"][0]["occurrenceId"],
                        "targetOrdinal": 1,
                        "targetPart": None,
                        "section": "common",
                        "order": 0,
                        "side": "right",
                        "hidden": False,
                    }
                ],
            },
        )
        matches = await op("problem_matches", rid)
        await op(
            "save_problem_matches",
            rid,
            {
                "matches": [
                    {
                        "sourceOrdinal": 1,
                        "sourceItem": matches["items"][0]["sourceItem"],
                        "decision": "insert_new",
                        "problemId": None,
                    }
                ]
            },
            matches["etag"],
        )
        grid = await op("metadata_grid", {**ids, "revisionId": rev})
        generated = await op(
            "generate_metadata",
            ids,
            {"revisionId": rev, "confirmedOverwrite": False},
            grid["etag"],
        )
        assert generated["rows"]
        file = await call("export_metadata_tsv", **ids, revision_id=rev)
        response = await f.client.get(
            urlsplit(file["url"]).path,
            headers=fixtures._headers(),
            cookies=fixtures._cookie(f, "admin"),
        )
        assert response.status == 200
        data = await response.read()
        assert "Номер\tНазвание" in data.decode()
        from base64 import b64decode

        resource = await client.call_tool(
            "read_export", {"export_id": file["exportId"]}
        )
        assert (
            not resource.is_error
            and b64decode(resource.content[0].resource.blob) == data
        )
        files["test"] = data.replace("Куб".encode(), "Кубики".encode())
        edit = {
            **ids,
            **rid,
            "etag": grid["etag"],
            "file": {
                "file_id": "test",
                "download_url": "https://test.oaiusercontent.com/upload",
            },
        }
        assert (await call("edit_metadata", **edit))["changes"]
        assert (await call("edit_metadata", **edit, apply=True))["applied"]
        assert (await client.call_tool("edit_metadata", edit)).is_error
        catalog = await call("search_problems", text="Кубики", group_id=group["gid"])
        answers = await call(
            "group_answers",
            group_id=group["gid"],
            problem_ids=[catalog["items"][0]["id"]],
        )
        assert any(not row["answers"][0]["submitted"] for row in answers["items"])
        html = await call("render_html", **ids, revisions={"condition": rev})
        assert "<math" in html["html"] and "Кубики" in html["html"]
        await op(
            "publish_material",
            {},
            {
                "groupLessonId": lesson,
                "kind": "condition",
                "revisionId": rev,
                "mode": "publish",
                "scheduledLocalTime": None,
                "businessTimezone": None,
                "expectedCurrentPublicationId": None,
                "expectedCurrentVersion": None,
                "expectedScheduledPublicationId": None,
                "expectedScheduledVersion": None,
            },
            '"none"',
        )
        assert "Кубики" in (await call("render_html", **ids))["html"]
        rendered = await content_fixtures._student_read(
            f, group_lesson=lesson, kind="condition"
        )
        assert rendered.status == 200
        state = await call("lesson_state", **ids)
        await op(
            "set_submission_cutoff",
            ids,
            {
                "businessTimezone": "Europe/Moscow",
                "submissionClosesLocalTime": "2026-12-05T18:00",
                "confirmChange": True,
            },
            state["window"]["etag"],
        )
        assert (await call("lesson_state", **ids))["window"][
            "submissionClosesAt"
        ].startswith("2026-12-05")
        pdf = await call(
            "upload_block_pdf", **ids, filename="cube.pdf", file=native("pdf")
        )
        markdown = f"[PDF]({pdf['file']['url']})\n\n::video[Разбор](https://youtu.be/dQw4w9WgXcQ)"
        block = await op(
            "save_lesson_block",
            {**ids, "position": "before"},
            {"markdown": markdown},
            '"none"',
        )
        assert block["block"]["draft"]["document"]["blocks"][-1]["type"] == "video"
        preview = await call("preview_lesson_block", **ids, position="before")
        assert "cube.pdf" in preview["html"] and "dQw4w9WgXcQ" in preview["html"]
        b = await op(
            "publish_lesson_block",
            {**ids, "position": "before"},
            {
                "revisionId": block["block"]["draft"]["revisionId"],
                "mode": "now",
                "scheduledAt": None,
            },
            block["etag"],
        )
        due = datetime.now(UTC) + timedelta(hours=1)
        await call(
            "schedule_hide",
            **ids,
            target="before",
            object_id=b["blockId"],
            object_version=b["version"],
            event_version=0,
            due=due.isoformat(),
        )
        # An unrelated pending revision survives hiding the active block.
        next_draft = await op(
            "save_lesson_block",
            {**ids, "position": "before"},
            {"markdown": "Новая редакция"},
            b["etag"],
        )
        await op(
            "publish_lesson_block",
            {**ids, "position": "before"},
            {
                "revisionId": next_draft["block"]["draft"]["revisionId"],
                "mode": "scheduled",
                "scheduledAt": (due + timedelta(days=3)).isoformat(),
            },
            next_draft["etag"],
        )
        now = (due + timedelta(days=1)).isoformat()
        assert f.factory.run_write(lambda c: activate(c, now, 10))
        assert not f.factory.run_write(lambda c: activate(c, now, 10))
        assert (await call("lesson_state", **ids))["blocks"]["before"][
            "published"
        ] is None
        assert (await call("lesson_state", **ids))["blocks"]["before"]["pending"][
            "markdown"
        ] == "Новая редакция"
        # Two independently authenticated editors share the same version precondition.
        grid = await op("metadata_grid", {**ids, "revisionId": rev})
        async with connect(f, (await issue(f))["access_token"]) as other:
            writes = await asyncio.gather(
                *(
                    editor.call_tool(
                        "edit_metadata",
                        {
                            **ids,
                            "revision_id": rev,
                            "etag": grid["etag"],
                            "apply": True,
                            "patches": {
                                str(grid["rows"][0]["problemId"]): {"title": title}
                            },
                        },
                    )
                    for editor, title in [(client, "Редактор A"), (other, "Редактор Б")]
                )
            )
            assert sorted(reply.is_error for reply in writes) == [False, True]


async def test_refresh_audience_and_live_role(review_http):
    f = review_http
    tokens = await issue(f)
    data = {
        "grant_type": "refresh_token",
        "client_id": oauth.client(),
        "resource": fixtures.ORIGIN + oauth.PATH,
        "refresh_token": tokens["refresh_token"],
    }

    async def exchange(form):
        return await f.client.post(
            oauth.ISSUER_PATH + "/token", headers=fixtures._headers(), data=form
        )

    assert (
        await exchange({**data, "resource": "https://other.example" + oauth.PATH})
    ).status == 400
    refreshed = await exchange(data)
    assert refreshed.status == 200
    rotated = await refreshed.json()
    assert (await exchange(data)).status == 400

    async def access(secret):
        return await f.client.post(
            oauth.PATH,
            headers={**fixtures._headers(), "Authorization": "Bearer " + secret},
        )

    assert (await access(tokens["access_token"])).status == 401
    async with connect(f, rotated["access_token"]) as client:
        assert not (await client.call_tool("get_my_access", {})).is_error
    f.factory.run_write(
        lambda c: (
            c.execute(
                "UPDATE users SET type=(SELECT type FROM users WHERE id=?) WHERE id=?",
                (fixtures.FULL_TEACHER_ID, fixtures.ADMIN_ID),
            ).rowcount
        )
    )
    assert (await access(rotated["access_token"])).status == 401


async def test_recheck_and_roster_history(content_http):
    f = content_http
    problem, revision = await content_fixtures._prepare_published_test_problem(
        f, correct_answer="179"
    )
    submitted = await f.client.post(
        f"/student/api/v1/problems/{problem}/test-attempts",
        json={
            "schemaVersion": 1,
            "idempotencyKey": "018f47f6-7668-7c85-a034-c5b8218bac09",
            "problemRevision": {"conditionRevisionId": revision, "configVersion": 1},
            "displayAnswer": "179",
            "clientCreatedAt": content_fixtures._timestamp(),
        },
        headers=content_fixtures._headers(unsafe=True),
        cookies=content_fixtures._cookie(f, "student"),
    )
    assert submitted.status == 201
    tokens = await issue(f)
    async with connect(f, tokens["access_token"]) as client:

        async def call(name, args):
            result = await client.call_tool(name, args)
            assert not result.is_error, (name, result)
            return json.loads(result.content[0].text)

        ids = {"group_lesson_id": f.group_lesson_a}
        grid = await call(
            "metadata_grid", {"identifiers": {**ids, "revisionId": revision}}
        )
        pid = grid["rows"][0]["problemId"]
        changed = await call(
            "edit_metadata",
            {
                **ids,
                "revision_id": revision,
                "etag": grid["etag"],
                "patches": {str(pid): {"correctAnswer": "180"}},
                "apply": True,
            },
        )
        assert changed["applied"]
        rid = {"problem_public_id": problem}
        preview = await call("preview_recheck", {"identifiers": rid})
        assert preview["verdictChanges"] == 1
        receipt = await call(
            "recheck_problem",
            {
                "identifiers": rid,
                "body": {
                    "schemaVersion": 1,
                    "problemRevision": preview["problemRevision"],
                },
            },
        )
        assert receipt["verdictChanges"] == 1
        group = f.factory.run_read(
            lambda c: c.execute(
                "SELECT public_id FROM groups WHERE group_id='content-a'"
            ).fetchone()["public_id"]
        )
        answers = await call(
            "group_answers", {"group_id": group, "problem_ids": [problem]}
        )
        assert answers["items"][0]["answers"][0]["testAttempts"][0]["answer"] == "179"


async def test_group_cursor_and_ambiguous_search(review_http):
    f = review_http

    def seed(c):
        group = c.execute(
            "SELECT * FROM groups WHERE group_id='review-http-a'"
        ).fetchone()
        c.execute(
            """INSERT INTO course_enrollments(student_user_id,course_id,active_group_id,attendance_mode,status,created_at,updated_at)
          VALUES(?,?,?,'online','active',?,?)""",
            (
                fixtures.STUDENT_ID,
                group["course_id"],
                group["group_id"],
                group["created_at"],
                group["updated_at"],
            ),
        )
        enrollment = c.execute(
            "SELECT * FROM course_enrollments WHERE student_user_id=?",
            (fixtures.STUDENT_ID,),
        ).fetchone()
        extra = c.execute(
            "INSERT INTO users(id,type,name,surname) SELECT 990001,type,'Ещё','Участник' FROM users WHERE id=? RETURNING id",
            (fixtures.STUDENT_ID,),
        ).fetchone()
        c.execute(
            """INSERT INTO course_enrollments(student_user_id,course_id,active_group_id,attendance_mode,status,created_at,updated_at)
          VALUES(?,?,?,'online','active',?,?)""",
            (
                extra["id"],
                enrollment["course_id"],
                enrollment["active_group_id"],
                enrollment["created_at"],
                enrollment["updated_at"],
            ),
        )
        return c.execute(
            "SELECT public_id FROM groups WHERE group_id=?",
            (enrollment["active_group_id"],),
        ).fetchone()["public_id"]

    group = f.factory.run_write(seed)
    async with connect(f, (await issue(f))["access_token"]) as client:

        async def call(name, args):
            result = await client.call_tool(name, args)
            assert not result.is_error, result
            return json.loads(result.content[0].text)

        found = await call("search_problems", {"text": "Общая задача"})
        assert len({item["id"] for item in found["items"]}) == 2
        selected = next(item for item in found["items"] if item["groupId"] == group)
        args = {"group_id": group, "problem_ids": [selected["id"]], "page_size": 1}
        first = await call("group_answers", args)
        second = await call(
            "group_answers", {**args, "after_student_id": first["nextAfterStudentId"]}
        )
        assert second["items"][0]["studentId"] != first["items"][0]["studentId"]
        assert second["nextAfterStudentId"] is None
        assert not second["items"][0]["answers"][0]["submitted"]


async def test_html_material_by_subpart_id(content_http, monkeypatch, render_bundle):
    monkeypatch.setattr("admin_mcp.render.BUNDLE", render_bundle)
    f = content_http
    ids = {"group_lesson_id": f.group_lesson_a}
    source = r"\задача Два числа. \пункт Сложите один. \пункт Сложите два. \кзадача"
    async with connect(f, (await issue(f))["access_token"]) as client:

        async def call(name, args):
            result = await client.call_tool(name, args)
            assert not result.is_error, (name, result)
            return json.loads(result.content[0].text)

        revisions = {}
        problem_ids = {}
        for kind, extra in [
            ("condition", ""),
            (
                "hint",
                r"\подсказка \пункт Первый совет. \пункт Второй совет. \кподсказка",
            ),
            (
                "solution",
                r"\решение \пункт Первый ответ. \пункт Второй ответ. \крешение",
            ),
        ]:
            upload = await call(
                "upload_material",
                {
                    **ids,
                    "kind": kind,
                    "filename": kind + ".tex",
                    "source": source + "\n" + extra,
                },
            )
            revision = upload["revisionId"]
            revisions[kind] = revision
            path = {"revision_id": revision}
            await call(
                "compile_material", {"identifiers": path, "etag": upload["etag"]}
            )
            matches = await call("problem_matches", {"identifiers": path})
            rows = [
                {
                    "sourceOrdinal": item["sourceOrdinal"],
                    "sourceItem": item["sourceItem"],
                    "decision": "manual_match" if problem_ids else "insert_new",
                    "problemId": problem_ids.get(item["sourceItem"]),
                }
                for item in matches["items"]
            ]
            matched = await call(
                "save_problem_matches",
                {
                    "identifiers": path,
                    "etag": matches["etag"],
                    "body": {"matches": rows},
                },
            )
            problem_ids = {
                item["sourceItem"]: item["match"]["problemId"]
                for item in matched["items"]
            }
        assert len(problem_ids) == 2
        for kind, wanted, other in [
            ("hint", "Второй совет", "Первый совет"),
            ("solution", "Второй ответ", "Первый ответ"),
        ]:
            output = await call(
                "render_html",
                {
                    **ids,
                    "mode": kind,
                    "revisions": revisions,
                    "problem_ids": [list(problem_ids.values())[1]],
                },
            )
            assert not output["missing"] and wanted in output["html"]
            assert other not in output["html"] and "Сложите один" not in output["html"]


async def test_missed_hide_preserves_replacement(content_http):
    from datetime import datetime, UTC, timedelta
    from admin_mcp.schedule import activate

    f = content_http
    lesson = f.group_lesson_a

    async def publish(text, **kwargs):
        revision, _ = await content_fixtures._upload_and_compile(
            f,
            group_lesson=lesson,
            kind="condition",
            filename="condition.tex",
            source=text,
        )
        response = await content_fixtures._publish(
            f,
            group_lesson=lesson,
            kind="condition",
            revision_id=revision["revisionId"],
            **kwargs,
        )
        assert response.status == 201, await response.text()
        return revision["revisionId"]

    await publish(r"\задача Старый листок. \кзадача")
    async with connect(f, (await issue(f))["access_token"]) as client:
        history = await client.call_tool(
            "material_history", {"identifiers": {"groupLesson": lesson}}
        )
        original = json.loads(history.content[0].text)["materials"][0][
            "currentPublished"
        ]
        now = datetime.now(UTC)
        event = {
            "group_lesson_id": lesson,
            "target": "condition",
            "object_id": original["publicationId"],
            "object_version": original["version"],
            "event_version": 0,
            "due": (now + timedelta(hours=1)).isoformat(),
        }
        assert not (await client.call_tool("schedule_hide", event)).is_error
        assert not (
            await client.call_tool(
                "schedule_hide", {**event, "event_version": 1, "due": None}
            )
        ).is_error
        assert not (
            await client.call_tool("schedule_hide", {**event, "event_version": 2})
        ).is_error
    new = await publish(
        r"\задача Новый листок. \кзадача",
        expected_id=original["publicationId"],
        expected_version=original["version"],
        if_match=original["etag"],
    )
    assert (
        f.factory.run_write(
            lambda c: activate(c, (now + timedelta(days=1)).isoformat(), 10)
        )
        == []
    )
    assert (
        f.factory.run_read(
            lambda c: c.execute("SELECT state FROM lesson_hide_events").fetchone()[
                "state"
            ]
        )
        == "superseded"
    )
    actual = await content_fixtures._student_read(
        f, group_lesson=lesson, kind="condition"
    )
    assert new in await actual.text()
