#!/bin/bash
# Guarded backend-only cutover; see this directory's README.md.
# Run as root on vmsh-nbg with the reviewed full commit SHA.
set -Eeuo pipefail
umask 027
BASE=/web/vmsh_tasks_bot
CODE=$BASE/vmsh_tasks_bot
TARGET=${1:?Pass the reviewed full commit SHA}
[[ "$TARGET" =~ ^[0-9a-f]{40}$ ]]
[[ $(hostname) == vmsh-nbg ]]
RELEASE=tlfprep-20261003-written-precedence-${TARGET:0:12}
RECORD=$BASE/deploy/releases/$RELEASE
STAGE=$RECORD/source
MODULE=pwa_tests.reports.written-result-precedence
MIGRATION=0110.pwa_written_result_precedence
DB=$CODE/db/production_prep.db
exec 9>"$BASE/deploy/metadata-deploy.lock"
flock -n 9
as_app() { runuser -u vmsh_tasks_bot -- "$@"; }
as_app git -C "$CODE" fetch origin vmshpwa
OLD_HEAD=$(as_app git -C "$CODE" rev-parse HEAD)
as_app git -C "$CODE" diff --quiet
as_app git -C "$CODE" diff --cached --quiet
as_app git -C "$CODE" merge-base --is-ancestor "$OLD_HEAD" "$TARGET"
as_app git -C "$CODE" merge-base --is-ancestor "$TARGET" origin/vmshpwa
as_app git -C "$CODE" diff --exit-code "$OLD_HEAD" "$TARGET" -- pyproject.toml uv.lock vmshpwa/pnpm-lock.yaml vmshpwa/apps vmshpwa/packages vmshpwa/deploy docs/deploy
NEW_MIGRATIONS=$(as_app git -C "$CODE" diff --name-only "$OLD_HEAD" "$TARGET" -- migrations)
test "$NEW_MIGRATIONS" = $'migrations/0110.pwa_written_result_precedence.rollback.sql\nmigrations/0110.pwa_written_result_precedence.sql'
test ! -e "$RECORD"
test ! -e "$BASE/vmshpwa/runtime/service-updating"
systemctl is-active --quiet vmshpwa.service vmshzoom.service
install -d -m 700 -o vmsh_tasks_bot -g nginx "$RECORD" "$STAGE"
install -m 700 "$0" "$RECORD/deploy.sh"
printf '%s\n' "$OLD_HEAD" > "$RECORD/source-before.txt"
OLD_STATIC=$(readlink "$BASE/vmshpwa/current")
NATS_PID=$(systemctl show -p MainPID --value nats.service)
ANALYTICS_ACTIVE=$(systemctl is-active vmsh-analytics.timer || true)
cd "$CODE"
sha256sum creds_prod/vmsh_bot_config_prod.json > "$RECORD/credentials-before.sha256"
as_app .venv/bin/python "$BASE/deploy/bin/backup.py" > "$RECORD/backup-before.json"
as_app git archive "$TARGET" | as_app tar -x -C "$STAGE"
as_app ln -s "$CODE/.venv" "$STAGE/.venv"
cd "$STAGE"
as_app .venv/bin/python - <<PY
import json, sqlite3
from pathlib import Path
report=json.loads(Path('$RECORD/backup-before.json').read_text())
source=Path('$BASE/backups')/report['backup']/'main.sqlite3'
with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as c:
    with sqlite3.connect('$RECORD/before-rehearsal.sqlite3') as t:
        c.backup(t)
PY
as_app .venv/bin/python -m "$MODULE.rehearse" --skip-incidents \
  --snapshot "$RECORD/before-rehearsal.sqlite3" --copy "$RECORD/rehearsal.sqlite3" \
  --report "$RECORD/rehearsal.json" > "$RECORD/rehearsal.log" 2>&1
