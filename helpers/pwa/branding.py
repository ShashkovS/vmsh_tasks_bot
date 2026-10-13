"""Repository-owned profiles shared with frontend/build tooling (docs/branding.md)."""

import json
from pathlib import Path

PROFILES = {
    profile["id"]: profile
    for profile in json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "vmshpwa/packages/contracts/src/brand-profiles.json"
        ).read_text()
    )
}


def brand_manifest(profile_id: str, audience: str) -> dict:
    profile = PROFILES[profile_id]
    base = f"/{audience}/"
    assets = (
        base
        if profile_id == "vmsh"
        else f"{base}brands/{profile_id}/v{profile['assetVersion']}/"
    )
    role = {"student": "Student", "family": "Family"}[audience]
    if profile["defaultLocale"] == "ru":
        role = {"student": "школьник", "family": "кабинет родителя"}[audience]
    return {
        "id": base,
        "name": f"{profile['name']} — {role}",
        "short_name": "ВМШ Родитель"
        if profile_id == "vmsh" and audience == "family"
        else profile["name"],
        "description": (
            {
                "student": "Задачи, ответы, проверка и прогресс школьника ВМШ 179",
                "family": "Расписание, прогресс и новости ВМШ 179 для родителя",
            }[audience]
            if profile_id == "vmsh"
            else f"{profile['name']} — {role}"
        ),
        "lang": profile["defaultLocale"],
        "start_url": base,
        "scope": base,
        "display": "standalone",
        "theme_color": profile["themeColor"],
        "background_color": profile["backgroundColor"],
        "icons": [
            {
                "src": f"{assets}icon.svg",
                "sizes": "any",
                "type": "image/svg+xml",
                "purpose": "any",
            },
            *[
                {
                    "src": f"{assets}icon-{size}.png",
                    "sizes": f"{size}x{size}",
                    "type": "image/png",
                    "purpose": "any",
                }
                for size in (192, 512)
            ],
            {
                "src": f"{assets}icon-maskable-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
    }
