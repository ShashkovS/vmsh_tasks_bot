#!/bin/bash
# Owner-authorized backend release; vmshpwa/docs/cpu-incident-20261004.md.
set -Eeuo pipefail
BASE=/web/vmsh_tasks_bot
CODE=$BASE/vmsh_tasks_bot
TARGET=${1:?Pass the reviewed full SHA}
[[ "$TARGET" =~ ^[0-9a-f]{40}$ ]]
[[ $(hostname) == vmsh-nbg ]]
RELEASE=tlfprep-20261004-cpu-${TARGET:0:12}
RECORD=$BASE/deploy/releases/$RELEASE
exec 9>"$BASE/deploy/metadata-deploy.lock"
flock -n 9
as_app(){ runuser -u vmsh_tasks_bot -- "$@"; }
step(){ printf '%s %s\n' "$(date -u +%FT%TZ)" "$*"; }
as_app git -C "$CODE" fetch origin vmshpwa
OLD_HEAD=$(as_app git -C "$CODE" rev-parse HEAD)
test "$OLD_HEAD" = cc60df33d01b29ae77476db0b43b711f79e5d370
as_app git -C "$CODE" diff --quiet
as_app git -C "$CODE" diff --cached --quiet
as_app git -C "$CODE" merge-base --is-ancestor "$OLD_HEAD" "$TARGET"
as_app git -C "$CODE" merge-base --is-ancestor "$TARGET" origin/vmshpwa
as_app git -C "$CODE" diff --exit-code "$OLD_HEAD" "$TARGET" -- migrations pyproject.toml uv.lock vmshpwa/pnpm-lock.yaml vmshpwa/apps vmshpwa/packages vmshpwa/deploy docs/deploy
as_app git -C "$CODE" diff --name-only "$OLD_HEAD" "$TARGET" | python3 -c '
import sys
allowed={"db_methods/pwa/content.py","db_methods/pwa/effective_results.py","pwa_tests/integration/test_written_result_precedence.py"}
assert all(p in allowed or p.endswith(".md") or p.startswith(("pwa_tests/reports/cpu-incident-20261004/","pwa_tests/reports/hint-preview-empty-materials-20261004/")) for p in sys.stdin.read().splitlines())'
test ! -e "$RECORD"
test ! -e "$BASE/vmshpwa/runtime/service-updating"
install -d -m 700 -o vmsh_tasks_bot -g nginx "$RECORD"
install -m 700 "$0" "$RECORD/deploy.sh"
printf '%s\n' "$OLD_HEAD" > "$RECORD/source-before.txt"
printf '%s\n' "$TARGET" > "$RECORD/source-after.txt"
STATIC=$(readlink "$BASE/vmshpwa/current")
NATS_PID=$(systemctl show -p MainPID --value nats.service)
ZOOM_PID=$(systemctl show -p MainPID --value vmshzoom.service)
cd "$CODE"
sha256sum creds_prod/vmsh_bot_config_prod.json > "$RECORD/credentials-before.sha256"
step 'Backing up live SQLite; frontend, dependencies and schema are unchanged'
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
step 'Restarting only PWA with the checked student-scoped result query'
systemctl stop vmshpwa.service
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
step "Backend release passed: source=$TARGET static_credentials_schema_unchanged=true NATS_Zoom_unchanged=true"
cat "$RECORD/http-smoke.log" "$RECORD/backup-before.json" "$RECORD/backup-after.json"
