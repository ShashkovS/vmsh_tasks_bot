# Cross-backups

Owner-approved 2026-10-10: one encrypted `.tar.7z` per host per day, stored on
both `vmsh.shashkovs.ru` and `prep.leaders.tech`. Preserve 14 UTC calendar days
and the last successful archive in each of the most recent 24 calendar months.
Existing `/web/vmsh_tasks_bot/backups` archives are separate and are not pruned.

Implementation: [backup.py](backup.py), [installer](install.py),
[tests](../../../tests/test_cross_backup.py), [progress](STATUS.md).

## Contents and recovery

Every archive contains verified online snapshots of main and analytics SQLite,
all of `/etc` (nginx, systemd, SSH, TLS/ACME, firewall, NATS, monitoring, accounts),
the actual external targets of nginx/systemd/monitoring configuration symlinks,
unit EnvironmentFiles, application credential directories and `.env` files,
root/users' SSH directories, user crontabs, the backup tooling, and a manifest
with hashes, installed package/unit inventory and runtime provenance.
Application files in S3 and uploaded media are outside this backup.
The full Swift compiler distribution found under `/etc/swift-*-RELEASE-*` on
prep is excluded as software; its exclusion is recorded in the manifest.

GNU tar preserves owners, modes, symlinks, ACLs and xattrs. 7zip uses AES-256,
encrypted headers, LZMA2 level 5 and two compression threads. Passwords are
provided over stdin, never in command-line arguments or logs. Configuration
capture runs as root; SQLite snapshots use shared lifecycle locks compatible
with `db_methods/pwa/runtime_lock.py`. No workers are stopped for a backup.

The archive password is `/etc/vmsh-cross-backup/archive-password` (root, 0600).
It is also reachable at `/web/vmsh_tasks_bot/cross-backup/config/archive-password`.
On each host, this password decrypts that host's archives; the adjacent
`peer-archive-password` decrypts archives originating from the other host.
Read them with `sudo cat` on the server. Each host's password remains unchanged
across daily backups and installer reruns.
**Save it outside both servers** before relying on these archives. An encrypted
copy of a password inside its own archive cannot recover a lost password.
Each installer generates its own password unless `--password-file` is supplied;
using the same password on both hosts is supported. Never paste passwords in
chat, Git, command arguments or the installation report.

Extract into an empty, private directory, never directly into `/`:

```sh
sudo python3 /usr/local/lib/vmsh-cross-backup/backup.py restore \
  --archive /var/lib/vmsh-cross-backup/incoming/vmsh-YYYYMMDDTHHMMSSZ.tar.7z \
  --password-file /secure/location/vmsh-password \
  --target /root/vmsh-recovery
```

This verifies archive/SQLite integrity and hashes without restoring production
files. The output contains `manifest.json`, restored `db/`, and `payload.tar`;
host files remain inside the tar under `host/etc`, `host/web`, etc. Review them
before any deliberate extraction into another empty private directory.
For a DB recovery, stop all relevant PWA/Telegram/Zoom/analytics writers, take a
safety backup, restore both DB snapshots with original ownership, remove only
their stale WAL/SHM, check migrations/integrity, then start the writers. Review
system configuration individually; restoring all `/etc` over a running host is
not part of this tool.

## Installation

Once prep is installed, the owner can complete VMSH installation and both-way
key/password exchange from this checkout with one reviewed script:

```sh
bash docs/deploy/cross-backup/install-vmsh.sh
```

This uses the owner's `vmshbeget` administrative SSH alias and the existing
`tlfprepagent` connection. Passwordless sudo is required. It starts a fresh
backup and verifies recovery in both directions. The agent does not run this
script. Keep offline copies of both password files afterwards.
The bootstrap prints each stage and the running systemd state every 10 seconds
while waiting for the initial backup and restore checks. These checks can take
several minutes. SSH connection/liveness timeouts prevent silent network hangs.

For an already working installation, add the discovery links and update the
VMSH installer without creating another archive or exchanging passwords:

```sh
bash docs/deploy/cross-backup/install-vmsh.sh --links-only
```

This repair also checks synchronization of existing archives on both hosts.

Run from a reviewed checkout as root (no application deploy/restart):

```sh
python3 docs/deploy/cross-backup/install.py --site prep
# On VMSH, run manually as the administrator:
sudo python3 docs/deploy/cross-backup/install.py --site vmsh
```

