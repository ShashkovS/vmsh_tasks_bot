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
(cd "$temporary" && sha256sum database.dump uploads.tar.gz compose.yml environment.env > SHA256SUMS)
mv "$temporary" "$destination"
find /var/backups/glitchtip -mindepth 1 -maxdepth 1 -type d -name '20*T*Z' -mtime +6 -exec rm -rf -- {} +
echo "GlitchTip backup completed: $stamp"
