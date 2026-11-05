#!/bin/bash
# Owner-authorized manual release; vmshpwa/docs/content-recovery-20261004.md.
set -Eeuo pipefail
BASE=/web/vmsh_tasks_bot
CODE=$BASE/vmsh_tasks_bot
TARGET=${1:?Pass the reviewed full commit SHA}
ROLLBACK=43b7d2f42c69169ca6f85fc0773071c7fe2b24e4
[[ "$TARGET" =~ ^[0-9a-f]{40}$ ]]
[[ $(hostname) == vmsh-nbg ]]
RELEASE=tlfprep-20261004-content-recovery-${TARGET:0:12}
RECORD=$BASE/deploy/releases/$RELEASE
STAGE=$RECORD/source
export PATH=$BASE/toolchains/node/bin:$BASE/toolchains/pnpm/node_modules/.bin:$BASE/toolchains/uv:$PATH
exec 9>"$BASE/deploy/metadata-deploy.lock"
flock -n 9
as_app() { runuser -u vmsh_tasks_bot -- "$@"; }
step() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*"; }
as_app git -C "$CODE" fetch origin vmshpwa codex/content-recovery-rollback-20261004
OLD_HEAD=$(as_app git -C "$CODE" rev-parse HEAD)
test "$OLD_HEAD" = b6476a52133ca301ad17861f30cc6c8a6c4b5bc7
as_app git -C "$CODE" diff --quiet
as_app git -C "$CODE" diff --cached --quiet
as_app git -C "$CODE" merge-base --is-ancestor "$OLD_HEAD" "$TARGET"
as_app git -C "$CODE" merge-base --is-ancestor "$TARGET" origin/vmshpwa
as_app git -C "$CODE" cat-file -e "$ROLLBACK^{commit}"
as_app git -C "$CODE" diff --exit-code "$OLD_HEAD" "$TARGET" -- pyproject.toml uv.lock vmshpwa/pnpm-lock.yaml vmshpwa/deploy docs/deploy/tlf-app/build_source.sh docs/deploy/tlf-app/render_server.py
as_app git -C "$CODE" diff --name-status "$OLD_HEAD" "$TARGET" -- migrations | python3 -c 'import sys; assert sys.stdin.read().splitlines()==["A\tmigrations/0112.scheduled_publication_lifecycle.py"]'
test ! -e "$RECORD"
test ! -e "$BASE/vmshpwa/runtime/service-updating"
install -d -m 700 -o vmsh_tasks_bot -g nginx "$RECORD" "$STAGE"
install -m 700 "$0" "$RECORD/deploy.sh"
printf '%s\n' "$OLD_HEAD" > "$RECORD/source-before.txt"
printf '%s\n' "$TARGET" > "$RECORD/source-after.txt"
OLD_STATIC=$(readlink "$BASE/vmshpwa/current")
printf '%s\n' "$OLD_STATIC" > "$RECORD/static-before.txt"
NATS_PID=$(systemctl show -p MainPID --value nats.service)
ANALYTICS_ACTIVE=$(systemctl is-active vmsh-analytics.timer || true)
cd "$CODE"
sha256sum creds_prod/vmsh_bot_config_prod.json > "$RECORD/credentials-before.sha256"
step 'Verified backups before release'
as_app .venv/bin/python "$BASE/deploy/bin/backup.py" > "$RECORD/backup-before.json"
as_app git archive "$TARGET" | as_app tar -x -C "$STAGE"
as_app ln -s "$CODE/.venv" "$STAGE/.venv"
install -m 644 "$STAGE/docs/deploy/tlf-app/rich_files_data_check.py" "$RECORD/data-check.py"
step 'Building isolated production bundles from cached frozen dependencies'
cd "$STAGE"
as_app env CI=true pnpm --dir vmshpwa install --frozen-lockfile --ignore-scripts --prefer-offline --store-dir "$BASE/cache/pnpm" > "$RECORD/frontend-install.log" 2>&1
as_app env TLF_RELEASE_ID="$RELEASE" .venv/bin/python - <<'PY' > "$RECORD/frontend-build.log" 2>&1
import json, os, re, subprocess
from pathlib import Path
config=json.loads(Path('/web/vmsh_tasks_bot/vmsh_tasks_bot/creds_prod/vmsh_bot_config_prod.json').read_text())
release=os.environ['TLF_RELEASE_ID']
environment=dict(os.environ, CI='true', VITE_SENTRY_DSN=config['sentry_dsn'], VITE_PWA_PROTOTYPE='false', VMSH_FRONTEND_BUILD_PROFILE='production', VITE_SENTRY_RELEASE=release, VITE_PUBLIC_MEDIA_ORIGIN='https://tlfprepimages.nbg1.your-objectstorage.com')
for audience in ('landing', 'student', 'family', 'staff'):
    subprocess.run(['../../node_modules/.bin/vite', 'build'], cwd=f'vmshpwa/apps/{audience}', env=environment, check=True)
    index=Path(f'vmshpwa/apps/{audience}/dist/index.html')
    index.write_text(re.sub(r'((?:src|href)="/[^"?]+/assets/[^"?]+\.(?:js|css))"',rf'\1?release={release}"',index.read_text()))
