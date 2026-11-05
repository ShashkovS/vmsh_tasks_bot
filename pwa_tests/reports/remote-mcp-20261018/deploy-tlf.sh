#!/bin/bash
# Owner-authorized release: vmshpwa/docs/ai-review-assistant.md.
# Run as root on TLF with the exact tested tree. Remote MCP continuation; no schema changes.
set -Eeuo pipefail
umask 027
BASE=/web/vmsh_tasks_bot
CODE=$BASE/vmsh_tasks_bot
TARGET=${1:?Pass the reviewed full commit SHA}
[[ "$TARGET" =~ ^[0-9a-f]{40}$ ]]
[[ $(hostname) == vmsh-nbg ]]
RELEASE=tlfprep-20261018-remote-mcp-${TARGET:0:12}
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
as_app git -C "$CODE" diff --exit-code "$OLD_HEAD" "$TARGET" -- vmshpwa/pnpm-lock.yaml vmshpwa/pnpm-workspace.yaml vmshpwa/deploy docs/deploy/tlf-app/build_source.sh
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
cp -a "$CODE/creds_prod/vmsh_bot_config_prod.json" "$RECORD/config-before.json"
STOPPED=false
MIGRATED=false
rollback() {
    status=$?; trap - ERR; set +e
    step "Release failed with status $status; restoring previous configuration/tools"
    cp -a "$RECORD/config-before.json" "$CODE/creds_prod/vmsh_bot_config_prod.json"
    if [[ "$STOPPED" == true ]]; then
        touch "$BASE/vmshpwa/runtime/service-updating"
        systemctl stop vmshpwa.service vmshzoom.service
        if [[ "$MIGRATED" == true ]]; then
            if ! as_app "$CODE/.venv/bin/python" "$STAGE/pwa_tests/reports/ai-review-assistant-20261018/rollback-combined.py" "$DB" "$STAGE/migrations" "$RECORD/migrations-before.json"; then
                step 'Rollback requires intervention; keeping maintenance and data'
                exit "$status"
            fi
        fi
        as_app git -C "$CODE" reset --hard "$OLD_HEAD"
        (cd "$CODE" && as_app env PATH="$PATH" UV_CACHE_DIR="$BASE/cache/uv" UV_PYTHON_INSTALL_DIR="$BASE/toolchains/python" uv sync --frozen --no-dev --managed-python --python 3.14.4)
        ln -s "$OLD_STATIC" "$BASE/vmshpwa/current.audit-rollback"
        mv -Tf "$BASE/vmshpwa/current.audit-rollback" "$BASE/vmshpwa/current"
        systemctl start vmshpwa.service vmshzoom.service
        if [[ "$ANALYTICS_ACTIVE" == active ]]; then systemctl start vmsh-analytics.timer; fi
        rm -f "$BASE/vmshpwa/runtime/service-updating"
    fi
    exit "$status"
}
trap rollback ERR
as_app git -C "$CODE" archive "$TARGET" | as_app tar -x -C "$STAGE"
as_app ln -s "$CODE/.venv" "$STAGE/.venv"
as_app ln -s "$CODE/creds_prod/vmsh_bot_config_prod.json" "$STAGE/creds_prod/vmsh_bot_config_prod.json"
install -d -m 700 -o vmsh_tasks_bot -g vmsh_tasks_bot "$STAGE/.runtime"
install -m 600 -o vmsh_tasks_bot -g vmsh_tasks_bot "$CODE/.runtime/glitchtip-portal.json" "$STAGE/.runtime/glitchtip-portal.json"
# cross-backup/README.md: preserve the installed helper and archives.
step 'Verified SQLite backups before production build'
as_app "$CODE/.venv/bin/python" "$BASE/deploy/bin/backup.py" > "$RECORD/backup-before.json"
cd "$STAGE"
step 'Building frozen production bundles and verifying private sourcemap upload'
as_app env CI=true pnpm --dir vmshpwa install --frozen-lockfile --ignore-scripts --prefer-offline --store-dir "$BASE/cache/pnpm" > "$RECORD/frontend-install.log" 2>&1
as_app python3 -m vmshpwa.scripts.production_frontend_build --release "$RELEASE" --media-origin https://tlfprepimages.nbg1.your-objectstorage.com > "$RECORD/frontend-build.log" 2>&1
as_app .venv/bin/python -m vmshpwa.scripts.static_release package --release-id "$RELEASE" --release-root "$RECORD/static" --report "$RECORD/static-package.json" > "$RECORD/static-package.log"
env RELEASE="$RELEASE" RECORD="$RECORD" python3 - <<'PY'
import os
import shutil
from pathlib import Path

base = Path('/web/vmsh_tasks_bot/vmshpwa')
source = Path(os.environ['RECORD']) / 'static' / os.environ['RELEASE']
release = base / 'releases' / os.environ['RELEASE']
shutil.copytree(source, release)
for audience in ('landing', 'student', 'family', 'staff'):
    assets = release / audience / 'assets'
    store = base / 'immutable-assets' / audience / 'assets'
    for path in assets.rglob('*'):
        if path.is_file():
            destination = store / path.relative_to(assets)
            if destination.exists():
                assert path.read_bytes() == destination.read_bytes(), 'Immutable asset collision'
    shutil.copytree(assets, store, dirs_exist_ok=True)
