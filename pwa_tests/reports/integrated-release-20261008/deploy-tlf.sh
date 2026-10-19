#!/bin/bash
# Owner-authorized release: docs/performance/integrated-release-20261008.md.
# Run as root on TLF; the only argument is the tested full commit SHA.
set -Eeuo pipefail
umask 027
BASE=/web/vmsh_tasks_bot
CODE=$BASE/vmsh_tasks_bot
TARGET=${1:?Pass the reviewed full commit SHA}
[[ "$TARGET" =~ ^[0-9a-f]{40}$ ]]
[[ $(hostname) == vmsh-nbg ]]
RELEASE=tlfprep-20261008-integrated-${TARGET:0:12}-r2
RECORD=$BASE/deploy/releases/$RELEASE
STAGE=$RECORD/source
DB=$CODE/db/production_prep.db
export PATH=$BASE/toolchains/node/bin:$BASE/toolchains/pnpm/node_modules/.bin:$BASE/toolchains/uv:$PATH
exec 9>"$BASE/deploy/metadata-deploy.lock"
flock -n 9
as_app() { runuser -u vmsh_tasks_bot -- "$@"; }
step() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*"; }
as_app git -C "$CODE" fetch origin vmshpwa
OLD_HEAD=$(as_app git -C "$CODE" rev-parse HEAD)
as_app git -C "$CODE" diff --quiet
as_app git -C "$CODE" diff --cached --quiet
as_app git -C "$CODE" merge-base --is-ancestor "$OLD_HEAD" "$TARGET"
as_app git -C "$CODE" merge-base --is-ancestor "$TARGET" origin/vmshpwa
as_app git -C "$CODE" diff --exit-code "$OLD_HEAD" "$TARGET" -- pyproject.toml uv.lock vmshpwa/pnpm-lock.yaml docs/deploy/tlf-app/build_source.sh docs/deploy/tlf-app/render_server.py
test "$(as_app git -C "$CODE" diff --name-only "$OLD_HEAD" "$TARGET" -- vmshpwa/deploy)" = $'vmshpwa/deploy/nginx/README.md\nvmshpwa/deploy/nginx/vmshpwa.conf.template'
test "$(as_app git -C "$CODE" diff --name-status "$OLD_HEAD" "$TARGET" -- migrations)" = $'A\tmigrations/0114.browser_image_uploads.py\nA\tmigrations/0115.vmsh_public_media_domain.py\nA\tmigrations/0116.notification_push_candidate_index.py'
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
step 'Verified main and analytics backups before release'
as_app .venv/bin/python "$BASE/deploy/bin/backup.py" > "$RECORD/backup-before.json"
as_app git archive "$TARGET" | as_app tar -x -C "$STAGE"
as_app ln -s "$CODE/.venv" "$STAGE/.venv"
as_app ln -s "$CODE/creds_prod/vmsh_bot_config_prod.json" "$STAGE/creds_prod/vmsh_bot_config_prod.json"
install -m 644 "$STAGE/docs/deploy/tlf-app/rich_files_data_check.py" "$RECORD/data-check.py"
cd "$STAGE"
step 'Building isolated production bundles using frozen dependencies'
as_app env CI=true pnpm --dir vmshpwa install --frozen-lockfile --ignore-scripts --prefer-offline --store-dir "$BASE/cache/pnpm" > "$RECORD/frontend-install.log" 2>&1
as_app env TLF_RELEASE_ID="$RELEASE" .venv/bin/python - <<'PY' > "$RECORD/frontend-build.log" 2>&1
import json, os, re, subprocess
from pathlib import Path
config=json.loads(Path('creds_prod/vmsh_bot_config_prod.json').read_text())
assert config.get('s3_direct_image_uploads_verified', False) is False
release=os.environ['TLF_RELEASE_ID']
environment=dict(os.environ, CI='true', VITE_SENTRY_DSN=config['sentry_dsn'], VITE_PWA_PROTOTYPE='false', VMSH_FRONTEND_BUILD_PROFILE='production', VITE_SENTRY_RELEASE=release, VITE_PUBLIC_MEDIA_ORIGIN='https://tlfprepimages.nbg1.your-objectstorage.com')
for audience in ('landing', 'student', 'family', 'staff'):
    subprocess.run(['../../node_modules/.bin/vite', 'build'], cwd=f'vmshpwa/apps/{audience}', env=environment, check=True)
    index=Path(f'vmshpwa/apps/{audience}/dist/index.html')
    index.write_text(re.sub(r'((?:src|href)="/[^"?]+/assets/[^"?]+\.(?:js|css))"',rf'\1?release={release}"',index.read_text()))