PY
step 'Verifying production provenance and preparing immutable static assets'
as_app .venv/bin/python -m vmshpwa.scripts.static_release package --release-id "$RELEASE" --release-root "$RECORD/static" --report "$RECORD/static-package.json" > "$RECORD/static-package.log"
env RELEASE="$RELEASE" RECORD="$RECORD" python3 - <<'PY'
import os, shutil
from pathlib import Path
base=Path('/web/vmsh_tasks_bot/vmshpwa')
source=Path(os.environ['RECORD'])/'static'/os.environ['RELEASE']
release=base/'releases'/os.environ['RELEASE']
shutil.copytree(source,release)
for audience in ('landing','student','family','staff'):
    assets=release/audience/'assets'; store=base/'immutable-assets'/audience/'assets'
    for path in assets.rglob('*'):
        if path.is_file():
            destination=store/path.relative_to(assets)
            if destination.exists(): assert path.read_bytes()==destination.read_bytes(),'Immutable asset collision'
    shutil.copytree(assets,store,dirs_exist_ok=True)
for directory in (release,base/'immutable-assets'):
    shutil.chown(directory,user='root',group='nginx');directory.chmod(0o750)
    for path in directory.rglob('*'):
        assert not path.is_symlink()
        shutil.chown(path,user='root',group='nginx');path.chmod(0o750 if path.is_dir() else 0o640)
PY
.venv/bin/python -m vmshpwa.scripts.static_release verify --release-id "$RELEASE" --release-root "$BASE/vmshpwa/releases" --report "$RECORD/static-verified.json" > "$RECORD/static-verified.log"
step 'Rehearsing migration 0112 on an online SQLite copy'
as_app .venv/bin/python - <<PY
import sqlite3
with sqlite3.connect('file:$CODE/db/production_prep.db?mode=ro',uri=True) as source:
    with sqlite3.connect('$RECORD/rehearsal.sqlite3') as destination: source.backup(destination)
PY
as_app .venv/bin/python "$RECORD/data-check.py" "$RECORD/rehearsal.sqlite3" > "$RECORD/rehearsal-before.json"
as_app .venv/bin/python - "$RECORD/rehearsal.sqlite3" <<'PY' > "$RECORD/rehearsal.json"
import json, sqlite3, sys, time
from db_methods.pwa.migrations import apply_schema_migrations, require_current_schema
path=sys.argv[1]
def objects(db):
    return db.execute("SELECT type,name,sql FROM sqlite_schema WHERE sql IS NOT NULL AND name NOT LIKE '_yoyo%' AND name<>'yoyo_lock' ORDER BY type,name").fetchall()
with sqlite3.connect(path) as db:
    before=objects(db)
    before_fk=sorted(db.execute('PRAGMA foreign_key_check').fetchall())
started=time.monotonic()
state=apply_schema_migrations(path)
assert state.is_current and len(state.expected)==2
require_current_schema(path)
with sqlite3.connect(path) as db:
    after=objects(db)
    changed=[name for kind,name,sql in after if (kind,name,sql) not in before]
    assert changed==['lesson_publications'],changed
    assert len(before)==len(after)
    assert sorted(db.execute('PRAGMA foreign_key_check').fetchall())==before_fk
    assert db.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
