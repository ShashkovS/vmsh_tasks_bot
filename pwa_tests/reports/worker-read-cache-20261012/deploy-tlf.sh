#!/bin/bash
# Owner-authorized backend release: docs/performance/worker-read-cache-release.md.
# Adapted from docs/deploy/tlf-app/deploy_review_photo.sh; static stays intact.
set -Eeuo pipefail
umask 027
BASE=/web/vmsh_tasks_bot
CODE=$BASE/vmsh_tasks_bot
TARGET=${1:?Pass the tested full commit SHA}
[[ "$TARGET" =~ ^[0-9a-f]{40}$ ]]
[[ $(hostname) == vmsh-nbg ]]
RECORD=$BASE/deploy/releases/tlfprep-20261013-worker-cache-${TARGET:0:12}
DB=$CODE/db/production_prep.db
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
as_app git -C "$CODE" diff --exit-code "$OLD_HEAD" "$TARGET" -- migrations pyproject.toml uv.lock vmshpwa/apps vmshpwa/packages vmshpwa/scripts vmshpwa/deploy vmshpwa/pnpm-lock.yaml vmshpwa/pnpm-workspace.yaml vmshpwa/package.json Makefile
test ! -e "$RECORD"
test ! -e "$BASE/vmshpwa/runtime/service-updating"
systemctl is-active --quiet vmshpwa.service vmshzoom.service nats.service
install -d -m 700 -o vmsh_tasks_bot -g nginx "$RECORD"
install -m 700 "$0" "$RECORD/deploy.sh"
printf '%s\n' "$OLD_HEAD" > "$RECORD/source-before.txt"
printf '%s\n' "$TARGET" > "$RECORD/source-after.txt"
OLD_STATIC=$(readlink "$BASE/vmshpwa/current")
printf '%s\n' "$OLD_STATIC" > "$RECORD/static-before.txt"
NATS_PID=$(systemctl show -p MainPID --value nats.service)
ANALYTICS_ACTIVE=$(systemctl is-active vmsh-analytics.timer || true)
sha256sum "$CODE/creds_prod/vmsh_bot_config_prod.json" "$BASE/vmshpwa/runtime/vmshpwa.env" > "$RECORD/config-before.sha256"
STOPPED=false
runtime_ready() {
    local audience passed attempt
    for audience in student family staff; do
        passed=false
        for attempt in $(seq 1 30); do
            if curl -fsS --max-time 5 --unix-socket "$BASE/vmshpwa/runtime/vmshpwa.sock" -H 'X-Forwarded-For: 127.0.0.1' -H 'X-Forwarded-Host: prep.leaders.tech' -H 'X-Forwarded-Proto: https' "http://localhost/$audience/api/v1/runtime" > "$RECORD/$audience-runtime.json" 2>/dev/null; then passed=true; break; fi
            sleep 1
        done
        test "$passed" = true || return 1
    done
    curl -fsS --max-time 5 --unix-socket "$BASE/vmshpwa/runtime/zoom.sock" http://localhost/health > "$RECORD/zoom-health.json"
}
rollback() {
    status=$?; trap - ERR; set +e
    step "Release failed with status $status; restoring previous source"
    if [[ "$STOPPED" == true ]]; then
        touch "$BASE/vmshpwa/runtime/service-updating"
        systemctl stop vmshpwa.service vmshzoom.service
        as_app git -C "$CODE" reset --hard "$OLD_HEAD"
        systemctl start vmshpwa.service vmshzoom.service
        if [[ "$ANALYTICS_ACTIVE" == active ]]; then systemctl start vmsh-analytics.timer; fi
        if runtime_ready && systemctl is-active --quiet vmshpwa.service vmshzoom.service; then
            rm -f "$BASE/vmshpwa/runtime/service-updating"
            step 'Previous workers recovered; product data untouched'
        else
            step 'Previous workers need manual recovery; maintenance retained'
        fi
    fi
    exit "$status"
}
trap rollback ERR
step 'Verified online SQLite backups and restore integrity'
as_app "$CODE/.venv/bin/python" "$BASE/deploy/bin/backup.py" > "$RECORD/backup-before.json"
test "$(as_app git -C "$CODE" rev-parse HEAD)" = "$OLD_HEAD"
step 'Switching backend workers; static/config/schema unchanged'
touch "$BASE/vmshpwa/runtime/service-updating"
STOPPED=true
systemctl stop vmsh-analytics.timer vmsh-analytics.service vmshpwa.service vmshzoom.service
as_app "$CODE/.venv/bin/python" "$CODE/docs/deploy/tlf-app/rich_files_data_check.py" "$DB" > "$RECORD/data-before.json"
as_app git -C "$CODE" merge --ff-only "$TARGET" > "$RECORD/checkout.log"
as_app "$CODE/.venv/bin/python" "$CODE/docs/deploy/tlf-app/rich_files_data_check.py" "$DB" > "$RECORD/data-after.json"
cmp "$RECORD/data-before.json" "$RECORD/data-after.json" > "$RECORD/live-data-check.log"
sha256sum -c "$RECORD/config-before.sha256" > "$RECORD/credentials-check.log"
test "$(readlink "$BASE/vmshpwa/current")" = "$OLD_STATIC"
systemctl start vmshpwa.service vmshzoom.service
runtime_ready
if [[ "$ANALYTICS_ACTIVE" == active ]]; then systemctl start vmsh-analytics.timer; fi
rm -f "$BASE/vmshpwa/runtime/service-updating"
cd "$CODE"
as_app .venv/bin/python -m vmshpwa.scripts.production_http_smoke --origin https://prep.leaders.tech --expected-instance production > "$RECORD/http-smoke.log" 2>&1
test "$(systemctl show -p MainPID --value nats.service)" = "$NATS_PID"
systemctl is-active --quiet vmshpwa.service vmshzoom.service vmsh-analytics.timer nats.service vmsh-cross-backup.timer vmsh-cross-backup-sync.timer vmsh-cross-backup-verify.timer
as_app .venv/bin/python "$BASE/deploy/bin/backup.py" > "$RECORD/backup-after.json"
trap - ERR
step "Deployment passed: source=$TARGET static/config/data/NATS preserved"
cat "$RECORD/http-smoke.log" "$RECORD/backup-before.json" "$RECORD/backup-after.json"
