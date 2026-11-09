#!/bin/bash
# Owner-authorized combined release; pwa_tests/reports/combined-optimization-figures-20261004/README.md.
set -Eeuo pipefail
BASE=/web/vmsh_tasks_bot
CODE=$BASE/vmsh_tasks_bot
TARGET=${1:?Pass the reviewed full commit SHA}
[[ "$TARGET" =~ ^[0-9a-f]{40}$ ]]
[[ $(hostname) == vmsh-nbg ]]
RELEASE=tlfprep-20261004-opt-figures-${TARGET:0:12}
RECORD=$BASE/deploy/releases/$RELEASE
STAGE=$RECORD/source
export PATH=$BASE/toolchains/node/bin:$BASE/toolchains/pnpm/node_modules/.bin:$BASE/toolchains/uv:$PATH
exec 9>"$BASE/deploy/metadata-deploy.lock"
flock -n 9
as_app() { runuser -u vmsh_tasks_bot -- "$@"; }
step() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*"; }
as_app git -C "$CODE" fetch origin vmshpwa
OLD_HEAD=$(as_app git -C "$CODE" rev-parse HEAD)
test "$OLD_HEAD" = dc80817329b81c405a86d83a05eb4d9b3fd5d74d
as_app git -C "$CODE" diff --quiet
as_app git -C "$CODE" diff --cached --quiet
as_app git -C "$CODE" merge-base --is-ancestor "$OLD_HEAD" "$TARGET"
as_app git -C "$CODE" merge-base --is-ancestor "$TARGET" origin/vmshpwa
as_app git -C "$CODE" diff --exit-code "$OLD_HEAD" "$TARGET" -- pyproject.toml uv.lock vmshpwa/pnpm-lock.yaml vmshpwa/deploy docs/deploy/tlf-app/build_source.sh docs/deploy/tlf-app/render_server.py
as_app git -C "$CODE" diff --name-status "$OLD_HEAD" "$TARGET" -- migrations | python3 -c 'import sys; rows=[line.rstrip().split("\t") for line in sys.stdin]; assert len(rows)==156; assert [r for r in rows if r[0]!="D"]==[["A","migrations/0111.current_schema.sql"]]'
test ! -e "$RECORD"
test ! -e "$BASE/vmshpwa/runtime/service-updating"
install -d -m 700 -o vmsh_tasks_bot -g nginx "$RECORD" "$STAGE"
install -m 700 "$0" "$RECORD/deploy.sh"
printf '%s\n' "$OLD_HEAD" > "$RECORD/source-before.txt"
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
step 'Adopting baseline on an online SQLite copy; comparing every product row'
as_app .venv/bin/python - <<PY
import sqlite3
with sqlite3.connect('file:$CODE/db/production_prep.db?mode=ro',uri=True) as source:
    with sqlite3.connect('$RECORD/rehearsal.sqlite3') as destination: source.backup(destination)
PY
as_app .venv/bin/python "$RECORD/data-check.py" "$RECORD/rehearsal.sqlite3" > "$RECORD/rehearsal-before.json"
as_app .venv/bin/python - <<PY > "$RECORD/rehearsal.log"
from db_methods.pwa.migrations import apply_schema_migrations,require_current_schema
from db_methods.pwa.schema_inventory import product_ddl_sha256
import sqlite3
state=apply_schema_migrations('$RECORD/rehearsal.sqlite3')
assert state.is_current and not state.baseline_adoptable and len(state.expected)==1
with sqlite3.connect('$RECORD/rehearsal.sqlite3') as db:
    assert product_ddl_sha256(db)=='7addfa22b6733d53fdfcdc0e9706b70ed81370b5a345506201c4025e5299d53a'
