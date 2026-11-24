"""Restrict the replica key to SQLite origins; docs/deploy/sqlite-replica/README.md."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    'replica_origin', Path(__file__).parents[1] / 'docs/deploy/sqlite-replica/origin.py')
origin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(origin)


def test_accepts_only_selected_database_and_matching_destination():
    for source, target in origin.DATABASES.items():
        assert origin.source_for(f'{origin.BINARY} --origin {source} {target} 2>/dev/null') == Path(source)


@pytest.mark.parametrize('command', [
    '', 'id', '/bin/sh -c id',
    f'{origin.BINARY} --origin /etc/shadow main.sqlite3',
    f'{origin.BINARY} --replica /web/vmsh_tasks_bot/vmsh_tasks_bot/db/production_v2.db main.sqlite3',
    f'{origin.BINARY} --origin /web/vmsh_tasks_bot/vmsh_tasks_bot/db/production_v2.db analytics.sqlite3',
    f'{origin.BINARY} --origin /web/vmsh_tasks_bot/vmsh_tasks_bot/db/production_v2.db main.sqlite3; id',
])
def test_rejects_shell_commands_wrong_roles_paths_and_arguments(command):
    with pytest.raises(ValueError):
        origin.source_for(command)
