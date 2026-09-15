"""Current result projection, shared by legacy and PWA adapters.

See vmshpwa/docs/live-marking.md and migration 0087. Older isolated legacy
fixtures can still use the raw ledger; migrated runtimes use the SQL view.
"""


def result_source(connection) -> str:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_schema WHERE type='view' AND name='effective_results'"
    ).fetchone()
    return "effective_results" if exists else "results"
