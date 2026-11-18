"""Loader and validation helpers for the deterministic PWA baseline fixture."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FIXTURES_ROOT = Path(__file__).resolve().parent
BASELINE_V1_PATH = FIXTURES_ROOT / "baseline-v1.json"
ANSWER_TYPES_V1_PATH = FIXTURES_ROOT / "answer-types-v1.json"


def load_json_fixture(path: Path) -> dict[str, Any]:
    """Read a committed UTF-8 fixture without accepting duplicate JSON keys."""

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate key {key!r} in {path.name}")
            result[key] = value
        return result

    payload = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys
    )
    if not isinstance(payload, dict):
        raise ValueError(f"Fixture {path.name} must contain a JSON object")
    return payload


def load_baseline_v1() -> dict[str, Any]:
    payload = load_json_fixture(BASELINE_V1_PATH)
    if payload.get("fixture") != "baseline-v1":
        raise ValueError("The baseline fixture must identify itself as baseline-v1")
    return payload


def load_answer_types_v1() -> dict[str, Any]:
    payload = load_json_fixture(ANSWER_TYPES_V1_PATH)
    if payload.get("fixture") != "answer-types-v1":
        raise ValueError("The answer fixture must identify itself as answer-types-v1")
    return payload
