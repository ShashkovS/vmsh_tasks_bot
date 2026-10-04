"""Rehearse 0113 and exact repository upload method on server-only SQLite copies.

Input is reviewed migration/method code. No production rows or secrets exported.
See vmshpwa/docs/content-recovery-20261004.md (repeat upload incident).
"""

import asyncio
import base64
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

import yoyo


ROOT = Path('/web/vmsh_tasks_bot/vmsh_tasks_bot')
MODE = sys.argv[1]
assert MODE in {'vmsh', 'tlf'}
DATABASE = ROOT / ('db/production_v2.db' if MODE == 'vmsh' else 'db/production_prep.db')
INPUT = json.load(sys.stdin)
MIGRATION_ID = '0113.content_upload_compiler_generation'


def snapshot(connection):
    tables = {}
    for (name,) in connection.execute(
        "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "AND name NOT LIKE '%yoyo%' ORDER BY name"
    ):
        quoted = '"' + name.replace('"', '""') + '"'
        fields = ','.join('"' + column[1].replace('"', '""') + '"'
                          for column in connection.execute(f'PRAGMA table_info({quoted})'))
        digest = hashlib.sha256()
        count = 0
        for row in connection.execute(f'SELECT {fields} FROM {quoted} ORDER BY {fields}'):
            digest.update(repr(row).encode())
            digest.update(b'\n')
            count += 1
        tables[name] = {'count': count, 'sha256': digest.hexdigest()}
    return tables


def objects(connection):
    return connection.execute(
        "SELECT type,name,sql FROM sqlite_schema WHERE sql IS NOT NULL "
        "AND name NOT LIKE '%yoyo%' ORDER BY type,name"
    ).fetchall()


