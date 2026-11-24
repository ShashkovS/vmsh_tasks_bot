# Independent S3 backup — 2026-11-17

Owner authorized hourly direct pulls to `vmsh` / prep, 10 GB budget, retained
source deletions and overwritten versions. Existing full-access key explicitly
authorized because the provider cannot issue a read-only one. Root-only config.

Implemented [backup.py](backup.py), [systemd units](systemd/),
[operation/recovery instructions](README.md). Native rclone crypt; one current
tree plus overwritten versions, no full hourly snapshots or nested archives.
Programmatic space preflight and transfer cap; never automatically delete data.

Passed on vmsh:
- Local encrypted fixture: same-size overwrite retained old bytes; deleting the
  source preserved current copy. Decryption also worked with independently
  re-created config from the existing archive password and documented salt.
- First complete copy: **3511 objects, 379,398,582 source bytes**.
- Full downloaded byte comparison passed at **2026-11-17T12:52:40Z**.
- Allocated state after first check: **392,409,088 bytes** of 10,000,000,000.
- Five local budget tests passed: same-size overwrite, unchanged/deleted source,
  insufficient budget, host free-space reserve, equivalent timezone timestamps.

Final incremental rerun at **2026-11-17T12:58:43Z** passed: **3512 objects**,
379,428,260 source bytes, **zero changed candidates, zero bytes transferred**,
10.3 seconds. Timer enabled and active, next scheduled run 13:21 UTC.
Restored public SVG: 15,109 bytes, SHA-256
`64f482ea9a62721253a678dae4deab39dd34a62bf91e8691a2b38005781af72d`.
A second full downloaded comparison passed before aligning local timestamps.

Initial rehearsal exposed inherited S3 metadata mtime differing from server
LastModified. Removed `--metadata`, now consistently use server modification time;
normalized backup mtimes only after successful full byte comparison. No content
was changed by normalization. Rehearsal created ~356 MiB of identical old copies.
Automatic approval review rejected mass deletion of those version files; they
remain intact. Final allocated state: **778,723,328 bytes**, below the 10 GB budget.
No automatic deduplication/deletion was added.
Small config/source/units/installation record included in existing config backup;
S3 objects, versions, logs and executable deliberately excluded from its archive.
Production S3 was read only throughout setup and testing.
