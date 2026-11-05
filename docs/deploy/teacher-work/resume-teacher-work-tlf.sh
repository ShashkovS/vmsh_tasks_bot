#!/bin/bash
# Resume the owner-authorized teacher-work deployment after a proof-file permission error.
set -Eeuo pipefail
umask 027
BASE=/web/vmsh_tasks_bot
CODE=$BASE/vmsh_tasks_bot
TARGET=33f6c950bd42ac48a33b630cb3d390bec6a65190
PREVIOUS=8357df87e2fee869ea9a1e127684d9e01c4d4a6c
RELEASE=tlfprep-20261011-teacher-work-33f6c950bd42
RECORD=$BASE/deploy/releases/$RELEASE
DB=$CODE/db/production_prep.db
[[ $(hostname) == vmsh-nbg ]]
export PATH=$BASE/toolchains/node/bin:$BASE/toolchains/pnpm/node_modules/.bin:$BASE/toolchains/uv:$PATH
exec 9>"$BASE/deploy/metadata-deploy.lock"
flock -n 9
as_app() { runuser -u vmsh_tasks_bot -- "$@"; }
cd "$CODE"
test "$(as_app git rev-parse HEAD)" = "$PREVIOUS"
as_app git diff --quiet
as_app git diff --cached --quiet
test "$(as_app git rev-parse origin/vmshpwa)" = "$TARGET"
test ! -e "$BASE/vmshpwa/runtime/service-updating"
cp -a "$CODE/creds_prod/vmsh_bot_config_prod.json" "$RECORD/config-resume-before.json"
OLD_STATIC=$(readlink "$BASE/vmshpwa/current")
ANALYTICS_ACTIVE=$(systemctl is-active vmsh-analytics.timer || true)
NATS_PID=$(systemctl show -p MainPID --value nats.service)
# Root reads root-owned proof files; the application user continues to own DB access.
.venv/bin/python "$RECORD/check.py" compare "$RECORD/data-before.json" "$RECORD/data-after.json" > "$RECORD/live-data-check.json"
as_app .venv/bin/python -m vmshpwa.scripts.static_release verify --release-id "$RELEASE" --release-root "$BASE/vmshpwa/releases" --report "$RECORD/resume-static-verify.json" > "$RECORD/resume-static-verify.log"
STOPPED=false
rollback() {
    status=$?; trap - ERR; set +e
    if [[ "$STOPPED" == true ]]; then
        systemctl stop vmshpwa.service vmshzoom.service
        as_app git reset --hard "$PREVIOUS"
        cp -a "$RECORD/config-resume-before.json" "$CODE/creds_prod/vmsh_bot_config_prod.json"
        ln -s "$OLD_STATIC" "$BASE/vmshpwa/current.teacher-work-rollback"
        mv -Tf "$BASE/vmshpwa/current.teacher-work-rollback" "$BASE/vmshpwa/current"
        systemctl start vmshpwa.service vmshzoom.service
        if [[ "$ANALYTICS_ACTIVE" == active ]]; then systemctl start vmsh-analytics.timer; fi
        rm -f "$BASE/vmshpwa/runtime/service-updating"
    fi
    exit "$status"
}
trap rollback ERR
touch "$BASE/vmshpwa/runtime/service-updating"
STOPPED=true
systemctl stop vmsh-analytics.timer vmsh-analytics.service vmshpwa.service vmshzoom.service
as_app .venv/bin/python "$RECORD/check.py" facts "$DB" > "$RECORD/data-resume-before.json"
as_app .venv/bin/python -c 'import sqlite3,sys; a=sqlite3.connect(sys.argv[1]); b=sqlite3.connect(sys.argv[2]); a.backup(b); assert b.execute("PRAGMA integrity_check").fetchall()==[("ok",)]; b.close(); a.close()' "$DB" "$RECORD/resume-cutover-before.sqlite3"
as_app chmod 600 "$RECORD/resume-cutover-before.sqlite3"
# The reviewed rollback commit is clean and already has 0118; preserve all SQLite data.
as_app git reset --hard "$TARGET" > "$RECORD/resume-checkout.log"
as_app env PROD=true VMSH_RUNTIME_PROFILE=pwa-production VMSH_PWA_PROTOTYPE=false VMSH_DB_FILENAME="$DB" .venv/bin/python -m vmshpwa.scripts.database_performance_guard > "$RECORD/resume-performance.json"
as_app .venv/bin/python "$RECORD/check.py" facts "$DB" > "$RECORD/data-resume-after.json"
cmp "$RECORD/data-resume-before.json" "$RECORD/data-resume-after.json"
as_app .venv/bin/python - "$RECORD/config-resume-before.json" "$RELEASE" <<'PY'
import json, sys
from pathlib import Path
p = Path('creds_prod/vmsh_bot_config_prod.json')
c = json.loads(p.read_text())
c['sentry_release'] = sys.argv[2]
p.write_text(json.dumps(c, ensure_ascii=False, indent=2) + '\n')
PY
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
ln -s "$BASE/vmshpwa/releases/$RELEASE" "$BASE/vmshpwa/current.teacher-work"
mv -Tf "$BASE/vmshpwa/current.teacher-work" "$BASE/vmshpwa/current"
if [[ "$ANALYTICS_ACTIVE" == active ]]; then systemctl start vmsh-analytics.timer; fi
rm -f "$BASE/vmshpwa/runtime/service-updating"
as_app .venv/bin/python -m vmshpwa.scripts.production_http_smoke --origin https://prep.leaders.tech --expected-instance production > "$RECORD/http-smoke.log" 2>&1
test "$(systemctl show -p MainPID --value nats.service)" = "$NATS_PID"
systemctl is-active --quiet vmshpwa.service vmshzoom.service vmsh-analytics.timer nats.service vmsh-cross-backup.timer vmsh-cross-backup-sync.timer vmsh-cross-backup-verify.timer
as_app .venv/bin/python "$BASE/deploy/bin/backup.py" > "$RECORD/backup-after.json"
trap - ERR
printf 'Deployment passed: source=%s release=%s existing data preserved\n' "$TARGET" "$RELEASE"
cat "$RECORD/http-smoke.log" "$RECORD/live-data-check.json" "$RECORD/migration-rehearsal.json" "$RECORD/backup-before.json" "$RECORD/backup-after.json"