with tempfile.TemporaryDirectory(prefix='content-upload-generation-') as temporary:
    directory = Path(temporary)
    copy_path = directory / 'rehearsal.sqlite3'
    with sqlite3.connect(f'file:{DATABASE}?mode=ro', uri=True) as live:
        with sqlite3.connect(copy_path) as copy:
            live.backup(copy, pages=256, sleep=0.05)
    with sqlite3.connect(copy_path) as copy:
        before = snapshot(copy)
        ddl_before = objects(copy)
        fk_before = sorted(copy.execute('PRAGMA foreign_key_check').fetchall())
        reproduced = []
        if MODE == 'vmsh':
            for public_id in ('cr-71', 'cr-75'):
                copy.execute('SAVEPOINT previous_upload')
                try:
                    copy.execute(
                        "UPDATE content_revisions SET status='uploaded', parser_version='vmsh-latex-compiler/9', "
                        "canonical_json=NULL, diagnostics_json='[]', version=version+1 WHERE public_id=?",
                        (public_id,),
                    )
                except sqlite3.IntegrityError as error:
                    assert 'terminal content revision is immutable' in str(error)
                    reproduced.append({'revision': public_id, 'cause': str(error)})
                else:
                    raise AssertionError('Expected terminal revision reset conflict')
                finally:
                    copy.execute('ROLLBACK TO previous_upload')
                    copy.execute('RELEASE previous_upload')
    migrations = directory / 'migrations'
    migrations.mkdir()
    for name in ('0111.current_schema.sql', '0112.scheduled_publication_lifecycle.py'):
        shutil.copyfile(ROOT / 'migrations' / name, migrations / name)
    migration_bytes = base64.b64decode(INPUT['migration'], validate=True)
    (migrations / f'{MIGRATION_ID}.py').write_bytes(migration_bytes)
    migration_list = yoyo.read_migrations(str(migrations))
    started = time.monotonic()
    with yoyo.get_backend(f'sqlite:///{copy_path}') as backend:
        with backend.lock():
            backend.apply_migrations(backend.to_apply(migration_list))
    migration_seconds = time.monotonic() - started
    with sqlite3.connect(copy_path) as copy:
        assert snapshot(copy) == before
        ddl_after = objects(copy)
        changed = [name for kind, name, sql in ddl_after if (kind, name, sql) not in ddl_before]
        assert changed == ['content_revisions'], changed
        assert len(ddl_after) == len(ddl_before)
        assert sorted(copy.execute('PRAGMA foreign_key_check').fetchall()) == fk_before
        assert copy.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
        copy.execute('PRAGMA journal_mode=WAL')

    # The legacy models package imports Config. Its existing isolated history
    # profile supplies fictitious credentials, opens no network or production DB.
    os.environ['VMSH_RUNTIME_PROFILE'] = 'telegram-history-test'
    os.environ['PROD'] = 'false'
    from db_methods.pwa import migrations as migration_module
    from db_methods.pwa import content as content_module
    from db_methods.pwa import PwaConnectionFactory
    from models.pwa.content import ContentKind, SourceRevisionPayload

    migration_module.MIGRATIONS_ROOT = migrations
    namespace = dict(vars(content_module))
    exec('from __future__ import annotations\n' + INPUT['method'], namespace)
    content_module.PwaContentRepository.resolve_source_and_append_revision = namespace['resolve_source_and_append_revision']
    factory = PwaConnectionFactory(copy_path)
    repository = content_module.PwaContentRepository(factory)

    async def upload_probes():
        results = []
        with sqlite3.connect(copy_path) as copy:
            if MODE == 'vmsh':
                candidates = ['cr-71', 'cr-75']
            else:
                candidates = [row[0] for row in copy.execute(
                    "SELECT r.public_id FROM content_revisions r JOIN content_sources s ON s.id=r.source_id "
                    "WHERE r.status IN ('ready','invalid') AND s.archived_at IS NULL "
                    "ORDER BY r.id LIMIT 2"
                )]
        for public_id in candidates:
            old = await repository.get_revision_context(public_id)
            encoding = old.revision.provenance.get('sourceEncoding', old.source.source_encoding)
            prefix = b'\xef\xbb\xbf' if old.revision.provenance.get('sourceHadUtf8Bom') else b''
            raw = prefix + old.revision.latex_text.encode(encoding)
            assert hashlib.sha256(raw).hexdigest() == old.revision.source_sha256
            payload = SourceRevisionPayload.from_bytes(raw, encoding=encoding, provenance=dict(old.revision.provenance))
            with sqlite3.connect(copy_path) as copy:
                actor = copy.execute('SELECT created_by_user_id FROM content_revisions WHERE id=?',
                                     (old.revision.id,)).fetchone()[0]
            arguments = dict(
                group_lesson_id=old.scope.group_lesson_id, kind=ContentKind(old.source.kind),
                logical_filename=old.source.logical_filename, payload=payload,
                actor_user_id=actor, parser_version='vmsh-latex-compiler/9',
            )
            upgraded = await repository.resolve_source_and_append_revision(
                source_public_id='unused-probe-source', revision_public_id='unused-probe-revision', **arguments,
            )
            repeated = await repository.resolve_source_and_append_revision(
                source_public_id='unused-probe-source-2', revision_public_id='unused-probe-revision-2', **arguments,
            )
            assert upgraded.source.id == old.source.id
            assert upgraded.revision.source_sha256 == old.revision.source_sha256
            assert upgraded.revision.id != old.revision.id
            assert upgraded.revision.status.value == 'uploaded'
            assert repeated.revision == upgraded.revision
            assert await repository.get_revision_context(public_id) == old
            results.append({'old_revision': public_id, 'old_status': old.revision.status.value,
                            'new_generation': 'uploaded', 'repeated_upload_idempotent': True,
                            'source_lineage_retained': True, 'terminal_snapshot_identical': True})
        await factory.aclose()
        return results

    probes = asyncio.run(upload_probes())
    output = dict(
        host=MODE, migration=MIGRATION_ID,
        migration_sha256=hashlib.sha256(migration_bytes).hexdigest(),
        repository_method_sha256=hashlib.sha256(INPUT['method'].encode()).hexdigest(),
        migration_seconds=round(migration_seconds, 3), product_tables=len(before),
        product_rows=sum(value['count'] for value in before.values()), product_rows_identical=True,
        changed_objects=changed, integrity='ok', existing_fk_errors=len(fk_before), new_fk_errors=0,
        old_failure_reproduced=reproduced, upload_probes=probes,
        data_export='Production row data stayed on server; disposable copy removed.',
    )
    print(json.dumps(output))
