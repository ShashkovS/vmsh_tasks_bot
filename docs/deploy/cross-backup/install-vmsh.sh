#!/usr/bin/env bash
# Owner-run administrative step; never run with the restricted VMSH agent.
# Contract: README.md. This script contains no passwords or private keys.
set -euo pipefail

SOURCE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
MODE=${1:-}
if [[ $# -gt 1 || ( -n "$MODE" && "$MODE" != --links-only ) ]]; then
    printf 'Usage: %s [--links-only]\n' "$0" >&2
    exit 2
fi
STEP=starting
trap 'printf "Failed during: %s (line %s)\n" "$STEP" "$LINENO" >&2' ERR

step() {
    STEP=$1
    printf '\n%s\n' "$STEP"
}

vmsh() {
    ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 \
        -o ServerAliveInterval=30 -o ServerAliveCountMax=3 vmshbeget "$@"
}

prep() {
    ssh -F "$SOURCE/../../ssh/config" -o BatchMode=yes \
        -o StrictHostKeyChecking=yes -o ConnectTimeout=15 \
        -o ServerAliveInterval=30 -o ServerAliveCountMax=3 tlfprepagent "$@"
}

run_unit() {
    local host=$1 unit=$2
    step "$host: $unit — waiting for completion; status every 10 seconds"
    "$host" "sudo -n bash -s -- '$unit'" <<'REMOTE'
set -euo pipefail
unit=$1
systemctl start "$unit" &
starter=$!
ticks=0
while kill -0 "$starter" 2>/dev/null; do
    if (( ticks % 10 == 0 )); then
        printf '[%s] %s: ' "$(date -u +%H:%M:%S)" "$unit"
        systemctl show "$unit" -p ActiveState -p SubState -p MainPID | tr '\n' ' '
        printf '\n'
    fi
    sleep 1
    ticks=$((ticks + 1))
done
wait "$starter"
printf '%s: completed successfully\n' "$unit"
REMOTE
}

# Transfer only reviewed tooling. All generated passwords remain on servers.
step 'VMSH: installing tooling, timers and /web/vmsh_tasks_bot/cross-backup links'
COPYFILE_DISABLE=1 tar --format=ustar -C "$SOURCE" -cf - \
    cross-backup/backup.py cross-backup/install.py cross-backup/README.md tlf-app/backup.py |
    vmsh 'sudo -n bash -c '\''set -eu
release=$(mktemp -d /var/tmp/vmsh-cross-backup.XXXXXX)
trap "rm -rf -- $release" EXIT
tar -xf - -C "$release"
python3 "$release/cross-backup/install.py" --site vmsh'\'''

if [[ "$MODE" == --links-only ]]; then
    step 'Prep: refreshing /web/vmsh_tasks_bot/cross-backup links'
    prep -n 'sudo -n python3 /usr/local/lib/vmsh-cross-backup/install.py --refresh-links'
    run_unit vmsh vmsh-cross-backup-sync.service
    run_unit prep vmsh-cross-backup-sync.service
    printf '\nLinks and sync checked on both hosts; existing archives and passwords preserved.\n'
    exit 0
fi

step 'Exchanging restricted peer public keys'
vmsh -n 'sudo -n cat /etc/vmsh-cross-backup/id_ed25519.pub' |
    prep 'sudo -n sh -c "umask 077; cat > /etc/vmsh-cross-backup/peer.pub"'
prep -n 'sudo -n python3 /usr/local/lib/vmsh-cross-backup/install.py --authorize-peer-key /etc/vmsh-cross-backup/peer.pub'
prep -n 'sudo -n cat /etc/vmsh-cross-backup/id_ed25519.pub' |
    vmsh 'sudo -n sh -c "umask 077; cat > /etc/vmsh-cross-backup/peer.pub"'
vmsh -n 'sudo -n python3 /usr/local/lib/vmsh-cross-backup/install.py --authorize-peer-key /etc/vmsh-cross-backup/peer.pub'

# The existing, verified owner SSH sessions are the trust source for host keys.
step 'Pinning trusted SSH host keys'
prep -n 'cat /etc/ssh/ssh_host_ed25519_key.pub' |
    sed 's/^/[188.245.158.162]:22179 /' |
    vmsh 'sudo -n sh -c "umask 077; cat > /etc/vmsh-cross-backup/known_hosts"'
vmsh -n 'cat /etc/ssh/ssh_host_ed25519_key.pub' |
    sed 's/^/[217.114.6.190]:22179 /' |
    prep 'sudo -n sh -c "umask 077; cat > /etc/vmsh-cross-backup/known_hosts"'

# Keep each recovery password on both hosts, over encrypted SSH pipes.
step 'Copying recovery passwords directly between hosts over SSH'
vmsh -n 'sudo -n cat /etc/vmsh-cross-backup/archive-password' |
    prep 'sudo -n sh -c "umask 077; cat > /etc/vmsh-cross-backup/peer-archive-password"'
prep -n 'sudo -n cat /etc/vmsh-cross-backup/archive-password' |
    vmsh 'sudo -n sh -c "umask 077; cat > /etc/vmsh-cross-backup/peer-archive-password"'

run_unit vmsh vmsh-cross-backup.service
run_unit prep vmsh-cross-backup.service
run_unit vmsh vmsh-cross-backup-verify.service
run_unit prep vmsh-cross-backup-verify.service
step 'Final backup / transfer / recovery status'
vmsh -n 'sudo -n cat /var/lib/vmsh-cross-backup/status.json'
prep -n 'sudo -n cat /var/lib/vmsh-cross-backup/status.json'
printf '\nCross-backups and both-way recovery checks completed successfully.\n'
