"""Current result projection, shared by legacy and PWA adapters.

See vmshpwa/docs/written-result-precedence.md and migration 0110. Older isolated legacy
fixtures can still use the raw ledger; migrated runtimes use the SQL view.
"""


def result_source(connection) -> str:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_schema WHERE type='view' AND name='effective_results'"
    ).fetchone()
    return "effective_results" if exists else "results"


def result_problem_join(connection) -> str:
    """Project the selected source result onto each confirmed problem alias."""
    exists = connection.execute(
        "SELECT 1 FROM sqlite_schema WHERE type='view' AND name='result_problem_groups'"
    ).fetchone()
    if exists:
        return """JOIN result_problem_groups source ON source.problem_id=r.problem_id
        JOIN result_problem_groups target ON target.logical_key=source.logical_key
        JOIN problems p ON p.id=target.problem_id"""
    return "JOIN problems p ON p.id=r.problem_id"
