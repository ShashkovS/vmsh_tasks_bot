#!/bin/bash
# Reviewed release: pwa_tests/reports/release-20261003/README.md.
# Run via ssh/config vmsh with sudo as root, with the reviewed full commit SHA.
set -Eeuo pipefail
BASE=/web/vmsh_tasks_bot
CODE=$BASE/vmsh_tasks_bot
TARGET=${1:?Pass the reviewed full commit SHA}
[[ "$TARGET" =~ ^[0-9a-f]{40}$ ]]
[[ $(hostname) == vmsh-nbg ]]
RELEASE=tlfprep-20261003-fresh-review-${TARGET:0:12}
RECORD=$BASE/deploy/releases/$RELEASE
STAGE=$RECORD/source
export PATH=$BASE/toolchains/node/bin:$BASE/toolchains/pnpm/node_modules/.bin:$BASE/toolchains/uv:$PATH
exec 9>"$BASE/deploy/metadata-deploy.lock"
flock -n 9
as_app() { runuser -u vmsh_tasks_bot -- "$@"; }
as_app git -C "$CODE" fetch origin vmshpwa
OLD_HEAD=$(as_app git -C "$CODE" rev-parse HEAD)
as_app git -C "$CODE" diff --quiet
as_app git -C "$CODE" diff --cached --quiet
as_app git -C "$CODE" merge-base --is-ancestor "$OLD_HEAD" "$TARGET"
as_app git -C "$CODE" merge-base --is-ancestor "$TARGET" origin/vmshpwa
as_app git -C "$CODE" diff --exit-code "$OLD_HEAD" "$TARGET" -- pyproject.toml uv.lock vmshpwa/pnpm-lock.yaml vmshpwa/deploy docs/deploy/tlf-app/build_source.sh docs/deploy/tlf-app/render_server.py
NEW_MIGRATIONS=$(as_app git -C "$CODE" diff --name-only "$OLD_HEAD" "$TARGET" -- migrations)
test "$NEW_MIGRATIONS" = $'migrations/0109.pwa_fresh_problem_sets.rollback.sql\nmigrations/0109.pwa_fresh_problem_sets.sql'
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
as_app .venv/bin/python "$BASE/deploy/bin/backup.py" > "$RECORD/backup-before.json"
as_app git archive "$TARGET" | as_app tar -x -C "$STAGE"
install -m 644 "$STAGE/pwa_tests/reports/release-20261003/data_check.py" "$RECORD/data-check.py"
as_app ln -s "$CODE/.venv" "$STAGE/.venv"
printf 'Building isolated production release %s\n' "$RELEASE"
cd "$STAGE"
as_app env CI=true pnpm --dir vmshpwa install --frozen-lockfile --ignore-scripts --store-dir "$BASE/cache/pnpm" > "$RECORD/frontend-install.log" 2>&1
as_app env TLF_RELEASE_ID="$RELEASE" .venv/bin/python - <<'PY' > "$RECORD/frontend-build.log" 2>&1
import json, os, subprocess
from pathlib import Path
config=json.loads(Path('/web/vmsh_tasks_bot/vmsh_tasks_bot/creds_prod/vmsh_bot_config_prod.json').read_text())
environment=dict(os.environ, CI='true', VITE_SENTRY_DSN=config['sentry_dsn'], VITE_PWA_PROTOTYPE='false', VMSH_FRONTEND_BUILD_PROFILE='production', VITE_SENTRY_RELEASE=os.environ['TLF_RELEASE_ID'], VITE_PUBLIC_MEDIA_ORIGIN='https://tlfprepimages.nbg1.your-objectstorage.com')
for audience in ('landing', 'student', 'family', 'staff'):
    subprocess.run(['../../node_modules/.bin/vite', 'build'], cwd=f'vmshpwa/apps/{audience}', env=environment, check=True)
PY
as_app .venv/bin/python - <<PY
import sqlite3
with sqlite3.connect('file:$CODE/db/production_prep.db?mode=ro', uri=True) as source:
    with sqlite3.connect('$RECORD/rehearsal.sqlite3') as destination:
        source.backup(destination)
PY
as_app .venv/bin/python "$RECORD/data-check.py" "$RECORD/rehearsal.sqlite3" > "$RECORD/rehearsal-before.json"
as_app .venv/bin/python - <<PY > "$RECORD/rehearsal.log" 2>&1
from db_methods.pwa.migrations import apply_schema_migrations
import yoyo
apply_schema_migrations('$RECORD/rehearsal.sqlite3')
selected=yoyo.read_migrations('$STAGE/migrations').filter(lambda migration: migration.id=='0109.pwa_fresh_problem_sets')
with yoyo.get_backend('sqlite:///$RECORD/rehearsal.sqlite3') as backend:
    with backend.lock():
        backend.rollback_migrations(backend.to_rollback(selected))
