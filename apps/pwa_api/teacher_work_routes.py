"""Admin-only teacher accounting adapter; vmshpwa/docs/teacher-work.md."""

import asyncio
import json
from collections import defaultdict

from aiohttp import web

from apps.pwa_api.errors import PwaApiError
from helpers.pwa.i18n import N_
from helpers.pwa.app_keys import PWA_DATABASE
from apps.pwa_api.statistics_recalculation_routes import course, ID
from apps.pwa_api.middleware import authenticated_session
from apps.pwa_api.staff_statistics_routes import _factory
from db_methods.pwa import teacher_work as records
from models.pwa.auth import AuthAudience
from models.pwa.teacher_work import (
    fingerprint,
    normalize_name,
    parse_roster,
    TeacherNameMatcher,
    teacher_name_key,
)
from models.pwa.teacher_work_commands import (
    execute_command,
    WorkConflict,
    validate_cell_key,
)
from models.pwa.teacher_work_report import build_report, export_tsv
from models.pwa.teacher_work_runner import TeacherWorkRunner, operation_payload

teacher_work_routes = web.RouteTableDef()
SERVICE = web.AppKey("teacher_work", dict)


def admin(request):
    principal = authenticated_session(request).principal
    if (
        principal.audience is not AuthAudience.STAFF
        or not principal.is_global_admin
        or principal.linked_user_id is None
    ):
        raise PwaApiError(
            status=403,
            code="forbidden",
            message="Учёт работы доступен только администратору",
        )
    return principal


def service(request):
    holder = request.app[SERVICE]
    if "service" not in holder:
        holder["service"] = TeacherWorkRunner(_factory(request).database_path)
        holder["service"].recover()
    return holder["service"]


async def start_teacher_work(app):
    database = app.get(PWA_DATABASE)
    if database and database.factory is not None:
        holder = app[SERVICE]
        holder["service"] = TeacherWorkRunner(database.factory.database_path)
        await asyncio.to_thread(holder["service"].recover)


async def close_teacher_work(app):
    instance = app.get(SERVICE, {}).get("service")
    if instance:
        await asyncio.to_thread(instance.close)


def response(payload, status=200):
    return web.json_response(
        payload, status=status, headers={"Cache-Control": "no-store"}
    )


async def body_of(request):
    try:
        body = await request.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Некорректный запрос учёта работы",
        )
    return body


def bad_request(exc):
    conflict = isinstance(exc, WorkConflict)
    return PwaApiError(
        status=409 if conflict else 422,
        code="version_conflict" if conflict else "validation_error",
        message=N_("Данные изменились. Обновите страницу и повторите правку")
        if conflict
        else N_("Проверьте преподавателей, время, комментарий и выбранное событие"),
    )


@teacher_work_routes.get("/staff/api/v1/teacher-work/catalog")
async def catalog(request):
    admin(request)
    return response(
        await _factory(request).run_read_async(
            lambda c: {
                "courses": records.rows(
                    c,
                    "SELECT public_id AS courseId,name,status FROM courses ORDER BY status='active' DESC,sort_order,id",
                ),
                "teachers": records.rows(
                    c,
                    "SELECT public_id AS teacherId,id,surname,name,middlename FROM users WHERE type IN (2,128) ORDER BY surname,name,id",
                ),
            }
        )
    )


