#!/usr/bin/bash
set -Eeuo pipefail
umask 027

# This file is installed root-owned at the fixed path allowed by sudoers. It
# receives no arguments from the webhook and deploys only origin/vmshpwa.
REPO_DIR=/web/vmsh_tasks_bot/vmsh_tasks_bot
DEPLOY_DIR=/web/vmsh_tasks_bot/deploy
RELEASE_ROOT=/web/vmsh_tasks_bot/vmshpwa
BRANCH=vmshpwa
DB_PATH=/web/vmsh_tasks_bot/vmsh_tasks_bot/db/production_v2.db
CONFIG_PATH=/web/vmsh_tasks_bot/vmsh_tasks_bot/creds_prod/vmsh_bot_config_prod.json
REVISION_FILE=/web/vmsh_tasks_bot/deploy/runtime/deploy/vmsh-tasks-bot.revision
LOCK_FILE=/web/vmsh_tasks_bot/deploy/runtime/deploy/vmsh-tasks-bot.lock
RUN_LOG=/web/vmsh_tasks_bot/deploy/logs/runs/vmsh-tasks-bot.log

export HOME=/home/vmsh_tasks_bot
export PATH=/home/vmsh_tasks_bot/.local/bin:/usr/local/texlive/2026/bin/x86_64-linux:/usr/local/bin:/usr/bin:/bin
export UV_CACHE_DIR=/web/vmsh_tasks_bot/cache/uv
export NVM_DIR=/web/vmsh_tasks_bot/toolchains/nvm
export NODE_OPTIONS=--max-old-space-size=4096

mkdir -p \
  /web/vmsh_tasks_bot/backups \
  /web/vmsh_tasks_bot/cache/uv \
  /web/vmsh_tasks_bot/cache/pnpm \
  /web/vmsh_tasks_bot/cache/npm \
  /web/vmsh_tasks_bot/deploy/logs/runs \
  /web/vmsh_tasks_bot/deploy/runtime/deploy \
  /web/vmsh_tasks_bot/vmshpwa/reports

exec >> >(tee -a "$RUN_LOG") 2>&1
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "Another vmsh_tasks_bot deployment is already running."
  exit 0
fi

CURRENT_STEP="initialization"
FRONTEND_ACTIVATED=false
PREVIOUS_RELEASE_ID=""
SERVICES_STOPPED=false
MIGRATION_FINISHED=false

notify_telegram() {
  local text=$1
  local token=""
  local chat_id=""

  if [[ ! -r "$CONFIG_PATH" ]]; then
    return 0
  fi
  token="$(/usr/bin/python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("telegram_bot_token", ""))' "$CONFIG_PATH" 2>/dev/null || true)"
  chat_id="$(/usr/bin/python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("exceptions_channel", ""))' "$CONFIG_PATH" 2>/dev/null || true)"
  if [[ -z "$token" || -z "$chat_id" ]]; then
    return 0
  fi
  /usr/bin/curl -fsS --max-time 15 \
    -X POST "https://api.telegram.org/bot${token}/sendMessage" \
    --data-urlencode "chat_id=${chat_id}" \
    --data-urlencode "text=${text}" >/dev/null 2>&1 || true
}

on_error() {
  local rc=$?
  local line=${BASH_LINENO[0]:-unknown}
  trap - ERR
  set +e

  echo "Deploy failed: step=${CURRENT_STEP} line=${line} exit=${rc}"
  if [[ "$FRONTEND_ACTIVATED" == true && -n "$PREVIOUS_RELEASE_ID" ]]; then
    echo "Rolling frontend back to ${PREVIOUS_RELEASE_ID}"
    cd "$REPO_DIR"
    make pwa-phase11-release-rollback \
      PWA_RELEASE_ID="$PREVIOUS_RELEASE_ID" \
      PWA_RELEASE_ROOT="$RELEASE_ROOT" \
      PWA_RELEASE_REPORT="$RELEASE_ROOT/reports/rollback-$(date -u +%Y%m%d%H%M%S).json"
  fi
  if [[ "$SERVICES_STOPPED" == true && "$MIGRATION_FINISHED" == true ]]; then
    sudo /usr/bin/systemctl start gunicorn.vmsh_tasks_bot.service
    sudo /usr/bin/systemctl start vmshpwa.service
  fi
  notify_telegram "VMSH deploy ERROR: step=${CURRENT_STEP}, line=${line}, exit=${rc}. See ${RUN_LOG}"
  exit "$rc"
}
trap on_error ERR

