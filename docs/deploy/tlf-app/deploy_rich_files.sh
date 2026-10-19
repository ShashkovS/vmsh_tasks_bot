#!/bin/bash
# Manual release: vmshpwa/docs/rich-file-attachments.md and its production record.
# Run via ssh/config tlfprepagent as root with the reviewed full commit SHA.
set -Eeuo pipefail
BASE=/web/vmsh_tasks_bot
CODE=$BASE/vmsh_tasks_bot
TARGET=${1:?Pass the reviewed full commit SHA}
[[ "$TARGET" =~ ^[0-9a-f]{40}$ ]]
[[ $(hostname) == vmsh-nbg ]]
RELEASE=tlfprep-$(date -u +%Y%m%d)-rich-files-${TARGET:0:12}
RECORD=$BASE/deploy/releases/$RELEASE
STAGE=$RECORD/source
NGINX=$BASE/vmshpwa/runtime/nginx/vmshpwa.conf
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
as_app git -C "$CODE" diff --exit-code "$OLD_HEAD" "$TARGET" -- pyproject.toml uv.lock vmshpwa/pnpm-lock.yaml docs/deploy/tlf-app/build_source.sh docs/deploy/tlf-app/render_server.py
NEW_MIGRATIONS=$(as_app git -C "$CODE" diff --name-only "$OLD_HEAD" "$TARGET" -- migrations)
test -z "$NEW_MIGRATIONS"
INFRA=$(as_app git -C "$CODE" diff --name-only "$OLD_HEAD" "$TARGET" -- vmshpwa/deploy)
test "$INFRA" = 'vmshpwa/deploy/nginx/vmshpwa.conf.template'
test ! -e "$RECORD"
test ! -e "$BASE/vmshpwa/runtime/service-updating"
install -d -m 700 -o vmsh_tasks_bot -g nginx "$RECORD" "$STAGE"
install -m 700 "$0" "$RECORD/deploy.sh"
printf '%s\n' "$OLD_HEAD" > "$RECORD/source-before.txt"
OLD_STATIC=$(readlink "$BASE/vmshpwa/current")
printf '%s\n' "$OLD_STATIC" > "$RECORD/static-before.txt"
NATS_PID=$(systemctl show -p MainPID --value nats.service)
ANALYTICS_ACTIVE=$(systemctl is-active vmsh-analytics.timer || true)
cp -p "$NGINX" "$RECORD/nginx-before.conf"
cd "$CODE"
sha256sum creds_prod/vmsh_bot_config_prod.json > "$RECORD/credentials-before.sha256"
as_app .venv/bin/python "$BASE/deploy/bin/backup.py" > "$RECORD/backup-before.json"
as_app git archive "$TARGET" | as_app tar -x -C "$STAGE"
as_app ln -s "$CODE/.venv" "$STAGE/.venv"
install -m 644 "$STAGE/docs/deploy/tlf-app/rich_files_data_check.py" "$RECORD/data-check.py"
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
# Only the reviewed public filesystem location may change; retain host config.
as_app env RICH_FILES_OLD_HEAD="$OLD_HEAD" .venv/bin/python - <<'PY' > "$RECORD/nginx-review.log"
import os, subprocess
from pathlib import Path
name='vmshpwa/deploy/nginx/vmshpwa.conf.template'
old=subprocess.check_output(['git','-C','/web/vmsh_tasks_bot/vmsh_tasks_bot','show',f"{os.environ['RICH_FILES_OLD_HEAD']}:{name}"],text=True)
new=Path(name).read_text()
start=new.index('    # Public filesystem attachments;')
end=new.index('    # aiohttp sends a heartbeat',start)
block=new[start:end]
assert new.replace(block,'',1)==old, 'Unexpected nginx template change'
active=Path('/web/vmsh_tasks_bot/vmshpwa/runtime/nginx/vmshpwa.conf').read_text()
assert 'location ^~ /pwa-rich-files/' not in active
anchor='    location = /student/ws {'
assert active.count(anchor)==1
Path('../nginx-after.conf').write_text(active.replace(anchor,block+anchor,1))
print('Only /pwa-rich-files/ location added; TLS, sockets, media origins and other locations retained')
PY
cd "$CODE"
STOPPED=false
CUTOVER=false
rollback() {
    status=$?
    trap - ERR
    if [[ "$STOPPED" == true ]]; then
        systemctl stop vmsh-analytics.timer vmsh-analytics.service vmshpwa.service vmshzoom.service
        if [[ "$CUTOVER" == true ]]; then
            # No migration: restore source/static/config while retaining every DB row.
            as_app git reset --hard "$OLD_HEAD"
            ln -s "$OLD_STATIC" "$BASE/vmshpwa/current.rich-files-rollback"
            mv -Tf "$BASE/vmshpwa/current.rich-files-rollback" "$BASE/vmshpwa/current"
            cp -p "$RECORD/nginx-before.conf" "$NGINX"
            nginx -t
            systemctl reload nginx.service
        fi
        systemctl start vmshpwa.service vmshzoom.service
        if [[ "$ANALYTICS_ACTIVE" == active ]]; then systemctl start vmsh-analytics.timer; fi
        rm -f "$BASE/vmshpwa/runtime/service-updating"
    fi
    exit "$status"
}
trap rollback ERR
test "$(as_app git rev-parse HEAD)" = "$OLD_HEAD"
touch "$BASE/vmshpwa/runtime/service-updating"
STOPPED=true
systemctl stop vmsh-analytics.timer vmsh-analytics.service vmshpwa.service vmshzoom.service
as_app .venv/bin/python "$RECORD/data-check.py" "$CODE/db/production_prep.db" > "$RECORD/data-before.json"
CUTOVER=true
as_app git reset --hard "$TARGET" > "$RECORD/checkout.log"
as_app .venv/bin/python - <<'PY' > "$RECORD/schema.json"
from db_methods.pwa.migrations import require_current_schema
from dataclasses import asdict
import json
print(json.dumps(asdict(require_current_schema('db/production_prep.db')), default=str))
PY
as_app .venv/bin/python "$RECORD/data-check.py" "$CODE/db/production_prep.db" > "$RECORD/data-after.json"
cmp "$RECORD/data-before.json" "$RECORD/data-after.json"
sha256sum -c "$RECORD/credentials-before.sha256" > "$RECORD/credentials-check.log"
systemctl start vmshpwa.service vmshzoom.service
for attempt in $(seq 1 30); do
    if curl -fsS --unix-socket "$BASE/vmshpwa/runtime/vmshpwa.sock" -H 'X-Forwarded-For: 127.0.0.1' -H 'X-Forwarded-Host: prep.leaders.tech' -H 'X-Forwarded-Proto: https' http://localhost/student/api/v1/health > "$RECORD/backend-health.json" 2>/dev/null && curl -fsS --unix-socket "$BASE/vmshpwa/runtime/zoom.sock" http://localhost/health > "$RECORD/zoom-health.json" 2>/dev/null; then break; fi
    sleep 1