@teacher_work_routes.get("/staff/api/v1/teacher-work/report")
async def report(request):
    principal = admin(request)
    course_id = await course(request, request.query.get("courseId"), principal)
    try:
        bounds = {
            k: int(request.query[k]) if k in request.query else None
            for k in ("first", "last")
        }
        if any(v is not None and not 0 <= v <= 10000 for v in bounds.values()) or (
            bounds["first"] is not None
            and bounds["last"] is not None
            and bounds["first"] > bounds["last"]
        ):
            raise ValueError()
    except ValueError:
        raise PwaApiError(
            status=422, code="validation_error", message="Проверьте диапазон занятий"
        )

    def read(connection):
        run = records.latest_run(connection, course_id, completed=True)
        latest = records.latest_run(connection, course_id)
        if not run:
            return {
                "run": None,
                "operation": operation_payload(latest),
                "columns": [],
                "rows": [],
                "lessons": [],
                "tsv": "",
            }
        snapshot = json.loads(run["snapshot_json"])
        overrides = {
            r["cell_key"]: r
            for r in records.rows(
                connection,
                "SELECT * FROM teacher_work_overrides WHERE course_id=?",
                (course_id,),
            )
        }
        # Manual-only cells remain visible even when their original source disappears.
        present = {c["key"] for c in snapshot["cells"]}
        for key in {
            k for k, v in overrides.items() if v["hours"] is not None
        } - present:
            kind, teacher, slot = key.split(":")
            snapshot["cells"].append(
                {
                    "key": key,
                    "kind": kind,
                    "teacherId": "u-" + teacher,
                    "slot": slot,
                    "hours": 0.0,
                    "source": "unknown",
                    "evidence": [],
                    "anomalies": ["source_removed"],
                    "fingerprint": fingerprint([]),
                }
            )
        data = build_report(
            snapshot, overrides, **bounds, query=request.query.get("q", "")[:100]
        )
        return {
            **data,
            "run": operation_payload(run),
            "operation": operation_payload(latest),
            "tsv": export_tsv(data),
        }

    return response(await _factory(request).run_read_async(read))


@teacher_work_routes.get("/staff/api/v1/teacher-work/details")
async def details(request):
    principal = admin(request)
    course_id = await course(request, request.query.get("courseId"), principal)
    key = request.query.get("cellKey", "")

    def read(connection):
        validate_cell_key(connection, course_id, key)
        run = records.latest_run(connection, course_id, completed=True)
        cells = json.loads(run["snapshot_json"])["cells"] if run else []
        cell = next((c for c in cells if c["key"] == key), None)
        if cell is None:
            import re

            if not re.fullmatch(r"(school|zoom|written):\d+:[\d-]+", key):
                raise ValueError()
            kind, teacher, slot = key.split(":")
            cell = {
                "key": key,
                "kind": kind,
                "teacherId": "u-" + teacher,
                "slot": slot,
                "hours": 0.0,
                "source": "unknown",
                "fingerprint": fingerprint([]),
                "evidence": [],
                "anomalies": [],
            }
        override = connection.execute(
            "SELECT * FROM teacher_work_overrides WHERE course_id=? AND cell_key=?",
            (course_id, key),
        ).fetchone()
        audit = records.rows(
            connection,
            """SELECT action,created_at,u.surname,u.name,before_json,after_json
          FROM teacher_work_mutations m JOIN users u ON u.id=m.actor_id
          WHERE m.course_id=? AND m.entity_key=? ORDER BY m.id DESC LIMIT 50""",
            (course_id, key),
        )
        return {
            "cell": cell,
            "override": dict(override) if override else None,
            "audit": audit,
        }

    try:
        return response(await _factory(request).run_read_async(read))
    except ValueError:
        raise PwaApiError(
            status=422, code="validation_error", message="Некорректная ячейка отчёта"
        )


@teacher_work_routes.get("/staff/api/v1/teacher-work/inputs")
async def inputs(request):
    principal = admin(request)
    course_id = await course(request, request.query.get("courseId"), principal)

    def read(connection):
        facts = records.input_facts(connection, course_id)
        signatures = defaultdict(list)
        for row in facts["zoom"]:
            signatures[row["zoom_user_name"] or ""].append(row)
        aliases = {r["normalized_name"]: r for r in facts["aliases"]}
        matcher = TeacherNameMatcher(facts["teachers"])
        candidates_by_name = {}
        names = []
        for name, events in signatures.items():
            alias = aliases.get(normalize_name(name))
            key = teacher_name_key(name)
            if key not in candidates_by_name:
                candidates_by_name[key] = matcher.candidates(name)
            names.append(
                {
                    "name": name,
                    "normalizedName": normalize_name(name),
                    "count": len(events),
                    "firstAt": events[0]["event_ts"],
                    "lastAt": events[-1]["event_ts"],
                    "teacherLike": any(
                        s in normalize_name(name) for s in ("риним", "ровер", "одерат")
                    ),
                    "alias": alias,
                    "examples": events[:3],
                    "candidates": candidates_by_name[key],
                }
            )
        return {
            "settings": facts["settings"],
            "shifts": [
                {
                    "teacherId": "u-" + str(sh["teacher_id"]),
                    "eventId": "ipe-" + str(sh["event_id"]),
                    "normHours": sh["norm_hours"],
                    "standardStartsAt": sh["standard_starts_at"],
                    "standardEndsAt": sh["standard_ends_at"],
                }
                for sh in facts["shifts"]
            ],
            "timezone": facts["course"]["timezone"],
            "events": facts["events"],
            "signatures": names,
            "rosters": records.rows(
                connection,
                """SELECT r.*,e.public_id AS eventPublicId FROM teacher_work_rosters r
                  JOIN in_person_events e ON e.id=r.event_id WHERE r.course_id=? ORDER BY e.starts_at DESC""",
                (course_id,),
            ),
        }

    return response(await _factory(request).run_read_async(read))