apply_schema_migrations('$RECORD/rehearsal.sqlite3')
print('Fresh sets migration up/down/up rehearsal completed')
PY
as_app .venv/bin/python "$RECORD/data-check.py" "$RECORD/rehearsal.sqlite3" > "$RECORD/rehearsal-after.json"
cmp "$RECORD/rehearsal-before.json" "$RECORD/rehearsal-after.json"
cd "$CODE"
STOPPED=false
CUTOVER=false
STARTED=false
rollback() {
    status=$?
    trap - ERR
    if [[ "$STOPPED" == true ]]; then
        systemctl stop vmsh-analytics.timer vmsh-analytics.service vmshpwa.service vmshzoom.service
        if [[ "$CUTOVER" == true ]]; then
            # After reopening writers, preserve new release flags, audit history, receipts and Zoom events.
            # Old static is compatible with the new capability-gated backend.
            if [[ "$STARTED" == true ]]; then
                printf 'Runtime reopened; retaining new source/schema and restoring prior static.\n' >&2
                ln -s "$OLD_STATIC" "$BASE/vmshpwa/current.problem-release-rollback"
                mv -Tf "$BASE/vmshpwa/current.problem-release-rollback" "$BASE/vmshpwa/current"
                systemctl start vmshpwa.service vmshzoom.service
                if [[ "$ANALYTICS_ACTIVE" == active ]]; then systemctl start vmsh-analytics.timer; fi
                rm -f "$BASE/vmshpwa/runtime/service-updating"
                exit "$status"
            fi
            printf 'Rolling back only 0109, source and static; production DB is retained.\n' >&2
            as_app .venv/bin/python - <<PY
import yoyo
migrations=yoyo.read_migrations('$STAGE/migrations').filter(lambda migration: migration.id=='0109.pwa_fresh_problem_sets')
with yoyo.get_backend('sqlite:////web/vmsh_tasks_bot/vmsh_tasks_bot/db/production_prep.db') as backend:
    with backend.lock():
        backend.rollback_migrations(backend.to_rollback(migrations))
PY
            as_app git reset --hard "$OLD_HEAD"
            ln -s "$OLD_STATIC" "$BASE/vmshpwa/current.problem-release-rollback"
            mv -Tf "$BASE/vmshpwa/current.problem-release-rollback" "$BASE/vmshpwa/current"
        fi
        systemctl start vmshpwa.service vmshzoom.service
        if [[ "$ANALYTICS_ACTIVE" == active ]]; then systemctl start vmsh-analytics.timer; fi
        rm -f "$BASE/vmshpwa/runtime/service-updating"
    fi
    exit "$status"
}
trap rollback ERR
test "$(as_app git rev-parse HEAD)" = "$OLD_HEAD"
printf 'Rehearsal passed; stopping writers for migration 0109.\n'
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
for attempt in $(seq 1 30); do
    if curl -fsS --unix-socket "$BASE/vmshpwa/runtime/vmshpwa.sock" -H 'X-Forwarded-For: 127.0.0.1' -H 'X-Forwarded-Host: prep.leaders.tech' -H 'X-Forwarded-Proto: https' http://localhost/student/api/v1/health > "$RECORD/backend-health.json" 2>/dev/null && curl -fsS --unix-socket "$BASE/vmshpwa/runtime/zoom.sock" http://localhost/health > "$RECORD/zoom-health.json" 2>/dev/null; then break; fi
    sleep 1
done
curl -fsS --unix-socket "$BASE/vmshpwa/runtime/vmshpwa.sock" -H 'X-Forwarded-For: 127.0.0.1' -H 'X-Forwarded-Host: prep.leaders.tech' -H 'X-Forwarded-Proto: https' http://localhost/student/api/v1/health >/dev/null
curl -fsS --unix-socket "$BASE/vmshpwa/runtime/zoom.sock" http://localhost/health >/dev/null
env TLF_PROBLEM_RELEASE_RELEASE="$RELEASE" TLF_PROBLEM_RELEASE_STAGE="$STAGE" python3 - <<'PY'
import os, re, shutil
from pathlib import Path
base=Path('/web/vmsh_tasks_bot/vmshpwa')
release=base/'releases'/os.environ['TLF_PROBLEM_RELEASE_RELEASE']
stage=Path(os.environ['TLF_PROBLEM_RELEASE_STAGE'])
for audience in ('landing','student','family','staff'):
    shutil.copytree(stage/f'vmshpwa/apps/{audience}/dist', release/audience)
    index=release/audience/'index.html'
    index.write_text(re.sub(r'((?:src|href)="/[^"?]+/assets/[^"?]+\.(?:js|css))"', rf'\1?release={release.name}"', index.read_text()))
    shutil.copytree(release/audience/'assets', base/f'immutable-assets/{audience}/assets', dirs_exist_ok=True)
for directory in (release, base/'immutable-assets'):
    shutil.chown(directory, user='root', group='nginx')
    for path in directory.rglob('*'):
        shutil.chown(path,user='root',group='nginx')
        path.chmod(0o750 if path.is_dir() else 0o640)
temporary=base/'current.problem-release'
temporary.symlink_to(release)
temporary.replace(base/'current')
PY
if [[ "$ANALYTICS_ACTIVE" == active ]]; then systemctl start vmsh-analytics.timer; fi
rm -f "$BASE/vmshpwa/runtime/service-updating"
as_app .venv/bin/python -m vmshpwa.scripts.production_http_smoke --origin https://prep.leaders.tech --expected-instance production > "$RECORD/http-smoke.log" 2>&1
test "$(systemctl show -p MainPID --value nats.service)" = "$NATS_PID"
as_app .venv/bin/python "$BASE/deploy/bin/backup.py" > "$RECORD/backup-after.json"
trap - ERR
printf 'Fresh/review deployment passed: source=%s release=%s record=%s data=unchanged credentials=unchanged NATS=unchanged\n' "$TARGET" "$RELEASE" "$RECORD"
cat "$RECORD/migration.log" "$RECORD/http-smoke.log" "$RECORD/backup-before.json" "$RECORD/backup-after.json"
