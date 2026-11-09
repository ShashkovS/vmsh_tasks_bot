"""Remaining vs cumulative estimate acceptance; docs/paste-evidence.md."""

import json

import pytest

from models.pwa.paste_evidence import paste_estimate, validate_text_origin


def estimate(text, bits=None, count=0):
    origin = (
        None
        if bits is None
        else json.dumps(
            {
                "version": 1,
                "utf16Length": len(text.encode("utf-16-le")) // 2,
                "bits": bits,
            }
        )
    )
    return paste_estimate(
        text=text,
        author_kind="student",
        channel="pwa",
        text_origin_json=origin,
        pasted_character_count=count,
    )


def test_remaining_counts_override_historical_total():
    assert estimate("abcd", "Dw==", 100)["percentage"] == 100
    assert estimate("abcd", "Aw==", 100)["percentage"] == 50
    assert estimate("abcd", "AA==", 100)["percentage"] == 0
    assert estimate("😀ab", "Aw==")["percentage"] == 50


def test_old_entries_are_clamped_and_nonzero_small_fraction_is_visible():
    assert estimate("ab", count=100) == {
        "percentage": 100,
        "method": "cumulative_pastes",
    }
    assert estimate("a" * 1000, count=1)["percentage"] == 1
    assert estimate("", count=10) is None
    assert paste_estimate(text="abc", author_kind="student", channel="telegram") is None
    assert paste_estimate(text="abc", author_kind="teacher", channel="pwa") is None


@pytest.mark.parametrize(
    "origin",
    [
        {"version": True, "utf16Length": 2, "bits": "Aw=="},
        {"version": 1, "utf16Length": 1, "bits": "Aw=="},
        {"version": 1, "utf16Length": 2, "bits": "AA="},
        {"version": 1, "utf16Length": 2, "bits": "/w=="},
        {"version": 1, "utf16Length": 2, "bits": "AB=="},
    ],
)
def test_invalid_origins(origin):
    with pytest.raises(ValueError):
        validate_text_origin(origin, "😀")
