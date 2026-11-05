#!/bin/bash
# Owner-authorized frontend release; vmshpwa/docs/lesson-statistics.md#staff-violin-polish-2026-10-05.
set -Eeuo pipefail
BASE=/web/vmsh_tasks_bot
CODE=$BASE/vmsh_tasks_bot
TARGET=${1:?Pass the reviewed full commit SHA}
[[ "$TARGET" =~ ^[0-9a-f]{40}$ ]]
[[ $(hostname) == vmsh-nbg ]]
RELEASE=tlfprep-20261005-violin-polish-${TARGET:0:12}
RECORD=$BASE/deploy/releases/$RELEASE
STAGE=$RECORD/source
export PATH=$BASE/toolchains/node/bin:$BASE/toolchains/pnpm/node_modules/.bin:$BASE/toolchains/uv:$PATH
exec 9>"$BASE/deploy/metadata-deploy.lock"
flock -n 9
as_app() { runuser -u vmsh_tasks_bot -- "$@"; }
step() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*"; }
as_app git -C "$CODE" fetch origin vmshpwa
OLD_HEAD=$(as_app git -C "$CODE" rev-parse HEAD)
test "$OLD_HEAD" = 09bc16f185de5220d4c22d7d3c171238ce653dad
as_app git -C "$CODE" diff --quiet
as_app git -C "$CODE" diff --cached --quiet
as_app git -C "$CODE" merge-base --is-ancestor "$OLD_HEAD" "$TARGET"
as_app git -C "$CODE" merge-base --is-ancestor "$TARGET" origin/vmshpwa
as_app git -C "$CODE" diff --exit-code "$OLD_HEAD" "$TARGET" -- pyproject.toml uv.lock vmshpwa/pnpm-lock.yaml vmshpwa/deploy docs/deploy/tlf-app/build_source.sh docs/deploy/tlf-app/render_server.py
as_app git -C "$CODE" diff --exit-code "$OLD_HEAD" "$TARGET" -- main.py apps db_methods helpers models handlers migrations
test ! -e "$RECORD"
test ! -e "$BASE/vmshpwa/runtime/service-updating"
install -d -m 700 -o vmsh_tasks_bot -g nginx "$RECORD" "$STAGE"
install -m 700 "$0" "$RECORD/deploy.sh"
printf '%s\n' "$OLD_HEAD" > "$RECORD/source-before.txt"
printf '%s\n' "$TARGET" > "$RECORD/source-after.txt"
OLD_STATIC=$(readlink "$BASE/vmshpwa/current")
printf '%s\n' "$OLD_STATIC" > "$RECORD/static-before.txt"
for service in vmshpwa.service vmshzoom.service nats.service; do
    systemctl show -p MainPID --value "$service" > "$RECORD/$service.pid-before"
done
cd "$CODE"
sha256sum creds_prod/vmsh_bot_config_prod.json > "$RECORD/credentials-before.sha256"
step 'Verified backups before release'
as_app .venv/bin/python "$BASE/deploy/bin/backup.py" > "$RECORD/backup-before.json"
as_app git archive "$TARGET" | as_app tar -x -C "$STAGE"
as_app ln -s "$CODE/.venv" "$STAGE/.venv"
step 'Building isolated production bundles from cached frozen dependencies'
cd "$STAGE"
as_app env CI=true pnpm --dir vmshpwa install --frozen-lockfile --ignore-scripts --prefer-offline --store-dir "$BASE/cache/pnpm" > "$RECORD/frontend-install.log" 2>&1
as_app env TLF_RELEASE_ID="$RELEASE" .venv/bin/python - <<'PY' > "$RECORD/frontend-build.log" 2>&1
import json, os, re, subprocess
from pathlib import Path
config=json.loads(Path('/web/vmsh_tasks_bot/vmsh_tasks_bot/creds_prod/vmsh_bot_config_prod.json').read_text())
release=os.environ['TLF_RELEASE_ID']
environment=dict(os.environ, CI='true', VITE_SENTRY_DSN=config['sentry_dsn'], VITE_PWA_PROTOTYPE='false', VMSH_FRONTEND_BUILD_PROFILE='production', VITE_SENTRY_RELEASE=release, VITE_PUBLIC_MEDIA_ORIGIN='https://tlfprepimages.nbg1.your-objectstorage.com')
for audience in ('landing', 'student', 'family', 'staff'):
    subprocess.run(['../../node_modules/.bin/vite', 'build'], cwd=f'vmshpwa/apps/{audience}', env=environment, check=True)
    index=Path(f'vmshpwa/apps/{audience}/dist/index.html')
    index.write_text(re.sub(r'((?:src|href)="/[^"?]+/assets/[^"?]+\.(?:js|css))"',rf'\1?release={release}"',index.read_text()))
PY
step 'Verifying production provenance and preparing immutable static assets'
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
.venv/bin/python -m vmshpwa.scripts.static_release verify --release-id "$RELEASE" --release-root "$BASE/vmshpwa/releases" --report "$RECORD/static-verified.json" > "$RECORD/static-verified.log"
cd "$CODE"
CUTOVER=false
rollback() {
    status=$?;trap - ERR
    step "Release failed with status $status; restore source/static without touching live data"
    if [[ "$CUTOVER" == true ]]; then
        as_app git -C "$CODE" reset --hard "$OLD_HEAD"
        ln -s "$OLD_STATIC" "$BASE/vmshpwa/current.violin-polish-rollback"
        mv -Tf "$BASE/vmshpwa/current.violin-polish-rollback" "$BASE/vmshpwa/current"
    fi
    exit "$status"
}
trap rollback ERR
test "$(as_app git rev-parse HEAD)" = "$OLD_HEAD"
as_app git diff --quiet
as_app git diff --cached --quiet
step 'Activating frontend-only release; all services keep running'
CUTOVER=true
as_app git merge --ff-only "$TARGET" > "$RECORD/checkout.log"
ln -s "$BASE/vmshpwa/releases/$RELEASE" "$BASE/vmshpwa/current.violin-polish"
mv -Tf "$BASE/vmshpwa/current.violin-polish" "$BASE/vmshpwa/current"
sha256sum -c "$RECORD/credentials-before.sha256" > "$RECORD/credentials-check.log"
as_app .venv/bin/python -m vmshpwa.scripts.production_http_smoke --origin https://prep.leaders.tech --expected-instance production > "$RECORD/http-smoke.log" 2>&1
for service in vmshpwa.service vmshzoom.service nats.service; do
    test "$(systemctl show -p MainPID --value "$service")" = "$(cat "$RECORD/$service.pid-before")"
done
systemctl is-active --quiet vmshpwa.service vmshzoom.service vmsh-analytics.timer nats.service
test ! -e "$BASE/vmshpwa/runtime/service-updating"
as_app .venv/bin/python "$BASE/deploy/bin/backup.py" > "$RECORD/backup-after.json"
trap - ERR
step "Deployment passed: source=$TARGET release=$RELEASE frontend-only all service PIDs unchanged"
cat "$RECORD/http-smoke.log" "$RECORD/backup-before.json" "$RECORD/backup-after.json"
