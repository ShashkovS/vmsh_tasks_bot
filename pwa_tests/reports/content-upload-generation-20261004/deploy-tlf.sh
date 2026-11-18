#!/bin/bash
# Owner-authorized backend release; vmshpwa/docs/content-recovery-20261004.md.
set -Eeuo pipefail
BASE=/web/vmsh_tasks_bot
CODE=$BASE/vmsh_tasks_bot
TARGET=${1:?Pass the reviewed full commit SHA}
ROLLBACK=${2:?Pass the schema-compatible rollback SHA}
[[ "$TARGET" =~ ^[0-9a-f]{40}$ && "$ROLLBACK" =~ ^[0-9a-f]{40}$ ]]
[[ $(hostname) == vmsh-nbg ]]
RELEASE=tlfprep-20261004-content-upload-${TARGET:0:12}
RECORD=$BASE/deploy/releases/$RELEASE
STAGE=$RECORD/source
exec 9>"$BASE/deploy/metadata-deploy.lock"
flock -n 9
as_app() { runuser -u vmsh_tasks_bot -- "$@"; }
step() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*"; }
as_app git -C "$CODE" fetch origin vmshpwa codex/content-upload-generation-rollback-20261004
OLD_HEAD=$(as_app git -C "$CODE" rev-parse HEAD)
test "$OLD_HEAD" = 9a14443fbc231617929536af3d5f17c3124eb7b9
as_app git -C "$CODE" diff --quiet
as_app git -C "$CODE" diff --cached --quiet
as_app git -C "$CODE" merge-base --is-ancestor "$OLD_HEAD" "$TARGET"
as_app git -C "$CODE" merge-base --is-ancestor "$TARGET" origin/vmshpwa
as_app git -C "$CODE" cat-file -e "$ROLLBACK^{commit}"
as_app git -C "$CODE" diff --exit-code "$OLD_HEAD" "$TARGET" -- pyproject.toml uv.lock vmshpwa/pnpm-lock.yaml vmshpwa/apps vmshpwa/packages helpers apps main.py
as_app git -C "$CODE" diff --name-status "$OLD_HEAD" "$TARGET" -- migrations | python3 -c 'import sys; assert sys.stdin.read().splitlines()==["A\tmigrations/0113.content_upload_compiler_generation.py"]'
test ! -e "$RECORD"
test ! -e "$BASE/vmshpwa/runtime/service-updating"
install -d -m 700 -o vmsh_tasks_bot -g nginx "$RECORD" "$STAGE"
install -m 700 "$0" "$RECORD/deploy.sh"
printf '%s\n' "$OLD_HEAD" > "$RECORD/source-before.txt"
printf '%s\n' "$TARGET" > "$RECORD/source-after.txt"
STATIC=$(readlink "$BASE/vmshpwa/current")
printf '%s\n' "$STATIC" > "$RECORD/static-before.txt"
NATS_PID=$(systemctl show -p MainPID --value nats.service)
ANALYTICS_ACTIVE=$(systemctl is-active vmsh-analytics.timer || true)
cd "$CODE"
sha256sum creds_prod/vmsh_bot_config_prod.json > "$RECORD/credentials-before.sha256"
step 'Verified backup before release; retaining current frontend and dependencies'
as_app .venv/bin/python "$BASE/deploy/bin/backup.py" > "$RECORD/backup-before.json"
as_app git archive "$TARGET" | as_app tar -x -C "$STAGE"
as_app ln -s "$CODE/.venv" "$STAGE/.venv"
install -m 644 "$STAGE/docs/deploy/tlf-app/rich_files_data_check.py" "$RECORD/data-check.py"
cd "$STAGE"
step 'Rehearsing 0113 on an online SQLite copy'
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
    return db.execute("SELECT type,name,sql FROM sqlite_schema WHERE sql IS NOT NULL AND name NOT LIKE '%yoyo%' ORDER BY type,name").fetchall()
with sqlite3.connect(path) as db:
    before=objects(db)
    before_fk=sorted(db.execute('PRAGMA foreign_key_check').fetchall())
started=time.monotonic()
state=apply_schema_migrations(path)
assert state.is_current and len(state.expected)==3
require_current_schema(path)
with sqlite3.connect(path) as db:
    after=objects(db)
    changed=[name for kind,name,sql in after if (kind,name,sql) not in before]
    assert changed==['content_revisions'],changed
    assert len(before)==len(after)
    assert sorted(db.execute('PRAGMA foreign_key_check').fetchall())==before_fk
    assert db.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
print(json.dumps(dict(migration='0113.content_upload_compiler_generation',seconds=round(time.monotonic()-started,3),schema_current=True,changed_objects=changed,existing_fk_errors=len(before_fk),new_fk_errors=0,integrity='ok')))
PY
as_app .venv/bin/python "$RECORD/data-check.py" "$RECORD/rehearsal.sqlite3" > "$RECORD/rehearsal-after.json"
cmp "$RECORD/rehearsal-before.json" "$RECORD/rehearsal-after.json"
cd "$CODE"
STOPPED=false
CUTOVER=false
rollback() {
    status=$?;trap - ERR
    step "Release failed with status $status; preserve live rows and compiler history"
    if [[ "$STOPPED" == true ]]; then
        systemctl stop vmsh-analytics.timer vmsh-analytics.service vmshpwa.service vmshzoom.service
        if [[ "$CUTOVER" == true ]]; then
            if as_app .venv/bin/python - <<PY
import sqlite3,sys
with sqlite3.connect('file:$CODE/db/production_prep.db?mode=ro',uri=True) as db:
    applied=db.execute("SELECT 1 FROM _yoyo_migration WHERE migration_id='0113.content_upload_compiler_generation'").fetchone()
sys.exit(0 if applied else 1)
PY
            then as_app git -C "$CODE" reset --hard "$ROLLBACK"
            else as_app git -C "$CODE" reset --hard "$OLD_HEAD";fi
        fi
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
test "$(readlink "$BASE/vmshpwa/current")" = "$STATIC"
if [[ "$ANALYTICS_ACTIVE" == active ]];then systemctl start vmsh-analytics.timer;fi
rm -f "$BASE/vmshpwa/runtime/service-updating"
as_app .venv/bin/python -m vmshpwa.scripts.production_http_smoke --origin https://prep.leaders.tech --expected-instance production > "$RECORD/http-smoke.log" 2>&1
test "$(systemctl show -p MainPID --value nats.service)" = "$NATS_PID"
systemctl is-active --quiet vmshpwa.service vmshzoom.service vmsh-analytics.timer nats.service
as_app .venv/bin/python "$BASE/deploy/bin/backup.py" > "$RECORD/backup-after.json"
trap - ERR
step "Deployment passed: source=$TARGET static_unchanged=true product_rows=unchanged credentials=unchanged NATS=unchanged"
cat "$RECORD/rehearsal.json" "$RECORD/migration.log" "$RECORD/http-smoke.log" "$RECORD/backup-before.json" "$RECORD/backup-after.json"
