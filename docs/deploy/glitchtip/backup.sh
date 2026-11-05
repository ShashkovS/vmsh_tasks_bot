#!/bin/bash
# Operation and restore procedure: docs/deploy/glitchtip/README.md.
set -euo pipefail
umask 077
cd /opt/glitchtip
mkdir -p /var/backups/glitchtip
exec 9>/var/backups/glitchtip/.lock
flock -n 9
stamp=$(date -u +%Y%m%dT%H%M%SZ)
destination=/var/backups/glitchtip/$stamp
temporary=$(mktemp -d /var/backups/glitchtip/.partial.XXXXXX)
trap 'rm -rf -- "$temporary"' EXIT
docker compose exec -T postgres pg_dump -U glitchtip -d glitchtip -Fc > "$temporary/database.dump"
docker compose exec -T postgres pg_restore --list < "$temporary/database.dump" > /dev/null
uploads=$(docker volume inspect glitchtip_uploads --format '{{.Mountpoint}}')
tar -C "$uploads" -czf "$temporary/uploads.tar.gz" .
tar -tzf "$temporary/uploads.tar.gz" > /dev/null
cp compose.yml "$temporary/compose.yml"
cp .env "$temporary/environment.env"
if [[ -f telegram.json ]]; then
    cp telegram.json "$temporary/telegram.json"
    cp /usr/local/libexec/glitchtip-telegram.py "$temporary/telegram-webhook.py"
    cp /etc/systemd/system/glitchtip-telegram.service "$temporary/glitchtip-telegram.service"
    python3 - "$temporary/telegram-state.sqlite3" <<'PY'
import sqlite3, sys
from pathlib import Path
state = Path('/var/lib/glitchtip-telegram/state.sqlite3')
if state.exists():
    with sqlite3.connect('file:' + str(state) + '?mode=ro', uri=True) as source:
        with sqlite3.connect(sys.argv[1]) as destination:
            source.backup(destination)
PY
fi
(cd "$temporary" && find . -maxdepth 1 -type f ! -name SHA256SUMS -print0 |
    sort -z | xargs -0 sha256sum > SHA256SUMS)
mv "$temporary" "$destination"
find /var/backups/glitchtip -mindepth 1 -maxdepth 1 -type d -name '20*T*Z' -mtime +6 -exec rm -rf -- {} +
echo "GlitchTip backup completed: $stamp"
