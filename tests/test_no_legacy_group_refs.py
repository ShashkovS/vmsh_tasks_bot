from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
LEGACY_KEYWORD = "level"
# The English word also describes log severity, headings and compression.  This
# guard is intentionally limited to code shapes that access the removed group
# field; the schema-level assertion lives in test_db_methods.py.
PATTERNS = (
    re.compile(rf"\[['\"]{LEGACY_KEYWORD}['\"]\]"),
    re.compile(rf"\.get\(\s*['\"]{LEGACY_KEYWORD}['\"]"),
    re.compile(rf"\b{LEGACY_KEYWORD}_id\b"),
    re.compile(rf"\b(?:user|problem|lesson)\.{LEGACY_KEYWORD}\b"),
)
SCAN_PATH_PREFIXES = (
    "apps/",
    "db_methods/",
    "handlers/",
    "helpers/",
    "models/",
    "tests/",
    "web/",
)
ALLOWED_FILES = {
    "groups.diff",
    "docs/db_structure.sql",
    "docs/db_data_examples.sql",
    # Rich-text heading levels are unrelated to the removed legacy group field.
    "models/pwa/rich_document.py",
    "tests/test_no_legacy_group_refs.py",
}


def test_no_legacy_group_keyword_references_outside_allowlist():
    offenders = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        top_dir = rel.split("/", 1)[0]
        if top_dir.startswith(".") and top_dir != ".changelog":
            continue
        if not any(rel.startswith(prefix) for prefix in SCAN_PATH_PREFIXES):
            continue
        if rel in ALLOWED_FILES:
            continue
        if (
            "/.git/" in f"/{rel}"
            or "/__pycache__/" in f"/{rel}"
            or "/.pytest_cache/" in f"/{rel}"
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if not any(pattern.search(line) for pattern in PATTERNS):
                continue
            offenders.append(f"{rel}:{lineno}: {line.strip()}")
    assert not offenders, "Legacy keyword references found:\n" + "\n".join(
        offenders[:50]
    )
