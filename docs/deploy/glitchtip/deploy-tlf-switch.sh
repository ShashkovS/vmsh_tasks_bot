#!/bin/bash
# Owner-authorized release: docs/deploy/glitchtip/migration-20261011.md.
# Run as root on TLF; the only argument is the tested full commit SHA.
set -Eeuo pipefail
umask 027
BASE=/web/vmsh_tasks_bot
CODE=$BASE/vmsh_tasks_bot
TARGET=${1:?Pass the reviewed full commit SHA}
[[ "$TARGET" =~ ^[0-9a-f]{40}$ ]]
[[ $(hostname) == vmsh-nbg ]]
RELEASE=tlfprep-20261011-glitchtip-${TARGET:0:12}-$(date -u +%H%M%S)
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
as_app git -C "$CODE" diff --exit-code "$OLD_HEAD" "$TARGET" -- pyproject.toml uv.lock vmshpwa/pnpm-lock.yaml docs/deploy/tlf-app/render_server.py
as_app git -C "$CODE" diff --quiet "$OLD_HEAD" "$TARGET" -- vmshpwa/deploy
as_app git -C "$CODE" diff --exit-code "$OLD_HEAD" "$TARGET" -- migrations
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
install -m 600 creds_prod/vmsh_bot_config_prod.json "$RECORD/config-before.json"
step 'Verified main and analytics backups before release'
as_app .venv/bin/python "$BASE/deploy/bin/backup.py" > "$RECORD/backup-before.json"
as_app git archive "$TARGET" | as_app tar -x -C "$STAGE"
as_app ln -s "$CODE/.venv" "$STAGE/.venv"
as_app ln -s "$CODE/creds_prod/vmsh_bot_config_prod.json" "$STAGE/creds_prod/vmsh_bot_config_prod.json"
install -m 644 "$STAGE/docs/deploy/tlf-app/rich_files_data_check.py" "$RECORD/data-check.py"
cd "$STAGE"
STOPPED=false
STARTED=false
CUTOVER=false
rollback() {
    status=$?; trap - ERR; set +e
    step "Release failed with status $status"
    install -m 600 -o vmsh_tasks_bot -g vmsh_tasks_bot "$RECORD/config-before.json" "$CODE/creds_prod/vmsh_bot_config_prod.json"
    if [[ "$STOPPED" == true ]]; then
        touch "$BASE/vmshpwa/runtime/service-updating"
        systemctl stop vmshpwa.service vmshzoom.service
        as_app git -C "$CODE" reset --hard "$OLD_HEAD"
        ln -s "$OLD_STATIC" "$BASE/vmshpwa/current.glitchtip-rollback"
        mv -Tf "$BASE/vmshpwa/current.glitchtip-rollback" "$BASE/vmshpwa/current"
        systemctl start vmshpwa.service vmshzoom.service
        if [[ "$ANALYTICS_ACTIVE" == active ]]; then systemctl start vmsh-analytics.timer; fi
        rm -f "$BASE/vmshpwa/runtime/service-updating"
    fi
    exit "$status"
}
trap rollback ERR
step 'Building isolated production bundles using frozen dependencies'
as_app env CI=true pnpm --dir vmshpwa install --frozen-lockfile --ignore-scripts --prefer-offline --store-dir "$BASE/cache/pnpm" > "$RECORD/frontend-install.log" 2>&1
install -d -m 700 -o vmsh_tasks_bot -g vmsh_tasks_bot "$STAGE/.runtime"
install -m 600 -o vmsh_tasks_bot -g vmsh_tasks_bot "$CODE/.runtime/glitchtip-portal.pending.json" "$STAGE/.runtime/glitchtip-portal.pending.json"
as_app python3 -m vmshpwa.scripts.production_frontend_build --release "$RELEASE" --media-origin https://tlfprepimages.nbg1.your-objectstorage.com > "$RECORD/frontend-build.log" 2>&1
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
cd "$CODE"
test "$(as_app git -C "$CODE" rev-parse HEAD)" = "$OLD_HEAD"
step 'Restarting workers for canonical DSN cutover; schema unchanged'
touch "$BASE/vmshpwa/runtime/service-updating"
STOPPED=true
systemctl stop vmsh-analytics.timer vmsh-analytics.service vmshpwa.service vmshzoom.service
as_app .venv/bin/python "$RECORD/data-check.py" "$DB" > "$RECORD/data-before.json"
CUTOVER=true
as_app git -C "$CODE" merge --ff-only "$TARGET" > "$RECORD/checkout.log"
as_app env PROD=true VMSH_RUNTIME_PROFILE=pwa-production VMSH_PWA_PROTOTYPE=false VMSH_DB_FILENAME="$DB" .venv/bin/python -m vmshpwa.scripts.migrate_runtime > "$RECORD/migration.log" 2>&1
as_app env PROD=true VMSH_RUNTIME_PROFILE=pwa-production VMSH_PWA_PROTOTYPE=false VMSH_DB_FILENAME="$DB" .venv/bin/python -m vmshpwa.scripts.database_performance_guard > "$RECORD/database-guard.json" 2>&1
as_app .venv/bin/python "$RECORD/data-check.py" "$DB" > "$RECORD/data-after.json"
cmp "$RECORD/data-before.json" "$RECORD/data-after.json" > "$RECORD/live-data-check.log"
python3 - <<PY > "$RECORD/credentials-check.log"
import json
from pathlib import Path
before=json.loads(Path('$RECORD/config-before.json').read_text())
after=json.loads(Path('$CODE/creds_prod/vmsh_bot_config_prod.json').read_text())
for key in ('sentry_dsn','frontend_sentry_dsn','sentry_release'):
    before.pop(key,None);after.pop(key,None)
assert before==after, 'Unrelated canonical configuration changed'
print('All canonical settings except approved DSN/release fields preserved')
PY
install -m 755 "$CODE/docs/deploy/tlf-app/build_source.sh" "$BASE/deploy/bin/build_source.sh"
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
install -m 600 -o vmsh_tasks_bot -g vmsh_tasks_bot "$STAGE/.runtime/glitchtip-portal.json" "$CODE/.runtime/glitchtip-portal.json"
rm "$CODE/.runtime/glitchtip-portal.pending.json"
trap - ERR
step "Deployment passed: source=$TARGET release=$RELEASE existing data/unrelated credentials/NATS unchanged"
cat "$RECORD/migration.log" "$RECORD/live-data-check.log" "$RECORD/http-smoke.log" "$RECORD/backup-before.json" "$RECORD/backup-after.json"