check_http_200() {
  local name=$1
  local url=$2
  local body_file="$DEPLOY_DIR/runtime/deploy/health-${name}.body"
  local code=""
  local attempt
  for attempt in 1 2 3 4 5; do
    code="$(/usr/bin/curl -sS --max-time 15 -o "$body_file" -w '%{http_code}' "$url" || true)"
    if [[ "$code" == 200 ]]; then
      echo "Health check passed: ${name}"
      return 0
    fi
    echo "Health check ${name} attempt ${attempt} failed: HTTP ${code}"
    sleep 2
  done
  echo "Health response for ${name}:"
  sed -n '1,20p' "$body_file" 2>/dev/null || true
  return 1
}

make_db_backup() {
  local label=$1
  local destination="/web/vmsh_tasks_bot/backups/vmsh-${label}-$(date -u +%Y%m%d%H%M%S).sqlite3"
  sqlite3 "$DB_PATH" ".backup '${destination}'"
  sqlite3 "$destination" 'PRAGMA quick_check;' | grep -Fxq ok
  echo "SQLite backup ready: ${destination}"
}

CURRENT_STEP="loading Node toolchain"
if [[ ! -s "$NVM_DIR/nvm.sh" ]]; then
  echo "Missing $NVM_DIR/nvm.sh"
  exit 1
fi
# shellcheck source=/dev/null
. "$NVM_DIR/nvm.sh"
nvm use --silent 26.5.1

CURRENT_STEP="fetching origin/${BRANCH}"
cd "$REPO_DIR"
git fetch origin "$BRANCH" --prune
TARGET_REV="$(git rev-parse "origin/${BRANCH}^{commit}")"
if [[ -s "$REVISION_FILE" ]] && git cat-file -e "$(<"$REVISION_FILE")^{commit}" 2>/dev/null; then
  OLD_REV="$(<"$REVISION_FILE")"
else
  OLD_REV="$(git rev-parse HEAD^{commit})"
fi

if [[ "$OLD_REV" == "$TARGET_REV" ]]; then
  echo "No changes to deploy: ${TARGET_REV}"
  notify_telegram "VMSH deploy skipped: origin/${BRANCH} is already ${TARGET_REV:0:12}"
  exit 0
fi

CHANGED_FILES="$(git diff --name-only "$OLD_REV" "$TARGET_REV")"
echo "Deploying ${OLD_REV:0:12} -> ${TARGET_REV:0:12}"
printf '%s\n' "$CHANGED_FILES"

NODE_DEPS_CHANGED=false
FRONTEND_CHANGED=false
PY_DEPS_CHANGED=false
BACKEND_CHANGED=false
MIGRATIONS_CHANGED=false
INFRA_CHANGED=false

