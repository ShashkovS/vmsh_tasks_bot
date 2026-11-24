#!/bin/bash
# Backend-only release; vmshpwa/docs/graceful-shutdown.md.
set -Eeuo pipefail
BASE=/web/vmsh_tasks_bot
CODE=$BASE/vmsh_tasks_bot
TARGET=${1:?Pass the reviewed full SHA}
[[ "$TARGET" =~ ^[0-9a-f]{40}$ ]]
[[ $(hostname) == vmsh-nbg ]]
RELEASE=tlfprep-20261004-shutdown-${TARGET:0:12}
RECORD=$BASE/deploy/releases/$RELEASE
STAGE=$RECORD/source
PRECHECK=/tmp/vmsh-shutdown-linux-preflight-20261004
exec 9>"$BASE/deploy/metadata-deploy.lock"
flock -n 9
as_app(){ runuser -u vmsh_tasks_bot -- "$@"; }
step(){ printf '%s %s\n' "$(date -u +%FT%TZ)" "$*"; }
as_app git -C "$CODE" fetch origin vmshpwa
OLD_HEAD=$(as_app git -C "$CODE" rev-parse HEAD)
test "$OLD_HEAD" = 52151e002b11142921c4c54f880bc626fbd611f3
as_app git -C "$CODE" diff --quiet
as_app git -C "$CODE" diff --cached --quiet
as_app git -C "$CODE" merge-base --is-ancestor "$OLD_HEAD" "$TARGET"
as_app git -C "$CODE" merge-base --is-ancestor "$TARGET" origin/vmshpwa
as_app git -C "$CODE" diff --name-only "$OLD_HEAD" "$TARGET" | python3 -c '
import sys
allowed={"main.py","helpers/checkers.py","helpers/math_worker.py","helpers/math_worker_process.py","pwa_tests/integration/test_math_worker_shutdown.py","pwa_tests/fixtures/shutdown_probe.py","vmshpwa/docs/graceful-shutdown.md","vmshpwa/dev/development-plan/STATUS.md","vmshpwa/dev/design-system/STATUS.md","vmshpwa/dev/development-plan/04-phase-0-baseline.md"}
assert all(p in allowed or p.startswith("pwa_tests/reports/graceful-shutdown-20261004/") for p in sys.stdin.read().splitlines())'
test ! -e "$RECORD"
test ! -e "$BASE/vmshpwa/runtime/service-updating"
install -d -m 700 -o vmsh_tasks_bot -g nginx "$RECORD" "$STAGE"
install -m 700 "$0" "$RECORD/deploy.sh"
STATIC=$(readlink "$BASE/vmshpwa/current")
NATS_PID=$(systemctl show -p MainPID --value nats.service)
ZOOM_PID=$(systemctl show -p MainPID --value vmshzoom.service)
cd "$CODE"
sha256sum creds_prod/vmsh_bot_config_prod.json > "$RECORD/credentials-before.sha256"
as_app git archive "$TARGET" | as_app tar -x -C "$STAGE"
as_app ln -s "$CODE/.venv" "$STAGE/.venv"
step 'Reuse successful Linux preflight after verifying the exact changed Python files'
cd "$STAGE"
test -s "$PRECHECK/checked-source.sha256"
grep -q '8 passed' "$PRECHECK/preflight.log"
sha256sum -c "$PRECHECK/checked-source.sha256" > "$RECORD/preflight-source-check.log"
cp "$PRECHECK/preflight.log" "$RECORD/linux-preflight.log"
cp "$PRECHECK/checked-source.sha256" "$RECORD/checked-source.sha256"
step 'Preflight passed; keeping current frontend/dependencies/schema'
cd "$CODE"
as_app .venv/bin/python "$BASE/deploy/bin/backup.py" > "$RECORD/backup-before.json"
STOPPED=false
CUTOVER=false
rollback(){
 status=$?;trap - ERR
 if [[ "$STOPPED" == true ]];then
  systemctl stop vmshpwa.service
  if [[ "$CUTOVER" == true ]];then as_app git -C "$CODE" reset --hard "$OLD_HEAD";fi
  systemctl start vmshpwa.service
  rm -f "$BASE/vmshpwa/runtime/service-updating"
 fi
 exit "$status"
}
trap rollback ERR
touch "$BASE/vmshpwa/runtime/service-updating"
STOPPED=true
OLD_STOP_START=$(date +%s)
step 'Stopping old PWA runtime; old code still has the known child leak'
systemctl stop vmshpwa.service
printf '%s\n' "$(( $(date +%s)-OLD_STOP_START ))" > "$RECORD/old-runtime-stop-seconds.txt"
CUTOVER=true
as_app git reset --hard "$TARGET" > "$RECORD/checkout.log"
sha256sum -c "$RECORD/credentials-before.sha256" > "$RECORD/credentials-check.log"
systemctl start vmshpwa.service
for attempt in $(seq 1 30);do
 if curl -fsS --unix-socket "$BASE/vmshpwa/runtime/vmshpwa.sock" -H 'Forwarded: for="127.0.0.1";proto=https;host="prep.leaders.tech"' http://prep.leaders.tech/student/api/v1/health > "$RECORD/health.json" 2>/dev/null;then break;fi
 sleep 1
done
curl -fsS --unix-socket "$BASE/vmshpwa/runtime/vmshpwa.sock" -H 'Forwarded: for="127.0.0.1";proto=https;host="prep.leaders.tech"' http://prep.leaders.tech/student/api/v1/health >/dev/null
test "$(readlink "$BASE/vmshpwa/current")" = "$STATIC"
test "$(systemctl show -p MainPID --value nats.service)" = "$NATS_PID"
test "$(systemctl show -p MainPID --value vmshzoom.service)" = "$ZOOM_PID"
systemctl is-active --quiet vmshpwa.service vmshzoom.service vmsh-analytics.timer nats.service
rm -f "$BASE/vmshpwa/runtime/service-updating"
as_app .venv/bin/python -m vmshpwa.scripts.production_http_smoke --origin https://prep.leaders.tech --expected-instance production > "$RECORD/http-smoke.log" 2>&1
as_app .venv/bin/python "$BASE/deploy/bin/backup.py" > "$RECORD/backup-after.json"
trap - ERR
step "Backend release passed: source=$TARGET static_unchanged=true config_unchanged=true NATS_Zoom_unchanged=true"
cat "$RECORD/http-smoke.log" "$RECORD/backup-before.json" "$RECORD/backup-after.json"
grep 'gunicorn_shutdown_seconds' "$RECORD/linux-preflight.log"
