"""Whiteboard assets are synthetic and confined to the guarded E2E profile."""

import asyncio
import hashlib
import struct
import zlib
import json
import sqlite3
from pathlib import Path
from helpers.object_storage import create_object_storage
from helpers.pwa.storage_config import load_storage_config
from vmshpwa.scripts.runtime_guard import require_pwa_profile_environment
from vmshpwa.scripts.seed_e2e_oral import TIMESTAMP, _require_e2e_target, _seed
from vmshpwa.scripts.seed_e2e_worksheet_print import document_factory, paragraph

TARGETS = (("chromium", 34101), ("webkit", 34102), ("firefox", 34103))


def png_chunk(kind, data):
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data))
    )


PNG = (
    b"\x89PNG\r\n\x1a\n"
    + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 120, 60, 8, 2, 0, 0, 0))
    + png_chunk(b"IDAT", zlib.compress((b"\0" + bytes((220, 30, 80)) * 120) * 60))
    + png_chunk(b"IEND", b"")
)
SHA = hashlib.sha256(PNG).hexdigest()


def document(**kwargs):
    doc = json.loads(document_factory(**kwargs))
    doc["introduction"] = [
        paragraph("Общее введение для разбора: обосновывайте каждый переход.")
    ]
    doc["problems"][0]["blocks"].append(
        {
            "type": "figure",
            "alt": "Цветной прямоугольник",
            "caption": [{"type": "text", "value": "Рис. 2. Цвета сохраняются."}],
            "asset": {
                "status": "available",
                "assetId": "ma-34101",
                "contentSha256": SHA,
                "src": "/pwa-content-assets/ma-34101",
                "mediaType": "image/png",
                "width": 120,
                "height": 60,
            },
        }
    )
    return json.dumps(doc, ensure_ascii=False)


def seed(config):
    database = _require_e2e_target(config)
    storage = create_object_storage(
        load_storage_config(
            runtime_profile="pwa-e2e",
            media_root=config.pwa_media_root,
            repository_root=Path(__file__).resolve().parents[2],
        )
    )
    asyncio.run(storage.put("whiteboard/color.png", PNG, "image/png"))
    with sqlite3.connect(database) as c:
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        if not _seed(c, TARGETS, document_factory=document):
            return
        c.execute(
            "INSERT INTO media_assets(id,sha256,storage_namespace,object_key,media_type,byte_size,width,height,created_at) VALUES(34101,?,'content','whiteboard/color.png','image/png',?,120,60,?)",
            (SHA, len(PNG), TIMESTAMP),
        )


if __name__ == "__main__":
    if require_pwa_profile_environment() != "pwa-e2e":
        raise RuntimeError("Whiteboard fixtures require pwa-e2e")
    from helpers.config import config

    seed(config)
