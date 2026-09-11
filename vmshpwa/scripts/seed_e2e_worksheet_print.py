"""Real published print fixtures; only the guarded E2E database/media.

See docs/worksheet-print.md and e2e/worksheet-print.spec.ts. No HTTP mocking.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from pathlib import Path

from helpers.object_storage import create_object_storage
from helpers.pwa.storage_config import load_storage_config
from vmshpwa.scripts.runtime_guard import require_pwa_profile_environment
from vmshpwa.scripts.seed_e2e_oral import (
    TIMESTAMP,
    _require_e2e_target,
    _seed,
    _web_document,
)

TARGETS = (("chromium", 32101), ("webkit", 32102), ("firefox", 32103))
SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="360" height="180" '
    b'viewBox="0 0 360 180"><rect width="360" height="180" fill="white"/>'
    b'<path d="M20 155L175 20L335 155Z" stroke="black" fill="none" '
    b'stroke-width="2"/><text x="170" y="17" font-size="16">A</text>'
    b'<text x="5" y="175" font-size="16">B</text>'
    b'<text x="337" y="175" font-size="16">C</text></svg>'
)
SHA = hashlib.sha256(SVG).hexdigest()


def paragraph(text):
    return {"type": "paragraph", "children": [{"type": "text", "value": text}]}


def figure():
    return {
        "type": "figure",
        "alt": "Треугольник ABC",
        "widthHint": "45%",
        "caption": [{"type": "text", "value": "Рис. 1. Треугольник ABC."}],
        "asset": {
            "status": "available",
            "assetId": "ma-32101",
            "contentSha256": SHA,
            "src": "/pwa-content-assets/ma-32101",
            "mediaType": "image/svg+xml",
            "width": 360,
            "height": 180,
        },
    }


def document_factory(**kwargs):
    doc = json.loads(_web_document(**kwargs))
    doc["problems"][0]["blocks"] = [
        paragraph("Найдите площадь треугольника ABC. Объясните своё решение."),
        {"type": "paragraph", "children": [{"type": "math", "latex": r"S=\frac{ah}{2}"}]},
        figure(),
    ]
    doc["problems"].append({
        "ordinal": 2,
        "sourceItem": None,
        "title": "Длинная задача с пунктами",
        "blocks": [
            {
                "type": "subpart", "label": "а", "title": "Рассуждение",
                "blocks": [
                    paragraph(
                        f"Шаг {n + 1}. Проведите высоту из вершины A и рассмотрите "
                        "два прямоугольных треугольника. Докажите равенство площадей "
                        "и запишите вывод."
                    )
                    for n in range(24)
                ],
            },
            {
                "type": "subpart", "label": "б", "title": "Чертёж ниже экрана",
                "blocks": [
                    paragraph("Проверьте полученный результат по чертежу."),
                    figure(),
                    {"type": "formula", "latex": r"a^2+b^2=c^2"},
                ],
            },
        ],
    })
    return json.dumps(doc, ensure_ascii=False)


def seed(config):
    database = _require_e2e_target(config)
    storage = create_object_storage(load_storage_config(
        runtime_profile="pwa-e2e", media_root=config.pwa_media_root,
        repository_root=Path(__file__).resolve().parents[2],
    ))
    asyncio.run(storage.put("worksheet-print/triangle.svg", SVG, "image/svg+xml"))
    with sqlite3.connect(database) as c:
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        if not _seed(c, TARGETS, document_factory=document_factory):
            return
        c.execute(
            'INSERT INTO '
            'media_assets(id,sha256,storage_namespace,object_key,media_type,byte_size,width,height,created_at) '
            "VALUES(32101,?,'content','worksheet-print/triangle.svg','image/svg+xml',?,360,180,?)",
            (
                SHA,
                len(SVG),
                TIMESTAMP,
            ),
        )
        for _, lesson in TARGETS:
            c.execute(
                "UPDATE course_lessons SET title='Геометрия для печати', updated_at=? WHERE "
                'id=?',
                (
                    TIMESTAMP,
                    lesson,
                ),
            )
            for offset, kind, label in ((10, "hint", "Подсказка"), (20, "solution", "Решение")):
                rid = lesson + offset
                c.execute(
                    'INSERT INTO '
                    'content_sources(id,group_lesson_id,kind,logical_filename,source_encoding,created_by_user_id,created_at) '
                    "VALUES(?,?,?,?,'utf-8',301,?)",
                    (
                        rid,
                        lesson,
                        kind,
                        kind + '.tex',
                        TIMESTAMP,
                    ),
                )
                doc = json.loads(_web_document(
                    revision_id=f"cr-{rid}", source_sha256=SHA, title=label,
                ))
                doc["materialKind"] = kind
                doc["problems"][0]["blocks"] = [
                    paragraph(f"{label} для печати: проведите высоту AH."), figure(),
                ]
                encoded = json.dumps(doc, ensure_ascii=False)
                c.execute(
                    'INSERT INTO '
                    'content_revisions(id,source_id,revision_number,source_sha256,latex_text,parser_version,status,canonical_json,diagnostics_json,provenance_json,created_by_user_id,created_at) '
                    "VALUES(?,?,1,?,'Материал','print-e2e','ready',?,'[]','{}',301,?)",
                    (
                        rid,
                        rid,
                        SHA,
                        encoded,
                        TIMESTAMP,
                    ),
                )
                c.execute(
                    'INSERT INTO '
                    'content_derivatives(revision_id,kind,renderer_version,content_text,sha256,diagnostics_json,provenance_json,created_at) '
                    "VALUES(?,'web_ast','print-e2e',?,?,'[]','{}',?)",
                    (
                        rid,
                        encoded,
                        hashlib.sha256(encoded.encode()).hexdigest(),
                        TIMESTAMP,
                    ),
                )
                c.execute(
                    'INSERT INTO '
                    'content_problem_matches(content_revision_id,source_ordinal,source_item,problem_id,decision,resolved_by_user_id,resolved_at,diagnostics_json,created_at) '
                    "VALUES(?,1,'1',?,'manual_match',301,?,'[]',?)",
                    (
                        rid,
                        lesson,
                        TIMESTAMP,
                        TIMESTAMP,
                    ),
                )
                c.execute(
                    'INSERT INTO '
                    'lesson_publications(group_lesson_id,kind,revision_id,state,published_at,created_by_user_id,published_by_user_id,created_at,updated_at) '
                    "VALUES(?,?,?,'published',?,301,301,?,?)",
                    (
                        lesson,
                        kind,
                        rid,
                        TIMESTAMP,
                        TIMESTAMP,
                        TIMESTAMP,
                    ),
                )
    print("Seeded worksheet print lessons")


if __name__ == "__main__":
    if require_pwa_profile_environment() != "pwa-e2e":
        raise RuntimeError("Worksheet fixture requires pwa-e2e")
    from helpers.config import config
    seed(config)