for directory in (release, base / 'immutable-assets'):
    shutil.chown(directory, user='root', group='nginx')
    directory.chmod(0o750)
    for path in directory.rglob('*'):
        assert not path.is_symlink()
        shutil.chown(path, user='root', group='nginx')
        path.chmod(0o750 if path.is_dir() else 0o640)
PY
as_app .venv/bin/python -m vmshpwa.scripts.static_release verify --release-id "$RELEASE" --release-root "$BASE/vmshpwa/releases" --report "$RECORD/static-verified.json" > "$RECORD/static-verified.log"
cd "$CODE"
test "$(as_app git -C "$CODE" rev-parse HEAD)" = "$OLD_HEAD"
step 'Switching workers without schema changes; business data preserved'
touch "$BASE/vmshpwa/runtime/service-updating"
STOPPED=true
systemctl stop vmsh-analytics.timer vmsh-analytics.service vmshpwa.service vmshzoom.service
as_app .venv/bin/python "$STAGE/docs/deploy/tlf-app/rich_files_data_check.py" "$DB" > "$RECORD/data-before.json"
env DB="$DB" RECORD="$RECORD" python3 - <<'BEFORE'
import json,os,sqlite3
from pathlib import Path
with sqlite3.connect(os.environ['DB']) as c:
    ids=[r[0] for r in c.execute('SELECT migration_id FROM _yoyo_migration ORDER BY migration_id')]
(Path(os.environ['RECORD'])/'migrations-before.json').write_text(json.dumps(ids))
BEFORE
as_app git -C "$CODE" merge --ff-only "$TARGET" > "$RECORD/checkout.log"
as_app env PATH="$PATH" UV_CACHE_DIR="$BASE/cache/uv" UV_PYTHON_INSTALL_DIR="$BASE/toolchains/python" uv sync --frozen --no-dev --managed-python --python 3.14.4 > "$RECORD/backend-sync.log" 2>&1
as_app env PROD=true VMSH_RUNTIME_PROFILE=pwa-production VMSH_PWA_PROTOTYPE=false VMSH_DB_FILENAME="$DB" .venv/bin/python -m vmshpwa.scripts.database_performance_guard > "$RECORD/database-guard.json" 2>&1
as_app .venv/bin/python "$CODE/docs/deploy/tlf-app/rich_files_data_check.py" "$DB" > "$RECORD/data-after.json"
env RECORD="$RECORD" python3 - <<'PARITY' > "$RECORD/live-data-check.json"
import json,os
from pathlib import Path
record=Path(os.environ['RECORD'])
before=json.loads((record/'data-before.json').read_text());after=json.loads((record/'data-after.json').read_text())
added=set(after)-set(before)
assert added <= {'ai_review_tokens','ai_review_suggestions','ai_review_events'}
assert all(after.get(k)==v for k,v in before.items()), 'Existing business rows changed'
assert all(after[k]['count']==0 for k in added), 'New tables must be empty at migration'
print(json.dumps({'businessTablesPreserved':len(before),'newEmptyTables':sorted(added)}))
PARITY
env RECORD="$RECORD" CODE="$CODE" python3 - <<'PY' > "$RECORD/credentials-check.log"
import json
import os
from pathlib import Path

before = json.loads((Path(os.environ['RECORD']) / 'config-before.json').read_text())
after = json.loads((Path(os.environ['CODE']) / 'creds_prod/vmsh_bot_config_prod.json').read_text())
before.pop('sentry_release', None)
after.pop('sentry_release', None)
assert before == after, 'Unrelated canonical settings changed'
print('Canonical settings preserved; only approved release label changed')
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
ln -s "$BASE/vmshpwa/releases/$RELEASE" "$BASE/vmshpwa/current.audit"
mv -Tf "$BASE/vmshpwa/current.audit" "$BASE/vmshpwa/current"
if [[ "$ANALYTICS_ACTIVE" == active ]]; then systemctl start vmsh-analytics.timer; fi
rm -f "$BASE/vmshpwa/runtime/service-updating"
as_app .venv/bin/python -m vmshpwa.scripts.production_http_smoke --origin https://prep.leaders.tech --expected-instance production > "$RECORD/http-smoke.log" 2>&1
test "$(systemctl show -p MainPID --value nats.service)" = "$NATS_PID"
systemctl is-active --quiet vmshpwa.service vmshzoom.service vmsh-analytics.timer nats.service vmsh-cross-backup.timer vmsh-cross-backup-sync.timer vmsh-cross-backup-verify.timer
as_app .venv/bin/python "$BASE/deploy/bin/backup.py" > "$RECORD/backup-after.json"
trap - ERR
step "Deployment passed: source=$TARGET release=$RELEASE data/config/NATS/backups preserved"
cat "$RECORD/http-smoke.log" "$RECORD/backup-before.json" "$RECORD/backup-after.json"
