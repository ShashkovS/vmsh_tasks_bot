from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
LEGACY_KEYWORD = 'le' 'vel'
PATTERN = re.compile(r'(\b|_)' + LEGACY_KEYWORD + r'\b')
SCAN_PATH_PREFIXES = (
    'apps/',
    'db_methods/',
    'handlers/',
    'helpers/',
    'models/',
    'tests/',
    'web/',
)
ALLOWED_FILES = {
    'groups.diff',
    'docs/db_structure.sql',
    'docs/db_data_examples.sql',
    'tests/test_no_legacy_group_refs.py',
}


def _is_allowed_logging_occurrence(line: str) -> bool:
    stripped = line.strip()
    return any(token in stripped for token in (
        'logging_' + LEGACY_KEYWORD,
        'event_' + LEGACY_KEYWORD + '=',
        LEGACY_KEYWORD + '=logging.',
        'basicConfig(' + LEGACY_KEYWORD + '=',
        '%(' + LEGACY_KEYWORD + 'name)s',
    ))


def test_no_legacy_group_keyword_references_outside_allowlist():
    offenders = []
    for path in ROOT.rglob('*'):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        top_dir = rel.split('/', 1)[0]
        if top_dir.startswith('.') and top_dir != '.changelog':
            continue
        if not any(rel.startswith(prefix) for prefix in SCAN_PATH_PREFIXES):
            continue
        if rel in ALLOWED_FILES:
            continue
        if '/.git/' in f'/{rel}' or '/__pycache__/' in f'/{rel}' or '/.pytest_cache/' in f'/{rel}':
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if not PATTERN.search(line):
                continue
            if _is_allowed_logging_occurrence(line):
                continue
            offenders.append(f'{rel}:{lineno}: {line.strip()}')
    assert not offenders, 'Legacy keyword references found:\n' + '\n'.join(offenders[:50])
