"""Render the scoped Staff projection with the same React component as the worksheet."""

import asyncio
import json
from html import escape
from pathlib import Path
from typing import Literal

from admin_mcp import exports
from admin_mcp.operations import unpack
from apps.pwa_api import content_routes as content
from db_methods.pwa.content import ContentNotFound
from helpers.pwa.content.material_selection import web_problem_has_material
from models.pwa.content import ContentKind

BUNDLE = Path(__file__).resolve().parents[1] / "vmshpwa/admin-render/dist/render.cjs"


async def run_renderer(payload):
    if not BUNDLE.is_file():
        raise ValueError("admin_renderer_missing: make pwa-admin-render")
    proc = await asyncio.create_subprocess_exec(
        "node",
        str(BUNDLE),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        async with asyncio.timeout(20):
            data, _ = await proc.communicate(
                json.dumps(payload, ensure_ascii=False).encode()
            )
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
    if proc.returncode:
        raise ValueError("invalid_render_document")
    return data.decode()


def selected_blocks(blocks, labels):
    output = []
    for block in blocks:
        if block["type"] == "subpart" and block["label"] not in labels:
            continue
        copy = dict(block)
        if "blocks" in copy:
            copy["blocks"] = selected_blocks(copy["blocks"], labels)
        if "items" in copy and block["type"] == "list":
            copy["items"] = [selected_blocks(item, labels) for item in copy["items"]]
        output.append(copy)
    return output


async def render_sheet(
    api,
    group_lesson_id,
    mode: Literal["condition", "hint", "solution"],
    revisions,
    problem_ids,
):
    repo, scope, _ = await content._authorized_lesson_window_scope(
        api.command(path={"group_lesson_id": group_lesson_id})
    )

    def command(revision):
        return api.command(path={"revision_id": revision, "preview": "web"})

    documents = []
    missing = []
    by_kind = {}
    for kind in dict.fromkeys(("condition", mode)):
        if revisions is not None:
            revision = revisions.get(kind)
            if not revision and kind != "condition":
                continue
            if not revision:
                raise ValueError("missing_condition_revision")
            context = await repo.get_revision_context(revision)
            if (
                context.scope.group_lesson_id != scope.group_lesson_id
                or context.source.kind.value != kind
            ):
                raise ValueError("revision_outside_lesson_or_kind")
            document = unpack(await content.content_preview(command(revision)))[
                "document"
            ]
        else:
            try:
                publication = await repo.get_published_content(
                    group_lesson_public_id=group_lesson_id, kind=ContentKind(kind)
                )
            except ContentNotFound:
                if kind == "condition":
                    raise ValueError("condition_not_published") from None
                continue
            document = publication.document
            revision = publication.revision_public_id
        matches = unpack(await content.get_problem_matches(command(revision)))["items"]
        by_kind[kind] = (document, revision, matches)
    doc, revision, condition_rows = by_kind["condition"]

    def identity(row):
        return (row["match"] or {}).get("problemId")

    requested = set(problem_ids or [])
    if requested - {identity(r) for r in condition_rows}:
        raise ValueError("problem_not_in_condition")
    if not requested:
        documents.append({**doc, "problems": []})
    for problem in doc["problems"]:
        rows = [
            r
            for r in condition_rows
            if r["sourceOrdinal"] == problem["ordinal"]
            and (not requested or identity(r) in requested)
        ]
        if requested and not rows:
            continue
        blocks = (
            selected_blocks(problem["blocks"], {r["sourceItem"] for r in rows})
            if requested
            else problem["blocks"]
        )
        documents.append(
            {
                **doc,
                "title": None,
                "introduction": [],
                "problems": [{**problem, "blocks": blocks}],
            }
        )
        if mode == "condition":
            continue
        extra = by_kind.get(mode)
        chosen = {}
        for row in rows:
            pid = identity(row)
            match = (
                next(
                    (r for r in extra[2] if pid is not None and identity(r) == pid),
                    None,
                )
                if extra
                else None
            )
            material = (
                next(
                    (
                        p
                        for p in extra[0]["problems"]
                        if match and match["sourceOrdinal"] == p["ordinal"]
                    ),
                    None,
                )
                if extra
                else None
            )
            if material and web_problem_has_material(
                material, match["sourceItem"] if material.get("partLabels") else None
            ):
                chosen.setdefault(match["sourceOrdinal"], set()).add(
                    match["sourceItem"]
                )
            else:
                missing.append(
                    {
                        "displayNumber": row["displayNumber"],
                        "problemId": pid,
                        "kind": mode,
                    }
                )
        if extra:
            for material in extra[0]["problems"]:
                labels = chosen.get(material["ordinal"])
                if labels:
                    documents.append(
                        {
                            **extra[0],
                            "title": None,
                            "introduction": [],
                            "problems": [
                                {
                                    **material,
                                    "blocks": selected_blocks(
                                        material["blocks"], labels
                                    ),
                                }
                            ],
                        }
                    )
    locale = api.session.current.locale
    body = await run_renderer(
        {"action": "render", "documents": documents, "locale": locale}
    )
    html = (
        f'<!doctype html><html lang="{locale}"><meta charset="utf-8"><base href="'
        + escape(api.origin, quote=True)
        + '/">'
        + body
        + "</html>"
    )
    return {
        "html": html if len(html.encode()) <= 4 * 1024 * 1024 else None,
        "htmlInExport": True,
        "missing": missing,
        "export": await exports.save(
            api, group_lesson_id, revision, "worksheet.html", "text/html", html.encode()
        ),
    }
