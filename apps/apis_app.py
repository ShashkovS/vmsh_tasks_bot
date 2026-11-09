# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from aiohttp import web

import db_methods as db
from helpers.config import config, logger, DEBUG
from helpers.consts import USER_TYPE
from models.user import _normilize_token

__ALL__ = ['routes']

routes = web.RouteTableDef()


def _json_response(*, status: int, ok: bool, **payload):
    data = {"ok": ok}
    data.update(payload)
    return web.json_response(data, status=status)


def _extract_bearer_token(request: web.Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[len("Bearer "):].strip()
    return token or None


def _validate_root_payload(payload: Any) -> tuple[dict | None, str | None]:
    if not isinstance(payload, dict):
        return None, "payload_must_be_object"
    if not isinstance(payload.get("lesson"), int):
        return None, "lesson_must_be_int"
    if not isinstance(payload.get("verdict"), int):
        return None, "verdict_must_be_int"
    if not isinstance(payload.get("res_type"), int):
        return None, "res_type_must_be_int"
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return None, "rows_must_be_list"
    dry_run = payload.get("dry_run", False)
    if not isinstance(dry_run, bool):
        return None, "dry_run_must_be_bool"
    return payload, None


@routes.post('/api/conduit/import')
async def conduit_import(request: web.Request):
    bearer_token = _extract_bearer_token(request)
    if not bearer_token:
        return _json_response(status=401, ok=False, error="missing_bearer_token")
    if not config.conduit_import_api_token:
        logger.error("conduit_import_api_token is not configured")
        return _json_response(status=503, ok=False, error="api_token_not_configured")
    if bearer_token != config.conduit_import_api_token:
        return _json_response(status=403, ok=False, error="invalid_token")

    try:
        payload = await request.json()
    except Exception:
        return _json_response(status=400, ok=False, error="invalid_json")

    payload, payload_error = _validate_root_payload(payload)
    if payload_error:
        return _json_response(status=400, ok=False, error=payload_error)

    lesson = payload["lesson"]
    verdict = payload["verdict"]
    res_type = payload["res_type"]
    dry_run = payload.get("dry_run", False)
    rows = payload["rows"]

    errors = []
    valid_rows = []
    students_cache: dict[str, dict | None] = {}
    problems_cache: dict[int, dict | None] = {}

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append({"index": index, "code": "row_must_be_object", "details": None})
            continue

        token = row.get("token")
        problem_id = row.get("problem_id")
        group_id = row.get("group_id")

        if not isinstance(token, str) or not token.strip():
            errors.append({"index": index, "code": "invalid_token", "details": "token"})
            continue
        if not isinstance(problem_id, int):
            errors.append({"index": index, "code": "invalid_problem_id", "details": "problem_id"})
            continue
        if not isinstance(group_id, str) or not group_id.strip():
            errors.append({"index": index, "code": "invalid_group_id", "details": "group_id"})
            continue

        normalized_token = _normilize_token(token)
        if normalized_token not in students_cache:
            students_cache[normalized_token] = db.user.get_by_token(normalized_token)
        student = students_cache[normalized_token]
        if not student:
            errors.append({"index": index, "code": "student_not_found", "details": normalized_token})
            continue
        try:
            student_type = USER_TYPE(student["type"])
        except Exception:
            errors.append({"index": index, "code": "student_type_invalid", "details": student["type"]})
            continue
        if student_type != USER_TYPE.STUDENT:
            errors.append({"index": index, "code": "student_not_student", "details": student["id"]})
            continue

        if problem_id not in problems_cache:
            problems_cache[problem_id] = db.problem.get_by_id(problem_id)
        problem = problems_cache[problem_id]
        if not problem:
            errors.append({"index": index, "code": "problem_not_found", "details": problem_id})
            continue
        if problem["lesson"] != lesson:
            errors.append({
                "index": index,
                "code": "lesson_mismatch",
                "details": {"problem_id": problem_id, "problem_lesson": problem["lesson"], "request_lesson": lesson},
            })
            continue

        valid_rows.append({
            "student_id": student["id"],
            "problem_id": problem_id,
            "group_id": group_id.strip(),
        })

    existing_or_planned = set()
    insert_candidates = 0
    already_exists = 0
    inserted = 0
    ts = datetime.now().isoformat().replace(":", "-")

    conn = db.sql.conn
    if dry_run:
        for row in valid_rows:
            dedupe_key = (row["student_id"], row["problem_id"], verdict)
            if dedupe_key in existing_or_planned:
                already_exists += 1
                continue
            exists = conn.execute("""
                SELECT 1 FROM results
                WHERE student_id = :student_id AND problem_id = :problem_id AND verdict = :verdict
                LIMIT 1
            """, {
                "student_id": row["student_id"],
                "problem_id": row["problem_id"],
                "verdict": verdict,
            }).fetchone()
            if exists:
                already_exists += 1
                existing_or_planned.add(dedupe_key)
                continue
            existing_or_planned.add(dedupe_key)
            insert_candidates += 1
    else:
        with conn:
            for row in valid_rows:
                dedupe_key = (row["student_id"], row["problem_id"], verdict)
                if dedupe_key in existing_or_planned:
                    already_exists += 1
                    continue
                exists = conn.execute("""
                    SELECT 1 FROM results
                    WHERE student_id = :student_id AND problem_id = :problem_id AND verdict = :verdict
                    LIMIT 1
                """, {
                    "student_id": row["student_id"],
                    "problem_id": row["problem_id"],
                    "verdict": verdict,
                }).fetchone()
                if exists:
                    already_exists += 1
                    existing_or_planned.add(dedupe_key)
                    continue

                existing_or_planned.add(dedupe_key)
                insert_candidates += 1
                conn.execute("""
                    INSERT INTO results (
                        student_id, problem_id, group_id, lesson, teacher_id, ts, verdict, answer, res_type
                    )
                    VALUES (
                        :student_id, :problem_id, :group_id, :lesson, :teacher_id, :ts, :verdict, :answer, :res_type
                    )
                """, {
                    "student_id": row["student_id"],
                    "problem_id": row["problem_id"],
                    "group_id": row["group_id"],
                    "lesson": lesson,
                    "teacher_id": None,
                    "ts": ts,
                    "verdict": verdict,
                    "answer": None,
                    "res_type": res_type,
                })
                inserted += 1

    response = {
        "ok": True,
        "dry_run": dry_run,
        "received_rows": len(rows),
        "valid_rows": len(valid_rows),
        "insert_candidates": insert_candidates,
        "already_exists": already_exists,
        "inserted": inserted,
        "skipped_invalid": len(errors),
        "errors": errors,
    }
    return web.json_response(response, status=200)


async def on_startup(app):
    logger.debug('apis on_startup')
    if __name__ == "__main__":
        db.sql.setup(config.db_filename)


async def on_shutdown(app):
    logger.warning('apis on_shutdown')
    if __name__ == "__main__":
        db.sql.disconnect()
    logger.warning('apis Bye!')


def configure(app):
    app.add_routes(routes)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)


configue = configure


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logger.setLevel(DEBUG)
    app = web.Application()
    configure(app)
    web.run_app(app)
