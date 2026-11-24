# Running SQLite replica — 2026-11-17

Owner approved an additional replica every ten minutes, preserving daily encrypted
archives. Installed official sqlite3_rsync 3.54.1 on FirstVDS and vmsh/prep;
verified tools archive SHA3-256 against sqlite.org. Application SQLite unchanged.

Implemented [origin.py](origin.py), [replicate.py](replicate.py),
[systemd units](systemd/), [operation/recovery guide](README.md).
Dedicated prep SSH key is restricted by source IP and forced command to the two
selected DB origins. Shared lifecycle locks serialize with maintenance.
Arbitrary shell command rejected in a real SSH probe; eight local tests passed.

First full copy succeeded at **2026-11-17T16:45:47Z** without stopping writers:
- Main: 881,430,528 bytes, quick_check OK, 101.82 seconds including validation.
- Analytics: 176,922,624 bytes, quick_check OK, 5.08 seconds including validation.
Replica data is private, not archived, and occupies approximately 1.06 GB.
Small scripts/units/install record and /etc are covered by existing archive config;
replica databases and executable are deliberately excluded from archive inputs.
Full integrity_check passed for both replicas (main: 176 tables, analytics: 2).
Incremental repeat succeeded at **2026-11-17T16:47:15Z**:
- Main: 7.16 seconds, sent 119,892 / received 477,270 bytes; quick_check OK.
- Analytics: 1.86 seconds, sent 9,546 / received 45,252 bytes; quick_check OK.
- Total exchange: **651,960 bytes** instead of copying 1.06 GB again.
Timer enabled and active; next run 16:50 UTC (18:50 Cyprus).
Production PWA/Telegram units active, service-status ready; daily archive timer
remains enabled. No application SQLite upgrade, production DB replacement or
writer interruption was performed. Daily copies retain their previous history.
All completion gates passed.