done
curl -fsS --unix-socket "$BASE/vmshpwa/runtime/vmshpwa.sock" -H 'X-Forwarded-For: 127.0.0.1' -H 'X-Forwarded-Host: prep.leaders.tech' -H 'X-Forwarded-Proto: https' http://localhost/student/api/v1/health >/dev/null
curl -fsS --unix-socket "$BASE/vmshpwa/runtime/zoom.sock" http://localhost/health >/dev/null
env RICH_FILES_RELEASE="$RELEASE" RICH_FILES_STAGE="$STAGE" python3 - <<'PY'
import os, re, shutil
from pathlib import Path
base=Path('/web/vmsh_tasks_bot/vmshpwa')
release=base/'releases'/os.environ['RICH_FILES_RELEASE']
stage=Path(os.environ['RICH_FILES_STAGE'])
for audience in ('landing','student','family','staff'):
    shutil.copytree(stage/f'vmshpwa/apps/{audience}/dist', release/audience)
    index=release/audience/'index.html'
    index.write_text(re.sub(r'((?:src|href)="/[^"?]+/assets/[^"?]+\.(?:js|css))"', rf'\1?release={release.name}"', index.read_text()))
    assets=base/f'immutable-assets/{audience}/assets'
    for source in (release/audience/'assets').rglob('*'):
        target=assets/source.relative_to(release/audience/'assets')
        if source.is_file() and target.exists():
            assert source.read_bytes()==target.read_bytes(), 'Immutable asset collision'
    shutil.copytree(release/audience/'assets', assets, dirs_exist_ok=True)
for directory in (release, base/'immutable-assets'):
    shutil.chown(directory,user='root',group='nginx')
    directory.chmod(0o750)
    for path in directory.rglob('*'):
        shutil.chown(path,user='root',group='nginx')
        path.chmod(0o750 if path.is_dir() else 0o640)
temporary=base/'current.rich-files'
temporary.symlink_to(release)
temporary.replace(base/'current')
PY
install -m 640 -o root -g nginx "$RECORD/nginx-after.conf" "$NGINX"
nginx -t > "$RECORD/nginx-check.log" 2>&1
systemctl reload nginx.service
if [[ "$ANALYTICS_ACTIVE" == active ]]; then systemctl start vmsh-analytics.timer; fi
rm -f "$BASE/vmshpwa/runtime/service-updating"
as_app .venv/bin/python -m vmshpwa.scripts.production_http_smoke --origin https://prep.leaders.tech --expected-instance production > "$RECORD/http-smoke.log" 2>&1
test "$(systemctl show -p MainPID --value nats.service)" = "$NATS_PID"
as_app .venv/bin/python "$BASE/deploy/bin/backup.py" > "$RECORD/backup-after.json"
trap - ERR
printf 'File attachment deployment passed: source=%s release=%s record=%s data=unchanged credentials=unchanged NATS=unchanged\n' "$TARGET" "$RELEASE" "$RECORD"
cat "$RECORD/http-smoke.log" "$RECORD/backup-before.json" "$RECORD/backup-after.json"