PY
step 'Checking production provenance and publishing immutable static assets'
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
as_app .venv/bin/python -m vmshpwa.scripts.static_release verify --release-id "$RELEASE" --release-root "$BASE/vmshpwa/releases" --report "$RECORD/static-verified.json" > "$RECORD/static-verified.log"
step 'Rehearsing all three migrations on a consistent online copy'
as_app .venv/bin/python - <<PY
import sqlite3
with sqlite3.connect('file:$DB?mode=ro',uri=True) as source:
    with sqlite3.connect('$RECORD/rehearsal.sqlite3') as destination: source.backup(destination)
PY
as_app .venv/bin/python "$RECORD/data-check.py" "$RECORD/rehearsal.sqlite3" > "$RECORD/rehearsal-before.json"
as_app env PROD=true VMSH_RUNTIME_PROFILE=pwa-production VMSH_PWA_PROTOTYPE=false VMSH_INSTANCE=migration-rehearsal VMSH_DB_FILENAME="$RECORD/rehearsal.sqlite3" .venv/bin/python -m vmshpwa.scripts.migrate_runtime > "$RECORD/rehearsal.log" 2>&1
as_app env PROD=true VMSH_RUNTIME_PROFILE=pwa-production VMSH_PWA_PROTOTYPE=false VMSH_INSTANCE=migration-rehearsal VMSH_DB_FILENAME="$RECORD/rehearsal.sqlite3" .venv/bin/python -m vmshpwa.scripts.database_performance_guard > "$RECORD/rehearsal-guard.json" 2>&1
as_app .venv/bin/python "$RECORD/data-check.py" "$RECORD/rehearsal.sqlite3" > "$RECORD/rehearsal-after.json"
check_rows() {
    # Shell redirections create root-owned receipts. Compare them as root;
    # this interpreter only reads JSON and never opens the application database.
    .venv/bin/python - "$1" "$2" <<'PY'
import json,sys
before=json.load(open(sys.argv[1])); after=json.load(open(sys.argv[2]))
assert after.pop('pwa_image_uploads')['count']==0
assert before==after, 'Existing product rows changed'
print('Every existing product table preserved; new upload table empty')
PY
}
check_rows "$RECORD/rehearsal-before.json" "$RECORD/rehearsal-after.json" > "$RECORD/rehearsal-data-check.log"
as_app .venv/bin/python - <<PY >> "$RECORD/rehearsal.log" 2>&1
import yoyo
from db_methods.pwa.migrations import apply_schema_migrations
selected=yoyo.read_migrations('$STAGE/migrations').filter(lambda migration:migration.id in {'0114.browser_image_uploads','0115.vmsh_public_media_domain','0116.notification_push_candidate_index'})
with yoyo.get_backend('sqlite:///$RECORD/rehearsal.sqlite3') as backend:
    with backend.lock(): backend.rollback_migrations(backend.to_rollback(selected))