The installer checks GNU tar/7zip, creates private state under
`/var/lib/vmsh-cross-backup`, installs a dedicated receiving user and root-owned
forced SSH command, generates an outgoing SSH key, and installs three timers.
It prints only its public SSH key. Exchange these public keys and trusted SSH
host keys as described below. The receiving key cannot read archives, overwrite
archives or execute shell/cleanup commands. No sshd reconfiguration is needed.

Run on each server as root, using the **other** server's printed public key:

```sh
python3 /usr/local/lib/vmsh-cross-backup/install.py --authorize-peer-key /path/to/peer.pub
# Copy the trusted peer host-key entry (port 22179) from the owner's known_hosts:
install -o root -g root -m 0600 /path/to/peer-known-hosts /etc/vmsh-cross-backup/known_hosts
systemctl start vmsh-cross-backup.service
```

Use `ssh-keygen -F '[217.114.6.190]:22179'` for the prep destination and
`ssh-keygen -F '[188.245.158.162]:22179'` for the VMSH destination on the owner's
computer. Copy the trusted output; do not automatically trust `ssh-keyscan`.
Authorization changes only the dedicated user's authorized_keys.

## Discoverability

Owner requirement, 2026-10-10: every filesystem object created outside
`/web/vmsh_tasks_bot` must be reachable through links inside that directory.
[install.py](install.py) maintains `/web/vmsh_tasks_bot/cross-backup/`:

- `systemd/`: individual links to all six `.service`/`.timer` files.
- `systemd/enabled/`: links to all three enabled timer entries.
- `config/`: SSH keys, pinned host keys, passwords and configuration in `/etc/vmsh-cross-backup`.
- `tools/` and `README.md`: installed programs and this runbook.
- `state/`, `outgoing/`, `incoming/`, `status.json`: state, archives, receipts and status.
- `receiver/`: dedicated `vmsh_crossbackup` account home and its restricted authorized key.
- `installations/`: persistent prep installation and proof directories, when present.

These links preserve target permissions; secrets and archives remain private.
Real privileged files stay in their canonical root-owned locations. Existing
conflicting links/files are rejected. Repair only links on an installed host:

```sh
sudo python3 /usr/local/lib/vmsh-cross-backup/install.py --refresh-links
ls -l /web/vmsh_tasks_bot/cross-backup/systemd
```

## Operation

Daily capture: VMSH 00:15 UTC, prep 01:15 UTC. Missing transfers retry hourly;
no new snapshot is created by retry. The timer catches missed daily runs after
boot. Each complete archive is tested and restored locally before publication.
The receiving command validates size/SHA-256 and atomically publishes the file;
interrupted uploads remain invisible and are removed. Each sync sends any local
archive absent from the receiver inventory and confirms matching hashes.

Cleanup of outgoing archives occurs only after a successful sync; incoming
archives are pruned locally by the receiving host after checking their receipts.
The newest archive is always retained. The legacy prep timer is disabled only
after the first successful cross-transfer. The legacy deployment helper keeps
making safety snapshots, but its old automatic 14-day deletion is removed.
Future TLF rendering respects an installed cross-backup configuration.
Subsequent syncs accept an absent, stopped legacy timer (including a remembered
failed state); a linked legacy unit
may disappear from systemd when it is disabled. A remaining active timer must
still be retired successfully before reporting success.
Inventory, uploads, incoming retention and verification wait up to two minutes
for the receiver lock, so simultaneous hourly retries serialize instead of
failing immediately on a short overlap.

Monthly verification restores the latest local archive and the latest foreign
archive. Supply the foreign site's password as
`/etc/vmsh-cross-backup/peer-archive-password` (0600) to enable its decrypt/restore
verification; until supplied, verification reports failure rather than success.
Both passwords should also be saved off-server by the owner.

```sh
systemctl list-timers 'vmsh-cross-backup*'
journalctl -u vmsh-cross-backup -u vmsh-cross-backup-sync -u vmsh-cross-backup-verify
cat /var/lib/vmsh-cross-backup/status.json
systemctl start vmsh-cross-backup-sync.service
systemctl start vmsh-cross-backup-verify.service
```

Archive manifests and status contain hashes/paths, not secret contents or user
data. No notifications are sent. At least 2 GiB must remain available after the
estimated capture workspace; failures preserve existing complete archives.
The receiving endpoint caps one upload at 4 GiB and reserves 2 GiB of free disk.
Old archives outside this system are neither imported nor deleted.
