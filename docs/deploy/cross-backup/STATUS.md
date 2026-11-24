# Cross-backup status

## 2026-10-10 — Installed and verified on both hosts

Owner decisions: daily cross-backups of both SQLite stores; 14 daily days and
24 calendar months; existing archives remain separate. Each daily archive also
includes host configuration and secrets, encrypted with 7zip. VMSH administrative
work is performed manually by the owner; prep is installed by the agent.
See [runbook](README.md), [backup tool](backup.py), [installer](install.py),
[owner bootstrap](install-vmsh.sh) and [tests](../../../tests/test_cross_backup.py).

Owner bootstrap completed: both sites report successful capture, cross-transfer
and local/foreign recovery checks (`error: null`). VMSH archive is 50,490,067
bytes; prep archive is 5,009,939 bytes. Daily/hourly/monthly timers are enabled
on both hosts. The apparent bootstrap hang was synchronous first compression,
transfer and verification without progress output. The script now prints stages
and unit state every 10 seconds, with SSH connection/liveness timeouts. Bootstrap
tar uses USTAR without macOS extended attributes.

Owner requirement: every created system object must be reachable through
symlinks beneath `/web/vmsh_tasks_bot`. Installer creates `cross-backup/` links to
all six units, three enabled timers, config/secrets, tooling, state, receiver and
installation/proof directory. Prep has 18 checked links, with target secret
permissions unchanged at 0600. The requirement is recorded in root `AGENTS.md`.

Final audit found the first hourly prep retry failed during repeated legacy
timer retirement: the unit file was already absent, but systemd remembered a
failed state. Sync now accepts an absent, stopped legacy timer. Receiver locks
wait up to two minutes to serialize inventory, upload, prune and verification.
Regression checks cover stopped/failed absent units, active retirement and
bounded lock waiting. Prep's hardened systemd sync passed twice after repair;
`lastCrossSuccess` is 18:54:19 UTC, `error: null`. All three local prep archives
match their VMSH copies by SHA-256; incoming VMSH archive receipt/hash is valid.

Owner completed `install-vmsh.sh --links-only`: both systemd sync jobs succeeded.
Read-only VMSH audit confirms 17 discovery links, all three services' latest
results are successful, and installed tool hashes match prep and reviewed source.
Prep confirms successful sync and `error: null`; password files remain 0600.
The previous hourly failure is resolved. No administrative follow-up remains.

Validation: 22 isolated pytest cases PASS, scoped Ruff PASS, Bash syntax and
full/repair fake-SSH bootstrap PASS, job failure propagation PASS. Discovery-link
idempotence, private permissions and operator-conflict/symlink-parent rejection
smoke PASS. Tests require no Telegram/Google credentials; archive tests use real
GNU tar/7zip. PWA, Zoom and NATS master PIDs on prep remained unchanged.

Earlier capture rehearsal verified config/secret contents and external symlink
targets, SQLite integrity/hash restore, SDK exclusion and receiver permissions.
The 2.3 GiB Swift SDK in `/etc` is excluded as software. All 88 legacy entries
were preserved; legacy automatic deletion is disabled. Existing legacy captures
and [first local proof](../../../pwa_tests/reports/cross-backup-20261010/verification.json)
remain separate historical records.

[Current sanitized proof](../../../pwa_tests/reports/cross-backup-20261010/completion.json)
records completed checks and successful VMSH owner repair. Root prep proof is
reachable through `cross-backup/installations/vmsh-cross-backup-release-20261010/completion.json`.
Keep both archive recovery passwords off-server as described in the runbook.