cd "$CODE"
STOPPED=false
CUTOVER=false
STARTED=false
on_error() {
    status=$?
    trap - ERR
    if [[ "$STOPPED" == true ]]; then
        systemctl stop vmsh-analytics.timer vmsh-analytics.service vmshpwa.service vmshzoom.service
        if [[ "$STARTED" == true ]]; then
            printf 'Writers reopened; retaining new source/schema and maintenance for forward repair.\n' >&2
            exit "$status"
        fi
        if [[ "$CUTOVER" == true ]]; then
            cd "$STAGE"
            as_app .venv/bin/python - <<PY
import yoyo
migrations=yoyo.read_migrations('$STAGE/migrations').filter(lambda m:m.id=='$MIGRATION')
with yoyo.get_backend('sqlite:///$DB') as backend:
    with backend.lock():
        backend.rollback_migrations(backend.to_rollback(migrations))
PY
            as_app git -C "$CODE" reset --hard "$OLD_HEAD"
        fi
        systemctl start vmshpwa.service vmshzoom.service
        if [[ "$ANALYTICS_ACTIVE" == active ]]; then systemctl start vmsh-analytics.timer; fi
        rm -f "$BASE/vmshpwa/runtime/service-updating"
    fi
    exit "$status"
}
trap on_error ERR
test "$(as_app git rev-parse HEAD)" = "$OLD_HEAD"
printf 'Rehearsal passed; stopping writers for migration 0110.\n'
touch "$BASE/vmshpwa/runtime/service-updating"
STOPPED=true
systemctl stop vmsh-analytics.timer vmsh-analytics.service vmshpwa.service vmshzoom.service
as_app .venv/bin/python - <<PY
import sqlite3
with sqlite3.connect('file:$DB?mode=ro',uri=True) as c:
    with sqlite3.connect('$RECORD/pre-cutover.sqlite3') as t:
        c.backup(t)
PY
CUTOVER=true
as_app git reset --hard "$TARGET" > "$RECORD/checkout.log"
as_app env PROD=true VMSH_RUNTIME_PROFILE=pwa-production VMSH_PWA_PROTOTYPE=false .venv/bin/python -m vmshpwa.scripts.migrate_runtime > "$RECORD/migration.log" 2>&1
as_app env PROD=true VMSH_RUNTIME_PROFILE=pwa-production VMSH_PWA_PROTOTYPE=false .venv/bin/python -m vmshpwa.scripts.database_performance_guard > "$RECORD/database-guard.json" 2>&1
as_app .venv/bin/python -m "$MODULE.verify_database" --before "$RECORD/pre-cutover.sqlite3" --after "$DB" > "$RECORD/data-check.json"
sha256sum -c "$RECORD/credentials-before.sha256" > "$RECORD/credentials-check.log"
STARTED=true
systemctl start vmshpwa.service vmshzoom.service
for attempt in $(seq 1 30); do
    if curl -fsS --unix-socket "$BASE/vmshpwa/runtime/vmshpwa.sock" -H 'X-Forwarded-For: 127.0.0.1' -H 'X-Forwarded-Host: prep.leaders.tech' -H 'X-Forwarded-Proto: https' http://localhost/student/api/v1/health > "$RECORD/backend-health.json" 2>/dev/null && curl -fsS --unix-socket "$BASE/vmshpwa/runtime/zoom.sock" http://localhost/health > "$RECORD/zoom-health.json" 2>/dev/null; then break; fi
    sleep 1
done
systemctl is-active --quiet vmshpwa.service vmshzoom.service
curl -fsS --unix-socket "$BASE/vmshpwa/runtime/vmshpwa.sock" -H 'X-Forwarded-For: 127.0.0.1' -H 'X-Forwarded-Host: prep.leaders.tech' -H 'X-Forwarded-Proto: https' http://localhost/student/api/v1/health >/dev/null
curl -fsS --unix-socket "$BASE/vmshpwa/runtime/zoom.sock" http://localhost/health >/dev/null
test "$(readlink "$BASE/vmshpwa/current")" = "$OLD_STATIC"
test "$(systemctl show -p MainPID --value nats.service)" = "$NATS_PID"
if [[ "$ANALYTICS_ACTIVE" == active ]]; then systemctl start vmsh-analytics.timer; fi
rm -f "$BASE/vmshpwa/runtime/service-updating"
as_app .venv/bin/python -m vmshpwa.scripts.production_http_smoke --origin https://prep.leaders.tech --expected-instance production > "$RECORD/http-smoke.log" 2>&1
as_app .venv/bin/python "$BASE/deploy/bin/backup.py" > "$RECORD/backup-after.json"
trap - ERR
printf 'Written precedence deployment passed: source=%s record=%s static=unchanged credentials=unchanged NATS=unchanged\n' "$TARGET" "$RECORD"
cat "$RECORD/data-check.json" "$RECORD/http-smoke.log" "$RECORD/backup-before.json" "$RECORD/backup-after.json"