print(json.dumps(dict(migration='0112.scheduled_publication_lifecycle',seconds=round(time.monotonic()-started,3),schema_current=True,changed_objects=changed,existing_fk_errors=len(before_fk),new_fk_errors=0,integrity='ok')))
PY
as_app .venv/bin/python "$RECORD/data-check.py" "$RECORD/rehearsal.sqlite3" > "$RECORD/rehearsal-after.json"
cmp "$RECORD/rehearsal-before.json" "$RECORD/rehearsal-after.json"
cd "$CODE"
STOPPED=false
CUTOVER=false
rollback() {
    status=$?;trap - ERR
    step "Release failed with status $status; retain live data and schedule history"
    if [[ "$STOPPED" == true ]]; then
        systemctl stop vmsh-analytics.timer vmsh-analytics.service vmshpwa.service vmshzoom.service
        if [[ "$CUTOVER" == true ]]; then
            # Once 0112 is marked, code rollback keeps it; see rollback-source.json.
            if as_app .venv/bin/python - <<PY
import sqlite3,sys
with sqlite3.connect('file:$CODE/db/production_prep.db?mode=ro',uri=True) as db:
    applied=db.execute("SELECT 1 FROM _yoyo_migration WHERE migration_id='0112.scheduled_publication_lifecycle'").fetchone()
sys.exit(0 if applied else 1)
PY
            then as_app git -C "$CODE" reset --hard "$ROLLBACK"
            else as_app git -C "$CODE" reset --hard "$OLD_HEAD";fi
        fi
        ln -s "$OLD_STATIC" "$BASE/vmshpwa/current.content-recovery-rollback"
        mv -Tf "$BASE/vmshpwa/current.content-recovery-rollback" "$BASE/vmshpwa/current"
        systemctl start vmshpwa.service vmshzoom.service
        if [[ "$ANALYTICS_ACTIVE" == active ]];then systemctl start vmsh-analytics.timer;fi
        rm -f "$BASE/vmshpwa/runtime/service-updating"
    fi
    exit "$status"
}
trap rollback ERR
test "$(as_app git rev-parse HEAD)" = "$OLD_HEAD"
step 'Stopping SQLite writers for the checked migration'
touch "$BASE/vmshpwa/runtime/service-updating"
STOPPED=true
systemctl stop vmsh-analytics.timer vmsh-analytics.service vmshpwa.service vmshzoom.service
as_app .venv/bin/python "$RECORD/data-check.py" "$CODE/db/production_prep.db" > "$RECORD/data-before.json"
CUTOVER=true
as_app git reset --hard "$TARGET" > "$RECORD/checkout.log"
as_app env PROD=true VMSH_RUNTIME_PROFILE=pwa-production VMSH_PWA_PROTOTYPE=false .venv/bin/python -m vmshpwa.scripts.migrate_runtime > "$RECORD/migration.log" 2>&1
as_app env PROD=true VMSH_RUNTIME_PROFILE=pwa-production VMSH_PWA_PROTOTYPE=false .venv/bin/python -m vmshpwa.scripts.database_performance_guard > "$RECORD/database-guard.json" 2>&1
as_app .venv/bin/python "$RECORD/data-check.py" "$CODE/db/production_prep.db" > "$RECORD/data-after.json"
cmp "$RECORD/data-before.json" "$RECORD/data-after.json"
sha256sum -c "$RECORD/credentials-before.sha256" > "$RECORD/credentials-check.log"
systemctl start vmshpwa.service vmshzoom.service
for attempt in $(seq 1 30);do
    if curl -fsS --unix-socket "$BASE/vmshpwa/runtime/vmshpwa.sock" -H 'Forwarded: for="127.0.0.1";proto=https;host="prep.leaders.tech"' http://prep.leaders.tech/student/api/v1/health > "$RECORD/backend-health.json" 2>/dev/null && curl -fsS --unix-socket "$BASE/vmshpwa/runtime/zoom.sock" http://localhost/health > "$RECORD/zoom-health.json" 2>/dev/null;then break;fi
    sleep 1
done
curl -fsS --unix-socket "$BASE/vmshpwa/runtime/vmshpwa.sock" -H 'Forwarded: for="127.0.0.1";proto=https;host="prep.leaders.tech"' http://prep.leaders.tech/student/api/v1/health >/dev/null
curl -fsS --unix-socket "$BASE/vmshpwa/runtime/zoom.sock" http://localhost/health >/dev/null
step 'Activating verified static; retaining assets from open tabs'
ln -s "$BASE/vmshpwa/releases/$RELEASE" "$BASE/vmshpwa/current.content-recovery"
mv -Tf "$BASE/vmshpwa/current.content-recovery" "$BASE/vmshpwa/current"
if [[ "$ANALYTICS_ACTIVE" == active ]];then systemctl start vmsh-analytics.timer;fi
rm -f "$BASE/vmshpwa/runtime/service-updating"
as_app .venv/bin/python -m vmshpwa.scripts.production_http_smoke --origin https://prep.leaders.tech --expected-instance production > "$RECORD/http-smoke.log" 2>&1
test "$(systemctl show -p MainPID --value nats.service)" = "$NATS_PID"
systemctl is-active --quiet vmshpwa.service vmshzoom.service vmsh-analytics.timer nats.service
as_app .venv/bin/python "$BASE/deploy/bin/backup.py" > "$RECORD/backup-after.json"
trap - ERR
step "Deployment passed: source=$TARGET release=$RELEASE product_rows=unchanged credentials=unchanged NATS=unchanged"
cat "$RECORD/rehearsal.json" "$RECORD/migration.log" "$RECORD/http-smoke.log" "$RECORD/backup-before.json" "$RECORD/backup-after.json"