state=apply_schema_migrations('$RECORD/rehearsal.sqlite3')
assert state.is_current and len(state.expected)==6
print('Three migrations up/down/up PASS')
PY
as_app .venv/bin/python "$RECORD/data-check.py" "$RECORD/rehearsal.sqlite3" > "$RECORD/rehearsal-reapplied.json"
check_rows "$RECORD/rehearsal-before.json" "$RECORD/rehearsal-reapplied.json" >> "$RECORD/rehearsal-data-check.log"
cd "$CODE"
STOPPED=false
STARTED=false
CUTOVER=false
rollback() {
    status=$?; trap - ERR; set +e
    step "Release failed with status $status"
    if [[ "$STOPPED" == true ]]; then
        touch "$BASE/vmshpwa/runtime/service-updating"
        systemctl stop vmsh-analytics.timer vmsh-analytics.service vmshpwa.service vmshzoom.service
        if [[ "$CUTOVER" == true && "$STARTED" == false ]]; then
            # Writers have not reopened: the rehearsed rollback cannot erase new photos/Zoom events.
            cd "$STAGE"
            if as_app .venv/bin/python - <<PY
import yoyo
from db_methods.pwa import maintenance_database_lock
selected=yoyo.read_migrations('$STAGE/migrations').filter(lambda migration:migration.id in {'0114.browser_image_uploads','0115.vmsh_public_media_domain','0116.notification_push_candidate_index'})
with maintenance_database_lock('$DB'):
    with yoyo.get_backend('sqlite:///$DB') as backend:
        with backend.lock(): backend.rollback_migrations(backend.to_rollback(selected))
PY
            then
                as_app git -C "$CODE" reset --hard "$OLD_HEAD"
                cd "$CODE"
                if as_app .venv/bin/python - <<PY
from db_methods.pwa.migrations import require_current_schema
require_current_schema('$DB')
PY
                then
                    ln -s "$OLD_STATIC" "$BASE/vmshpwa/current.integrated-rollback"
                    mv -Tf "$BASE/vmshpwa/current.integrated-rollback" "$BASE/vmshpwa/current"
                    systemctl start vmshpwa.service vmshzoom.service
                    if [[ "$ANALYTICS_ACTIVE" == active ]]; then systemctl start vmsh-analytics.timer; fi
                    rm -f "$BASE/vmshpwa/runtime/service-updating"
                fi
            fi
        else
            step 'Preserve new source/schema and all receipts; maintenance remains until health recovery'
        fi
    fi
    exit "$status"
}
trap rollback ERR
test "$(as_app git -C "$CODE" rev-parse HEAD)" = "$OLD_HEAD"
step 'Stopping all SQLite writers for migration cutover'
touch "$BASE/vmshpwa/runtime/service-updating"
STOPPED=true
systemctl stop vmsh-analytics.timer vmsh-analytics.service vmshpwa.service vmshzoom.service
as_app .venv/bin/python "$RECORD/data-check.py" "$DB" > "$RECORD/data-before.json"
CUTOVER=true
as_app git -C "$CODE" merge --ff-only "$TARGET" > "$RECORD/checkout.log"
as_app env PROD=true VMSH_RUNTIME_PROFILE=pwa-production VMSH_PWA_PROTOTYPE=false VMSH_DB_FILENAME="$DB" .venv/bin/python -m vmshpwa.scripts.migrate_runtime > "$RECORD/migration.log" 2>&1
as_app env PROD=true VMSH_RUNTIME_PROFILE=pwa-production VMSH_PWA_PROTOTYPE=false VMSH_DB_FILENAME="$DB" .venv/bin/python -m vmshpwa.scripts.database_performance_guard > "$RECORD/database-guard.json" 2>&1
as_app .venv/bin/python "$RECORD/data-check.py" "$DB" > "$RECORD/data-after.json"
check_rows "$RECORD/data-before.json" "$RECORD/data-after.json" > "$RECORD/live-data-check.log"
sha256sum -c "$RECORD/credentials-before.sha256" > "$RECORD/credentials-check.log"
STARTED=true
systemctl start vmshpwa.service vmshzoom.service
for audience in student family staff; do
    passed=false
    for attempt in $(seq 1 30); do
        if curl -fsS --max-time 5 --unix-socket "$BASE/vmshpwa/runtime/vmshpwa.sock" -H 'X-Forwarded-For: 127.0.0.1' -H 'X-Forwarded-Host: prep.leaders.tech' -H 'X-Forwarded-Proto: https' "http://localhost/$audience/api/v1/runtime" > "$RECORD/$audience-runtime.json" 2>/dev/null; then passed=true; break; fi
        sleep 1
    done
    test "$passed" = true
done
curl -fsS --max-time 5 --unix-socket "$BASE/vmshpwa/runtime/zoom.sock" http://localhost/health > "$RECORD/zoom-health.json"
ln -s "$BASE/vmshpwa/releases/$RELEASE" "$BASE/vmshpwa/current.integrated"
mv -Tf "$BASE/vmshpwa/current.integrated" "$BASE/vmshpwa/current"
if [[ "$ANALYTICS_ACTIVE" == active ]]; then systemctl start vmsh-analytics.timer; fi
rm -f "$BASE/vmshpwa/runtime/service-updating"
as_app .venv/bin/python -m vmshpwa.scripts.production_http_smoke --origin https://prep.leaders.tech --expected-instance production > "$RECORD/http-smoke.log" 2>&1
test "$(systemctl show -p MainPID --value nats.service)" = "$NATS_PID"
systemctl is-active --quiet vmshpwa.service vmshzoom.service vmsh-analytics.timer nats.service
as_app .venv/bin/python "$BASE/deploy/bin/backup.py" > "$RECORD/backup-after.json"
trap - ERR
step "Deployment passed: source=$TARGET release=$RELEASE existing data/credentials/NATS unchanged"
cat "$RECORD/migration.log" "$RECORD/live-data-check.log" "$RECORD/http-smoke.log" "$RECORD/backup-before.json" "$RECORD/backup-after.json"