@teacher_work_routes.post("/staff/api/v1/teacher-work/roster-preview")
async def preview(request):
    principal = admin(request)
    body = await body_of(request)
    course_id = await course(request, body.get("courseId"), principal)
    if (
        not isinstance(body.get("rawText"), str)
        or not 1 <= len(body["rawText"]) <= 100000
    ):
        raise PwaApiError(
            status=422,
            code="validation_error",
            message="Вставьте распределение преподавателей",
        )

    def read(connection):
        facts = records.roster_facts(connection, course_id)
        matcher = TeacherNameMatcher(facts["teachers"])
        parsed = parse_roster(
            body["rawText"],
            facts["events"],
            facts["teachers"],
            facts["course"]["timezone"],
        )
        mappings = defaultdict(set)
        allowed = {t["public_id"] for t in facts["teachers"]}
        for roster in records.rows(
            connection,
            "SELECT rows_json FROM teacher_work_rosters WHERE course_id=? AND state='confirmed'",
            (course_id,),
        ):
            for row in json.loads(roster["rows_json"]):
                if row["teacherId"] in allowed:
                    mappings[teacher_name_key(row["name"])].add(row["teacherId"])
        for row in parsed["rows"]:
            confirmed = mappings[teacher_name_key(row["name"])]
            if len(confirmed) == 1:
                row["teacherId"] = next(iter(confirmed))
                row["matchKind"] = "remembered"
            elif len(confirmed) > 1:
                row["teacherId"] = None
                row["matchKind"] = "ambiguous"
                row["candidates"] = [matcher.candidate(t, 1) for t in sorted(confirmed)]
        return parsed

    return response(await _factory(request).run_read_async(read))


@teacher_work_routes.post("/staff/api/v1/teacher-work/command")
async def command(request):
    principal = admin(request)
    body = await body_of(request)
    course_id = await course(request, body.get("courseId"), principal)
    try:
        result = await _factory(request).run_write_async(
            lambda c: execute_command(c, course_id, principal.linked_user_id, body)
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise bad_request(exc)
    # docs/teacher-work.md, input correction: save is independent of calculation.
    return response(result)


@teacher_work_routes.get("/staff/api/v1/teacher-work/recalculate")
async def status(request):
    principal = admin(request)
    course_id = await course(request, request.query.get("courseId"), principal)
    return response(await asyncio.to_thread(service(request).status, course_id))


@teacher_work_routes.post("/staff/api/v1/teacher-work/recalculate")
async def recalculate(request):
    principal = admin(request)
    body = await body_of(request)
    course_id = await course(request, body.get("courseId"), principal)
    key = body.get("idempotencyKey")
    if not isinstance(key, str) or not ID.fullmatch(key):
        raise PwaApiError(
            status=422, code="validation_error", message="Некорректный запрос пересчёта"
        )
    try:
        data = await asyncio.to_thread(
            service(request).start, course_id, principal.linked_user_id, key
        )
    except ValueError as exc:
        raise bad_request(WorkConflict(str(exc)))
    return response(data, 202 if data["busy"] else 200)