print('Current baseline accepted; product DDL unchanged, no historical chain executed')
PY
as_app .venv/bin/python "$RECORD/data-check.py" "$RECORD/rehearsal.sqlite3" > "$RECORD/rehearsal-after.json"
cmp "$RECORD/rehearsal-before.json" "$RECORD/rehearsal-after.json"
cd "$CODE"
STOPPED=false
CUTOVER=false
STARTED=false
rollback() {
    status=$?;trap - ERR
    step "Release failed with status $status"
    if [[ "$STOPPED" == true ]]; then
        systemctl stop vmsh-analytics.timer vmsh-analytics.service vmshpwa.service vmshzoom.service
        if [[ "$CUTOVER" == true && "$STARTED" == false ]]; then
            # Adoption only records yoyo metadata; undo that mark, never restore product data.
            cd "$STAGE"
            as_app .venv/bin/python - <<PY
import yoyo
selected=yoyo.read_migrations('$STAGE/migrations').filter(lambda migration:migration.id=='0111.current_schema')
with yoyo.get_backend('sqlite:///$CODE/db/production_prep.db') as backend:
    with backend.lock():backend.unmark_migrations(selected)
PY
            as_app git -C "$CODE" reset --hard "$OLD_HEAD"
        fi
        ln -s "$OLD_STATIC" "$BASE/vmshpwa/current.opt-figures-rollback"
        mv -Tf "$BASE/vmshpwa/current.opt-figures-rollback" "$BASE/vmshpwa/current"
        # After writers reopened, retain new source/schema and all new rows.
        systemctl start vmshpwa.service vmshzoom.service
        if [[ "$ANALYTICS_ACTIVE" == active ]];then systemctl start vmsh-analytics.timer;fi
        rm -f "$BASE/vmshpwa/runtime/service-updating"
    fi
    exit "$status"
}
trap rollback ERR
test "$(as_app git rev-parse HEAD)" = "$OLD_HEAD"
step 'Stopping writers for baseline metadata cutover'
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
STARTED=true
systemctl start vmshpwa.service vmshzoom.service
for attempt in $(seq 1 30);do
    if curl -fsS --unix-socket "$BASE/vmshpwa/runtime/vmshpwa.sock" -H 'Forwarded: for="127.0.0.1";proto=https;host="prep.leaders.tech"' http://prep.leaders.tech/student/api/v1/health > "$RECORD/backend-health.json" 2>/dev/null && curl -fsS --unix-socket "$BASE/vmshpwa/runtime/zoom.sock" http://localhost/health > "$RECORD/zoom-health.json" 2>/dev/null;then break;fi
    sleep 1
done
curl -fsS --unix-socket "$BASE/vmshpwa/runtime/vmshpwa.sock" -H 'Forwarded: for="127.0.0.1";proto=https;host="prep.leaders.tech"' http://prep.leaders.tech/student/api/v1/health >/dev/null
curl -fsS --unix-socket "$BASE/vmshpwa/runtime/zoom.sock" http://localhost/health >/dev/null
step 'Activating verified static; retaining assets from open tabs'
ln -s "$BASE/vmshpwa/releases/$RELEASE" "$BASE/vmshpwa/current.opt-figures"
mv -Tf "$BASE/vmshpwa/current.opt-figures" "$BASE/vmshpwa/current"
if [[ "$ANALYTICS_ACTIVE" == active ]];then systemctl start vmsh-analytics.timer;fi
rm -f "$BASE/vmshpwa/runtime/service-updating"
as_app .venv/bin/python -m vmshpwa.scripts.production_http_smoke --origin https://prep.leaders.tech --expected-instance production > "$RECORD/http-smoke.log" 2>&1
test "$(systemctl show -p MainPID --value nats.service)" = "$NATS_PID"
as_app .venv/bin/python "$BASE/deploy/bin/backup.py" > "$RECORD/backup-after.json"
trap - ERR
step "Deployment passed: source=$TARGET release=$RELEASE product_rows=unchanged credentials=unchanged NATS=unchanged"
cat "$RECORD/migration.log" "$RECORD/http-smoke.log" "$RECORD/backup-before.json" "$RECORD/backup-after.json"
