"""Release-only schema rollback; docs/deploy/ai-review-performance-20261018.md."""
import json
import sqlite3
import sys
from pathlib import Path
import yoyo

database, migrations, before_path = sys.argv[1:]
before = set(json.loads(Path(before_path).read_text()))
with sqlite3.connect(database) as connection:
    names = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for name in ('ai_review_tokens', 'ai_review_suggestions', 'ai_review_events'):
        if name in names and connection.execute(f'SELECT count(*) FROM {name}').fetchone()[0]:
            raise RuntimeError('AI data exists; retain maintenance and current schema')
backend = yoyo.get_backend(f'sqlite:///{database}')
with backend.lock():
    pending = [m for m in backend.to_rollback(yoyo.read_migrations(migrations)) if m.id not in before]
    if not all(m.id in {'0121.review_sheet_indexes', '0122.ai_review_assistant'} for m in pending):
        raise RuntimeError('Unexpected rollback set')
    backend.rollback_migrations(pending)
print(json.dumps({'rolledBack': [m.id for m in pending]}))