while IFS= read -r changed_file; do
  [[ -n "$changed_file" ]] || continue
  if [[ "$changed_file" != */* && "$changed_file" == *.py ]]; then
    BACKEND_CHANGED=true
    continue
  fi
  case "$changed_file" in
    pyproject.toml|uv.lock|requirements.txt|requirements/*.txt)
      PY_DEPS_CHANGED=true
      BACKEND_CHANGED=true
      ;;
    migrations/*)
      MIGRATIONS_CHANGED=true
      BACKEND_CHANGED=true
      ;;
    apps/*|db_methods/*|models/*|helpers/*|handlers/*|templates/*|web/*)
      BACKEND_CHANGED=true
      ;;
    vmshpwa/scripts/static_release.py)
      FRONTEND_CHANGED=true
      ;;
    vmshpwa/scripts/*.py)
      BACKEND_CHANGED=true
      ;;
    vmshpwa/pnpm-lock.yaml|vmshpwa/pnpm-workspace.yaml|vmshpwa/package.json|vmshpwa/apps/*/package.json|vmshpwa/packages/*/package.json)
      NODE_DEPS_CHANGED=true
      FRONTEND_CHANGED=true
      ;;
    Makefile|vmshpwa/apps/*|vmshpwa/packages/*|vmshpwa/.storybook/*|vmshpwa/*.json|vmshpwa/*.ts|vmshpwa/*.js|vmshpwa/*.css)
      FRONTEND_CHANGED=true
      ;;
    docs/deploy/*|vmshpwa/deploy/*)
      INFRA_CHANGED=true
      ;;
  esac
done <<< "$CHANGED_FILES"

CURRENT_STEP="updating deployment checkout"
git checkout -B "$BRANCH" "$TARGET_REV"
git reset --hard "$TARGET_REV"
git submodule update --init --recursive

if [[ "$PY_DEPS_CHANGED" == true ]]; then
  CURRENT_STEP="syncing Python dependencies"
  uv sync --frozen
else
  echo "Python dependencies unchanged."
fi

if [[ "$NODE_DEPS_CHANGED" == true ]]; then
  CURRENT_STEP="installing frontend dependencies"
  cd "$REPO_DIR/vmshpwa"
  CI=true pnpm install --frozen-lockfile --prefer-offline --reporter=append-only
else
  echo "Frontend dependencies unchanged."
fi

PWA_RELEASE_ID=""
if [[ "$FRONTEND_CHANGED" == true ]]; then
  CURRENT_STEP="building frontend"
  cd "$REPO_DIR"
  PWA_RELEASE_ID="${TARGET_REV:0:12}-$(date -u +%Y%m%d%H%M%S)"
  make pwa-production-build \
    PWA_RELEASE_ID="$PWA_RELEASE_ID" \
    VITE_PUBLIC_MEDIA_ORIGIN=https://s3.ru1.storage.beget.cloud \
    VITE_SENTRY_DSN=https://09d20146c8b808c3760a240956fb3c90@o489435.ingest.us.sentry.io/4511885728088064

  find \
    "$REPO_DIR/vmshpwa/apps/landing/dist" \
    "$REPO_DIR/vmshpwa/apps/student/dist" \
    "$REPO_DIR/vmshpwa/apps/family/dist" \
    "$REPO_DIR/vmshpwa/apps/staff/dist" \
    -type f -size +1024c \
    \( -name '*.js' -o -name '*.css' -o -name '*.html' -o -name '*.json' -o -name '*.svg' -o -name '*.webmanifest' -o -name '*.wasm' \) \
    -print0 | xargs -0 -r -n1 brotli --force --quality=11

  CURRENT_STEP="packaging frontend release"
  make pwa-phase11-release-package \
    PWA_RELEASE_ID="$PWA_RELEASE_ID" \
    PWA_RELEASE_ROOT="$RELEASE_ROOT" \
    PWA_RELEASE_REPORT="$RELEASE_ROOT/reports/${PWA_RELEASE_ID}-package.json"
else
  echo "Frontend unchanged."
fi

if [[ "$MIGRATIONS_CHANGED" == true ]]; then
  CURRENT_STEP="creating pre-deploy SQLite backup"
  make_db_backup before-deploy

  CURRENT_STEP="stopping SQLite writers"
  sudo /usr/bin/systemctl stop vmshpwa.service
  sudo /usr/bin/systemctl stop gunicorn.vmsh_tasks_bot.service
  SERVICES_STOPPED=true

  CURRENT_STEP="applying database migrations"
  cd "$REPO_DIR"
  VMSH_RUNTIME_PROFILE=pwa-production \
  VMSH_PWA_PROTOTYPE=false \
    uv run --no-sync python -m vmshpwa.scripts.migrate_runtime
  sqlite3 "$DB_PATH" 'PRAGMA quick_check;' | grep -Fxq ok
  MIGRATION_FINISHED=true
fi

if [[ "$BACKEND_CHANGED" == true ]]; then
  if [[ "$MIGRATIONS_CHANGED" == true ]]; then
    CURRENT_STEP="starting backend services"
    sudo /usr/bin/systemctl start gunicorn.vmsh_tasks_bot.service
    sudo /usr/bin/systemctl start vmshpwa.service
    SERVICES_STOPPED=false
  else
    CURRENT_STEP="restarting backend services"
    sudo /usr/bin/systemctl restart gunicorn.vmsh_tasks_bot.service
    sudo /usr/bin/systemctl restart vmshpwa.service
  fi
  sleep 3

  CURRENT_STEP="checking backend services"
  /usr/bin/systemctl is-active --quiet gunicorn.vmsh_tasks_bot.service
  /usr/bin/systemctl is-active --quiet vmshpwa.service
  check_http_200 aiohttp-metrics http://127.0.0.1:8000/metrics
  check_http_200 student-runtime https://vmsh.shashkovs.ru/student/api/v1/runtime
  check_http_200 family-runtime https://vmsh.shashkovs.ru/family/api/v1/runtime
  check_http_200 staff-runtime https://vmsh.shashkovs.ru/staff/api/v1/runtime
else
  echo "Backend unchanged."
fi

if [[ "$FRONTEND_CHANGED" == true ]]; then
  CURRENT_STEP="activating frontend release"
  if [[ -L "$RELEASE_ROOT/current" ]]; then
    PREVIOUS_RELEASE_ID="$(basename "$(readlink -f "$RELEASE_ROOT/current")")"
  fi
  cd "$REPO_DIR"
  make pwa-phase11-release-activate \
    PWA_RELEASE_ID="$PWA_RELEASE_ID" \
    PWA_RELEASE_ROOT="$RELEASE_ROOT" \
    PWA_RELEASE_REPORT="$RELEASE_ROOT/reports/${PWA_RELEASE_ID}-activate.json"
  FRONTEND_ACTIVATED=true

  CURRENT_STEP="checking public frontend"
  check_http_200 landing https://vmsh.shashkovs.ru/
  check_http_200 student https://vmsh.shashkovs.ru/student/
  check_http_200 family https://vmsh.shashkovs.ru/family/
  check_http_200 staff https://vmsh.shashkovs.ru/staff/
fi

if [[ "$MIGRATIONS_CHANGED" == true ]]; then
  CURRENT_STEP="creating post-deploy SQLite backup"
  make_db_backup after-deploy
fi

CURRENT_STEP="recording deployed revision"
printf '%s\n' "$TARGET_REV" > "${REVISION_FILE}.new"
mv "${REVISION_FILE}.new" "$REVISION_FILE"

if [[ "$INFRA_CHANGED" == true ]]; then
  echo "Deployment infrastructure changed in git; reinstall root-owned webhook/nginx/systemd artifacts manually."
  notify_telegram "VMSH deploy warning: docs/deploy changed; reinstall the root-owned webhook artifacts manually."
fi

echo "Deploy finished: revision=${TARGET_REV:0:12} frontend=${FRONTEND_CHANGED} backend=${BACKEND_CHANGED} migrations=${MIGRATIONS_CHANGED}"
notify_telegram "VMSH deploy finished: ${TARGET_REV:0:12}; frontend=${FRONTEND_CHANGED}, backend=${BACKEND_CHANGED}, migrations=${MIGRATIONS_CHANGED}"
