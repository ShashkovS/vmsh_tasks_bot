#!/bin/bash
set -euo pipefail
BASE=/web/vmsh_tasks_bot
CODE=$BASE/vmsh_tasks_bot
export TLF_RELEASE_ID=${TLF_RELEASE_ID:-tlfprep-20260930}
export PATH=$BASE/toolchains/node/bin:$BASE/toolchains/pnpm/node_modules/.bin:$BASE/toolchains/uv:$PATH
cd "$CODE"
sudo runuser -u vmsh_tasks_bot -- env PATH="$PATH" UV_CACHE_DIR="$BASE/cache/uv" UV_PYTHON_INSTALL_DIR="$BASE/toolchains/python" "$BASE/toolchains/uv/uv" sync --frozen --no-dev --managed-python --python 3.14.4 > "$BASE/deploy/reports/backend-build.log" 2>&1
sudo runuser -u vmsh_tasks_bot -- env PATH="$PATH" CI=true pnpm --dir vmshpwa install --frozen-lockfile --ignore-scripts --store-dir "$BASE/cache/pnpm" > "$BASE/deploy/reports/frontend-install.log" 2>&1
# See glitchtip/migration-20261011.md: canonical frontend DSN and private maps.
sudo runuser -u vmsh_tasks_bot -- env PATH="$PATH" python3 -m vmshpwa.scripts.production_frontend_build \
    --release "$TLF_RELEASE_ID" --media-origin https://tlfprepimages.nbg1.your-objectstorage.com \
    > "$BASE/deploy/reports/frontend-build.log" 2>&1
printf 'production source build completed; migrate only after both workers stop\n'
