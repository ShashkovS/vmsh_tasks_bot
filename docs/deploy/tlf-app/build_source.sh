#!/bin/bash
set -euo pipefail
BASE=/web/vmsh_tasks_bot
CODE=$BASE/vmsh_tasks_bot
export TLF_RELEASE_ID=${TLF_RELEASE_ID:-tlfprep-20260930}
export PATH=$BASE/toolchains/node/bin:$BASE/toolchains/pnpm/node_modules/.bin:$BASE/toolchains/uv:$PATH
cd "$CODE"
sudo runuser -u vmsh_tasks_bot -- env PATH="$PATH" UV_CACHE_DIR="$BASE/cache/uv" UV_PYTHON_INSTALL_DIR="$BASE/toolchains/python" "$BASE/toolchains/uv/uv" sync --frozen --no-dev --managed-python --python 3.14.4 > "$BASE/deploy/reports/backend-build.log" 2>&1
sudo runuser -u vmsh_tasks_bot -- env PATH="$PATH" CI=true pnpm --dir vmshpwa install --frozen-lockfile --ignore-scripts --store-dir "$BASE/cache/pnpm" > "$BASE/deploy/reports/frontend-install.log" 2>&1
sudo runuser -u vmsh_tasks_bot -- env PATH="$PATH" TLF_RELEASE_ID="$TLF_RELEASE_ID" python3 - <<'PY' > "$BASE/deploy/reports/frontend-build.log" 2>&1
import json,os,subprocess
from pathlib import Path
c=json.loads(Path('creds_prod/vmsh_bot_config_prod.json').read_text())
env=dict(os.environ,CI='true',VITE_SENTRY_DSN=c['sentry_dsn'],VITE_PWA_PROTOTYPE='false',VMSH_FRONTEND_BUILD_PROFILE='production',VITE_SENTRY_RELEASE=os.environ.get('TLF_RELEASE_ID','tlfprep-20260930'),VITE_PUBLIC_MEDIA_ORIGIN='https://tlfprepimages.nbg1.your-objectstorage.com')
for audience in ('landing','student','family','staff'):
    subprocess.run(['../../node_modules/.bin/vite','build'],cwd=f'vmshpwa/apps/{audience}',env=env,check=True)
PY
printf 'production source build completed; migrate only after both workers stop\n'
