#!/bin/bash
# Restore only into a new temporary database; never replace the running database.
set -euo pipefail
cd /opt/glitchtip
snapshot=${1:?Pass a snapshot directory under /var/backups/glitchtip}
case "$snapshot" in
    /var/backups/glitchtip/20*T*Z) ;;
    *) echo 'Unexpected snapshot path' >&2; exit 1 ;;
esac
(cd "$snapshot" && sha256sum --check --status SHA256SUMS)
database=glitchtip_restorecheck_$(date -u +%Y%m%d%H%M%S)
docker compose exec -T postgres createdb -U glitchtip "$database"
trap 'docker compose exec -T postgres dropdb -U glitchtip --if-exists "$database"' EXIT
docker compose exec -T postgres pg_restore -U glitchtip -d "$database" --exit-on-error --no-owner < "$snapshot/database.dump"
docker compose exec -T postgres psql -U glitchtip -d "$database" -v ON_ERROR_STOP=1 -c '
SELECT (SELECT count(*) FROM users_user) AS users,
       (SELECT count(*) FROM organizations_ext_organization) AS organizations,
       (SELECT count(*) FROM projects_project) AS projects,
       (SELECT count(*) FROM issue_events_issueevent) AS events;'
tar -tzf "$snapshot/uploads.tar.gz" > /dev/null
echo "Restore rehearsal completed; live database was not changed."
