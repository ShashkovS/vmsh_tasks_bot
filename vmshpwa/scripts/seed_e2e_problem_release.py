"""Fifteen real tasks for docs/problem-release.md; guarded E2E database only."""

from contextlib import closing

import hashlib
import json
import sqlite3

from vmshpwa.scripts.runtime_guard import require_pwa_profile_environment
from vmshpwa.scripts.seed_e2e_oral import (
    TIMESTAMP,
    _require_e2e_target,
    _seed,
    _web_document,
)

TARGETS = (("chromium", 15101), ("webkit", 15102), ("firefox", 15103))


def document_factory(**kwargs):
    document = json.loads(_web_document(**kwargs))
    document["problems"] = [
        {
            "ordinal": number,
            "sourceItem": str(number),
            "title": f"Выдача задачи {number}",
            "blocks": [
                {
                    "type": "paragraph",
                    "children": [
                        {
                            "type": "text",
                            "value": f"Условие открываемой задачи {number}.",
                        }
                    ],
                }
            ],
        }
        for number in range(1, 16)
    ]
    return json.dumps(document, ensure_ascii=False)


def seed(config):
    database = _require_e2e_target(config)
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        if not _seed(connection, TARGETS, document_factory=document_factory):
            return
        for _, lesson in TARGETS:
            for number in range(2, 16):
                problem_id = lesson + number * 100_000
                title = f"Выдача задачи {number}"
                connection.execute(
                    "INSERT INTO problems (id,group_id,lesson,prob,item,title,prob_text,prob_type,ans_type,synonyms) "
                    "SELECT ?,group_id,lesson,?,'',?,'',3,NULL,'' FROM problems WHERE id=?",
                    (problem_id, number, title, lesson),
                )
                connection.execute(
                    "INSERT INTO content_problem_matches "
                    "(content_revision_id,source_ordinal,source_item,problem_id,decision,resolved_by_user_id,resolved_at,diagnostics_json,created_at) "
                    "VALUES(?,?,?,?,'manual_match',301,?,'[]',?)",
                    (lesson, number, str(number), problem_id, TIMESTAMP, TIMESTAMP),
                )
                connection.execute(
                    "INSERT INTO problem_revisions "
                    "(problem_id,content_revision_id,source_ordinal,source_item,display_number,title,normalized_title,problem_type,answer_type,answer_config_json,attempt_policy_json,config_version,created_at) "
                    "VALUES(?,?,?,?,?,?,?,3,NULL,'{}','{}',1,?)",
                    (
                        problem_id,
                        lesson,
                        number,
                        str(number),
                        str(number),
                        title,
                        title.casefold(),
                        TIMESTAMP,
                    ),
                )
            html = "<p>Условия для позадачной публикации.</p>"
            connection.execute(
                "UPDATE problems SET ans_type=NULL WHERE id=?", (lesson,)
            )
            connection.execute(
                "INSERT INTO content_derivatives (revision_id,kind,renderer_version,content_text,sha256,diagnostics_json,provenance_json,created_at) "
                "VALUES(?,'telegram_html','release-e2e',?,?,'[]','{}',?)",
                (lesson, html, hashlib.sha256(html.encode()).hexdigest(), TIMESTAMP),
            )


if __name__ == "__main__":
    if require_pwa_profile_environment() != "pwa-e2e":
        raise RuntimeError("Problem release seed requires the isolated E2E profile")
    from helpers.config import config

    seed(config)
