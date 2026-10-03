"""Course metadata model contract; see vmshpwa/docs/metadata-generation.md."""

import re


DEFAULT_METADATA_MODEL = "openai/gpt-5.6-luna"
METADATA_MODEL_PATTERN = r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._:/-]*"


def normalize_metadata_model(value: object) -> str:
    """Accept OpenRouter model IDs without a fixed list of providers/models."""

    if not isinstance(value, str):
        raise ValueError("invalid_metadata_model")
    normalized = value.strip()
    if (
        len(normalized) > 200
        or re.fullmatch(METADATA_MODEL_PATTERN, normalized) is None
    ):
        raise ValueError("invalid_metadata_model")
    return normalized
