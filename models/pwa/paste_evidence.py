"""Text provenance and Staff estimates; vmshpwa/docs/paste-evidence.md."""

import base64
import binascii
import json
import math


def utf16_length(text: str | None) -> int:
    return len((text or "").encode("utf-16-le", errors="surrogatepass")) // 2


def validate_text_origin(value: object, text: str | None) -> dict | None:
    if value is None:
        return None
    if (
        not isinstance(value, dict)
        or set(value) != {"version", "utf16Length", "bits"}
        or type(value["version"]) is not int
        or value["version"] != 1
        or type(value["utf16Length"]) is not int
        or not 0 <= value["utf16Length"] <= 100_000
        or value["utf16Length"] != utf16_length(text)
        or not isinstance(value["bits"], str)
        or len(value["bits"]) > 16_668
    ):
        raise ValueError("invalid text origin")
    try:
        bits = base64.b64decode(value["bits"], validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError("invalid text origin bits") from error
    length = value["utf16Length"]
    if (
        len(bits) != (length + 7) // 8
        or base64.b64encode(bits).decode("ascii") != value["bits"]
        or (length % 8 and bits[-1] >> (length % 8))
    ):
        raise ValueError("invalid text origin bits")
    return value


def stored_origin(value: str | None) -> dict | None:
    return json.loads(value) if value is not None else None


def paste_estimate(
    *,
    text: str | None,
    author_kind: str,
    channel: str,
    text_origin_json: str | None = None,
    pasted_character_count: int = 0,
) -> dict | None:
    if (
        author_kind != "student"
        or channel not in ("pwa", "staff")
        or not text
        or not text.strip()
    ):
        return None
    length = utf16_length(text)
    origin = stored_origin(text_origin_json)
    if origin is not None:
        validate_text_origin(origin, text)
        count = sum(byte.bit_count() for byte in base64.b64decode(origin["bits"]))
        method = "remaining_text"
    else:
        count = min(length, pasted_character_count)
        method = "cumulative_pastes"
    percentage = (
        min(100, max(1, math.floor(count * 100 / length + 0.5))) if count else 0
    )
    return {"percentage": percentage, "method": method}


def estimate_row(row) -> dict | None:
    return paste_estimate(
        text=row["text"],
        author_kind=row["author_kind"],
        channel=row["channel"],
        text_origin_json=row["text_origin_json"],
        pasted_character_count=row["pasted_character_count"],
    )


def project_detail(detail: dict) -> dict:
    """Project storage provenance into the Staff history/serial wire boundary."""
    for entry in detail["entries"]:
        source = entry.pop("_pasteSource", None)
        entry["pasteEstimate"] = estimate_row(source) if source else None
    return detail
